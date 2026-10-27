"""Playwright explorer. Read-only: never submits forms, blocks every non-GET request, honors robots.txt,
stays in the start origin for navigation, validates every request/redirect hop, never bypasses auth."""
import asyncio, re, time
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PWError, async_playwright

from . import config
from .safety import UnsafeURL, UrlChecker, origin_of

SKIP_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|css|js|pdf|zip|gz|mp4|mp3|woff2?|ttf|xml|json|txt)$", re.I)
DESTRUCTIVE = re.compile(r"(delete|remove|pay|purchase|buy now|logout|log out|sign out|unsubscribe|cancel|confirm|submit order)", re.I)
BLOCK_HINT = re.compile(r"(captcha|verify you are human|access denied|are you a robot|unusual traffic)", re.I)

EXTRACT_JS = r"""() => {
 const t=e=>(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ').slice(0,80);
 const q=s=>[...document.querySelectorAll(s)];
 const gen=document.querySelector('meta[name=generator]');
 return {
  title: document.title,
  headings: q('h1,h2,h3').map(t).filter(Boolean).slice(0,20),
  links: q('a[href]').map(a=>({text:t(a),href:a.href})).slice(0,300),
  buttons: q('button,[role=button],input[type=submit],input[type=button]').map(b=>({text:t(b),type:b.getAttribute('type')||'button',inForm:!!b.closest('form')})).filter(b=>b.text).slice(0,30),
  forms: [...document.forms].map(f=>({action:f.getAttribute('action')||'',method:(f.method||'get'),fields:[...f.elements].map(e=>e.name).filter(Boolean)})).slice(0,10),
  text_len: (document.body?document.body.innerText.length:0),
  generator: gen?gen.content:null,
  mounts: ['#__next','#root','#app','[ng-version]','#___gatsby','#__nuxt'].filter(s=>document.querySelector(s)),
  globals: ['__NEXT_DATA__','__NUXT__','ng','Vue','React','jQuery'].filter(k=>k in window),
  scripts: q('script[src]').map(s=>s.src).slice(0,20)
 };
}"""
INIT_JS = "window.WebSocket=function(){throw new Error('WebSocket disabled by Atlas')};window.EventSource=function(){throw new Error('EventSource disabled by Atlas')};"


def norm(url: str) -> str:
    u = urldefrag(url)[0]
    s = urlsplit(u)
    return f"{s.scheme}://{s.netloc}{s.path or '/'}"  # query dropped to bound the crawl


async def explore(start_url, *, max_pages, deadline, checker: UrlChecker, scope_prefix="/", on_progress=None, cancelled=lambda: False):
    origin = origin_of(start_url)
    out = {"pages": [], "followed": [], "redirect_map": {}, "third_party": {}, "notes": [], "skipped": []}
    capture: list[dict] = []
    seen_hosts: dict[str, int] = out["third_party"]

    async def guard(route, request):
        url = request.url
        if url.startswith(("data:", "blob:", "about:")):
            return await route.continue_()
        try:
            await checker.check(url)
        except UnsafeURL as e:
            capture.append({"method": request.method, "url": url, "type": request.resource_type, "blocked": f"unsafe destination: {e}"})
            return await route.abort("blockedbyclient")
        rec = {"method": request.method, "url": url, "type": request.resource_type, "blocked": None}
        if request.is_navigation_request() and origin_of(url) != origin:
            rec["blocked"] = "cross-origin navigation out of scope"
        elif request.method not in ("GET", "HEAD", "OPTIONS"):
            rec["blocked"] = "mutating request blocked (read-only mode)"
        elif origin_of(url) == origin and not urlsplit(url).path.startswith(scope_prefix):
            rec["blocked"] = "outside scope prefix"
        capture.append(rec)
        if rec["blocked"]:
            return await route.abort("blockedbyclient")
        if origin_of(url) != origin:
            h = urlsplit(url).hostname or ""
            seen_hosts[h] = seen_hosts.get(h, 0) + 1
        await route.continue_()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, executable_path=config.BROWSER_PATH, args=config.BROWSER_ARGS)
        ctx = await browser.new_context(service_workers="block", accept_downloads=False, user_agent=config.USER_AGENT, viewport={"width": 1280, "height": 800})
        await ctx.add_init_script(INIT_JS)
        await ctx.route("**/*", guard)
        page = await ctx.new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))

        # robots.txt (fetched only after destination validation)
        robots = RobotFileParser()
        try:
            await checker.check(origin + "/robots.txt")
            r = await ctx.request.get(origin + "/robots.txt", timeout=5000, max_redirects=0)
            if r.ok:
                robots.parse((await r.text()).splitlines())
                out["notes"].append("robots.txt found and honored")
            else:
                robots.parse([])
        except Exception:
            robots.parse([])

        queue: list[tuple[str, str | None, str]] = [(norm(start_url), None, "start")]
        queued = {norm(start_url)}
        path_to_id: dict[str, str] = {}

        def progress(msg):
            if on_progress:
                on_progress(len(queued), len(out["pages"]), msg)

        while queue and len(out["pages"]) < max_pages and time.monotonic() < deadline and not cancelled():
            url, src, link_text = queue.pop(0)
            if not robots.can_fetch(config.USER_AGENT, url):
                out["skipped"].append({"url": url, "reason": "disallowed by robots.txt"})
                continue
            progress(f"Visiting {urlsplit(url).path or '/'}")
            capture.clear()
            try:
                resp = await page.goto(url, wait_until="load", timeout=10000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=2500)
                except PWError:
                    pass
            except PWError as e:
                out["skipped"].append({"url": url, "reason": "navigation failed: " + str(e).split("\n")[0][:120]})
                continue
            if resp is None:
                continue
            final = norm(page.url)
            chain, rq = [], resp.request
            while rq.redirected_from:
                rq = rq.redirected_from
                chain.append(rq.url)
            status = resp.status
            if final in path_to_id:  # redirected to an already-known page
                out["redirect_map"][url] = path_to_id[final]
                out["followed"].append({"source": src, "target": path_to_id[final], "text": link_text, "redirects": chain, "status": status})
                continue
            data = await page.evaluate(EXTRACT_JS)
            raw = ""
            try:
                raw = await resp.text()
            except PWError:
                pass
            body_text = (await page.evaluate("document.body?document.body.innerText:''"))[:2000]
            blocked_hint = status in (401, 403, 429) or bool(BLOCK_HINT.search(body_text))
            load_reqs = [dict(c) for c in capture if c["type"] in ("fetch", "xhr") or c["blocked"]]
            hdrs = {k: v for k, v in (await resp.all_headers()).items() if k in ("server", "x-powered-by", "via", "cf-ray", "x-vercel-id", "content-type")}

            interactions = []
            if not blocked_hint:
                cands = [b for b in data["buttons"] if b["type"] != "submit" and not b["inForm"] and not DESTRUCTIVE.search(b["text"])][:3]
                for b in cands:
                    if time.monotonic() > deadline or cancelled():
                        break
                    mark, before_len, before_url = len(capture), (await page.evaluate("document.body.innerText.length")), page.url
                    try:
                        await page.get_by_role("button", name=b["text"], exact=True).first.click(timeout=2000)
                        await page.wait_for_timeout(500)
                    except PWError:
                        continue
                    new = [dict(c) for c in capture[mark:] if c["type"] in ("fetch", "xhr", "document") or c["blocked"]]
                    after_len = await page.evaluate("document.body.innerText.length")
                    interactions.append({"button": b["text"], "requests": new, "dom_text_delta": after_len - before_len, "navigated": page.url != before_url})
                    if page.url != before_url:
                        break

            pid = f"p{len(out['pages'])}"
            u = urlsplit(final)
            links, seen_l = [], set()
            for l in data["links"]:
                h = urldefrag(l["href"])[0]
                if h.startswith(("http://", "https://")) and h not in seen_l:
                    seen_l.add(h)
                    links.append({"text": l["text"], "href": h})
            rec = {
                "id": pid, "url": final, "path": u.path or "/", "title": data["title"], "status_code": status,
                "headings": data["headings"], "links": links, "buttons": sorted({b["text"] for b in data["buttons"]}),
                "forms": data["forms"], "requests": load_reqs, "interactions": interactions, "headers": hdrs,
                "redirected_from": chain, "inaccessible": blocked_hint,
                "render": {"raw_links": len(re.findall(r"<a\s[^>]*href", raw, re.I)), "dom_links": len(links), "raw_text": len(re.sub(r"<[^>]+>", "", raw)), "dom_text": data["text_len"]},
                "signals": [s for s in ([f"meta generator: {data['generator']}"] if data["generator"] else []) + [f"mount point {m}" for m in data["mounts"]] + [f"window.{g} present" for g in data["globals"]]],
            }
            out["pages"].append(rec)
            path_to_id[final] = pid
            out["followed"].append({"source": src, "target": pid, "text": link_text, "redirects": chain, "status": status})
            if url != final:
                out["redirect_map"][url] = pid
            if not blocked_hint:
                for l in links:
                    n = norm(l["href"])
                    if origin_of(n) == origin and urlsplit(n).path.startswith(scope_prefix) and not SKIP_EXT.search(urlsplit(n).path) and n not in queued:
                        queued.add(n)
                        queue.append((n, pid, l["text"]))
            progress(f"Visited {rec['path']} (HTTP {status})")

        if queue and len(out["pages"]) >= max_pages:
            out["notes"].append(f"page limit reached; {len(queue)} discovered pages not visited")
        if time.monotonic() >= deadline:
            out["notes"].append("time limit reached")
        out["path_to_id"] = path_to_id
        await browser.close()
    return out
