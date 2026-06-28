"""Domain models for the CleanRun IQ Python port."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemType(StrEnum):
    """Supported item types from the Rork/Expo app."""

    DEFECT = "defect"
    INCOMPLETE = "incomplete"
    CLIENT = "client"


class ItemStatus(StrEnum):
    """Full item workflow status values."""

    OPEN = "open"
    ISSUED = "issued"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    UNDER_INSPECTION = "under_inspection"
    REJECTED = "rejected"
    CLOSED = "closed"
    COMPLETE = "complete"


class Priority(StrEnum):
    """Supported priority values."""

    HIGH = "high"
    URGENT = "urgent"


class SyncState(StrEnum):
    """Local-first sync state equivalent to the Expo app."""

    SYNCED = "synced"
    PENDING = "pending"
    OFFLINE = "offline"
    FAILED = "failed"


ESCALATION_DAYS = 10

RAISED_BY_OPTIONS: tuple[str, ...] = (
    "Client PM",
    "Superintendent",
    "Consultant",
    "Architect",
    "Buyer",
    "Other",
)

TRADES: tuple[str, ...] = (
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
)

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

TYPE_LABEL: dict[ItemType, str] = {
    ItemType.DEFECT: "Defect",
    ItemType.INCOMPLETE: "Incomplete Work",
    ItemType.CLIENT: "Client Defect",
}

CODE_PREFIX: dict[ItemType, str] = {
    ItemType.DEFECT: "DEF",
    ItemType.INCOMPLETE: "INC",
    ItemType.CLIENT: "CLD",
}


class RectificationEvidence(BaseModel):
    """Subcontractor-supplied rectification evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str
    photo: str | None = None
    comment: str | None = None
    by: str
    at: str


class CloseoutEvidence(BaseModel):
    """Site-team closeout evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str
    photo: str | None = None
    by: str
    role: str
    note: str | None = None
    confirmation: str | None = None
    at: str


class Comment(BaseModel):
    """Item comment."""

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    by: str
    at: str


class IssueEvent(BaseModel):
    """Record of an item being issued or re-issued."""

    model_config = ConfigDict(extra="forbid")

    at: str
    to: str
    by: str | None = None
    note: str | None = None
    reissue: bool | None = None


class InspectionEvent(BaseModel):
    """Inspection history event."""

    model_config = ConfigDict(extra="forbid")

    at: str
    by: str
    action: Literal["started", "accepted", "rejected"]
    reason: str | None = None


class AuditEvent(BaseModel):
    """Audit event for immutable item history."""

    model_config = ConfigDict(extra="forbid")

    at: str
    action: str
    by: str | None = None
    note: str | None = None


class VoiceNote(BaseModel):
    """Structured voice-note metadata."""

    model_config = ConfigDict(extra="forbid")

    transcript: str
    audio_uri: str | None = Field(default=None, alias="audioUri")
    parsed_fields: dict[str, Any] | None = Field(default=None, alias="parsedFields")
    created_at: str = Field(alias="createdAt")
    status: Literal["recorded", "transcribed", "parsed", "failed"]


class Item(BaseModel):
    """CleanRun IQ item model translated from the Rork TypeScript model."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    code: str
    type: ItemType
    project: str
    building: str = ""
    level: str = ""
    unit: str = ""
    room: str = ""
    trade: str = ""
    subcontractor: str = ""
    priority: Priority = Priority.HIGH
    due_date: str = Field(alias="dueDate")
    description: str
    status: ItemStatus
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    original_photos: list[str] = Field(default_factory=list, alias="originalPhotos")
    rectification_evidence: list[RectificationEvidence] = Field(default_factory=list, alias="rectificationEvidence")
    closeout_evidence: list[CloseoutEvidence] = Field(default_factory=list, alias="closeoutEvidence")
    comments: list[Comment] = Field(default_factory=list)
    issue_history: list[IssueEvent] = Field(default_factory=list, alias="issueHistory")
    inspection_history: list[InspectionEvent] = Field(default_factory=list, alias="inspectionHistory")
    audit_events: list[AuditEvent] = Field(default_factory=list, alias="auditEvents")
    raised_by: str | None = Field(default=None, alias="raisedBy")
    voice_transcript: str | None = Field(default=None, alias="voiceTranscript")
    voice_note: VoiceNote | None = Field(default=None, alias="voiceNote")
    issued_at: str | None = Field(default=None, alias="issuedAt")
    in_progress_at: str | None = Field(default=None, alias="inProgressAt")
    ready_for_review_at: str | None = Field(default=None, alias="readyForReviewAt")
    under_inspection_at: str | None = Field(default=None, alias="underInspectionAt")
    closed_at: str | None = Field(default=None, alias="closedAt")
    rejection_reason: str | None = Field(default=None, alias="rejectionReason")
    sync: SyncState = SyncState.SYNCED


class SubProfile(BaseModel):
    """Subcontractor profile."""

    model_config = ConfigDict(extra="forbid")

    name: str
    trade: str | None = None
    contact: str | None = None
    email: str | None = None
    phone: str | None = None


class ProjectConfig(BaseModel):
    """Per-project field defaults."""

    model_config = ConfigDict(extra="forbid")

    name: str
    address: str | None = None
    buildings: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    rooms: list[str] = Field(default_factory=list)
    default_due_days: int = Field(default=7, alias="defaultDueDays")


class Settings(BaseModel):
    """Application settings translated from the Rork store."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    projects: list[str]
    project_configs: dict[str, ProjectConfig] = Field(alias="projectConfigs")
    subcontractors: list[str]
    sub_profiles: dict[str, SubProfile] = Field(alias="subProfiles")
    active_project: str = Field(alias="activeProject")
    company: str
    prepared_by: str = Field(alias="preparedBy")


class PlanPin(BaseModel):
    """Normalised plan pin."""

    model_config = ConfigDict(extra="forbid")

    id: str
    x: float
    y: float
    item_id: str | None = Field(default=None, alias="itemId")
    label: str | None = None


class Plan(BaseModel):
    """Plan/drawing record."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project: str
    building: str
    level: str
    name: str
    image: str
    pins: list[PlanPin] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")


class CreateItemInput(BaseModel):
    """Input payload for creating an item."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    type: ItemType
    project: str
    building: str = ""
    level: str = ""
    unit: str = ""
    room: str = ""
    trade: str = ""
    subcontractor: str = ""
    priority: Priority = Priority.HIGH
    due_date: str = Field(alias="dueDate")
    description: str
    status: ItemStatus = ItemStatus.OPEN
    created_by: str | None = Field(default=None, alias="createdBy")
    original_photos: list[str] = Field(default_factory=list, alias="originalPhotos")
    raised_by: str | None = Field(default=None, alias="raisedBy")
    voice_transcript: str | None = Field(default=None, alias="voiceTranscript")
    voice_note: VoiceNote | None = Field(default=None, alias="voiceNote")


class UpdateItemInput(BaseModel):
    """Input payload for editing item details."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    type: ItemType | None = None
    project: str | None = None
    building: str | None = None
    level: str | None = None
    unit: str | None = None
    room: str | None = None
    trade: str | None = None
    subcontractor: str | None = None
    priority: Priority | None = None
    due_date: str | None = Field(default=None, alias="dueDate")
    description: str | None = None
    raised_by: str | None = Field(default=None, alias="raisedBy")
