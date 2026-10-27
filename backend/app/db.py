import json, sqlite3, threading
from . import config

_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, target TEXT, status TEXT, started_at TEXT, data TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS embeddings (analysis_id TEXT PRIMARY KEY, model TEXT, vectors TEXT)")
    return c


def save(a: dict):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO analyses VALUES (?,?,?,?,?)", (a["id"], a["target_url"], a["status"], a["started_at"], json.dumps(a)))


def load(id_: str) -> dict | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT data FROM analyses WHERE id=?", (id_,)).fetchone()
    return json.loads(r[0]) if r else None


def list_all() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT id,target,status,started_at,data FROM analyses ORDER BY started_at DESC LIMIT 50").fetchall()
    return [{"id": i, "target_url": t, "status": s, "started_at": st, "demo": json.loads(d).get("demo", False)} for i, t, s, st, d in rows]


def save_embeddings(analysis_id: str, model: str, vecs: dict[str, list[float]]):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?,?)", (analysis_id, model, json.dumps(vecs)))


def load_embeddings(analysis_id: str) -> tuple[str, dict[str, list[float]]] | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT model, vectors FROM embeddings WHERE analysis_id=?", (analysis_id,)).fetchone()
    return (r[0], json.loads(r[1])) if r else None
