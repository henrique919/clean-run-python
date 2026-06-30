from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from app.models import (
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
    ItemUpdate,
    ItemType,
    ProjectConfig,
    RectificationEvidence,
    Settings,
    SubProfile,
    SyncState,
    CODE_PREFIX,
    now_iso,
)
from app.validation import (
    validate_capture,
    validate_closeout,
    validate_issue_target,
    validate_ready_for_review,
    validate_rectification,
    validate_reject_reason,
    validate_update_merged,
)
from app.workflow import (
    CLOSE_FROM,
    IN_PROGRESS_FROM,
    INSPECTION_FROM,
    ISSUE_FROM,
    REJECT_FROM,
    RECTIFICATION_FROM,
    READY_FROM,
    require_status,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("CLEANRUN_DATA_DIR", ".cleanrun-data"))
DATA_FILE = DATA_DIR / "cleanrun.json"
DUPLICATE_CREATE_WINDOW_SECONDS = int(os.getenv("CLEANRUN_DUPLICATE_CREATE_WINDOW_SECONDS", "300"))
SNAPSHOT_SEED_FILES = (
    Path(os.getenv("CLEANRUN_SEED_SNAPSHOT", "")) if os.getenv("CLEANRUN_SEED_SNAPSHOT") else None,
    REPO_ROOT / "cleanrun_data.json",
)


def _snake_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rename = {
        "dueDate": "due_date",
        "originalPhotos": "original_photos",
        "voiceTranscript": "voice_transcript",
        "voiceNote": "voice_note",
        "createdBy": "created_by",
        "createdAt": "created_at",
        "updatedAt": "updated_at",
        "rectificationEvidence": "rectification_evidence",
        "closeoutEvidence": "closeout_evidence",
        "issueHistory": "issue_history",
        "inspectionHistory": "inspection_history",
        "auditEvents": "audit_events",
        "issuedAt": "issued_at",
        "inProgressAt": "in_progress_at",
        "readyForReviewAt": "ready_for_review_at",
        "underInspectionAt": "under_inspection_at",
        "closedAt": "closed_at",
        "rejectionReason": "rejection_reason",
        "raisedBy": "raised_by",
    }
    result = dict(payload)
    for source, target in rename.items():
        if source in result:
            result[target] = result.pop(source)
    return result


def _snake_settings_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    if "activeProject" in result:
        result["active_project"] = result.pop("activeProject")
    if "projectConfigs" in result:
        result["project_configs"] = result.pop("projectConfigs")
    if "subProfiles" in result:
        result["sub_profiles"] = result.pop("subProfiles")
    if "preparedBy" in result:
        result["prepared_by"] = result.pop("preparedBy")

    configs = result.get("project_configs")
    if isinstance(configs, dict):
        for config in configs.values():
            if isinstance(config, dict):
                if "defaultDueDays" in config:
                    config["default_due_days"] = config.pop("defaultDueDays")
                if "preferredItemsView" in config:
                    config["preferred_items_view"] = config.pop("preferredItemsView")
                if "codePrefix" in config:
                    config["code_prefix"] = config.pop("codePrefix")
                if "codePrefixLocked" in config:
                    config["code_prefix_locked"] = config.pop("codePrefixLocked")
                if "codePrefixHiddenOnCards" in config:
                    config["code_prefix_hidden_on_cards"] = config.pop("codePrefixHiddenOnCards")
    return result


def _normalize_app_data_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["items"] = [_snake_item_payload(item) for item in result.get("items", [])]
    if isinstance(result.get("settings"), dict):
        result["settings"] = _snake_settings_payload(result["settings"])
    return result


def default_due(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _normalized_value(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip().lower()


def _capture_fingerprint(payload: ItemCreate | Item) -> tuple[str, ...]:
    return (
        _normalized_value(payload.type),
        _normalized_value(payload.project),
        _normalized_value(payload.building),
        _normalized_value(payload.level),
        _normalized_value(payload.unit),
        _normalized_value(payload.room),
        _normalized_value(payload.trade),
        _normalized_value(payload.subcontractor),
        _normalized_value(payload.due_date),
        _normalized_value(payload.description),
        _normalized_value(payload.created_by),
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
    for path in SNAPSHOT_SEED_FILES:
        if path and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return AppData.model_validate(_normalize_app_data_payload(payload))

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
            payload = data.model_dump_json(indent=2)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as temp:
                temp.write(payload)
                temp_path = Path(temp.name)
            temp_path.replace(self.path)

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

    def next_code(self, items: list[Item], item_type: str, *, project: str | None = None, settings: Settings | None = None) -> str:
        type_prefix = CODE_PREFIX[ItemType(item_type)]
        project_prefix = ""
        if project and settings:
            cfg = settings.project_configs.get(project)
            if cfg and cfg.code_prefix_locked and cfg.code_prefix:
                project_prefix = cfg.code_prefix
        code_stem = f"{project_prefix}-{type_prefix}" if project_prefix else type_prefix
        numbers: list[int] = []
        for item in items:
            if project_prefix and item.project != project:
                continue
            if item.code.startswith(f"{code_stem}-"):
                try:
                    numbers.append(int(item.code.rsplit("-", 1)[1]))
                except ValueError:
                    pass
        return f"{code_stem}-{(max(numbers) if numbers else 1000) + 1}"

    def create_item(self, payload: ItemCreate, *, issue_now: bool = False, actor: dict[str, Any] | None = None) -> Item:
        validate_capture(payload, for_issue=issue_now)
        data = self._read()
        now = now_iso()
        duplicate = self._recent_duplicate(data.items, payload, now)
        if duplicate:
            return duplicate
        code = self.next_code(data.items, payload.type, project=payload.project, settings=data.settings)
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
        data.items.insert(0, item)
        self._write(data)
        return item

    def _recent_duplicate(self, items: list[Item], payload: ItemCreate, now: str) -> Item | None:
        if DUPLICATE_CREATE_WINDOW_SECONDS <= 0:
            return None
        now_at = _parse_iso_datetime(now)
        if not now_at:
            return None
        fingerprint = _capture_fingerprint(payload)
        for item in sorted(items, key=lambda current: current.created_at, reverse=True):
            created_at = _parse_iso_datetime(item.created_at)
            if not created_at:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if now_at.tzinfo is None:
                now_at = now_at.replace(tzinfo=timezone.utc)
            if (now_at - created_at).total_seconds() > DUPLICATE_CREATE_WINDOW_SECONDS:
                continue
            if _capture_fingerprint(item) == fingerprint:
                return item
        return None

    def update_item(self, item_id: str, payload: ItemUpdate, *, by: str | None = None, actor: dict[str, Any] | None = None) -> Item:
        def mut(item: Item) -> Item:
            validate_update_merged(item, payload)
            return self._update_mutation(item, payload, by=by, actor=actor)

        return self._patch(item_id, mut)

    def issue_item(self, item_id: str, *, to: str, by: str | None = None, note: str | None = None, reissue: bool = False, actor: dict[str, Any] | None = None) -> Item:
        def mut(item: Item) -> Item:
            require_status(item, ISSUE_FROM, action="issue")
            validate_issue_target(to=to, item=item)
            return self._issue_mutation(item, to=to, by=by, note=note, reissue=reissue, actor=actor)

        return self._patch(item_id, mut)

    def mark_in_progress(self, item_id: str, *, by: str | None = None, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()

        def mut(item: Item) -> Item:
            require_status(item, IN_PROGRESS_FROM, action="mark in progress")
            return self._audit(item.model_copy(update={"status": ItemStatus.IN_PROGRESS, "in_progress_at": item.in_progress_at or at}), "Marked in progress", by=by, at=at, actor=actor)

        return self._patch(item_id, mut)

    def mark_ready(self, item_id: str, *, by: str | None = None, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()

        def mut(item: Item) -> Item:
            require_status(item, READY_FROM, action="mark ready for review")
            validate_ready_for_review(item)
            return self._audit(item.model_copy(update={"status": ItemStatus.READY_FOR_REVIEW, "ready_for_review_at": at}), "Marked ready for review", by=by, at=at, actor=actor)

        return self._patch(item_id, mut)

    def start_inspection(self, item_id: str, *, by: str, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()

        def mut(item: Item) -> Item:
            require_status(item, INSPECTION_FROM, action="start inspection")
            event = InspectionEvent(at=at, by=by, action="started")
            item = item.model_copy(update={"status": ItemStatus.UNDER_INSPECTION, "under_inspection_at": at, "inspection_history": [*item.inspection_history, event]})
            return self._audit(item, "Inspection started", by=by, at=at, actor=actor)

        return self._patch(item_id, mut)

    def reject(self, item_id: str, *, by: str, reason: str, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()

        def mut(item: Item) -> Item:
            require_status(item, REJECT_FROM, action="reject")
            validate_reject_reason(reason)
            event = InspectionEvent(at=at, by=by, action="rejected", reason=reason)
            item = item.model_copy(update={"status": ItemStatus.REJECTED, "rejection_reason": reason, "inspection_history": [*item.inspection_history, event]})
            return self._audit(item, "Rejected on inspection", by=by, note=reason, at=at, actor=actor)

        return self._patch(item_id, mut)

    def close_with_evidence(self, item_id: str, evidence: CloseoutEvidence, *, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()

        def mut(item: Item) -> Item:
            require_status(item, CLOSE_FROM, action="close out")
            validate_closeout(item, evidence)
            status = ItemStatus.COMPLETE if item.type == "incomplete" else ItemStatus.CLOSED
            history = item.inspection_history
            if item.status == ItemStatus.UNDER_INSPECTION:
                history = [*history, InspectionEvent(at=at, by=evidence.by, action="accepted")]
            item = item.model_copy(update={"status": status, "closed_at": at, "closeout_evidence": [*item.closeout_evidence, evidence], "inspection_history": history})
            return self._audit(item, "Closed with evidence", by=evidence.by, at=at, actor=actor)

        return self._patch(item_id, mut)

    def add_comment(self, item_id: str, comment: Comment, *, actor: dict[str, Any] | None = None) -> Item:
        return self._patch(item_id, lambda item: self._audit(item.model_copy(update={"comments": [*item.comments, comment]}), "Comment added", by=comment.by, note=comment.text, at=comment.at, actor=actor))

    def add_rectification(self, item_id: str, evidence: RectificationEvidence, *, advance_to_ready: bool = False, actor: dict[str, Any] | None = None) -> Item:
        validate_rectification(evidence)

        def mut(item: Item) -> Item:
            require_status(item, RECTIFICATION_FROM, action="add rectification")
            status = ItemStatus.IN_PROGRESS if item.status in {ItemStatus.ISSUED, ItemStatus.REJECTED} else item.status
            item = item.model_copy(update={"status": status, "rectification_evidence": [*item.rectification_evidence, evidence]})
            item = self._audit(item, "Rectification evidence added", by=evidence.by, note=evidence.comment, at=evidence.at, actor=actor)
            if advance_to_ready:
                require_status(item, READY_FROM, action="mark ready for review")
                validate_ready_for_review(item)
                item = item.model_copy(update={"status": ItemStatus.READY_FOR_REVIEW, "ready_for_review_at": now_iso()})
            return item

        return self._patch(item_id, mut)

    def reset_demo(self) -> AppData:
        data = seed_data()
        self._write(data)
        return data

    def update_settings(self, settings: Settings) -> Settings:
        data = self._read()
        data.settings = settings
        self._write(data)
        return data.settings

    def create_access_request(self, payload: AccessRequest) -> AccessRequest:
        data = self._read()
        data.access_requests.insert(0, payload)
        self._write(data)
        return payload

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

    def _audit(self, item: Item, action: str, *, by: str | None = None, note: str | None = None, at: str | None = None, actor: dict[str, Any] | None = None) -> Item:
        event = AuditEvent(
            at=at or now_iso(),
            action=action,
            by=by,
            note=note,
            user_id=actor.get("id") if actor else None,
            email=actor.get("email") if actor else (by if by and "@" in by else None),
            role=actor.get("role") if actor else None,
            context=actor,
        )
        return item.model_copy(update={"audit_events": [*item.audit_events, event], "updated_at": event.at})

    def _update_mutation(self, item: Item, payload: ItemUpdate, *, by: str | None = None, actor: dict[str, Any] | None = None) -> Item:
        updates = payload.model_dump(exclude_unset=True)
        append_photos = updates.pop("append_original_photos", None)
        if append_photos:
            updates["original_photos"] = [*item.original_photos, *append_photos]
        item = item.model_copy(update=updates)
        return self._audit(item, "Item details edited", by=by, actor=actor)

    def _issue_mutation(self, item: Item, *, to: str, by: str | None = None, note: str | None = None, reissue: bool = False, actor: dict[str, Any] | None = None) -> Item:
        at = now_iso()
        issue = IssueEvent(at=at, to=to, by=by, note=note, reissue=reissue)
        item = item.model_copy(update={"subcontractor": to or item.subcontractor, "status": ItemStatus.ISSUED, "issued_at": item.issued_at or at, "issue_history": [*item.issue_history, issue]})
        return self._audit(item, "Re-issued to " + to if reissue else "Issued to " + to, by=by, note=note, at=at, actor=actor)
