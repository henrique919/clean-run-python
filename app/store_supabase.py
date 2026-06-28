from __future__ import annotations

import logging
import os
from collections import defaultdict
from threading import RLock
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.models import (
    AccessRequest,
    AppData,
    AuditEvent,
    CloseoutEvidence,
    Comment,
    Item,
    RectificationEvidence,
    Settings,
    SyncState,
)
from app.config import is_production
from app.store import CleanRunStore, seed_data, seed_settings
from app.storage import normalize_photo
from app.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
SETTINGS_ID = "default"
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _stable_uuid(*parts: Any) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(str(part) for part in parts if part is not None)))


def _first_id(response: Any) -> str | None:
    data = getattr(response, "data", None) or []
    return data[0].get("id") if data else None


class SupabaseCleanRunStore(CleanRunStore):
    """Supabase-backed store using normalized relational tables.

    The items.payload column is written only as a legacy snapshot for migration
    and rollback support. New reads are assembled from normalized item and child
    tables.
    """

    def __init__(self) -> None:
        self.lock = RLock()
        if is_production():
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

    def _ensure_settings(self) -> None:
        response = self.client.table("app_settings").select("id").eq("id", SETTINGS_ID).limit(1).execute()
        if not response.data:
            self.update_settings(seed_settings())

    def _read(self) -> AppData:
        with self.lock:
            item_rows = (
                self.client.table("items")
                .select(
                    "id, code, type, status, project, building, level, unit, room, trade, subcontractor, "
                    "priority, due_date, description, raised_by, created_by_label, rejection_reason, "
                    "issued_at, started_at, ready_at, inspected_at, closed_at, created_at, updated_at"
                )
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
        return grouped

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
            sync=SyncState.SYNCED,
        )

    def _write(self, data: AppData) -> None:
        with self.lock:
            for item in data.items:
                self._upsert_item(item, data.settings)

    def _upsert_item(self, item: Item, settings: Settings) -> str:
        company_id = self._ensure_company(settings.company)
        project_id = self._ensure_project(company_id, item.project, settings)
        location_id = self._ensure_location(company_id, project_id, item)
        subcontractor_id = self._ensure_subcontractor(company_id, project_id, item)
        db_item_id = _stable_uuid("item", item.id or item.code)
        item = self._with_storage_photos(item)
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
        self.client.table("items").upsert(row, on_conflict="id").execute()
        self._upsert_item_photos(company_id, project_id, db_item_id, item)
        self._upsert_comments(company_id, project_id, db_item_id, item)
        self._upsert_audit_events(company_id, project_id, db_item_id, item)
        return db_item_id

    def _with_storage_photos(self, item: Item) -> Item:
        original_photos = [normalize_photo(photo, folder="original") for photo in item.original_photos]
        rectification_evidence = [
            evidence.model_copy(update={"photo": normalize_photo(evidence.photo, folder="rectification")})
            for evidence in item.rectification_evidence
        ]
        closeout_evidence = [
            evidence.model_copy(update={"photo": normalize_photo(evidence.photo, folder="closeout")})
            for evidence in item.closeout_evidence
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

    def _upsert_item_photos(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        rows: list[dict[str, Any]] = []
        for index, photo in enumerate(item.original_photos):
            rows.append(self._photo_row(company_id, project_id, item_id, "original", photo, index, item.created_by))
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
        if rows:
            self.client.table("item_photos").upsert(rows, on_conflict="id").execute()

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
            "id": _stable_uuid("photo", item_id, photo_type, key),
            "company_id": company_id,
            "project_id": project_id,
            "item_id": item_id,
            "photo_type": photo_type,
            "storage_path": photo if photo and not str(photo).startswith("data:") else None,
            "photo": photo if photo and str(photo).startswith("data:") else None,
            "caption": caption,
            "created_by_label": by,
            "created_at": at,
        }
        if row["created_at"] is None:
            row.pop("created_at")
        return row

    def _upsert_comments(self, company_id: str, project_id: str, item_id: str, item: Item) -> None:
        rows = [
            {
                "id": _stable_uuid("comment", item_id, comment.id or index),
                "company_id": company_id,
                "project_id": project_id,
                "item_id": item_id,
                "text": comment.text,
                "created_by_label": comment.by,
                "created_at": comment.at,
            }
            for index, comment in enumerate(item.comments)
        ]
        if rows:
            self.client.table("item_comments").upsert(rows, on_conflict="id").execute()

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
        if rows:
            self.client.table("item_audit_events").upsert(rows, on_conflict="id").execute()

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
