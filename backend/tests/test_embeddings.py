"""Embeddings client/grouping tests use a mocked NVIDIA response; real-key behaviour is NOT covered here."""
import asyncio, httpx, pytest
from app import config, embeddings


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_embed_sends_nvidia_request_and_orders_by_index(monkeypatch):
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-test")
    seen = {}
    def h(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], req.read()
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})
    out = asyncio.run(embeddings.embed(["a", "b"], client=_client(h)))
    assert out == [[1.0, 0.0], [0.0, 1.0]]
    assert seen["url"] == "https://integrate.api.nvidia.com/v1/embeddings" and seen["auth"] == "Bearer nvapi-test"
    assert b'"input_type": "passage"' in seen["body"] or b'"input_type":"passage"' in seen["body"]
    assert config.NVIDIA_EMBEDDING_MODEL.encode() in seen["body"]


@pytest.mark.parametrize("resp", [httpx.Response(401), httpx.Response(200, json={"oops": 1}), httpx.Response(200, json={"data": []})])
def test_embed_errors_are_typed(monkeypatch, resp):
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "k")
    with pytest.raises(embeddings.EmbeddingError):
        asyncio.run(embeddings.embed(["x"], client=_client(lambda r: resp)))


def test_embed_requires_key(monkeypatch):
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "")
    with pytest.raises(embeddings.EmbeddingError):
        asyncio.run(embeddings.embed(["x"]))


def test_grouping_ranking_and_hypotheses_are_inferred():
    vecs = {"a": [1, 0.1], "b": [0.9, 0.2], "c": [0, 1]}
    g = embeddings.groups(vecs, 0.9)
    assert len(g) == 1 and set(g[0][0]) == {"a", "b"}
    assert embeddings.rank([0, 1], vecs, 1)[0]["page_id"] == "c"
    pages = [{"id": i, "path": f"/{i}", "title": i.upper()} for i in vecs]
    h = embeddings.semantic_hypotheses(pages, vecs, 0.9)
    assert len(h) == 1 and h[0]["provenance"] == "inferred" and h[0]["confidence"] in ("low", "medium")
    assert any("cosine" in e for e in h[0]["evidence"])


def test_page_text_ignores_global_nav_links():
    t = embeddings.page_text({"title": "Cart", "path": "/cart", "headings": ["Your cart"], "buttons": ["Checkout"], "forms": [], "links": [{"text": "SHARED-NAV", "href": "/"}]})
    assert "Cart" in t and "Checkout" in t and "SHARED-NAV" not in t


def test_dotenv_loader_reads_file_and_env_wins(tmp_path, monkeypatch):
    import os
    from app import config as cfg
    env = tmp_path / ".env"
    env.write_text('# c\nNVIDIA_API_KEY="nvapi-from-file"  \nATLAS_MAX_CONCURRENT=3 # inline\nexport FOO_TEST=bar\n')
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False); monkeypatch.delenv("FOO_TEST", raising=False)
    monkeypatch.setenv("ATLAS_MAX_CONCURRENT", "9")
    try:
        cfg._load_dotenv([env])
        assert os.environ["NVIDIA_API_KEY"] == "nvapi-from-file" and os.environ["FOO_TEST"] == "bar"
        assert os.environ["ATLAS_MAX_CONCURRENT"] == "9"  # real env wins over file
    finally:
        os.environ.pop("NVIDIA_API_KEY", None); os.environ.pop("FOO_TEST", None)


def test_model_autodiscovery_and_retry(monkeypatch):
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "k"); monkeypatch.setattr(config, "NVIDIA_EMBEDDING_MODEL", "bad-model")
    real_sleep = asyncio.sleep
    async def fast(_s): await real_sleep(0)
    monkeypatch.setattr(embeddings.asyncio, "sleep", fast)
    n = {"429": 0}
    def h(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "llama-chat"}, {"id": "nvidia/nv-embedqa-1b-v2"}]})
        body = req.read().decode()
        if "bad-model" in body:
            return httpx.Response(404)
        if n["429"] == 0:
            n["429"] = 1; return httpx.Response(429)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})
    assert asyncio.run(embeddings.embed(["x"], client=_client(h))) == [[1.0, 2.0]]
    assert config.NVIDIA_EMBEDDING_MODEL == "nvidia/nv-embedqa-1b-v2"


def test_auto_threshold_is_clamped_and_used(monkeypatch):
    monkeypatch.setattr(config, "EMBED_SIMILARITY", None)
    vecs = {"a": [1, 0], "b": [0.99, 0.1], "c": [0, 1]}
    t = embeddings.auto_threshold(vecs)
    assert 0.5 <= t <= 0.92
    assert embeddings.semantic_hypotheses([{"id": i, "path": "/" + i, "title": i} for i in vecs], vecs)  # works with no fixed threshold


def test_query_input_type_and_fallback_without_input_type(monkeypatch):
    """E5-style models need input_type; GTE-style models reject it -> client retries once without it."""
    monkeypatch.setattr(config, "NVIDIA_API_KEY", "k"); monkeypatch.setattr(config, "NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
    bodies = []
    def h(req):
        b = req.read().decode(); bodies.append(b)
        return httpx.Response(400) if "input_type" in b and "gte" in b else httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 0]}]})
    asyncio.run(embeddings.embed(["q"], client=_client(h), input_type="query"))
    assert "query" in bodies[0] and "input_type" in bodies[0]
    monkeypatch.setattr(config, "NVIDIA_EMBEDDING_MODEL", "gte-test"); bodies.clear()
    assert asyncio.run(embeddings.embed(["q"], client=_client(h))) == [[1.0, 0.0]]
    assert "input_type" in bodies[0] and "input_type" not in bodies[1]
