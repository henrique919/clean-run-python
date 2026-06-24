from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from threading import RLock
from typing import Callable

from app.models import (
    AppData,
    AuditEvent,
    CloseoutEvidence,
    Comment,
    InspectionEvent,
    IssueEvent,
    Item,
    ItemCreate,
    ItemStatus,
    ItemUpdate,
    ProjectConfig,
    RectificationEvidence,
    Settings,
    SubProfile,
    SyncState,
    CODE_PREFIX,
    now_iso,
)
from app.validation import validate_capture, validate_update

DATA_DIR = Path(os.getenv("CLEANRUN_DATA_DIR", ".cleanrun-data"))
DATA_FILE = DATA_DIR / "cleanrun.json"


def default_due(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def seed_settings() -> Settings:
    return Settings(
        projects=["Jura Noosa", "Meta Street"],
        active_project="Jura Noosa",
        company="qld Built",
        prepared_by="Site Team",
        project_configs={
            "Jura Noosa": ProjectConfig(
                name="Jura Noosa",
                address="79–83 Eumundi Noosa Rd, Noosaville",
                buildings=["B1", "B2", "B3", "B4", "B5", "B6", "B7"],
                levels=["Ground", "Level 1", "Level 2", "Roof"],
                units=["U101", "U102", "U201", "U202", "U301", "U302", "External"],
                rooms=["Kitchen", "Living", "Bathroom", "Ensuite", "Balcony", "Bedroom", "External"],
                default_due_days=7,
            ),
            "Meta Street": ProjectConfig(
                name="Meta Street",
                address="38 Meta Street, Mooloolaba",
                buildings=["Main Building"],
                levels=["Ground", "Level 1", "Level 2", "Level 3", "Roof"],
                units=["Unit 1", "Unit 2", "Unit 3", "External"],
                rooms=["Kitchen", "Living", "Bathroom", "Ensuite", "Balcony", "Stair", "External"],
                default_due_days=7,
            ),
        },
        subcontractors=["ASTW Tiling", "CLP Painting", "I-Inject Waterproofing", "H&L Roofing", "King Truss"],
        sub_profiles={
            "ASTW Tiling": SubProfile(name="ASTW Tiling", trade="Tiling"),
            "CLP Painting": SubProfile(name="CLP Painting", trade="Painting"),
            "I-Inject Waterproofing": SubProfile(name="I-Inject Waterproofing", trade="Waterproofing"),
            "H&L Roofing": SubProfile(name="H&L Roofing", trade="Roofing"),
            "King Truss": SubProfile(name="King Truss", trade="Carpentry"),
        },
    )


def seed_data() -> AppData:
    settings = seed_settings()
    now = now_iso()
    item = Item(
        id="seed-def-001",
        code="DEF-1001",
        type="defect",
        project="Jura Noosa",
        building="B3",
        level="Level 2",
        unit="U201",
        room="Bathroom",
        trade="Tiling",
        subcontractor="ASTW Tiling",
        priority="high",
        due_date=default_due(3),
        description="Cracked tile under vanity. Replace tile and regrout before client inspection.",
        original_photos=["seed://navy/cracked-tile"],
        created_by="Site Team",
        status="open",
        created_at=now,
        updated_at=now,
        audit_events=[AuditEvent(at=now, action="Created (DEF-1001)", by="Site Team")],
    )
    return AppData(items=[item], settings=settings)


class CleanRunStore:
    def __init__(self, path: Path = DATA_FILE) -> None:
        self.path = path
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(seed_data())

    def _read(self) -> AppData:
        with self.lock:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return AppData.model_validate(raw)

    def _write(self, data: AppData) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(data.model_dump_json(indent=2), encoding="utf-8")

    def snapshot(self) -> AppData:
        return self._read()

    def list_items(self, project: str | None = None, status: str | None = None) -> list[Item]:
        data = self._read()
        items = data.items
        if project:
            items = [i for i in items if i.project == project]
        if status:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda i: i.updated_at, reverse=True)

    def get_item(self, item_id: str) -> Item:
        item = next((i for i in self._read().items if i.id == item_id), None)
        if not item:
            raise KeyError(item_id)
        return item

    def next_code(self, items: list[Item], item_type: str) -> str:
        prefix = CODE_PREFIX[item_type]
        numbers: list[int] = []
        for item in items:
            if item.code.startswith(f"{prefix}-"):
                try:
                    numbers.append(int(item.code.split("-", 1)[1]))
                except ValueError:
                    pass
        return f"{prefix}-{(max(numbers) if numbers else 1000) + 1}"

    def create_item(self, payload: ItemCreate, *, issue_now: bool = False) -> Item:
        validate_capture(payload, for_issue=issue_now)
        data = self._read()
        now = now_iso()
        code = self.next_code(data.items, payload.type)
        payload_data = payload.model_dump(exclude={"status"})
        item = Item(
            **payload_data,
            code=code,
            status=ItemStatus.OPEN,
            created_at=now,
            updated_at=now,
            sync=SyncState.SYNCED,
            audit_events=[AuditEvent(at=now, action=f"Created ({code})", by=payload.created_by)],
        )
        if issue_now:
            item = self._issue_mutation(item, to=payload.subcontractor, by=payload.created_by)
        data.items.insert(0, item)
        self._write(data)
        return item

    def update_item(self, item_id: str, payload: ItemUpdate, *, by: str | None = None) -> Item:
        validate_update(payload)
        return self._patch(item_id, lambda item: self._update_mutation(item, payload, by=by))

    def issue_item(self, item_id: str, *, to: str, by: str | None = None, note: str | None = None, reissue: bool = False) -> Item:
        return self._patch(item_id, lambda item: self._issue_mutation(item, to=to, by=by, note=note, reissue=reissue))

    def mark_in_progress(self, item_id: str, *, by: str | None = None) -> Item:
        at = now_iso()
        return self._patch(item_id, lambda item: self._audit(item.model_copy(update={"status": ItemStatus.IN_PROGRESS, "in_progress_at": item.in_progress_at or at}), "Marked in progress", by=by, at=at))

    def mark_ready(self, item_id: str, *, by: str | None = None) -> Item:
        at = now_iso()
        return self._patch(item_id, lambda item: self._audit(item.model_copy(update={"status": ItemStatus.READY_FOR_REVIEW, "ready_for_review_at": at}), "Marked ready for review", by=by, at=at))

    def start_inspection(self, item_id: str, *, by: str) -> Item:
        at = now_iso()
        def mut(item: Item) -> Item:
            event = InspectionEvent(at=at, by=by, action="started")
            item = item.model_copy(update={"status": ItemStatus.UNDER_INSPECTION, "under_inspection_at": at, "inspection_history": [*item.inspection_history, event]})
            return self._audit(item, "Inspection started", by=by, at=at)
        return self._patch(item_id, mut)

    def reject(self, item_id: str, *, by: str, reason: str) -> Item:
        at = now_iso()
        def mut(item: Item) -> Item:
            event = InspectionEvent(at=at, by=by, action="rejected", reason=reason)
            item = item.model_copy(update={"status": ItemStatus.REJECTED, "rejection_reason": reason, "inspection_history": [*item.inspection_history, event]})
            return self._audit(item, "Rejected on inspection", by=by, note=reason, at=at)
        return self._patch(item_id, mut)

    def close_with_evidence(self, item_id: str, evidence: CloseoutEvidence) -> Item:
        at = now_iso()
        def mut(item: Item) -> Item:
            status = ItemStatus.COMPLETE if item.type == "incomplete" else ItemStatus.CLOSED
            history = item.inspection_history
            if item.status == ItemStatus.UNDER_INSPECTION:
                history = [*history, InspectionEvent(at=at, by=evidence.by, action="accepted")]
            item = item.model_copy(update={"status": status, "closed_at": at, "closeout_evidence": [*item.closeout_evidence, evidence], "inspection_history": history})
            return self._audit(item, "Closed with evidence", by=evidence.by, at=at)
        return self._patch(item_id, mut)

    def add_comment(self, item_id: str, comment: Comment) -> Item:
        return self._patch(item_id, lambda item: self._audit(item.model_copy(update={"comments": [*item.comments, comment]}), "Comment added", by=comment.by, note=comment.text, at=comment.at))

    def add_rectification(self, item_id: str, evidence: RectificationEvidence, *, advance_to_ready: bool = False) -> Item:
        def mut(item: Item) -> Item:
            status = ItemStatus.IN_PROGRESS if item.status == ItemStatus.ISSUED else item.status
            item = item.model_copy(update={"status": status, "rectification_evidence": [*item.rectification_evidence, evidence]})
            item = self._audit(item, "Rectification evidence added", by=evidence.by, note=evidence.comment, at=evidence.at)
            if advance_to_ready:
                item = item.model_copy(update={"status": ItemStatus.READY_FOR_REVIEW, "ready_for_review_at": now_iso()})
            return item
        return self._patch(item_id, mut)

    def reset_demo(self) -> AppData:
        data = seed_data()
        self._write(data)
        return data

    def _patch(self, item_id: str, mutator: Callable[[Item], Item]) -> Item:
        data = self._read()
        next_items: list[Item] = []
        changed: Item | None = None
        for item in data.items:
            if item.id == item_id:
                changed = mutator(item)
                changed.updated_at = now_iso()
                next_items.append(changed)
            else:
                next_items.append(item)
        if changed is None:
            raise KeyError(item_id)
        data.items = next_items
        self._write(data)
        return changed

    def _audit(self, item: Item, action: str, *, by: str | None = None, note: str | None = None, at: str | None = None) -> Item:
        event = AuditEvent(at=at or now_iso(), action=action, by=by, note=note)
        return item.model_copy(update={"audit_events": [*item.audit_events, event], "updated_at": event.at})

    def _update_mutation(self, item: Item, payload: ItemUpdate, *, by: str | None = None) -> Item:
        updates = payload.model_dump(exclude_unset=True)
        item = item.model_copy(update=updates)
        return self._audit(item, "Item details edited", by=by)

    def _issue_mutation(self, item: Item, *, to: str, by: str | None = None, note: str | None = None, reissue: bool = False) -> Item:
        at = now_iso()
        issue = IssueEvent(at=at, to=to, by=by, note=note, reissue=reissue)
        item = item.model_copy(update={"subcontractor": to or item.subcontractor, "status": ItemStatus.ISSUED, "issued_at": item.issued_at or at, "issue_history": [*item.issue_history, issue]})
        return self._audit(item, "Re-issued to " + to if reissue else "Issued to " + to, by=by, note=note, at=at)
