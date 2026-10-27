"""Clone Builder — uses the NVIDIA LLM to generate a self-contained HTML clone of a crawled app."""
import re
import httpx
from . import config


def enabled() -> bool:
    return bool(config.LLM_API_KEY)


def _build_prompt(analysis: dict) -> str:
    target_url = analysis.get("target_url", "")
    pages = analysis.get("pages", [])[:40]
    edges = analysis.get("edges", [])[:60]
    hypotheses = analysis.get("hypotheses", [])[:20]

    # Build detailed page summaries
    page_lines = []
    for p in pages:
        path = p.get("path", "/")
        title = p.get("title", "")
        headings = p.get("headings", [])[:8]
        buttons = p.get("buttons", [])[:10]
        forms = p.get("forms", [])
        form_fields = []
        for f in forms:
            for field in f.get("fields", [])[:8]:
                name = field.get("name") or field.get("placeholder") or field.get("type", "text")
                form_fields.append(name)
        links = p.get("links", [])[:8]
        api_calls = p.get("api_calls", [])[:6]

        line = f"  PAGE: {path}"
        if title:
            line += f"\n    Title: {title}"
        if headings:
            line += f"\n    Headings: {', '.join(str(h) for h in headings)}"
        if buttons:
            line += f"\n    Buttons: {', '.join(str(b) for b in buttons)}"
        if form_fields:
            line += f"\n    Form fields: {', '.join(form_fields)}"
        if api_calls:
            line += f"\n    API calls observed: {', '.join(str(a) for a in api_calls)}"
        if links:
            line += f"\n    Nav links: {', '.join(str(l) for l in links)}"
        page_lines.append(line)

    pages_section = "\n".join(page_lines) if page_lines else "  (no pages crawled)"

    # Build nav edges summary
    edge_lines = []
    for e in edges[:30]:
        src = e.get("from") or e.get("source", "")
        dst = e.get("to") or e.get("target", "")
        label = e.get("label") or e.get("text", "")
        if src and dst:
            edge_lines.append(f"  {src} → {dst}" + (f" [{label}]" if label else ""))
    edges_section = "\n".join(edge_lines) if edge_lines else "  (no navigation edges)"

    # Hypothesis summaries for tech/architecture hints
    hyp_lines = []
    for h in hypotheses:
        hyp_lines.append(f"  [{h.get('category','')}] {h.get('title','')}: {h.get('description','')[:200]}")
    hyp_section = "\n".join(hyp_lines) if hyp_lines else "  (no hypotheses)"

    # Derive nav paths for routing
    nav_paths = list(dict.fromkeys(p.get("path", "/") for p in pages))

    prompt = f"""You are an expert frontend developer. I have reverse-engineered a web application at: {target_url}

Here is everything observed about the app during automated crawling:

=== PAGES DISCOVERED ===
{pages_section}

=== NAVIGATION GRAPH (page transitions) ===
{edges_section}

=== ARCHITECTURE HYPOTHESES ===
{hyp_section}

=== ALL DISCOVERED ROUTES (for routing) ===
{', '.join(nav_paths)}

=== YOUR TASK ===
Generate a COMPLETE, SELF-CONTAINED single HTML file that is a faithful clone/replica of this web application. Requirements:

1. **Single file**: Everything (HTML, CSS, JS) in one .html file. No external files except CDN links.
2. **Tailwind CSS**: Include via CDN: <script src="https://cdn.tailwindcss.com"></script>
3. **Hash routing**: Use window.location.hash for navigation. Each page path becomes a hash route (e.g. /dashboard → #dashboard). The router listens to hashchange events.
4. **All pages**: Create a distinct view/section for EVERY page discovered above. Each view must contain:
   - The page title as an <h1> or prominent heading
   - All headings observed on that page
   - All buttons (functional where possible, otherwise styled placeholders)
   - All forms with all discovered fields (with proper labels and input types)
   - Realistic mock content/data (fake users, products, stats, etc. as appropriate)
   - A card/panel layout matching a real SaaS app
5. **Navigation**: A sidebar or top navbar with links to ALL pages. Clicking a link shows that page's view and hides others.
6. **Color scheme**: Derive a professional color scheme from the app's domain/name. Use Tailwind classes.
7. **Interactivity**: Forms submit with fake success messages. Buttons show feedback. Tables are sortable if present.
8. **Mock data**: Include realistic fake data arrays in JS (e.g. products, users, orders, logs) rendered dynamically.
9. **Comments**: Add HTML comments explaining what each section represents (e.g. <!-- Dashboard page - shows analytics overview -->)
10. **Polish**: Make it look like a real, production-quality web app. Use proper spacing, shadows, and visual hierarchy.

IMPORTANT: Output ONLY the raw HTML. Do not wrap in markdown code fences. Do not add any explanation before or after. Start directly with <!DOCTYPE html> and end with </html>.
"""
    return prompt


def _extract_html(raw: str) -> str:
    """Strip markdown code fences if the LLM wrapped the response."""
    raw = raw.strip()
    # Remove ```html ... ``` or ``` ... ``` fences
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()
    # Ensure it starts with <!DOCTYPE or <html
    if not raw.lower().startswith("<!doctype") and not raw.lower().startswith("<html"):
        # Try to find the start
        idx = raw.lower().find("<!doctype")
        if idx == -1:
            idx = raw.lower().find("<html")
        if idx != -1:
            raw = raw[idx:]
    return raw


async def build_clone(analysis: dict) -> dict:
    """Generate a self-contained HTML clone. Returns {html, filename}."""
    if not enabled():
        raise RuntimeError("LLM not enabled — set LLM_API_KEY or NVIDIA_API_KEY")

    prompt = _build_prompt(analysis)

    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            config.LLM_API_URL,
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
            json={
                "model": config.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 8192,
            },
        )
        r.raise_for_status()

    raw_html = r.json()["choices"][0]["message"]["content"]
    html = _extract_html(raw_html)

    # Derive a safe filename from the target URL
    target_url = analysis.get("target_url", "app")
    from urllib.parse import urlsplit
    try:
        domain = urlsplit(target_url).netloc or target_url
    except Exception:
        domain = target_url
    safe_domain = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")[:50] or "app"
    filename = f"clone-{safe_domain}.html"

    return {"html": html, "filename": filename}
