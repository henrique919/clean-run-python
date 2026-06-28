from __future__ import annotations

import logging
import os
import json
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import RequestContext, get_request_context
from app.config import app_env, is_production
from app.db import build_repository
from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, ItemUpdate, ProjectConfig, RectificationEvidence, RAISED_BY_OPTIONS, Settings, TRADES
from app.permissions import (
    require_close_item,
    require_comment_access,
    require_create_item,
    require_demo_reset,
    require_issue_item,
    require_item_access,
    require_rectification_access,
    require_report_access,
    require_storage_status_access,
    require_update_item,
    visible_items,
    visible_projects,
)
from app.services import items as item_service
from app.services import projects as project_service
from app.services import reports as report_service
from app.validation import ValidationError

logger = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
FIELD_APP_DIR = REPO_ROOT / "CleanRun-IQ-Full-App-Render3"
FIELD_ASSETS_DIR = FIELD_APP_DIR / "assets"


app = FastAPI(title="CleanRun IQ Python", version="0.1.0")
store = build_repository()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if FIELD_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FIELD_ASSETS_DIR)), name="assets")


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
    by: str | None = None
    advance_to_ready: bool = False


class SettingsPayload(BaseModel):
    active_project: str | None = None
    company: str | None = None
    prepared_by: str | None = None
    projects: list[str] | None = None
    project_configs: dict[str, ProjectConfig] | None = None


def actor_label(ctx: RequestContext) -> str:
    return ctx.user.audit_label


def actor_context(ctx: RequestContext) -> dict[str, str | None]:
    return {
        "id": ctx.user.id,
        "email": ctx.user.email,
        "role": ctx.user.company_role or ctx.user.project_roles.get("*"),
        "auth_method": ctx.user.auth_method,
    }


def get_authorized_item(item_id: str, ctx: RequestContext):
    try:
        item = item_service.get_item(store, item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")
    require_item_access(ctx.user, item)
    return item


def scoped_settings(settings: Settings, ctx: RequestContext) -> Settings:
    projects = visible_projects(ctx.user, settings)
    project_configs = {name: cfg for name, cfg in settings.project_configs.items() if name in projects}
    active_project = settings.active_project if settings.active_project in projects else (projects[0] if projects else "")
    return settings.model_copy(
        update={
            "projects": projects,
            "project_configs": project_configs,
            "active_project": active_project,
            "prepared_by": ctx.user.audit_label,
        }
    )


def configured_voice_context(project: str, ctx: RequestContext) -> dict[str, object]:
    require_create_item(ctx.user, project)
    data = store.snapshot()
    visible = scoped_settings(data.settings, ctx)
    cfg = visible.project_configs.get(project)
    if not cfg:
        raise HTTPException(status_code=400, detail="Unknown or unauthorized project for voice parsing")
    return {
        "project": project,
        "buildings": cfg.buildings,
        "levels": cfg.levels,
        "units": cfg.units,
        "rooms": cfg.rooms,
        "trades": TRADES,
        "subcontractors": visible.subcontractors,
        "sub_profiles": {name: profile.model_dump() for name, profile in visible.sub_profiles.items()},
        "item_types": ["defect", "incomplete", "client"],
        "priorities": ["high", "urgent"],
    }


def voice_item_schema() -> dict[str, object]:
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


@app.get("/api/auth/config")
def auth_config() -> dict[str, object]:
    return {
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY"),
        "environment": os.getenv("CLEANRUN_ENV", "development"),
        "dev_tokens_enabled": not is_production(),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    field_app = FIELD_APP_DIR / "index.html"
    html = (field_app if field_app.exists() else STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/voice/status")
def voice_status(ctx: RequestContext = Depends(get_request_context)) -> dict[str, bool | str]:
    return {
        "ai_voice_enabled": bool(os.getenv("OPENAI_API_KEY")),
        "transcribe_model": os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        "parse_model": os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini"),
    }


@app.post("/api/voice/parse")
async def parse_voice_note(
    audio: UploadFile = File(...),
    project: str = Form(...),
    ctx: RequestContext = Depends(get_request_context),
):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="AI voice parsing is not configured. Type the note and use Draft form from note.")

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.exception("OpenAI SDK unavailable")
        raise HTTPException(status_code=503, detail="AI voice parser dependency is unavailable.") from exc

    context = configured_voice_context(project, ctx)
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
                    "schema": voice_item_schema(),
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


@app.get("/api/storage-status")
def storage_status(ctx: RequestContext = Depends(get_request_context)):
    require_storage_status_access(ctx.user)
    data = store.snapshot()
    response = {
        "requested_storage": os.getenv("CLEANRUN_STORAGE", "local"),
        "active_store": store.__class__.__name__,
        "environment": app_env(),
        "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
        "supabase_publishable_key_configured": bool(os.getenv("SUPABASE_PUBLISHABLE_KEY")),
        "auth_jwt_secret_configured": bool(os.getenv("SUPABASE_JWT_SECRET")),
        "requires_supabase": os.getenv("CLEANRUN_STORAGE", "").lower() == "supabase",
        "storage_bucket": os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence"),
        "item_count": len(data.items),
    }
    if not is_production():
        latest = data.items[0] if data.items else None
        response["latest_item_code"] = latest.code if latest else None
    return response


@app.get("/api/bootstrap")
def bootstrap(ctx: RequestContext = Depends(get_request_context)):
    data = store.snapshot()
    items = visible_items(ctx.user, data.items)
    return {
        "settings": scoped_settings(data.settings, ctx),
        "items": items,
        "trades": TRADES,
        "raised_by_options": RAISED_BY_OPTIONS,
        "user": {
            "id": ctx.user.id,
            "email": ctx.user.email,
            "company_role": ctx.user.company_role,
            "project_roles": ctx.user.project_roles,
        },
    }


@app.patch("/api/settings")
def update_settings(payload: SettingsPayload, ctx: RequestContext = Depends(get_request_context)):
    require_storage_status_access(ctx.user)
    data = store.snapshot()
    current = data.settings
    updates = payload.model_dump(exclude_unset=True)
    settings = Settings.model_validate({**current.model_dump(), **updates})
    return project_service.update_settings(store, settings)


@app.get("/api/items")
def list_items(
    project: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
):
    if project:
        require_report_access(ctx.user, project)
    return visible_items(ctx.user, item_service.list_items(store, project=project, status=status))


@app.get("/api/items/{item_id}")
def get_item(item_id: str, ctx: RequestContext = Depends(get_request_context)):
    return get_authorized_item(item_id, ctx)


@app.post("/api/items", status_code=201)
def create_item(payload: ItemCreate, issue_now: bool = Query(default=False), ctx: RequestContext = Depends(get_request_context)):
    require_create_item(ctx.user, payload.project)
    payload = payload.model_copy(update={"created_by": actor_label(ctx)})
    try:
        return item_service.create_item(store, payload, issue_now=issue_now, actor=actor_context(ctx))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.patch("/api/items/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, by: str | None = Query(default=None), ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_update_item(ctx.user, item)
    try:
        return item_service.update_item(store, item_id, payload, by=actor_label(ctx), actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/items/{item_id}/issue")
def issue_item(item_id: str, payload: IssuePayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_issue_item(ctx.user, item)
    try:
        return store.issue_item(item_id, to=payload.to, by=actor_label(ctx), note=payload.note, reissue=payload.reissue, actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/in-progress")
def mark_in_progress(item_id: str, payload: ActorPayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_rectification_access(ctx.user, item)
    try:
        return store.mark_in_progress(item_id, by=actor_label(ctx), actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/ready")
def mark_ready(item_id: str, payload: ActorPayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_rectification_access(ctx.user, item)
    try:
        return store.mark_ready(item_id, by=actor_label(ctx), actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/inspection/start")
def start_inspection(item_id: str, payload: ActorPayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_close_item(ctx.user, item)
    try:
        return store.start_inspection(item_id, by=actor_label(ctx), actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/inspection/reject")
def reject_item(item_id: str, payload: RejectPayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_close_item(ctx.user, item)
    try:
        return store.reject(item_id, by=actor_label(ctx), reason=payload.reason, actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/closeout")
def closeout_item(item_id: str, payload: CloseoutEvidence, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_close_item(ctx.user, item)
    payload = payload.model_copy(update={"by": actor_label(ctx)})
    try:
        return store.close_with_evidence(item_id, payload, actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/rectification")
def add_rectification(item_id: str, payload: RectificationPayload, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_rectification_access(ctx.user, item)
    try:
        evidence = RectificationEvidence(photo=payload.photo, comment=payload.comment, by=actor_label(ctx))
        return store.add_rectification(item_id, evidence, advance_to_ready=payload.advance_to_ready, actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/items/{item_id}/comments")
def add_comment(item_id: str, payload: Comment, ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_comment_access(ctx.user, item)
    payload = payload.model_copy(update={"by": actor_label(ctx)})
    try:
        return store.add_comment(item_id, payload, actor=actor_context(ctx))
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found")


@app.get("/api/reports/{report_type}", response_class=HTMLResponse)
def report_html(report_type: str, project: str | None = Query(default=None), ctx: RequestContext = Depends(get_request_context)):
    data = store.snapshot()
    project_name = project or data.settings.active_project
    require_report_access(ctx.user, project_name)
    items = [i for i in data.items if i.project == project_name]
    html = report_service.build_report(items, data.settings, report_type=report_type)
    return HTMLResponse(html)


@app.get("/api/reports/{report_type}/summary")
def report_summary(report_type: str, project: str | None = Query(default=None), ctx: RequestContext = Depends(get_request_context)):
    data = store.snapshot()
    project_name = project or data.settings.active_project
    require_report_access(ctx.user, project_name)
    items = report_service.report_items([i for i in data.items if i.project == project_name], report_type)
    return {
        "report_type": report_type,
        "project": project_name,
        "count": len(items),
        "closed": len([i for i in items if i.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]),
        "outstanding": len([i for i in items if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]),
    }


@app.post("/api/reset-demo")
def reset_demo(ctx: RequestContext = Depends(get_request_context)):
    require_demo_reset(ctx.user)
    return store.reset_demo()
