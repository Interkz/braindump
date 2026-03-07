import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import database as db
from . import processor

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Braindump — The Well", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class DropRequest(BaseModel):
    content: str


class SettingsRequest(BaseModel):
    anthropic_api_key: str | None = None
    processing_mode: str | None = None


@app.get("/", response_class=HTMLResponse)
async def well(request: Request):
    return templates.TemplateResponse("well.html", {"request": request})


@app.post("/api/drop")
async def drop(payload: DropRequest, background_tasks: BackgroundTasks):
    drop = db.insert_drop(payload.content.strip())
    background_tasks.add_task(processor.process_drops)
    return JSONResponse({"status": "ok", "drop": drop})


@app.get("/api/drops")
async def get_drops(limit: int = 50, count_only: bool = False):
    if count_only:
        count = db.count_drops()
        return JSONResponse({"count": count})
    drops = db.get_recent_drops(limit)
    return JSONResponse({"drops": drops})


@app.get("/findings", response_class=HTMLResponse)
async def findings_page(request: Request):
    topics = db.get_topics_with_summaries()
    return templates.TemplateResponse("findings.html", {"request": request, "topics": topics})


@app.get("/api/findings")
async def get_findings():
    topics = db.get_topics_with_summaries()
    return JSONResponse({"topics": topics})


@app.get("/api/findings/{topic_id}")
async def get_finding(topic_id: int):
    result = db.get_topic_with_drops(topic_id)
    if not result:
        return JSONResponse({"error": "Topic not found"}, status_code=404)
    return JSONResponse(result)


@app.post("/api/process")
async def trigger_processing():
    count = processor.process_drops()
    return JSONResponse({"status": "ok", "processed": count})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    api_key = db.get_setting("anthropic_api_key")
    masked_key = ""
    if api_key:
        masked_key = "••••" + api_key[-4:] if len(api_key) > 4 else "••••"
    mode = db.get_setting("processing_mode", "auto")
    has_key = bool(api_key or os.getenv("ANTHROPIC_API_KEY", ""))
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "masked_key": masked_key,
        "processing_mode": mode,
        "has_key": has_key,
    })


@app.post("/api/settings")
async def update_settings(payload: SettingsRequest):
    if payload.anthropic_api_key is not None:
        db.set_setting("anthropic_api_key", payload.anthropic_api_key.strip())
    if payload.processing_mode is not None:
        if payload.processing_mode not in ("auto", "keyword", "llm"):
            return JSONResponse({"error": "Invalid mode"}, status_code=400)
        db.set_setting("processing_mode", payload.processing_mode)
    return JSONResponse({"status": "ok"})


@app.post("/api/settings/test")
async def test_processing():
    """Process one unprocessed drop and return the result."""
    conn = db.get_connection()
    drop = conn.execute(
        "SELECT * FROM drops WHERE processed = 0 ORDER BY dropped_at LIMIT 1"
    ).fetchone()
    conn.close()

    if not drop:
        return JSONResponse({"status": "no_drops", "message": "No unprocessed drops to test with"})

    mode = processor.get_processing_mode()
    api_key = processor.get_api_key()
    effective_mode = mode
    if mode == "auto":
        effective_mode = "llm" if api_key else "keyword"

    count = processor.process_drops()
    return JSONResponse({
        "status": "ok",
        "mode_used": effective_mode,
        "processed": count,
    })
