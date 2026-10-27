import os, shlex
from pathlib import Path


def _load_dotenv(files=None):
    """Minimal .env loader (no dependency). Real environment variables win. Looks in backend/.env then the project-root .env."""
    here = Path(__file__).resolve().parents[1]
    for f in files or (here / ".env", here.parent / ".env"):
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().removeprefix("export ").strip(), v.strip()
            if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) > 1:
                v = v[1:-1]
            else:
                v = v.split(" #", 1)[0].strip()
            if k and v and not os.environ.get(k):
                os.environ[k] = v


_load_dotenv()

DB_PATH = os.getenv("ATLAS_DB", "atlas.db")
BROWSER_PATH = os.getenv("ATLAS_BROWSER_PATH") or None          # optional custom Chromium
BROWSER_ARGS = shlex.split(os.getenv("ATLAS_BROWSER_ARGS", ""))  # e.g. "--no-sandbox" inside containers
MAX_CONCURRENT_JOBS = int(os.getenv("ATLAS_MAX_CONCURRENT", "2"))
USER_AGENT = "BlackBoxAtlas/0.1 (research crawler; honors robots.txt; read-only)"

# NVIDIA hosted NIM API (OpenAI-compatible, https://build.nvidia.com). Embeddings are enabled when an API key (nvapi-...) is set.
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
NVIDIA_EMBEDDING_MODEL = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")  # must be a model your key can access
EMBED_SIMILARITY = float(os.environ["ATLAS_EMBED_SIMILARITY"]) if os.getenv("ATLAS_EMBED_SIMILARITY") else None  # None = auto-tuned per analysis

# Optional LLM enrichment (OpenAI-compatible chat). Defaults to NVIDIA and reuses NVIDIA_API_KEY when LLM_API_KEY is empty.
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip() or NVIDIA_API_KEY
LLM_API_URL = os.getenv("LLM_API_URL") or f"{NVIDIA_BASE_URL}/chat/completions"
LLM_MODEL = os.getenv("LLM_MODEL") or "meta/llama-3.1-70b-instruct"
