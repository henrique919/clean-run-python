from __future__ import annotations

import logging
from threading import RLock
from typing import Any

from app.models import AppData, Item, Settings, SyncState
from app.store import CleanRunStore, seed_data, seed_settings
from app.storage import normalize_photo
from app.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
SETTINGS_ID = "default"


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _with_storage_photos(item: Item) -> Item:
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


def _item_to_row(item: Item) -> dict[str, Any]:
    item = _with_storage_photos(item)
    return {
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
        "created_by": item.created_by,
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


class SupabaseCleanRunStore(CleanRunStore):
    """Supabase-backed store using item code plus a JSON payload."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.client = get_supabase_client()
        self._bootstrap_if_empty()

    def _bootstrap_if_empty(self) -> None:
        response = self.client.table("items").select("code").limit(1).execute()
        if not response.data:
            self._write(seed_data())
        self._ensure_settings()

    def _ensure_settings(self) -> None:
        try:
            response = self.client.table("app_settings").select("id").eq("id", SETTINGS_ID).limit(1).execute()
            if not response.data:
                self.update_settings(seed_settings())
        except Exception:
            logger.exception("Supabase settings table unavailable. Using seeded settings for this process.")

    def _read(self) -> AppData:
        with self.lock:
            response = (
                self.client
                .table("items")
                .select("payload, updated_at")
                .order("updated_at", desc=True)
                .execute()
            )
            items: list[Item] = []
            for row in response.data or []:
                payload = row.get("payload")
                if not payload:
                    continue
                item = Item.model_validate(payload)
                item.sync = SyncState.SYNCED
                items.append(item)

            return AppData(items=items, settings=self._read_settings())

    def _write(self, data: AppData) -> None:
        with self.lock:
            for item in data.items:
                row = _item_to_row(item)
                self.client.table("items").upsert(row, on_conflict="code").execute()

    def update_settings(self, settings: Settings) -> Settings:
        with self.lock:
            try:
                self.client.table("app_settings").upsert(
                    {"id": SETTINGS_ID, "payload": settings.model_dump(mode="json")},
                    on_conflict="id",
                ).execute()
            except Exception:
                logger.exception("Could not persist Supabase settings. Returning in-memory settings.")
        return settings

    def _read_settings(self) -> Settings:
        try:
            response = self.client.table("app_settings").select("payload").eq("id", SETTINGS_ID).limit(1).execute()
            payload = response.data[0].get("payload") if response.data else None
            if payload:
                return Settings.model_validate(payload)
        except Exception:
            logger.exception("Could not load Supabase settings. Falling back to seeded settings.")
        return seed_settings()
