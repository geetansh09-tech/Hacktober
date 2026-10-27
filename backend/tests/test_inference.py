from app.inference import build_edges, infer, pattern


def page(i, path, **kw):
    base = dict(id=f"p{i}", url="https://t.test" + path, path=path, title=path, status_code=200, headings=[], links=[], buttons=[], forms=[], requests=[], interactions=[],
                headers={}, redirected_from=[], inaccessible=False, render={"raw_links": 1, "dom_links": 1, "raw_text": 10, "dom_text": 10}, signals=[])
    base.update(kw)
    return base


def sample():
    pages = [page(0, "/", links=[{"text": "Cart", "href": "https://t.test/cart"}], buttons=[]),
             page(1, "/cart", links=[], buttons=["Checkout"]),
             page(2, "/login", forms=[{"action": "/login", "method": "post", "fields": ["email", "password"]}]),
             page(3, "/item/1"), page(4, "/item/2")]
    out = {"pages": pages, "followed": [{"source": "p0", "target": "p1", "text": "Cart", "redirects": [], "status": 200}], "redirect_map": {},
           "path_to_id": {p["url"]: p["id"] for p in pages}, "third_party": {}, "notes": [], "skipped": []}
    return out


def test_pattern():
    assert pattern("/item/42") == "/item/{id}" and pattern("/") == "/"


def test_edges_distinguish_observed_and_inferred():
    out = sample()
    edges = build_edges(out)
    assert [e["provenance"] for e in edges if e["source"] == "p0"] == ["observed"]
    assert any("navigated" in x for x in edges[0]["evidence"])


def test_hypotheses_have_evidence_and_no_invented_internals():
    out = sample()
    res = infer(out, build_edges(out))
    assert res["hypotheses"] and all(h["evidence"] for h in res["hypotheses"])
    titles = " ".join(h["title"].lower() for h in res["hypotheses"])
    assert "authentication" in titles and "{id}" in titles
    assert not any(w in titles for w in ("postgres", "mysql", "mongodb", "redis"))
    assert any("not explored" in m.lower() for m in res["missing_info"])
