from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import database as db
from . import processor


class TopicGroup(BaseModel):
    name: str
    summary: str = ""
    drop_ids: list[int]


class SplitRequest(BaseModel):
    groups: list[TopicGroup]

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


@app.post("/api/topics/{topic_id}/split")
async def split_topic(topic_id: int, payload: SplitRequest):
    if len(payload.groups) < 2:
        return JSONResponse(
            {"error": "Must provide at least 2 groups to split into"},
            status_code=400,
        )
    try:
        groups = [g.model_dump() for g in payload.groups]
        new_topics = db.split_topic(topic_id, groups)
        return JSONResponse({"status": "ok", "new_topics": new_topics})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


@app.post("/api/process")
async def trigger_processing():
    count = processor.process_drops()
    return JSONResponse({"status": "ok", "processed": count})
