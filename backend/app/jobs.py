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
                raise RuntimeError("No page could be loaded: " + "; ".join(s["reason"] for s in out["skipped"][:3]) if out["skipped"] else "No page could be loaded")
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
