"""Verify your NVIDIA key before running Atlas:  python -m app.check"""
import asyncio, sys
import httpx
from . import config, embeddings


async def main() -> int:
    if not embeddings.enabled():
        print("✖ NVIDIA_API_KEY is not set (put it in backend/.env or the project-root .env).")
        return 1
    print(f"Endpoint: {config.NVIDIA_BASE_URL}/embeddings\nModel:    {config.NVIDIA_EMBEDDING_MODEL}\nKey:      …{config.NVIDIA_API_KEY[-4:]}")
    try:
        a, b, c = await embeddings.embed(["login page with email and password", "sign in form", "shopping cart checkout"], input_type="passage")
    except embeddings.EmbeddingError as e:
        print(f"✖ Failed: {e}"); return 2
    print(f"✔ Embeddings work (model now '{config.NVIDIA_EMBEDDING_MODEL}', {len(a)} dims).")
    print(f"  similarity login~signin = {embeddings.cosine(a, b):.2f}  vs login~cart = {embeddings.cosine(a, c):.2f}  (first should be higher)")
    if config.LLM_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(config.LLM_API_URL, headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                                 json={"model": config.LLM_MODEL, "messages": [{"role": "user", "content": "Reply with the word OK"}], "max_tokens": 5})
            print(f"{'✔' if r.status_code == 200 else '⚠'} Chat model '{config.LLM_MODEL}': HTTP {r.status_code}"
                  + ("" if r.status_code == 200 else " (optional LLM step will be skipped; set LLM_MODEL to a model your key can use)"))
        except httpx.HTTPError as e:
            print(f"⚠ Chat check failed ({type(e).__name__}); the optional LLM step will be skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
