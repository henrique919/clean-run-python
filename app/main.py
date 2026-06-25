from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, ItemUpdate, RectificationEvidence, RAISED_BY_OPTIONS, TRADES
from app.reporting import build_report_html, filter_items
from app.store import CleanRunStore
from app.store_supabase import SupabaseCleanRunStore
from app.validation import ValidationError

logger = logging.getLogger(__name__)


def build_store():
    if os.getenv("CLEANRUN_STORAGE", "").lower() == "supabase":
        try:
            return SupabaseCleanRunStore()
        except Exception:
            logger.exception("Supabase storage unavailable. Falling back to local JSON storage.")
    return CleanRunStore()


app = FastAPI(title="CleanRun IQ Python", version="0.1.0")
store = build_store()

app.mount("/static", StaticFiles(directory="app/static"), name="static")


class IssuePayload(BaseModel):
    to: str
    by: str | None = None
    note: str | None = None
    reissue: bool = False


class ActorPayload(BaseModel):
    by: str = "Site Team"
    note: str | None = None


class RejectPayload(BaseModel):
    by: str = "Site Team"
    reason: str


class RectificationPayload(BaseModel):
    photo: str | None = None
    comment: str | None = None
    by: str
    advance_to_ready: bool = False


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap():
    data = store.snapshot()
    return {
        "settings": data.settings,
        "items": data.items,
        "trades": TRADES,
        "raised_by_options": RAISED_BY_OPTIONS,
    }


@app.get("/api/items")
def list_items(project: str | None = Query(default=None), status: str | None = Query(default=None)):
    return store.list_items(project=project, status=status)


@app.get("/api/items/{item_id}")
def get_item(item_id: str):
    try:
        return store.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items", status_code=201)
def create_item(payload: ItemCreate, issue_now: bool = Query(default=False)):
    try:
        return store.create_item(payload, issue_now=issue_now)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.patch("/api/items/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, by: str | None = Query(default=None)):
    try:
        return store.update_item(item_id, payload, by=by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/items/{item_id}/issue")
def issue_item(item_id: str, payload: IssuePayload):
    try:
        return store.issue_item(item_id, to=payload.to, by=payload.by, note=payload.note, reissue=payload.reissue)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/in-progress")
def mark_in_progress(item_id: str, payload: ActorPayload):
    try:
        return store.mark_in_progress(item_id, by=payload.by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/ready")
def mark_ready(item_id: str, payload: ActorPayload):
    try:
        return store.mark_ready(item_id, by=payload.by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/inspection/start")
def start_inspection(item_id: str, payload: ActorPayload):
    try:
        return store.start_inspection(item_id, by=payload.by)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/inspection/reject")
def reject_item(item_id: str, payload: RejectPayload):
    try:
        return store.reject(item_id, by=payload.by, reason=payload.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/closeout")
def closeout_item(item_id: str, payload: CloseoutEvidence):
    try:
        return store.close_with_evidence(item_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/rectification")
def add_rectification(item_id: str, payload: RectificationPayload):
    try:
        evidence = RectificationEvidence(photo=payload.photo, comment=payload.comment, by=payload.by)
        return store.add_rectification(item_id, evidence, advance_to_ready=payload.advance_to_ready)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/comments")
def add_comment(item_id: str, payload: Comment):
    try:
        return store.add_comment(item_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/api/reports/{report_type}", response_class=HTMLResponse)
def report_html(report_type: str, project: str | None = Query(default=None)):
    data = store.snapshot()
    project_name = project or data.settings.active_project
    items = [i for i in data.items if i.project == project_name]
    html = build_report_html(items, data.settings, report_type=report_type)
    return HTMLResponse(html)


@app.get("/api/reports/{report_type}/summary")
def report_summary(report_type: str, project: str | None = Query(default=None)):
    data = store.snapshot()
    project_name = project or data.settings.active_project
    items = filter_items([i for i in data.items if i.project == project_name], report_type)
    return {
        "report_type": report_type,
        "project": project_name,
        "count": len(items),
        "closed": len([i for i in items if i.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]),
        "outstanding": len([i for i in items if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]),
    }


@app.post("/api/reset-demo")
def reset_demo():
    return store.reset_demo()
