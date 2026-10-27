"""Full stack with a LOCAL FAKE of the NVIDIA embeddings API (hashed bag-of-words vectors):
real Chromium explores the demo app -> embeddings stored in SQLite -> /search ranks pages. Proves wiring, not DO model quality."""
import hashlib, re, socket, threading, time
import httpx, pytest, uvicorn
from fastapi import FastAPI
from test_e2e_demo import _browser_ok


def _vec(text, dim=96):
    v = [0.0] * dim
    for w in re.findall(r"[a-z]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1
    return v


def _serve(app):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{port}/", timeout=1); break
        except httpx.HTTPStatusError: break
        except Exception: time.sleep(0.1)
    return srv, f"http://127.0.0.1:{port}"


@pytest.mark.skipif(not _browser_ok(), reason="no Chromium available")
def test_embeddings_pipeline_and_search(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    fake = FastAPI(); calls = []
    @fake.post("/v1/embeddings")
    async def emb(body: dict, authorization: str = ""):
        calls.append((body["model"], body.get("input_type")))
        inp = body["input"] if isinstance(body["input"], list) else [body["input"]]
        return {"data": [{"index": i, "embedding": _vec(t)} for i, t in enumerate(inp)], "model": body["model"]}
    fsrv, fbase = _serve(fake)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-fake"); monkeypatch.setattr(config, "NVIDIA_BASE_URL", fbase + "/v1")
    monkeypatch.setattr(config, "EMBED_SIMILARITY", 0.5)
    from app.main import app
    srv, base = _serve(app)
    try:
        assert httpx.get(base + "/api/config").json()["embeddings"]["enabled"] is True
        id_ = httpx.post(base + "/api/analyses", json={"demo": True, "max_pages": 25, "time_limit_s": 90}).json()["id"]
        a = {}
        for _ in range(150):
            a = httpx.get(f"{base}/api/analyses/{id_}").json()
            if a["status"] in ("completed", "failed"): break
            time.sleep(1)
        assert a["status"] == "completed", a.get("error")
        assert a["embeddings"]["pages_embedded"] == len(a["pages"]) and calls and all(t == "passage" for _, t in calls)
        r = httpx.post(f"{base}/api/analyses/{id_}/search", json={"query": "login password sign in"})
        assert r.status_code == 200, r.text
        assert calls[-1][1] == "query"  # search queries use input_type=query
        res = r.json()["results"]
        assert "login" in res[0]["path"] and len(res) >= 3 and res[0]["score"] >= res[-1]["score"]
        # without a key the endpoint refuses clearly instead of crashing
        monkeypatch.setattr(config, "NVIDIA_API_KEY", "")
        assert httpx.post(f"{base}/api/analyses/{id_}/search", json={"query": "x"}).status_code == 503
    finally:
        srv.should_exit = True; fsrv.should_exit = True
