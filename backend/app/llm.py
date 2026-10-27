"""Optional LLM enhancement (OpenAI-compatible chat API). Output is validated and forced to 'inferred'.
Not exercised by the automated tests (needs a real key)."""
import json
import httpx
from . import config


def enabled() -> bool:
    return bool(config.LLM_API_KEY)


async def enhance(hypotheses: list[dict], pages: list[dict]) -> list[dict]:
    digest = [{"path": p["path"], "title": p["title"], "headings": p["headings"][:5], "buttons": p["buttons"][:6], "forms": [f["fields"] for f in p["forms"]]} for p in pages[:30]]
    prompt = ("You analyze browser observations of a web app. Propose up to 4 ADDITIONAL hypotheses about modules/workflows. "
              "Never state private APIs, databases or internals as fact. Each must cite evidence copied from the observations. "
              'Reply ONLY with JSON: [{"category":"module|workflow|architecture","title":"","description":"","confidence":"low|medium","evidence":["..."]}]\n'
              f"Observations: {json.dumps(digest)}\nExisting hypotheses: {json.dumps([h['title'] for h in hypotheses])}")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(config.LLM_API_URL, headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                         json={"model": config.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
        r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"].strip().strip("`").removeprefix("json").strip()
    new = []
    for i, h in enumerate(json.loads(text)[:4]):
        if h.get("category") in ("module", "workflow", "architecture") and h.get("title") and h.get("evidence"):
            new.append({"id": f"l{i}", "category": h["category"], "title": f"[LLM] {h['title']}"[:120], "description": str(h.get("description", ""))[:500],
                        "provenance": "inferred", "confidence": h.get("confidence") if h.get("confidence") in ("low", "medium") else "low", "evidence": [str(e)[:200] for e in h["evidence"]][:6]})
    return new
