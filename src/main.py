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


@app.get("/", response_class=HTMLResponse)
async def well(request: Request):
    return templates.TemplateResponse("well.html", {"request": request})


@app.post("/api/drop")
async def drop(payload: DropRequest, background_tasks: BackgroundTasks):
    content = payload.content.strip()
    drop = db.insert_drop(content)
    tags = db.extract_tags(content)
    if tags:
        db.insert_tags(drop["id"], tags)
    background_tasks.add_task(processor.process_drops)
    return JSONResponse({"status": "ok", "drop": drop, "tags": tags})


@app.get("/api/drops")
async def get_drops(limit: int = 50, count_only: bool = False):
    if count_only:
        count = db.count_drops()
        return JSONResponse({"count": count})
    drops = db.get_recent_drops(limit)
    return JSONResponse({"drops": drops})


@app.get("/findings", response_class=HTMLResponse)
async def findings_page(request: Request, tag: str | None = None):
    topics = db.get_topics_with_summaries()
    all_tags = db.get_all_tags()
    drops = []
    if tag:
        drops = db.get_drops_by_tag(tag)
        for d in drops:
            d["tags"] = db.get_tags_for_drop(d["id"])
    return templates.TemplateResponse("findings.html", {
        "request": request,
        "topics": topics,
        "all_tags": all_tags,
        "active_tag": tag,
        "drops": drops,
    })


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


@app.get("/api/tags")
async def get_tags():
    tags = db.get_all_tags()
    return JSONResponse({"tags": tags})


@app.get("/api/tags/{tag}")
async def get_tag_drops(tag: str):
    drops = db.get_drops_by_tag(tag)
    for d in drops:
        d["tags"] = db.get_tags_for_drop(d["id"])
    return JSONResponse({"tag": tag, "drops": drops})


@app.post("/api/process")
async def trigger_processing():
    count = processor.process_drops()
    return JSONResponse({"status": "ok", "processed": count})
