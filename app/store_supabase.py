from __future__ import annotations

from threading import RLock
from typing import Any

from app.models import AppData, Item, SyncState
from app.store import CleanRunStore, seed_data, seed_settings
from app.supabase_client import get_supabase_client


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _item_to_row(item: Item) -> dict[str, Any]:
    return {
        "id": item.id,
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
    """Supabase-backed store using a JSON payload for app-compatible items.

    This intentionally keeps the same public methods as CleanRunStore so the
    FastAPI routes and frontend do not need to change while the app moves from
    local JSON storage to a hosted database.
    """

    def __init__(self) -> None:
        self.lock = RLock()
        self.client = get_supabase_client()
        self._bootstrap_if_empty()

    def _bootstrap_if_empty(self) -> None:
        response = self.client.table("items").select("id").limit(1).execute()
        if not response.data:
            self._write(seed_data())

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

            return AppData(items=items, settings=seed_settings())

    def _write(self, data: AppData) -> None:
        with self.lock:
            current_response = self.client.table("items").select("id").execute()
            current_ids = {row["id"] for row in (current_response.data or []) if row.get("id")}
            next_ids = {item.id for item in data.items}

            for item in data.items:
                row = _item_to_row(item)
                self.client.table("items").upsert(row, on_conflict="id").execute()

            for stale_id in current_ids - next_ids:
                self.client.table("items").delete().eq("id", stale_id).execute()
