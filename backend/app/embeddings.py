"""NVIDIA NIM embeddings: semantic grouping of observed pages + semantic search over them.
Vectors only describe *wording similarity of observed page content*; they never prove shared code or backend modules,
so every hypothesis produced here is labelled inferred. The endpoint URL comes from server config, never from user input."""
import asyncio
import math
import statistics
import httpx
from . import config


class EmbeddingError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(config.NVIDIA_API_KEY)


def page_text(p: dict) -> str:
    """Text digest of one observation. Link texts are excluded on purpose: shared header/footer nav would make every page look alike."""
    parts = [p.get("title", ""), p.get("path", "").replace("/", " ").replace("-", " "), *p.get("headings", [])[:6], *p.get("buttons", [])[:8]]
    for f in p.get("forms", [])[:3]:
        parts.append(f"form {f.get('method', '')} fields: " + ", ".join(f.get("fields", [])[:8]))
    return " | ".join(x for x in parts if x).strip()[:1200] or p.get("path", "/")


async def _post(client: httpx.AsyncClient, batch: list[str], input_type: str | None) -> httpx.Response:
    """POST with small retry/backoff for rate limits (429) and transient 5xx. input_type is 'passage' or 'query' (None = omit)."""
    payload: dict = {"model": config.NVIDIA_EMBEDDING_MODEL, "input": batch, "encoding_format": "float"}
    if input_type:
        payload["input_type"] = input_type
    r = None
    for attempt in range(3):
        try:
            r = await client.post(f"{config.NVIDIA_BASE_URL}/embeddings", headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"}, json=payload)
        except httpx.HTTPError as e:
            if attempt == 2:
                raise EmbeddingError(f"network error ({type(e).__name__})") from e
        else:
            if r.status_code != 429 and r.status_code < 500:
                return r
            if attempt == 2:
                return r
        await asyncio.sleep(1.5 * (2 ** attempt))
    return r  # pragma: no cover


async def _discover_model(client: httpx.AsyncClient) -> str | None:
    """If the configured model is rejected, ask the provider which models this key can use and pick an embedding one."""
    try:
        r = await client.get(f"{config.NVIDIA_BASE_URL}/models", headers={"Authorization": f"Bearer {config.NVIDIA_API_KEY}"})
        ids = [m["id"] for m in r.json().get("data", []) if isinstance(m, dict) and "id" in m] if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError, AttributeError):
        return None
    cands = [i for i in ids if i != config.NVIDIA_EMBEDDING_MODEL and any(k in i.lower() for k in ("embedqa", "embed", "gte", "e5"))
             and not any(k in i.lower() for k in ("vl", "vlm", "clip", "rerank"))]
    return next((i for i in cands if "embedqa" in i.lower()), cands[0] if cands else None)


async def embed(texts: list[str], client: httpx.AsyncClient | None = None, input_type: str = "passage") -> list[list[float]]:
    if not enabled():
        raise EmbeddingError("NVIDIA_API_KEY is not configured")
    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):  # small batches keep requests well under provider limits
            batch = texts[i:i + 32]
            r = await _post(client, batch, input_type)
            if r.status_code in (400, 422):  # some models (GTE/GTR) reject input_type: retry once without it
                r = await _post(client, batch, None)
            if r.status_code in (400, 404, 422):  # likely "model not available to this key": try to auto-pick one the key can use
                alt = await _discover_model(client)
                if alt:
                    config.NVIDIA_EMBEDDING_MODEL = alt
                    r = await _post(client, batch, input_type)
                    if r.status_code in (400, 422):
                        r = await _post(client, batch, None)
            if r.status_code in (401, 403):
                raise EmbeddingError(f"HTTP {r.status_code}: the NVIDIA API key was rejected or lacks access to model '{config.NVIDIA_EMBEDDING_MODEL}'")
            if r.status_code != 200:
                raise EmbeddingError(f"HTTP {r.status_code} from embeddings endpoint (model '{config.NVIDIA_EMBEDDING_MODEL}'; check model name and rate limits)")
            try:
                rows = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
                vecs = [[float(x) for x in d["embedding"]] for d in rows]
            except (KeyError, TypeError, ValueError) as e:
                raise EmbeddingError("unexpected embeddings response shape") from e
            if len(vecs) != len(batch):
                raise EmbeddingError("embeddings count did not match input count")
            out += vecs
        return out
    finally:
        if own:
            await client.aclose()


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def groups(vecs: dict[str, list[float]], threshold: float) -> list[tuple[list[str], float]]:
    """Single-linkage grouping (union-find) of ids whose pairwise cosine >= threshold. Returns (ids, mean pairwise cosine), size >= 2."""
    ids = list(vecs)
    parent = {i: i for i in ids}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if cosine(vecs[a], vecs[b]) >= threshold:
                parent[find(a)] = find(b)
    comp: dict[str, list[str]] = {}
    for i in ids:
        comp.setdefault(find(i), []).append(i)
    res = []
    for g in comp.values():
        if len(g) >= 2:
            sims = [cosine(vecs[a], vecs[b]) for k, a in enumerate(g) for b in g[k + 1:]]
            res.append((g, sum(sims) / len(sims)))
    return sorted(res, key=lambda t: (-len(t[0]), -t[1]))


def rank(query_vec: list[float], vecs: dict[str, list[float]], top_k: int = 8) -> list[dict]:
    scored = sorted(((cosine(query_vec, v), pid) for pid, v in vecs.items()), reverse=True)
    return [{"page_id": pid, "score": round(s, 4)} for s, pid in scored[:top_k]]


def auto_threshold(vecs: dict[str, list[float]]) -> float:
    """Different embedding models have different similarity scales, so by default use mean + 1 std of this analysis' pairwise
    cosines, clamped to [0.5, 0.92]. Set ATLAS_EMBED_SIMILARITY to pin a fixed value."""
    ids = list(vecs)
    sims = [cosine(vecs[a], vecs[b]) for k, a in enumerate(ids) for b in ids[k + 1:]]
    if len(sims) < 2:
        return 0.75
    return min(0.92, max(0.5, statistics.fmean(sims) + statistics.pstdev(sims)))


def semantic_hypotheses(pages: list[dict], vecs: dict[str, list[float]], threshold: float | None = None) -> list[dict]:
    threshold = threshold if threshold is not None else (config.EMBED_SIMILARITY if config.EMBED_SIMILARITY is not None else auto_threshold(vecs))
    by_id = {p["id"]: p for p in pages}
    H = []
    for g, avg in groups(vecs, threshold)[:4]:
        paths = [by_id[i]["path"] for i in g if i in by_id]
        ev = [f"{by_id[i]['path']} — “{by_id[i]['title']}”" for i in g if i in by_id]
        ev.append(f"mean pairwise cosine similarity {avg:.2f} (threshold {threshold:.2f}), model {config.NVIDIA_EMBEDDING_MODEL}")
        H.append({"id": f"s{len(H)}", "category": "module", "title": "Semantically related pages: " + ", ".join(paths[:4]) + ("…" if len(paths) > 4 else ""),
                  "description": "NVIDIA embeddings rate the visible content of these pages as similar. This suggests a shared feature area, but it only reflects wording similarity — it does not show shared code or backend modules.",
                  "provenance": "inferred", "confidence": "medium" if avg >= 0.75 else "low", "evidence": ev[:10]})
    return H


async def enrich(pages: list[dict]) -> tuple[list[dict], dict[str, list[float]]]:
    vecs_list = await embed([page_text(p) for p in pages])
    vecs = {p["id"]: v for p, v in zip(pages, vecs_list)}
    return semantic_hypotheses(pages, vecs), vecs
