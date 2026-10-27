import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import clone, config, db, embeddings, jobs, llm
from .demo_app import demo
from .safety import UnsafeURL

app = FastAPI(title="BlackBox Atlas API")


class StartRequest(BaseModel):
    url: str = Field(default="demo", max_length=2048)
    demo: bool = False
    max_pages: int = Field(default=25, ge=1, le=100)
    time_limit_s: int = Field(default=120, ge=10, le=600)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def get_config():  # capability flags only; secrets are never exposed
    return {"embeddings": {"enabled": embeddings.enabled(), "model": config.NVIDIA_EMBEDDING_MODEL if embeddings.enabled() else None, "provider": "NVIDIA"}, "llm": llm.enabled()}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=8, ge=1, le=25)


@app.post("/api/analyses/{id_}/search")
async def search(id_: str, req: SearchRequest):
    a = jobs.JOBS.get(id_) or db.load(id_)
    if not a:
        raise HTTPException(404, "Analysis not found")
    if not embeddings.enabled():
        raise HTTPException(503, "Semantic search needs NVIDIA_API_KEY in the backend environment.")
    stored = db.load_embeddings(id_)
    if not stored:
        raise HTTPException(409, "This analysis has no stored embeddings (it ran without a key, or embedding failed).")
    model, vecs = stored
    try:
        (qv,) = await embeddings.embed([req.query], input_type="query")
    except embeddings.EmbeddingError as e:
        raise HTTPException(502, f"Embeddings provider error: {e}")
    if model != config.NVIDIA_EMBEDDING_MODEL:
        raise HTTPException(409, f"Stored vectors use model '{model}' but the server is set to '{config.NVIDIA_EMBEDDING_MODEL}'; re-run the analysis.")
    paths = {p["id"]: p for p in a["pages"]}
    return {"model": model, "results": [{**r, "path": paths[r["page_id"]]["path"], "title": paths[r["page_id"]]["title"]} for r in embeddings.rank(qv, vecs, req.top_k) if r["page_id"] in paths]}


@app.post("/api/analyses")
async def start(req: StartRequest, request: Request):
    origin = f"{request.url.scheme}://{request.url.netloc}"
    if req.demo:
        url, demo_origin, scope = f"{origin}/demo/", origin, "/demo"
    else:
        url, demo_origin, scope = req.url.strip(), None, "/"
    try:
        checker = await jobs.validate_target(url, demo_origin)
    except UnsafeURL as e:
        raise HTTPException(400, f"Target rejected: {e}")
    a = jobs.new_job(url, req.demo, req.max_pages, req.time_limit_s)
    task = asyncio.create_task(jobs.run(a, checker, scope))
    jobs.TASKS.add(task); task.add_done_callback(jobs.TASKS.discard)
    return {"id": a["id"]}


@app.get("/api/analyses")
def list_():
    return db.list_all()


@app.get("/api/analyses/{id_}")
def get(id_: str):
    a = jobs.JOBS.get(id_) or db.load(id_)
    if not a:
        raise HTTPException(404, "Analysis not found")
    return a


@app.post("/api/analyses/{id_}/clone")
async def build_clone(id_: str):
    a = jobs.JOBS.get(id_) or db.load(id_)
    if not a:
        raise HTTPException(404, "Analysis not found")
    if not clone.enabled():
        raise HTTPException(503, "Clone Builder needs LLM_API_KEY or NVIDIA_API_KEY set in the backend environment.")
    try:
        result = await clone.build_clone(a)
    except Exception as e:
        raise HTTPException(502, f"Clone generation failed: {e}")
    return result


@app.post("/api/analyses/{id_}/cancel")
def cancel(id_: str):
    if id_ not in jobs.JOBS:
        raise HTTPException(404, "Analysis not found")
    jobs.CANCEL.add(id_)
    return {"ok": True}


app.mount("/demo", demo)
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():  # single-command mode: serve the built UI
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
