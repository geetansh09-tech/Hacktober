# BlackBox Atlas

AI-assisted black-box reverse engineering: give it a URL, it explores public pages in a sandboxed Chromium
(Playwright), records what it **observes**, builds a behavioral graph, and generates an evidence-backed blueprint.
Everything shown comes from browser observations; guesses are labelled **INFERRED** with a confidence level.

## Quick start (one command)
```bash
./run.sh          # Linux/macOS   (Windows: .\run.ps1)
```
It creates `.env` from `.env.example` on first run, installs everything, builds the UI, checks your NVIDIA key, and serves
everything at **http://localhost:8000**. To enable embeddings, put your key in `.env` (`NVIDIA_API_KEY=nvapi-...`) and re-run.
The backend loads `.env` itself (real environment variables take precedence). Check a key on its own with `cd backend && python -m app.check`.
Demo mode works with no key and no internet.

## Manual setup
```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp ../.env.example ../.env     # optional; the backend reads it automatically
uvicorn app.main:app --port 8000

# Frontend (second terminal)
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8000)
```
Single-command mode: `cd frontend && npm run build`, then open http://localhost:8000 (the API serves `frontend/dist`).

## Try it
Leave **Demo mode** on and press **Start analysis**. Atlas explores a bundled synthetic shop ("Northwind", mounted at
`/demo`, clearly labelled). Known ground truth to check against (see `backend/app/demo_app.py`):
catalog is client-rendered from `GET /demo/api/products`; the product page's *Add to cart* issues `POST /demo/api/cart`
(Atlas blocks it and reports the attempt); `/demo/checkout` redirects to `/demo/login`; `/demo/admin` returns 401;
`/demo/help` is only reachable from the footer.

## Safety model
- Target + **every browser request and redirect hop** is validated: http(s) only, no credentials, ports 80/443/8080/8443,
  DNS resolved and *all* answers must be public (blocks loopback, RFC1918, link-local/metadata `169.254.x`, CGNAT, IPv6 private,
  mapped IPv4, decimal/hex IP tricks). The only exception is the exact origin of the bundled demo app.
- Read-only: forms are never submitted, **all non-GET requests are aborted** (attempts are recorded as evidence),
  cross-origin navigation is aborted, WebSocket/EventSource disabled, service workers blocked, downloads off.
- Honors `robots.txt`; never retries or bypasses 401/403/429/CAPTCHA pages — they are reported as inaccessible.
- Page/time limits (1–100 pages, 10–600 s) plus a hard job timeout. Target JavaScript runs only inside Chromium, never on the host.
- **Known limitation:** DNS is resolved by Atlas and again by Chromium, so a DNS-rebinding attacker could in theory race the two.
  For production, run the worker in a network namespace/container with egress firewall rules blocking private ranges.

## API
`POST /api/analyses {url, demo, max_pages, time_limit_s}` → `{id}` · `GET /api/analyses/{id}` · `GET /api/analyses` · `POST /api/analyses/{id}/cancel`

## NVIDIA embeddings (optional)
Set `NVIDIA_API_KEY` (see `.env.example`) and restart the backend. Atlas then calls `POST https://integrate.api.nvidia.com/v1/embeddings`
(model `nvidia/nv-embedqa-e5-v5` by default):
- after exploration, each page's observed text (title, path, headings, buttons, form fields — not shared nav links) is embedded with
  `input_type=passage` and stored in SQLite;
- pages that are semantically close are surfaced as **INFERRED** "related pages" hypotheses with cosine scores as evidence;
- the **Semantic search** tab embeds your question with `input_type=query`, ranks pages (`POST /api/analyses/{id}/search`) and selects the hit in the graph.

`GET /api/config` reports whether embeddings are on (never the key). Embedding failures degrade gracefully to the deterministic report.
If the model is rejected, Atlas asks `/v1/models` for another embedding model your key can use; models that reject `input_type` are retried without it.
Check a key with `cd backend && python -m app.check`. **Not verified against the live NVIDIA service** — tests use a local fake of the API.

## Optional LLM
Set `LLM_API_KEY` (+ `LLM_API_URL`, `LLM_MODEL`) to add up to 4 extra hypotheses. They are forced to *inferred*, low/medium
confidence, must cite evidence, and are prefixed `[LLM]`. Without a key, deterministic rules run. The LLM path is not covered by tests.

## Tests
`cd backend && pytest` (SSRF rules, embeddings client/grouping/search against a fake NVIDIA API, inference rules, end-to-end real-browser run of the demo app; the e2e test skips if no Chromium)
· `cd frontend && npm test`. In containers set `ATLAS_BROWSER_PATH` / `ATLAS_BROWSER_ARGS=--no-sandbox`.
