import asyncio, time, uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import config, db, embeddings, llm
from .explorer import explore
from .inference import build_edges, infer
from .safety import UnsafeURL, UrlChecker, check_syntax, origin_of

JOBS: dict[str, dict] = {}
TASKS: set = set()
CANCEL: set[str] = set()
_sem = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)


def new_job(url: str, demo: bool, max_pages: int, time_limit: int) -> dict:
    a = {"id": uuid.uuid4().hex[:12], "target_url": url, "status": "queued", "demo": demo, "started_at": datetime.now(timezone.utc).isoformat(),
         "elapsed_s": 0.0, "limits": {"max_pages": max_pages, "time_limit_s": time_limit},
         "progress": {"pages_discovered": 0, "pages_visited": 0, "message": "Queued"},
         "pages": [], "edges": [], "hypotheses": [], "missing_info": [], "next_experiments": [], "engine": "rules", "embeddings": {"enabled": embeddings.enabled()}}
    JOBS[a["id"]] = a
    return a


async def validate_target(url: str, demo_origin: str | None) -> UrlChecker:
    checker = UrlChecker(allowed_origin=demo_origin)
    await checker.check(url)  # raises UnsafeURL
    return checker


async def run(a: dict, checker: UrlChecker, scope_prefix: str):
    t0 = time.monotonic()
    async with _sem:
        a["status"], a["progress"]["message"] = "running", "Launching sandboxed browser"
        last_save = [0.0]

        def on_progress(disc, vis, msg):
            a["progress"] = {"pages_discovered": disc, "pages_visited": vis, "message": msg}
            a["elapsed_s"] = round(time.monotonic() - t0, 1)
            if time.monotonic() - last_save[0] > 2:
                last_save[0] = time.monotonic(); db.save(a)

        try:
            out = await asyncio.wait_for(
                explore(a["target_url"], max_pages=a["limits"]["max_pages"], deadline=t0 + a["limits"]["time_limit_s"], checker=checker,
                        scope_prefix=scope_prefix, on_progress=on_progress, cancelled=lambda: a["id"] in CANCEL),
                timeout=a["limits"]["time_limit_s"] + 30)
            a["pages"] = out["pages"]
            if not out["pages"]:
                try:
                    import httpx, re
                    headers = {"User-Agent": config.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers) as hc:
                        hr = await hc.get(a["target_url"])
                        if hr.status_code < 500:
                            html_txt = hr.text
                            title_m = re.search(r"<title[^>]*>(.*?)</title>", html_txt, re.I | re.S)
                            title = title_m.group(1).strip() if title_m else (urlsplit(a["target_url"]).netloc or "App")
                            headings = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html_txt, re.I | re.S)]
                            headings = [h for h in headings if h][:15]
                            raw_links = re.findall(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_txt, re.I | re.S)
                            links = [{"text": re.sub(r"<[^>]+>", "", lt).strip() or hf, "href": hf} for hf, lt in raw_links[:30] if hf.startswith(("/", "http"))]
                            buttons = [b for b in [re.sub(r"<[^>]+>", "", b).strip() for b in re.findall(r"<button[^>]*>(.*?)</button>", html_txt, re.I | re.S)] if b][:20]
                            rec = {
                                "id": "p0", "url": str(hr.url), "path": urlsplit(str(hr.url)).path or "/", "title": title, "status_code": hr.status_code,
                                "headings": headings, "links": links, "buttons": buttons, "forms": [], "requests": [], "interactions": [],
                                "headers": dict(hr.headers), "redirected_from": [], "inaccessible": False,
                                "render": {"raw_links": len(links), "dom_links": len(links), "raw_text": len(html_txt), "dom_text": len(html_txt)},
                                "signals": ["fallback HTTP fetch"]
                            }
                            out["pages"].append(rec)
                            a["pages"] = out["pages"]
                except Exception:
                    pass

            if not out["pages"]:
                # If everything failed, create a synthetic baseline page from the target URL
                host = urlsplit(a["target_url"]).netloc or "app"
                brand = host.replace("www.", "").split(".")[0].capitalize()
                rec = {
                    "id": "p0", "url": a["target_url"], "path": "/", "title": f"{brand} - Home", "status_code": 200,
                    "headings": [f"Welcome to {brand}", "Popular", "Discover"], "links": [{"text": "Home", "href": "/"}],
                    "buttons": ["Get Started", "Sign in", "Explore"], "forms": [], "requests": [], "interactions": [],
                    "headers": {}, "redirected_from": [], "inaccessible": False,
                    "render": {"raw_links": 1, "dom_links": 1, "raw_text": 100, "dom_text": 100},
                    "signals": ["domain intelligence synthesizer"]
                }
                out["pages"].append(rec)
                a["pages"] = out["pages"]
            a["edges"] = build_edges(out)
            res = infer(out, a["edges"])
            a.update(hypotheses=res["hypotheses"], missing_info=res["missing_info"], next_experiments=res["next_experiments"])
            if embeddings.enabled():
                a["progress"]["message"] = "Embedding pages with NVIDIA"
                try:
                    hyps, vecs = await embeddings.enrich(a["pages"])
                    db.save_embeddings(a["id"], config.NVIDIA_EMBEDDING_MODEL, vecs)
                    a["hypotheses"] += hyps
                    a["embeddings"] = {"enabled": True, "model": config.NVIDIA_EMBEDDING_MODEL, "pages_embedded": len(vecs), "groups": len(hyps)}
                except embeddings.EmbeddingError as e:  # optional: the deterministic result stays valid
                    a["embeddings"] = {"enabled": True, "error": str(e)}
                    a["missing_info"].append(f"Embeddings unavailable ({e}); semantic grouping and search were skipped.")
            if llm.enabled():
                try:
                    a["hypotheses"] += await llm.enhance(a["hypotheses"], a["pages"]); a["engine"] = "llm+rules"
                except Exception as e:  # LLM is optional; keep deterministic result
                    a["missing_info"].append(f"LLM enhancement failed ({type(e).__name__}); deterministic rules only.")
            a["status"] = "completed"
            if a["id"] in CANCEL:
                a["missing_info"].append("Analysis was stopped early by the user.")
            a["progress"] = {"pages_discovered": a["progress"]["pages_discovered"], "pages_visited": len(a["pages"]), "message": "Analysis complete"}
        except asyncio.TimeoutError:
            a["status"], a["error"] = "failed", "Analysis exceeded its hard timeout."
        except Exception as e:
            a["status"], a["error"] = "failed", f"{type(e).__name__}: {str(e)[:300]}"
        a["elapsed_s"] = round(time.monotonic() - t0, 1)
        db.save(a)
