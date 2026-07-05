from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Any, Callable
from uuid import UUID
from uuid import NAMESPACE_URL, uuid5

from app.models import (
    canonical_item_id,
    AccessRequest,
    AppData,
    AuditEvent,
    CloseoutEvidence,
    Comment,
    InspectionEvent,
    IssueEvent,
    Item,
    ItemCreate,
    ItemStatus,
    RectificationEvidence,
    Settings,
    SyncState,
    now_iso,
)
from app.config import is_production
from app.store import CleanRunStore, seed_data, seed_settings
from app.storage import normalize_photo, reset_upload_timing_ms, read_upload_timing_ms
from app.supabase_client import get_supabase_client
from app.validation import validate_capture

logger = logging.getLogger(__name__)
SETTINGS_ID = "default"
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
CREATE_CONTEXT_SELECT = (
    "id, code, type, project, building, level, unit, room, trade, subcontractor, "
    "due_date, description, created_by_label, created_at"
)
ITEM_ROW_SELECT = (
    "id, code, type, status, project, building, level, unit, room, trade, subcontractor, "
    "priority, due_date, description, raised_by, created_by_label, rejection_reason, "
    "issued_at, started_at, ready_at, inspected_at, closed_at, created_at, updated_at, payload"
)
UPLOAD_MAX_WORKERS = int(os.getenv("CLEANRUN_UPLOAD_MAX_WORKERS", "4"))


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _stable_uuid(*parts: Any) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(str(part) for part in parts if part is not None)))


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _item_db_id(item: Item) -> str:
    if _is_uuid(item.id):
        return str(item.id)
    return _stable_uuid("item", item.id or item.code)


def _child_db_id(kind: str, item_id: str, *parts: Any) -> str:
    key = parts[0] if parts else None
    if _is_uuid(key):
        return str(key)
    return _stable_uuid(kind, item_id, *parts)


def _first_id(response: Any) -> str | None:
    data = getattr(response, "data", None) or []
    return data[0].get("id") if data else None


def _storage_slug(value: str | None, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or fallback


def _storage_folder(item: Item, evidence_type: str) -> str:
    project = _storage_slug(item.project, "unknown-project")
    item_key = _storage_slug(item.code or item.id, "unassigned-item")
    return f"projects/{project}/items/{item_key}/{evidence_type}"


class SupabaseCleanRunStore(CleanRunStore):
    """Supabase-backed store using normalized relational tables.

    The items.payload column is written only as a legacy snapshot for migration
    and rollback support. New reads are assembled from normalized item and child
    tables.
    """

    def __init__(self) -> None:
        self.lock = RLock()
        if is_production():
            if os.getenv("CLEANRUN_BOOTSTRAP_SEED_DATA", "true").lower() in {"1", "true", "yes", "on"}:
                logger.info("Backfilling Supabase production bootstrap data.")
                self._backfill_seed_data()
            else:
                logger.info("Skipping Supabase startup seed in production; migrations/admin setup own bootstrap data.")
            return
        self._bootstrap_if_empty()

    @property
    def client(self):
        return get_supabase_client()

    def _bootstrap_if_empty(self) -> None:
        response = self.client.table("items").select("id").limit(1).execute()
        if not response.data:
            self._write(seed_data())
        self._ensure_settings()

    def _backfill_seed_data(self) -> None:
        data = seed_data()
        for item in data.items:
            self._upsert_item(item, data.settings)
        self._ensure_settings()

    def _ensure_settings(self) -> None:
        response = self.client.table("app_settings").select("id").eq("id", SETTINGS_ID).limit(1).execute()
        if not response.data:
            self.update_settings(seed_settings())

    def _read_code_index(self) -> list[Item]:
        rows = self.client.table("items").select("code, project").execute().data or []
        return [
            Item(
                code=row["code"],
                project=row.get("project") or "",
                due_date="",
                description="",
            )
            for row in rows
            if row.get("code")
        ]

    def _read_create_context(self) -> AppData:
        """Lightweight snapshot for code allocation and duplicate-create checks."""
        with self.lock:
            item_rows = (
                self.client.table("items")
                .select(CREATE_CONTEXT_SELECT)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
                .data
                or []
            )
            items = [self._item_stub_from_row(row) for row in item_rows]
            return AppData(items=items, settings=self._read_settings())

    def _item_stub_from_row(self, row: dict[str, Any]) -> Item:
        return Item(
            id=str(row["id"]),
            code=row["code"],
            type=row["type"],
            project=row.get("project") or "",
            building=row.get("building") or "",
            level=row.get("level") or "",
            unit=row.get("unit") or "",
            room=row.get("room") or "",
            trade=row.get("trade") or "",
            subcontractor=row.get("subcontractor") or "",
            due_date=str(row.get("due_date") or ""),
            description=row.get("description") or "",
            created_by=row.get("created_by_label"),
            created_at=row.get("created_at"),
        )

    def _read_item_by_id(self, item_id: str) -> Item | None:
        with self.lock:
            lookup_id = canonical_item_id(item_id) or item_id
            response = self.client.table("items").select(ITEM_ROW_SELECT).eq("id", lookup_id).limit(1).execute()
            if not response.data:
                return None
            row = response.data[0]
            db_item_id = str(row["id"])
            photos = self._children_by_item("item_photos", [db_item_id]).get(db_item_id, [])
            comments = self._children_by_item("item_comments", [db_item_id]).get(db_item_id, [])
            audit_events = self._children_by_item("item_audit_events", [db_item_id]).get(db_item_id, [])
            return self._item_from_rows(row, photos, comments, audit_events)

    def _read(self) -> AppData:
        with self.lock:
            item_rows = (
                self.client.table("items")
                .select(ITEM_ROW_SELECT)
                .order("updated_at", desc=True)
                .execute()
                .data
                or []
            )
            item_ids = [row["id"] for row in item_rows if row.get("id")]
            photos = self._children_by_item("item_photos", item_ids)
            comments = self._children_by_item("item_comments", item_ids)
            audit_events = self._children_by_item("item_audit_events", item_ids)

            items = [
                self._item_from_rows(
                    row,
                    photos.get(row["id"], []),
                    comments.get(row["id"], []),
                    audit_events.get(row["id"], []),
                )
                for row in item_rows
            ]
            return AppData(items=items, settings=self._read_settings())

    def _children_by_item(self, table: str, item_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not item_ids:
            return {}
        rows = (
            self.client.table(table)
            .select("*")
            .in_("item_id", item_ids)
            .order("created_at")
            .execute()
            .data
            or []
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["item_id"]].append(row)
        return {item_id: self._dedupe_child_rows(table, child_rows) for item_id, child_rows in grouped.items()}

    def _dedupe_child_rows(self, table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            if table == "item_photos":
                key = (
                    row.get("photo_type"),
                    row.get("storage_path") or row.get("photo"),
                    row.get("caption"),
                    row.get("created_by_label"),
                    row.get("created_at"),
                )
            elif table == "item_comments":
                key = (row.get("text"), row.get("created_by_label"), row.get("created_at"))
            elif table == "item_audit_events":
                key = (
                    row.get("message") or row.get("event_type"),
                    row.get("note"),
                    row.get("created_by_label"),
                    row.get("created_at"),
                )
            else:
                key = (row.get("id"),)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def _hydrate_issue_history(
        self,
        issue_history: list[IssueEvent],
        audit_rows: list[dict[str, Any]],
        row: dict[str, Any],
    ) -> list[IssueEvent]:
        if issue_history:
            return issue_history
        rebuilt: list[IssueEvent] = []
        for event in audit_rows:
            action = (event.get("message") or event.get("event_type") or "").strip()
            if action.startswith("Re-issued to "):
                rebuilt.append(
                    IssueEvent(
                        at=event.get("created_at"),
                        to=action[len("Re-issued to ") :],
                        by=event.get("created_by_label"),
                        note=event.get("note"),
                        reissue=True,
                    )
                )
            elif action.startswith("Issued to "):
                rebuilt.append(
                    IssueEvent(
                        at=event.get("created_at"),
                        to=action[len("Issued to ") :],
                        by=event.get("created_by_label"),
                        note=event.get("note"),
                        reissue=False,
                    )
                )
        if rebuilt:
            return rebuilt
        status = row.get("status")
        if status not in {ItemStatus.OPEN, ItemStatus.OPEN.value, None, ""} and row.get("issued_at"):
            return [
                IssueEvent(
                    at=row.get("issued_at"),
                    to=row.get("subcontractor") or "",
                    by=row.get("created_by_label"),
                    reissue=False,
                )
            ]
        return []


    def _item_from_rows(
        self,
        row: dict[str, Any],
        photo_rows: list[dict[str, Any]],
        comment_rows: list[dict[str, Any]],
        audit_rows: list[dict[str, Any]],
    ) -> Item:
        original_photos = [
            photo.get("storage_path") or photo.get("photo") or ""
            for photo in photo_rows
            if photo.get("photo_type") == "original"
        ]
        rectification_evidence = [
            RectificationEvidence(
                id=str(photo.get("id")),
                photo=photo.get("storage_path") or photo.get("photo"),
                comment=photo.get("caption"),
                by=photo.get("created_by_label") or "Unknown",
                at=photo.get("created_at"),
            )
            for photo in photo_rows
            if photo.get("photo_type") == "rectification"
        ]
        closeout_evidence = [
            CloseoutEvidence(
                id=str(photo.get("id")),
                photo=photo.get("storage_path") or photo.get("photo"),
                by=photo.get("created_by_label") or "Unknown",
                note=photo.get("caption"),
                at=photo.get("created_at"),
            )
            for photo in photo_rows
            if photo.get("photo_type") == "closeout"
        ]
        comments = [
            Comment(
                id=str(comment.get("id")),
                text=comment.get("text") or "",
                by=comment.get("created_by_label") or "Unknown",
                at=comment.get("created_at"),
            )
            for comment in comment_rows
        ]
        events = [
            AuditEvent(
                at=event.get("created_at"),
                action=event.get("message") or event.get("event_type") or "Audit event",
                by=event.get("created_by_label"),
                note=event.get("note"),
                user_id=event.get("created_by"),
                email=(event.get("context") or {}).get("email"),
                role=(event.get("context") or {}).get("role"),
                context=event.get("context") or {},
            )
            for event in audit_rows
        ]
        payload = row.get("payload") or {}
        issue_history = [
            IssueEvent.model_validate(event)
            for event in payload.get("issue_history", [])
            if isinstance(event, dict)
        ]
        issue_history = self._hydrate_issue_history(issue_history, audit_rows, row)
        inspection_history = [
            InspectionEvent.model_validate(event)
            for event in payload.get("inspection_history", [])
            if isinstance(event, dict)
        ]
        return Item(
            id=str(row["id"]),
            code=row["code"],
            type=row["type"],
            status=row["status"],
            project=row.get("project") or "",
            building=row.get("building") or "",
            level=row.get("level") or "",
            unit=row.get("unit") or "",
            room=row.get("room") or "",
            trade=row.get("trade") or "",
            subcontractor=row.get("subcontractor") or "",
            priority=row.get("priority") or "high",
            due_date=str(row.get("due_date") or ""),
            description=row.get("description") or "",
            raised_by=row.get("raised_by"),
            original_photos=original_photos,
            created_by=row.get("created_by_label"),
            rejection_reason=row.get("rejection_reason"),
            issued_at=row.get("issued_at"),
            in_progress_at=row.get("started_at"),
            ready_for_review_at=row.get("ready_at"),
            under_inspection_at=row.get("inspected_at"),
            closed_at=row.get("closed_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            rectification_evidence=rectification_evidence,
            closeout_evidence=closeout_evidence,
            comments=comments,
            audit_events=events,
            issue_history=issue_history,
            inspection_history=inspection_history,
            sync=SyncState.SYNCED,
        )

    def _write(self, data: AppData) -> None:
        with self.lock:
            for item in data.items:
                self._upsert_item(item, data.settings)

    def create_item(self, payload: ItemCreate, *, issue_now: bool = False, actor: dict[str, Any] | None = None) -> Item:
        validate_capture(payload, for_issue=issue_now)
        data = self._read_create_context()
        now = now_iso()
        duplicate = self._recent_duplicate(data.items, payload, now)
        if duplicate:
            return duplicate
        code = self.next_code(self._read_code_index(), payload.type, project=payload.project, settings=data.settings)
        payload_data = payload.model_dump(exclude={"status"})
        item = Item(
            **payload_data,
            code=code,
            status=ItemStatus.OPEN,
            created_at=now,
            updated_at=now,
            sync=SyncState.SYNCED,
        )
        item = self._audit(item, f"Created ({code})", by=payload.created_by, at=now, actor=actor)
        if issue_now:
            item = self._issue_mutation(item, to=payload.subcontractor, by=payload.created_by, actor=actor)
        with self.lock:
            db_item_id = self._upsert_item(item, data.settings)
        return item.model_copy(update={"id": canonical_item_id(db_item_id)})

    def _patch(self, item_id: str, mutator: Callable[[Item], Item]) -> Item:
        settings = self._read_settings()
        item = self._read_item_by_id(item_id)
        if item is None:
            raise KeyError(item_id)
        changed = mutator(item)
        changed.updated_at = now_iso()
        with self.lock:
            self._upsert_item(changed, settings)
        return changed

    def _upsert_item(self, item: Item, settings: Settings) -> str:
        company_id = self._ensure_company(settings.company)
        project_id = self._ensure_project(company_id, item.project, settings)
        location_id = self._ensure_location(company_id, project_id, item)
        subcontractor_id = self._ensure_subcontractor(company_id, project_id, item)
        db_item_id = _item_db_id(item)
        reset_upload_timing_ms()
        normalize_started = time.perf_counter()
        item = self._with_storage_photos(item)
        normalize_total_ms = (time.perf_counter() - normalize_started) * 1000
        storage_upload_ms = read_upload_timing_ms()
        normalize_photos_ms = max(normalize_total_ms - storage_upload_ms, 0.0)
        row = {
            "id": db_item_id,
            "company_id": company_id,
            "project_id": project_id,
            "location_id": location_id,
            "subcontractor_id": subcontractor_id,
            "code": item.code,
            "type": _enum_value(item.type),
            "status": _enum_value(item.status),
            "project": item.project,
            "building": item.building,
            "level": item.level,
            "unit": item.unit,
            "room": item.room,
            "trade": item.trade,
            "subcontractor": item.subcontractor,
            "priority": _enum_value(item.priority),
            "due_date": item.due_date or None,
            "description": item.description,
            "raised_by": item.raised_by,
            "created_by_label": item.created_by,
            "rejection_reason": item.rejection_reason,
            "issued_at": item.issued_at,
            "started_at": item.in_progress_at,
            "ready_at": item.ready_for_review_at,
            "inspected_at": item.under_inspection_at,
            "closed_at": item.closed_at,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "payload": item.model_dump(mode="json"),
        }
        db_started = time.perf_counter()
        self.client.table("items").upsert(row, on_conflict="id").execute()
        db_upsert_ms = (time.perf_counter() - db_started) * 1000
        sync_started = time.perf_counter()
        self._sync_item_photos(company_id, project_id, db_item_id, item)
        sync_photos_ms = (time.perf_counter() - sync_started) * 1000
        logger.info(
            "item_upsert_timing item_id=%s normalize_photos=%.1fms storage_upload=%.1fms db_upsert=%.1fms sync_photos=%.1fms",
            db_item_id,
            normalize_photos_ms,
            storage_upload_ms,
            db_upsert_ms,
            sync_photos_ms,
        )
        self._upsert_comments(company_id, project_id, db_item_id, item)
        self._upsert_audit_events(company_id, project_id, db_item_id, item)
        return db_item_id

    def _normalize_photos_parallel(self, photos: list[str], *, folder: str) -> list[str | None]:
        if not photos:
            return []
        if len(photos) == 1:
            return [normalize_photo(photos[0], folder=folder)]
        workers = min(UPLOAD_MAX_WORKERS, len(photos))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda photo: normalize_photo(photo, folder=folder), photos))

    def _with_storage_photos(self, item: Item) -> Item:
        original_photos = self._normalize_photos_parallel(
            item.original_photos,
            folder=_storage_folder(item, "original"),
        )
        rect_folder = _storage_folder(item, "rectification")
        rect_photos = self._normalize_photos_parallel(
            [evidence.photo for evidence in item.rectification_evidence],
            folder=rect_folder,
        )
        rectification_evidence = [
            evidence.model_copy(update={"photo": photo})
            for evidence, photo in zip(item.rectification_evidence, rect_photos, strict=True)
        ]
        close_folder = _storage_folder(item, "closeout")
        close_photos = self._normalize_photos_parallel(
            [evidence.photo for evidence in item.closeout_evidence],
            folder=close_folder,
        )
        closeout_evidence = [
            evidence.model_copy(update={"photo": photo})
            for evidence, photo in zip(item.closeout_evidence, close_photos, strict=True)
        ]
        return item.model_copy(
            update={
                "original_photos": original_photos,
                "rectification_evidence": rectification_evidence,
                "closeout_evidence": closeout_evidence,
            }
        )

    def _ensure_company(self, name: str) -> str:
        configured_id = os.getenv("CLEANRUN_COMPANY_ID")
        if configured_id:
            return configured_id
        company_id = DEFAULT_COMPANY_ID
        self.client.table("companies").upsert({"id": company_id, "name": name or "CleanRun Demo"}, on_conflict="id").execute()
        return company_id

    def _ensure_project(self, company_id: str, project_name: str, settings: Settings) -> str:
        project_id = _stable_uuid("project", company_id, project_name)
        config = settings.project_configs.get(project_name)
        self.client.table("projects").upsert(
            {
                "id": project_id,
                "company_id": company_id,
                "name": project_name,
                "address": config.address if config else None,
            },
            on_conflict="id",
        ).execute()
        return project_id

    def _ensure_location(self, company_id: str, project_id: str, item: Item) -> str:
        location_id = _stable_uuid("location", project_id, item.building, item.level, item.unit, item.room)
        label = " - ".join(part for part in [item.building, item.level, item.unit, item.room] if part)
        self.client.table("locations").upsert(
            {
                "id": location_id,
                "company_id": company_id,
                "project_id": project_id,
                "building": item.building or "",
                "level": item.level or "",
                "unit": item.unit or "",
                "room": item.room or "",
                "label": label,
            },
            on_conflict="id",
        ).execute()
        return location_id

    def _ensure_subcontractor(self, company_id: str, project_id: str, item: Item) -> str | None:
        if not item.subcontractor:
            return None
        subcontractor_id = _stable_uuid("subcontractor", project_id, item.subcontractor)
        self.client.table("subcontractors").upsert(
            {
                "id": subcontractor_id,
                "company_id": company_id,
                "project_id": project_id,
                "name": item.subcontractor,
                "trade": item.trade or None,
            },
            on_conflict="id",
        ).execute()
        self.client.table("project_subcontractors").upsert(
            {
                "project_id": project_id,
                "subcontractor_id": subcontractor_id,
                "trade": item.trade or None,
            },
            on_conflict="project_id,subcontractor_id",
        ).execute()
        return subcontractor_id

    def _insert_missing_child_rows(self, table: str, rows: list[dict[str, Any]], *, item_id: str) -> None:
        if not rows:
            return
        row_ids = [str(row["id"]) for row in rows if row.get("id")]
        existing_ids: set[str] = set()
        if row_ids:
            response = self.client.table(table).select("id").eq("item_id", item_id).in_("id", row_ids).execute()
            existing_ids = {str(row["id"]) for row in (response.data or [])}
        missing_rows = [row for row in rows if str(row.get("id")) not in existing_ids]
        if missing_rows:
            self.client.table(table).insert(missing_rows).execute()

    def _sync_item_photos(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        rows: list[dict[str, Any]] = []
        for index, photo in enumerate(item.original_photos):
            rows.append(
                self._photo_row(
                    company_id,
                    project_id,
                    item_id,
                    "original",
                    photo,
                    index,
                    item.created_by,
                    at=item.created_at,
                )
            )
        for index, evidence in enumerate(item.rectification_evidence):
            rows.append(
                self._photo_row(
                    company_id,
                    project_id,
                    item_id,
                    "rectification",
                    evidence.photo,
                    evidence.id or index,
                    evidence.by,
                    evidence.comment,
                    evidence.at,
                )
            )
        for index, evidence in enumerate(item.closeout_evidence):
            rows.append(
                self._photo_row(
                    company_id,
                    project_id,
                    item_id,
                    "closeout",
                    evidence.photo,
                    evidence.id or index,
                    evidence.by,
                    evidence.note,
                    evidence.at,
                )
            )
        original_ids = {str(row["id"]) for row in rows if row["photo_type"] == "original"}
        existing_originals = (
            self.client.table("item_photos")
            .select("id")
            .eq("item_id", item_id)
            .eq("photo_type", "original")
            .execute()
            .data
            or []
        )
        for row in existing_originals:
            if str(row["id"]) not in original_ids:
                self.client.table("item_photos").delete().eq("id", row["id"]).execute()
        if rows:
            self.client.table("item_photos").upsert(rows, on_conflict="id").execute()

    def _upsert_item_photos(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        self._sync_item_photos(company_id, project_id, item_id, item)

    def _photo_row(
        self,
        company_id: str,
        project_id: str,
        item_id: str,
        photo_type: str,
        photo: str | None,
        key: Any,
        by: str | None = None,
        caption: str | None = None,
        at: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": _child_db_id("photo", item_id, key, photo_type),
            "company_id": company_id,
            "project_id": project_id,
            "item_id": item_id,
            "photo_type": photo_type,
            "storage_path": photo if photo and not str(photo).startswith("data:") else None,
            "photo": photo if photo and str(photo).startswith("data:") else None,
            "caption": caption,
            "created_by_label": by,
            "created_at": at or now_iso(),
        }
        return row

    def _upsert_comments(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        rows = [
            {
                "id": _child_db_id("comment", item_id, comment.id or index),
                "company_id": company_id,
                "project_id": project_id,
                "item_id": item_id,
                "text": comment.text,
                "created_by_label": comment.by,
                "created_at": comment.at,
            }
            for index, comment in enumerate(item.comments)
        ]
        self._insert_missing_child_rows("item_comments", rows, item_id=item_id)

    def _upsert_audit_events(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        rows = [
            {
                "id": _stable_uuid("audit", item_id, event.at, event.action, index),
                "company_id": company_id,
                "project_id": project_id,
                "item_id": item_id,
                "event_type": event.action,
                "message": event.action,
                "note": event.note,
                "created_by_label": event.by,
                "context": event.context or {},
                "created_at": event.at,
            }
            for index, event in enumerate(item.audit_events)
        ]
        self._insert_missing_child_rows("item_audit_events", rows, item_id=item_id)

    def update_settings(self, settings: Settings) -> Settings:
        with self.lock:
            company_id = self._ensure_company(settings.company)
            self.client.table("app_settings").upsert(
                {
                    "id": SETTINGS_ID,
                    "company_id": company_id,
                    "payload": settings.model_dump(mode="json"),
                },
                on_conflict="id",
            ).execute()
        return settings

    def create_access_request(self, payload: AccessRequest) -> AccessRequest:
        self.client.rpc(
            "submit_access_request",
            {
                "p_id": payload.id,
                "p_full_name": payload.full_name,
                "p_email": payload.email,
                "p_company": payload.company,
                "p_role_requested": payload.role_requested,
                "p_project_site": payload.project_site,
                "p_message": payload.message,
            },
        ).execute()
        return payload

    def _read_settings(self) -> Settings:
        response = self.client.table("app_settings").select("payload").eq("id", SETTINGS_ID).limit(1).execute()
        payload = response.data[0].get("payload") if response.data else None
        if payload:
            return Settings.model_validate(payload)
        return seed_settings()
