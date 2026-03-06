import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import database as db
from . import processor

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent.parent / "static"

PROCESS_INTERVAL = 5 * 60  # seconds

_last_processed_at: str | None = None


async def _periodic_processor():
    global _last_processed_at
    while True:
        await asyncio.sleep(PROCESS_INTERVAL)
        try:
            count = await asyncio.to_thread(processor.process_drops)
            _last_processed_at = datetime.now(timezone.utc).isoformat()
            if count:
                log.info("Periodic processing: %d drops processed", count)
        except Exception:
            log.exception("Periodic processing failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(_periodic_processor())
    yield
    task.cancel()


app = FastAPI(title="Braindump — The Well", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class DropRequest(BaseModel):
    content: str


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


@app.get("/api/status")
async def status():
    counts = db.get_status_counts()
    return JSONResponse({
        "status": "ok",
        "total_drops": counts["total_drops"],
        "topics_count": counts["topics_count"],
        "unprocessed_count": counts["unprocessed_count"],
        "last_processed_at": _last_processed_at,
    })


@app.post("/api/process")
async def trigger_processing():
    global _last_processed_at
    count = processor.process_drops()
    _last_processed_at = datetime.now(timezone.utc).isoformat()
    return JSONResponse({"status": "ok", "processed": count})
