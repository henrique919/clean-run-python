"""Demo data equivalent to the Rork `demoSeed.ts` file."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from cleanrun_iq.models import (
    AuditEvent,
    Item,
    ItemStatus,
    ItemType,
    Priority,
    ProjectConfig,
    Settings,
    SubProfile,
    SyncState,
)
from cleanrun_iq.utils import add_days, make_id

DEFAULT_SUBS = [
    "Coastline Painting",
    "Apex Plastering",
    "Sterling Tiling",
    "AquaSeal Waterproofing",
    "TrueLine Joinery",
    "Northline Electrical",
    "Pacific Plumbing",
    "Skyline Glazing",
    "Premier Flooring",
    "Endeavour Cleaning",
]


def seed_photo(label: str, tone: str) -> str:
    """Create a seed photo URI.

    Args:
        label: Photo label.
        tone: UI colour tone.

    Returns:
        Seed URI.
    """
    return f"seed://{tone}/{label.replace(' ', '%20')}"


def days_ago(days: int) -> str:
    """Return ISO timestamp from a number of days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def trade_guess(name: str) -> str | None:
    """Infer trade from subcontractor name."""
    lower = name.lower()
    if "paint" in lower:
        return "Painting"
    if "plaster" in lower:
        return "Plastering"
    if "til" in lower:
        return "Tiling"
    if "water" in lower or "seal" in lower:
        return "Waterproofing"
    if "joinery" in lower:
        return "Joinery"
    if "electric" in lower:
        return "Electrical"
    if "plumb" in lower:
        return "Hydraulic"
    if "glaz" in lower or "window" in lower:
        return "Windows / Aluminium"
    if "floor" in lower:
        return "Flooring"
    if "clean" in lower:
        return "Cleaning"
    return None


def default_project_config(name: str) -> ProjectConfig:
    """Build the default project config."""
    return ProjectConfig(
        name=name,
        address="",
        buildings=["Block A", "Block B"],
        levels=["L01", "L02", "L03"],
        units=[],
        rooms=["Kitchen", "Living", "Bathroom", "Ensuite", "Bedroom 1", "Bedroom 2", "Laundry", "Balcony", "Hallway", "Garage"],
        defaultDueDays=7,
    )


def build_demo_settings() -> Settings:
    """Build demo settings.

    Returns:
        Settings instance.
    """
    profiles = {
        name: SubProfile(
            name=name,
            trade=trade_guess(name),
            contact="Site Contact",
            email=f"{''.join(c for c in name.lower() if c.isalpha())}@example.com",
            phone="0400 000 000",
        )
        for name in DEFAULT_SUBS
    }
    jura = default_project_config("Jura Noosa")
    jura.address = "Jura · Noosa Heads QLD"
    jura.units = ["A-304", "A-305", "B-112", "B-204"]
    meta = default_project_config("Meta Street")
    meta.address = "Meta Street · Mooloolaba QLD"
    meta.buildings = ["Tower 1"]
    meta.levels = ["L01", "L02", "L05", "L08", "L10"]
    meta.units = ["T1-502", "T1-803", "T1-1004"]
    return Settings(
        projects=["Jura Noosa", "Meta Street"],
        projectConfigs={"Jura Noosa": jura, "Meta Street": meta},
        subcontractors=sorted(DEFAULT_SUBS),
        subProfiles=profiles,
        activeProject="Jura Noosa",
        company="CleanRun Construction",
        preparedBy="Site Manager",
    )


def _base(**overrides: object) -> Item:
    code = str(overrides.pop("code"))
    item_type = overrides.pop("type")
    status = overrides.pop("status")
    now = days_ago(0)
    data = {
        "id": make_id(),
        "code": code,
        "type": item_type,
        "status": status,
        "project": "Jura Noosa",
        "building": "Block A",
        "level": "L03",
        "unit": "A-304",
        "room": "Bathroom",
        "trade": "Tiling",
        "subcontractor": "Sterling Tiling",
        "priority": Priority.HIGH,
        "dueDate": add_days(3),
        "description": "",
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "Site Manager",
        "originalPhotos": [],
        "rectificationEvidence": [],
        "closeoutEvidence": [],
        "comments": [],
        "issueHistory": [],
        "inspectionHistory": [],
        "auditEvents": [AuditEvent(at=now, action=f"Created ({code})", by="Site Manager")],
        "sync": SyncState.SYNCED,
    }
    data.update(overrides)
    return Item.model_validate(data)


def build_demo_items() -> list[Item]:
    """Build demo items.

    Returns:
        List of demo items.
    """
    return [
        _base(
            id="demo-def-open-jura",
            code="DEF-001",
            type=ItemType.DEFECT,
            status=ItemStatus.OPEN,
            building="Block B",
            level="L02",
            unit="B-204",
            room="Bathroom",
            dueDate=add_days(2),
            description="Cracked floor tile beside vanity unit. Chip on adjacent skirting tile.",
            originalPhotos=[seed_photo("Cracked tile", "amber"), seed_photo("Skirting chip", "amber")],
            createdAt=days_ago(1),
        ),
        _base(
            id="demo-def-issued-jura",
            code="DEF-002",
            type=ItemType.DEFECT,
            status=ItemStatus.ISSUED,
            building="Block A",
            level="L03",
            unit="A-305",
            room="Ensuite",
            trade="Waterproofing",
            subcontractor="AquaSeal Waterproofing",
            priority=Priority.URGENT,
            dueDate=add_days(1),
            description="Active moisture behind shower wall — membrane suspected compromised.",
            originalPhotos=[seed_photo("Moisture stain", "red")],
            issuedAt=days_ago(2),
        ),
        _base(
            id="demo-ready-jura",
            code="DEF-003",
            type=ItemType.DEFECT,
            status=ItemStatus.READY_FOR_REVIEW,
            unit="A-304",
            room="Bathroom",
            description="Grout discolouration along bath hob, re-grout required.",
            originalPhotos=[seed_photo("Grout staining", "amber")],
            readyForReviewAt=days_ago(1),
        ),
    ]
