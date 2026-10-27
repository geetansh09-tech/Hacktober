"""Deterministic reverse-engineering rules. Every hypothesis carries evidence strings derived from observations.
Claims about private internals are never made; architecture items are labelled inferred with low/medium confidence."""
import re
from urllib.parse import urlsplit

from .explorer import norm

KEYWORDS = ["checkout", "cart", "login", "sign in", "register", "catalog", "search", "help", "account", "profile", "pricing"]
ID_SEG = re.compile(r"^(\d+|[0-9a-f]{8,}|[0-9a-f-]{32,})$", re.I)


def pattern(path: str) -> str:
    return "/" + "/".join("{id}" if ID_SEG.match(s) else s for s in path.strip("/").split("/")) if path.strip("/") else "/"


def build_edges(out: dict) -> list[dict]:
    pages = out["pages"]
    ids = {**out["path_to_id"], **{u: t for u, t in out["redirect_map"].items()}}
    followed = {(f["source"], f["target"], f["text"]): f for f in out["followed"] if f["source"]}
    edges, idx = [], {}
    for p in pages:
        for l in p["links"]:
            t = ids.get(norm(l["href"]))
            if not t or t == p["id"]:
                continue
            f = followed.get((p["id"], t, l["text"]))
            tgt = next(x for x in pages if x["id"] == t)
            ev = [f"anchor '{l['text'] or '(no text)'}' with href {urlsplit(l['href']).path} found on {p['path']}", f"target {tgt['path']} loaded with HTTP {tgt['status_code']}"]
            if f:
                ev.append("browser navigated this link during exploration")
                if f["redirects"]:
                    ev.append("redirect chain: " + " → ".join(urlsplit(r).path for r in f["redirects"]) + f" → {tgt['path']}")
            if (p["id"], t) in idx:  # one edge per page pair; extra anchors become extra evidence
                e = idx[(p["id"], t)]
                e["evidence"].append(f"additional anchor '{l['text'] or '(no text)'}' to the same target")
                if f and "browser navigated" not in " ".join(e["evidence"]):
                    e["evidence"] += ev[2:]
                    e["action"] = f"link '{l['text'] or urlsplit(l['href']).path}'"
                continue
            e = {"id": f"e{len(edges)}", "source": p["id"], "target": t, "provenance": "observed", "action": f"link '{l['text'] or urlsplit(l['href']).path}'", "evidence": ev}
            idx[(p["id"], t)] = e
            edges.append(e)
    # tag edges to targets linked from most pages (header/footer navigation) so the UI can de-clutter
    if len(pages) >= 5:
        srcs: dict[str, set] = {}
        for e in edges:
            srcs.setdefault(e["target"], set()).add(e["source"])
        hubs = {t for t, ss in srcs.items() if len(ss) >= 0.6 * (len(pages) - 1)}
        for e in edges:
            e["global_nav"] = e["target"] in hubs and e["source"] != pages[0]["id"]
    # inferred: form actions and button labels hinting at other known pages
    by_path = {p["path"]: p["id"] for p in pages}
    have = {(e["source"], e["target"]) for e in edges}
    for p in pages:
        for f in p["forms"]:
            t = by_path.get(urlsplit(f["action"]).path) if f["action"] else None
            if t and t != p["id"] and (p["id"], t) not in have:
                have.add((p["id"], t))
                edges.append({"id": f"e{len(edges)}", "source": p["id"], "target": t, "provenance": "inferred", "action": f"form {f['method'].upper()} → {urlsplit(f['action']).path}",
                              "evidence": [f"form action points to {urlsplit(f['action']).path}", "form was NOT submitted (read-only mode), so the resulting navigation is unobserved"]})
        for b in p["buttons"]:
            for kw in KEYWORDS:
                if kw in b.lower():
                    t = next((q["id"] for q in pages if q["id"] != p["id"] and kw.replace(" ", "") in q["path"].lower().replace("-", "")), None)
                    if t and (p["id"], t) not in have:
                        have.add((p["id"], t))
                        edges.append({"id": f"e{len(edges)}", "source": p["id"], "target": t, "provenance": "inferred", "action": f"button '{b}' (label match)",
                                      "evidence": [f"button '{b}' on {p['path']}", f"page path contains '{kw}'", "button click did not navigate during exploration; relationship is a label-based guess"]})
    return edges


def _h(L, cat, title, desc, prov, conf, ev):
    L.append({"id": f"h{len(L)}", "category": cat, "title": title, "description": desc, "provenance": prov, "confidence": conf, "evidence": ev[:10]})


def infer(out: dict, edges: list[dict]) -> dict:
    pages, H = out["pages"], []
    pth = lambda p: p["path"]

    # authentication
    auth = [(p, f) for p in pages for f in p["forms"] if any(re.search(r"pass(word|wd)?$", x, re.I) for x in f["fields"])]
    if auth:
        _h(H, "module", "Authentication / accounts UI", "Forms with a password field were observed. A credential-handling backend is a reasonable inference, but the mechanism (sessions, tokens, SSO) is unknown.", "observed", "high",
           [f"{pth(p)}: {f['method'].upper()} form [{', '.join(f['fields'])}]" for p, f in auth])
        _h(H, "architecture", "Server-side credential handling", "POST credential forms usually imply an endpoint that validates users; session vs token mechanism cannot be determined without authenticated traffic.", "inferred", "low", [f"{pth(p)} posts to {f['action'] or '(self)'}" for p, f in auth])

    # list/detail
    groups: dict[str, list[dict]] = {}
    for p in pages:
        groups.setdefault(pattern(p["path"]), []).append(p)
    for pat, ps in groups.items():
        if "{id}" in pat:
            _h(H, "module", f"Detail-page route family {pat}", f"{len(ps)} pages share the route pattern {pat}, suggesting a parameterised detail view backed by a data collection.", "observed" if len(ps) > 1 else "inferred", "high" if len(ps) > 1 else "medium",
               [f"{pth(p)} — {p['title']}" for p in ps])

    # search / filter
    for p in pages:
        sf = [f for f in p["forms"] if f["method"].lower() == "get" and any(x.lower() in ("q", "query", "search", "category", "sort", "filter") for x in f["fields"])]
        flt = [i for i in p["interactions"] if re.search(r"filter|search|sort", i["button"], re.I)]
        if sf or flt:
            _h(H, "module", f"Search / filtering on {pth(p)}", "Filter controls were observed; whether filtering runs client-side or server-side depends on the network calls listed in the evidence.", "observed", "medium",
               [f"GET form [{', '.join(f['fields'])}]" for f in sf] + [f"clicking '{i['button']}' issued " + (", ".join(f"{r['method']} {urlsplit(r['url']).path}?{urlsplit(r['url']).query}" for r in i["requests"]) or "no network requests") for i in flt])

    # commerce
    com = [p for p in pages if re.search(r"cart|checkout|basket|order", p["path"], re.I) or any(re.search(r"add to cart|checkout|buy", b, re.I) for b in p["buttons"])]
    if com:
        _h(H, "module", "Cart / checkout flow", "Cart- and checkout-related pages or controls were observed. Pricing, inventory and payment logic live somewhere server-side but were not observed.", "observed", "medium",
           [f"{pth(p)}: buttons {p['buttons'][:4]}" for p in com])

    # network: same-origin JSON endpoints
    gets, muts = {}, {}
    for p in pages:
        for r in p["requests"] + [x for i in p["interactions"] for x in i["requests"]]:
            if r["type"] not in ("fetch", "xhr"):
                continue
            key = f"{r['method']} {urlsplit(r['url']).path}"
            (muts if r["blocked"] and r["method"] not in ("GET", "HEAD") else gets).setdefault(key, set()).add(pth(p))
    if gets:
        _h(H, "architecture", "Client-side data fetching from HTTP endpoints", "The browser called these same-origin endpoints via fetch/XHR. The endpoints are observed; their implementation, storage and framework are not.", "observed", "high",
           [f"{k} (seen on {', '.join(sorted(v))})" for k, v in gets.items()])
    if muts:
        _h(H, "architecture", "Write endpoints exist behind UI actions", "A UI action attempted a mutating request. Atlas blocked it (read-only mode), so request bodies and responses are unknown.", "observed", "medium",
           [f"{k} attempted from {', '.join(sorted(v))} — blocked" for k, v in muts.items()])

    # rendering model
    csr = [p for p in pages if p["render"]["dom_links"] > p["render"]["raw_links"] + 1]
    if csr:
        _h(H, "architecture", "Client-side rendering for part of the UI", "The rendered DOM has more links than the initial HTML, so some content is built by JavaScript after load.", "inferred", "medium",
           [f"{pth(p)}: {p['render']['raw_links']} links in raw HTML vs {p['render']['dom_links']} in rendered DOM" for p in csr])
    elif pages:
        _h(H, "architecture", "Mostly server-rendered HTML", "Raw HTML and rendered DOM contain similar link counts. A SPA that server-renders would look the same.", "inferred", "low",
           [f"{pth(p)}: raw links {p['render']['raw_links']}, DOM links {p['render']['dom_links']}" for p in pages[:5]])

    # tech signals
    sig = [f"{pth(p)}: {s}" for p in pages for s in p["signals"]] + [f"{pth(p)}: header {k}: {v}" for p in pages for k, v in p["headers"].items() if k in ("server", "x-powered-by", "via", "cf-ray", "x-vercel-id")]
    if sig:
        _h(H, "architecture", "Technology hints", "Explicit hints (headers, meta tags, framework globals) were observed. Headers can be spoofed or generic; treat as hints, not proof.", "observed", "low", sorted(set(sig)))
    if out["third_party"]:
        _h(H, "architecture", "Third-party hosts contacted by the page", "These external hosts served subresources. Their role (CDN, analytics, fonts, auth) is a guess from the hostname only.", "observed", "medium", [f"{h}: {n} request(s)" for h, n in out["third_party"].items()])

    # access control
    prot = [p for p in pages if p["status_code"] in (401, 403)] + [p for p in pages if p["redirected_from"]]
    if prot:
        _h(H, "architecture", "Access-controlled routes", "Some routes returned 401/403 or redirected. Atlas does not attempt to bypass them; the access model is inferred only.", "inferred", "medium",
           [f"{pth(p)}: HTTP {p['status_code']}" + (f", reached via redirect from {', '.join(urlsplit(r).path for r in p['redirected_from'])}" if p["redirected_from"] else "") for p in prot])

    # workflows: shortest observed path from first page to commerce / auth pages
    adj: dict[str, list[tuple[str, dict]]] = {}
    for e in edges:
        adj.setdefault(e["source"], []).append((e["target"], e))
    def path_to(goal):
        if not pages:
            return None
        q, prev = [pages[0]["id"]], {pages[0]["id"]: None}
        while q:
            n = q.pop(0)
            if n == goal:
                out_p = []
                while prev[n]:
                    out_p.append(prev[n][1]); n = prev[n][0]
                return out_p[::-1]
            for t, e in adj.get(n, []):
                if t not in prev:
                    prev[t] = (n, e); q.append(t)
    name = {p["id"]: pth(p) for p in pages}
    for label, pred in [("Reach cart/checkout", lambda p: re.search(r"checkout|cart", p["path"], re.I)), ("Reach sign-in", lambda p: re.search(r"login|signin", p["path"], re.I))]:
        tgt = next((p for p in pages[1:] if pred(p)), None)
        route = path_to(tgt["id"]) if tgt else None
        if route:
            allobs = all(e["provenance"] == "observed" for e in route)
            _h(H, "workflow", f"{label}: " + " → ".join([name[route[0]["source"]]] + [name[e["target"]] for e in route]), "Shortest navigation path found in the behavioral graph." + ("" if allobs else " Contains inferred hops."), "observed" if allobs else "inferred", "high" if allobs else "low",
               [f"{name[e['source']]} → {name[e['target']]} via {e['action']} [{e['provenance']}]" for e in route])
    if any("/register" in pth(p) for p in pages) and any("/login" in pth(p) for p in pages):
        _h(H, "workflow", "Account creation / sign-in", "Registration and login pages are mutually reachable. Outcome of submitting either form was not observed.", "inferred", "medium", [f"{pth(p)}" for p in pages if re.search(r"login|register", pth(p))])

    # gaps
    missing = ["Authenticated areas were not explored (Atlas never bypasses authentication).", "Forms were never submitted and all non-GET requests were blocked; write behavior is unobserved.", "Server-side implementation (languages, databases, services) cannot be observed from the browser."]
    if out["skipped"]:
        missing.append(f"{len(out['skipped'])} URL(s) skipped: " + "; ".join(f"{urlsplit(s['url']).path} ({s['reason']})" for s in out["skipped"][:4]))
    missing += out["notes"]
    inacc = [p for p in pages if p["inaccessible"]]
    if inacc:
        missing.append("Inaccessible/blocked pages: " + ", ".join(f"{pth(p)} (HTTP {p['status_code']})" for p in inacc))
    nxt = ["Capture response bodies of the observed GET endpoints to infer data models (schema only, public data).", "Compare initial HTML vs rendered DOM on more pages to confirm the rendering model.", "Re-run with a higher page limit to reach deeper routes."]
    if muts:
        nxt.append("With permission, run a test account to observe what the blocked write endpoints return.")
    if auth:
        nxt.append("With a test account you own, explore authenticated pages to map post-login modules.")
    return {"hypotheses": H, "missing_info": missing, "next_experiments": nxt}
