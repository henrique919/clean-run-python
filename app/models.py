from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class ItemType(StrEnum):
    DEFECT = "defect"
    INCOMPLETE = "incomplete"
    CLIENT = "client"


class ItemStatus(StrEnum):
    OPEN = "open"
    ISSUED = "issued"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    UNDER_INSPECTION = "under_inspection"
    REJECTED = "rejected"
    CLOSED = "closed"
    COMPLETE = "complete"


class Priority(StrEnum):
    HIGH = "high"
    URGENT = "urgent"


class SyncState(StrEnum):
    SYNCED = "synced"
    PENDING = "pending"
    OFFLINE = "offline"
    FAILED = "failed"


RAISED_BY_OPTIONS = [
    "Client PM",
    "Superintendent",
    "Consultant",
    "Architect",
    "Buyer",
    "Other",
]

TRADES = [
    "Painting",
    "Plastering",
    "Tiling",
    "Waterproofing",
    "Joinery",
    "Doors / Hardware",
    "Windows / Aluminium",
    "Flooring",
    "Roofing",
    "Cladding",
    "Electrical",
    "Hydraulic",
    "Mechanical",
    "Fire Services",
    "Cleaning",
    "Landscaping",
    "Concrete",
    "Render",
    "Caulking / Sealant",
    "General Damage",
]

TYPE_LABEL: dict[ItemType, str] = {
    ItemType.DEFECT: "Defect",
    ItemType.INCOMPLETE: "Incomplete Work",
    ItemType.CLIENT: "Client Defect",
}

STATUS_LABEL: dict[ItemStatus, str] = {
    ItemStatus.OPEN: "Open",
    ItemStatus.ISSUED: "Issued",
    ItemStatus.IN_PROGRESS: "In Progress",
    ItemStatus.READY_FOR_REVIEW: "Ready for Review",
    ItemStatus.UNDER_INSPECTION: "Under Inspection",
    ItemStatus.REJECTED: "Rejected",
    ItemStatus.CLOSED: "Closed",
    ItemStatus.COMPLETE: "Complete",
}

CODE_PREFIX: dict[ItemType, str] = {
    ItemType.DEFECT: "DEF",
    ItemType.INCOMPLETE: "INC",
    ItemType.CLIENT: "CLD",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id() -> str:
    return uuid4().hex


class RectificationEvidence(BaseModel):
    id: str = Field(default_factory=make_id)
    photo: str | None = None
    comment: str | None = None
    by: str
    at: str = Field(default_factory=now_iso)


class CloseoutEvidence(BaseModel):
    id: str = Field(default_factory=make_id)
    photo: str | None = None
    by: str
    role: str = "Supervisor"
    note: str | None = None
    confirmation: str | None = None
    at: str = Field(default_factory=now_iso)


class Comment(BaseModel):
    id: str = Field(default_factory=make_id)
    text: str
    by: str
    at: str = Field(default_factory=now_iso)


class IssueEvent(BaseModel):
    at: str = Field(default_factory=now_iso)
    by: str | None = None
    to: str
    note: str | None = None
    reissue: bool = False


class InspectionEvent(BaseModel):
    at: str = Field(default_factory=now_iso)
    by: str
    action: Literal["started", "accepted", "rejected"]
    reason: str | None = None


class AuditEvent(BaseModel):
    at: str = Field(default_factory=now_iso)
    action: str
    by: str | None = None
    note: str | None = None


class VoiceNote(BaseModel):
    transcript: str
    audio_uri: str | None = None
    parsed_fields: dict[str, Any] | None = None
    created_at: str = Field(default_factory=now_iso)
    status: Literal["recorded", "transcribed", "parsed", "failed"] = "parsed"


class ItemCreate(BaseModel):
    type: ItemType = ItemType.DEFECT
    project: str
    building: str = ""
    level: str = ""
    unit: str = ""
    room: str = ""
    trade: str = ""
    subcontractor: str = ""
    priority: Priority = Priority.HIGH
    due_date: str
    description: str
    raised_by: str | None = None
    original_photos: list[str] = Field(default_factory=list)
    voice_transcript: str | None = None
    voice_note: VoiceNote | None = None
    created_by: str | None = None
    status: ItemStatus = ItemStatus.OPEN

    @field_validator("description")
    @classmethod
    def description_clean(cls, value: str) -> str:
        return value.strip()


class ItemUpdate(BaseModel):
    type: ItemType | None = None
    project: str | None = None
    building: str | None = None
    level: str | None = None
    unit: str | None = None
    room: str | None = None
    trade: str | None = None
    subcontractor: str | None = None
    priority: Priority | None = None
    due_date: str | None = None
    description: str | None = None
    raised_by: str | None = None


class Item(ItemCreate):
    id: str = Field(default_factory=make_id)
    code: str
    status: ItemStatus = ItemStatus.OPEN
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    rectification_evidence: list[RectificationEvidence] = Field(default_factory=list)
    closeout_evidence: list[CloseoutEvidence] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    issue_history: list[IssueEvent] = Field(default_factory=list)
    inspection_history: list[InspectionEvent] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    issued_at: str | None = None
    in_progress_at: str | None = None
    ready_for_review_at: str | None = None
    under_inspection_at: str | None = None
    closed_at: str | None = None
    rejection_reason: str | None = None
    sync: SyncState = SyncState.SYNCED


class ProjectConfig(BaseModel):
    name: str
    address: str = ""
    buildings: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    rooms: list[str] = Field(default_factory=list)
    default_due_days: int = 7


class SubProfile(BaseModel):
    name: str
    trade: str | None = None
    contact: str | None = None
    email: str | None = None
    phone: str | None = None


class Settings(BaseModel):
    projects: list[str]
    project_configs: dict[str, ProjectConfig]
    subcontractors: list[str]
    sub_profiles: dict[str, SubProfile]
    active_project: str
    company: str = "qld Built"
    prepared_by: str = "Site Team"


class AppData(BaseModel):
    items: list[Item]
    settings: Settings
