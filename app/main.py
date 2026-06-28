from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, ItemUpdate, ProjectConfig, RectificationEvidence, RAISED_BY_OPTIONS, Settings, TRADES
from app.reporting import build_report_html, filter_items
from app.store import CleanRunStore
from app.validation import ValidationError

logger = logging.getLogger(__name__)


def build_store():
    if os.getenv("CLEANRUN_STORAGE", "").lower() == "supabase":
        try:
            from app.store_supabase import SupabaseCleanRunStore

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


class SettingsPayload(BaseModel):
    active_project: str | None = None
    company: str | None = None
    prepared_by: str | None = None
    projects: list[str] | None = None
    project_configs: dict[str, ProjectConfig] | None = None


def _configured_project_context(project: str) -> dict:
    data = store.snapshot()
    cfg = data.settings.project_configs.get(project)
    if not cfg:
        raise HTTPException(status_code=400, detail="Unknown project for voice parsing")
    return {
        "project": project,
        "buildings": cfg.buildings,
        "levels": cfg.levels,
        "units": cfg.units,
        "rooms": cfg.rooms,
        "trades": TRADES,
        "subcontractors": data.settings.subcontractors,
        "sub_profiles": {name: profile.model_dump() for name, profile in data.settings.sub_profiles.items()},
        "item_types": ["defect", "incomplete", "client"],
        "priorities": ["high", "urgent"],
    }


def _voice_item_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "project": {"type": ["string", "null"]},
            "building": {"type": ["string", "null"]},
            "level": {"type": ["string", "null"]},
            "unit": {"type": ["string", "null"]},
            "room": {"type": ["string", "null"]},
            "trade": {"type": ["string", "null"]},
            "subcontractor": {"type": ["string", "null"]},
            "priority": {"type": "string", "enum": ["high", "urgent"]},
            "type": {"type": "string", "enum": ["defect", "incomplete", "client"]},
            "due_date": {"type": ["string", "null"]},
            "description": {"type": "string"},
            "raw_transcript": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "project",
            "building",
            "level",
            "unit",
            "room",
            "trade",
            "subcontractor",
            "priority",
            "type",
            "due_date",
            "description",
            "raw_transcript",
            "confidence",
            "warnings",
        ],
    }


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    if "/static/photo-compression.js" not in html:
        html = html.replace(
            '<script src="/static/app.js"></script>',
            '<script src="/static/app.js"></script>\n  <script src="/static/photo-compression.js"></script>',
        )
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/storage-status")
def storage_status():
    data = store.snapshot()
    latest = data.items[0] if data.items else None
    latest_photo = None
    if latest and latest.original_photos:
        latest_photo = latest.original_photos[0]
    return {
        "requested_storage": os.getenv("CLEANRUN_STORAGE", "local"),
        "active_store": store.__class__.__name__,
        "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
        "supabase_key_configured": bool(os.getenv("SUPABASE_KEY")),
        "storage_bucket": os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence"),
        "item_count": len(data.items),
        "latest_item_code": latest.code if latest else None,
        "latest_item_description": latest.description if latest else None,
        "latest_photo_type": "storage_url" if latest_photo and str(latest_photo).startswith("http") else "base64_or_empty" if latest_photo else "none",
        "latest_photo_preview": str(latest_photo)[:80] if latest_photo else None,
    }


@app.get("/api/voice/status")
def voice_status() -> dict[str, bool | str]:
    return {
        "ai_voice_enabled": bool(os.getenv("OPENAI_API_KEY")),
        "transcribe_model": os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        "parse_model": os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini"),
    }


@app.post("/api/voice/parse")
async def parse_voice_note(audio: UploadFile = File(...), project: str = Form(...)):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="AI voice parsing is not configured. Type the note and use Draft form from note.")

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.exception("OpenAI SDK unavailable")
        raise HTTPException(status_code=503, detail="AI voice parser dependency is unavailable.") from exc

    context = _configured_project_context(project)
    suffix = Path(audio.filename or "voice-note.webm").suffix or ".webm"
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Voice recording was empty. Retry or type the note.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
                file=audio_file,
                response_format="text",
            )

        transcript = transcription if isinstance(transcription, str) else getattr(transcription, "text", "")
        transcript = str(transcript or "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="No speech was detected. Retry or type the note.")

        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert Australian construction site voice notes into CleanRun IQ item fields. "
                        "Use the allowed project context wherever possible. Do not invent locations, trades, or subcontractors. "
                        "Preserve the full spoken note as raw_transcript, but keep description concise and remove structured location data. "
                        "Example: 'Building 3, Unit 305, Balcony, on Level 1, tiling to be repaired.' becomes "
                        "building B3/Building 3, unit U305/Unit 305, room Balcony, level Level 1, trade Tiling, "
                        "description 'Tiling to be repaired.'"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"transcript": transcript, "allowed_context": context}),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "cleanrun_voice_item",
                    "strict": True,
                    "schema": _voice_item_schema(),
                },
            },
        )
        parsed = json.loads(completion.choices[0].message.content or "{}")
        parsed["raw_transcript"] = transcript
        return {"transcript": transcript, "parsed": parsed, "source": "ai"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("AI voice parse failed")
        raise HTTPException(status_code=502, detail="AI voice parsing failed. Retry or type the note.") from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.get("/api/bootstrap")
def bootstrap():
    data = store.snapshot()
    return {
        "settings": data.settings,
        "items": data.items,
        "trades": TRADES,
        "raised_by_options": RAISED_BY_OPTIONS,
    }


@app.patch("/api/settings")
def update_settings(payload: SettingsPayload):
    data = store.snapshot()
    current = data.settings
    updates = payload.model_dump(exclude_unset=True)
    settings = Settings.model_validate({**current.model_dump(), **updates})
    return store.update_settings(settings)


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
