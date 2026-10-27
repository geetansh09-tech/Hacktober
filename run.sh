#!/usr/bin/env bash
# One-command launcher (Linux/macOS): installs everything, builds the UI, checks your NVIDIA key, starts Atlas on :8000.
set -e
cd "$(dirname "$0")"
if [ ! -f .env ]; then cp .env.example .env; echo ">> Created .env — your NVIDIA key goes in it."; fi
if ! grep -Eq '^NVIDIA_API_KEY=.+' .env && [ -z "$NVIDIA_API_KEY" ]; then
  read -r -p ">> Paste your NVIDIA API key (nvapi-...), or press Enter to skip: " K
  [ -n "$K" ] && sed -i.bak "s|^NVIDIA_API_KEY=.*|NVIDIA_API_KEY=$K|" .env && rm -f .env.bak
fi
cd backend
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -m playwright install chromium
cd ../frontend
[ -d node_modules ] || npm install
[ -d dist ] || npm run build
cd ../backend
python -m app.check || echo ">> Continuing without NVIDIA embeddings."
echo ">> Open http://localhost:8000"
exec uvicorn app.main:app --port 8000
