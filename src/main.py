from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
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


@app.get("/api/export")
async def export_drops(format: str = "json"):
    if format == "markdown":
        grouped, uncategorised = db.get_drops_grouped_by_topic()
        lines: list[str] = []
        for topic in grouped:
            lines.append(f"# {topic['name']}")
            for drop in topic["drops"]:
                lines.append(f"- {drop}")
            lines.append("")
        if uncategorised:
            lines.append("# Uncategorised")
            for drop in uncategorised:
                lines.append(f"- {drop}")
            lines.append("")
        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=braindump-export.md"},
        )

    drops = db.get_all_drops()
    return Response(
        content=json.dumps({"drops": drops}, default=str),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=braindump-export.json"},
    )


@app.post("/api/process")
async def trigger_processing():
    count = processor.process_drops()
    return JSONResponse({"status": "ok", "processed": count})
