"""FastAPI application exposing the CleanRun IQ Python domain layer."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

from cleanrun_iq.models import CreateItemInput, Item, Settings, UpdateItemInput
from cleanrun_iq.report_builder import build_report_html, filter_items
from cleanrun_iq.services import CleanRunService, WorkflowError
from cleanrun_iq.store import JsonStore, StoreError
from cleanrun_iq.voice_parser import ParsedFields, parse_transcript

DATA_DIR = Path(os.getenv("CLEANRUN_DATA_DIR", "./data"))
store = JsonStore(DATA_DIR)
service = CleanRunService(store=store)
app = FastAPI(title="CleanRun IQ Python Port", version="0.1.0")


class IssueRequest(BaseModel):
    """Issue item request."""

    to: str
    by: str | None = None
    note: str | None = None
    reissue: bool = False


class EvidenceRequest(BaseModel):
    """Rectification evidence request."""

    by: str
    photo: str | None = None
    comment: str | None = None


class CloseRequest(BaseModel):
    """Close item request."""

    by: str
    role: str
    photo: str | None = None
    note: str | None = None
    confirmation: str | None = None


class ActorRequest(BaseModel):
    """Actor-only request."""

    by: str


class RejectRequest(BaseModel):
    """Reject item request."""

    by: str
    reason: str


class CommentRequest(BaseModel):
    """Comment request."""

    by: str
    text: str


class VoiceParseRequest(BaseModel):
    """Voice parse request."""

    transcript: str


@app.get("/health")
def health() -> dict[str, str]:
    """Health-check endpoint."""
    return {"status": "ok"}


@app.get("/settings", response_model=Settings)
def get_settings() -> Settings:
    """Return app settings."""
    try:
        return store.get_settings()
    except StoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/items", response_model=list[Item])
def list_items(status: str | None = Query(default=None), project: str | None = Query(default=None)) -> list[Item]:
    """List items with optional filters."""
    try:
        items = store.get_items()
    except StoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if status:
        items = [item for item in items if item.status == status]
    if project:
        items = [item for item in items if item.project == project]
    return items


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str) -> Item:
    """Return one item by ID."""
    for item in store.get_items():
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/items", response_model=Item)
def create_item(payload: CreateItemInput) -> Item:
    """Create an item."""
    try:
        return service.create_item(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, payload: UpdateItemInput) -> Item:
    """Edit item details."""
    try:
        return service.update_item(item_id, payload, by=store.get_settings().prepared_by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/issue", response_model=Item)
def issue_item(item_id: str, payload: IssueRequest) -> Item:
    """Issue item to a subcontractor."""
    try:
        return service.issue_item(item_id, payload.to, payload.by, payload.note, payload.reissue)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/in-progress", response_model=Item)
def mark_in_progress(item_id: str, payload: ActorRequest) -> Item:
    """Mark item as in progress."""
    try:
        return service.mark_in_progress(item_id, payload.by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/rectification", response_model=Item)
def add_rectification(item_id: str, payload: EvidenceRequest) -> Item:
    """Add rectification evidence."""
    try:
        return service.add_rectification_evidence(item_id, payload.by, payload.photo, payload.comment)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/items/{item_id}/ready-for-review", response_model=Item)
def ready_for_review(item_id: str, payload: ActorRequest) -> Item:
    """Mark item ready for review."""
    try:
        return service.mark_ready_for_review(item_id, payload.by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/inspection/start", response_model=Item)
def start_inspection(item_id: str, payload: ActorRequest) -> Item:
    """Start inspection."""
    try:
        return service.start_inspection(item_id, payload.by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/inspection/reject", response_model=Item)
def reject_item(item_id: str, payload: RejectRequest) -> Item:
    """Reject item during inspection."""
    try:
        return service.reject_item(item_id, payload.by, payload.reason)
    except (KeyError, ValueError, WorkflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/items/{item_id}/close", response_model=Item)
def close_item(item_id: str, payload: CloseRequest) -> Item:
    """Close item with evidence."""
    try:
        return service.close_with_evidence(item_id, payload.by, payload.role, payload.photo, payload.note, payload.confirmation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/items/{item_id}/comments", response_model=Item)
def add_comment(item_id: str, payload: CommentRequest) -> Item:
    """Add comment."""
    try:
        return service.add_comment(item_id, payload.text, payload.by)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/voice/parse")
def parse_voice(payload: VoiceParseRequest) -> ParsedFields:
    """Parse a transcript into structured item fields."""
    return parse_transcript(payload.transcript, store.get_settings().subcontractors)


@app.get("/reports/{report_type}")
def report(report_type: str) -> Response:
    """Return an HTML report."""
    try:
        items = filter_items(store.get_items(), report_type)
        html = build_report_html(items, report_type, store.get_settings())
        return Response(content=html, media_type="text/html")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
