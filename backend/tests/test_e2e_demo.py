"""End-to-end: real Chromium explores the bundled synthetic app. Skipped if no browser is available."""
import os, shutil, socket, threading, time
import httpx, pytest, uvicorn


def _browser_ok():
    from pathlib import Path
    if os.getenv("ATLAS_BROWSER_PATH"):
        return os.path.exists(os.environ["ATLAS_BROWSER_PATH"])
    root = Path(os.getenv("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ".cache/ms-playwright")
    return (root.exists() and any(root.glob("chromium*"))) or bool(shutil.which("chromium"))


@pytest.mark.skipif(not _browser_ok(), reason="no Chromium available (run `playwright install chromium`)")
def test_demo_analysis_from_real_observations(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "t.db"))
    from app import config
    config.DB_PATH = str(tmp_path / "t.db")
    from app.main import app
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(base + "/api/health"); break
        except Exception:
            time.sleep(0.1)
    # SSRF: private target rejected before any browser starts
    assert httpx.post(base + "/api/analyses", json={"url": "http://169.254.169.254/", "demo": False}).status_code == 400
    id_ = httpx.post(base + "/api/analyses", json={"demo": True, "max_pages": 25, "time_limit_s": 90}).json()["id"]
    a = {}
    for _ in range(150):
        a = httpx.get(f"{base}/api/analyses/{id_}").json()
        if a["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    srv.should_exit = True
    assert a["status"] == "completed", a.get("error")
    paths = {p["path"] for p in a["pages"]}
    assert {"/demo/", "/demo/catalog", "/demo/login", "/demo/product/1", "/demo/cart"} <= paths
    assert any(p["path"] == "/demo/admin" and p["status_code"] == 401 for p in a["pages"])      # inaccessible handled
    prov = {e["provenance"] for e in a["edges"]}
    assert prov == {"observed", "inferred"}
    titles = " ".join(h["title"] for h in a["hypotheses"])
    assert "Client-side data fetching" in titles and "Write endpoints" in titles
    posts = [r for p in a["pages"] for i in p["interactions"] for r in i["requests"] if r["method"] == "POST"]
    assert posts and all(r["blocked"] for r in posts)  # mutation attempted by the page, blocked by Atlas
