from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import RequestContext, get_request_context, is_production
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
            logger.exception("Supabase storage unavailable.")
            strict = os.getenv("CLEANRUN_REQUIRE_SUPABASE", "").lower() in {"1", "true", "yes"}
            production = os.getenv("CLEANRUN_ENV", "development").lower() == "production"
            if strict or production:
                raise
            logger.warning("Falling back to local JSON storage because CLEANRUN_REQUIRE_SUPABASE is not enabled.")
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
        item = store.get_item(item_id)
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
def storage_status(ctx: RequestContext = Depends(get_request_context)):
    require_storage_status_access(ctx.user)
    data = store.snapshot()
    latest = data.items[0] if data.items else None
    latest_photo = None
    if latest and latest.original_photos:
        latest_photo = latest.original_photos[0]
    return {
        "requested_storage": os.getenv("CLEANRUN_STORAGE", "local"),
        "active_store": store.__class__.__name__,
        "supabase_url_configured": bool(os.getenv("SUPABASE_URL")),
        "supabase_publishable_key_configured": bool(os.getenv("SUPABASE_PUBLISHABLE_KEY")),
        "service_role_key_present": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        "requires_supabase": os.getenv("CLEANRUN_REQUIRE_SUPABASE", "").lower() in {"1", "true", "yes"},
        "storage_bucket": os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence"),
        "item_count": len(data.items),
        "latest_item_code": latest.code if latest else None,
        "latest_item_description": latest.description if latest else None,
        "latest_photo_type": "storage_url" if latest_photo and str(latest_photo).startswith("http") else "base64_or_empty" if latest_photo else "none",
        "latest_photo_preview": str(latest_photo)[:80] if latest_photo else None,
    }


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
    return store.update_settings(settings)


@app.get("/api/items")
def list_items(
    project: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: RequestContext = Depends(get_request_context),
):
    if project:
        require_report_access(ctx.user, project)
    return visible_items(ctx.user, store.list_items(project=project, status=status))


@app.get("/api/items/{item_id}")
def get_item(item_id: str, ctx: RequestContext = Depends(get_request_context)):
    return get_authorized_item(item_id, ctx)


@app.post("/api/items", status_code=201)
def create_item(payload: ItemCreate, issue_now: bool = Query(default=False), ctx: RequestContext = Depends(get_request_context)):
    require_create_item(ctx.user, payload.project)
    payload = payload.model_copy(update={"created_by": actor_label(ctx)})
    try:
        return store.create_item(payload, issue_now=issue_now, actor=actor_context(ctx))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.patch("/api/items/{item_id}")
def update_item(item_id: str, payload: ItemUpdate, by: str | None = Query(default=None), ctx: RequestContext = Depends(get_request_context)):
    item = get_authorized_item(item_id, ctx)
    require_update_item(ctx.user, item)
    try:
        return store.update_item(item_id, payload, by=actor_label(ctx), actor=actor_context(ctx))
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
    html = build_report_html(items, data.settings, report_type=report_type)
    return HTMLResponse(html)


@app.get("/api/reports/{report_type}/summary")
def report_summary(report_type: str, project: str | None = Query(default=None), ctx: RequestContext = Depends(get_request_context)):
    data = store.snapshot()
    project_name = project or data.settings.active_project
    require_report_access(ctx.user, project_name)
    items = filter_items([i for i in data.items if i.project == project_name], report_type)
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
