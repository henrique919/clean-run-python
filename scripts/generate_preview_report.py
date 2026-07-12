"""Generate local compact report preview with 5 multi-status fixture items."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.models import CloseoutEvidence, Item, ItemStatus, Priority, RectificationEvidence
from app.reporting import build_report_html
from app.store import CleanRunStore

NOW = datetime(2026, 7, 5, 10, 16, tzinfo=timezone.utc).isoformat()
PHOTOS = {
    "po1": "https://picsum.photos/seed/po1.jpg/480/360",
    "po2": "https://picsum.photos/seed/po2.jpg/480/360",
    "po3": "https://picsum.photos/seed/po3.jpg/480/360",
    "po5": "https://picsum.photos/seed/po5.jpg/480/360",
    "pr1": "https://picsum.photos/seed/pr1.jpg/480/360",
    "pc1": "https://picsum.photos/seed/pc1.jpg/480/360",
}


def base(**kw) -> Item:
    data = dict(
        id=kw.pop("id", "item"),
        code=kw.pop("code", "DEF-1000"),
        type="defect",
        project="Esplanade Drive",
        building="Tower A",
        level="Level 3",
        unit="301",
        room="Ensuite",
        trade="Tiling",
        subcontractor="ASTW Tiling",
        priority=Priority.HIGH,
        due_date="2026-07-15",
        description="Sample defect",
        original_photos=[],
        rectification_evidence=[],
        closeout_evidence=[],
        created_at=NOW,
        updated_at=NOW,
    )
    data.update(kw)
    return Item(**data)


def preview_items() -> list[Item]:
    return [
        base(
            id="i5",
            code="DEF-1005",
            status=ItemStatus.IN_PROGRESS,
            description="Ceiling cornice gap in living area.",
            original_photos=[PHOTOS["po5"]],
        ),
        base(
            id="i4",
            code="DEF-1004",
            status=ItemStatus.REJECTED,
            description=(
                "Waterproofing membrane incomplete at floor waste. Contractor must return to site "
                "and re-install membrane to manufacturer specification before re-inspection."
            ),
            original_photos=[],
        ),
        base(
            id="i3",
            code="DEF-1003",
            status=ItemStatus.READY_FOR_REVIEW,
            description="Door hardware misaligned — awaiting supervisor review.",
            original_photos=[PHOTOS["po3"]],
            rectification_evidence=[
                RectificationEvidence(photo=PHOTOS["pr1"], comment="Adjusted hinges", by="Trade Lead", at=NOW)
            ],
        ),
        base(
            id="i2",
            code="DEF-1002",
            status=ItemStatus.ISSUED,
            due_date="2020-01-01",
            description="Paint overspray on balcony balustrade.",
            original_photos=[PHOTOS["po2"]],
        ),
        base(
            id="i1",
            code="DEF-1001",
            status=ItemStatus.CLOSED,
            description="Cracked floor tile near shower hob — rectified and signed off.",
            original_photos=[PHOTOS["po1"]],
            closeout_evidence=[
                CloseoutEvidence(
                    photo=PHOTOS["pc1"],
                    by="Site Manager",
                    role="Supervisor",
                    confirmation="Verified",
                    at=NOW,
                )
            ],
        ),
    ]


def main() -> None:
    settings = CleanRunStore().snapshot().settings.model_copy(
        update={
            "active_project": "Esplanade Drive",
            "company": "CleanRun Construction",
            "prepared_by": "Site Manager",
        }
    )
    items = preview_items()

    def resolve(value: str | None) -> str | None:
        if value and (value.startswith("http") or value.startswith("data:")):
            return value
        return None

    with patch("app.reporting.resolve_photo_url", side_effect=resolve), patch(
        "app.reporting.resolve_share_photo_url", return_value=None
    ):
        html = build_report_html(items, settings, "register", projects=["Esplanade Drive"])

    targets = [
        REPO / "preview-report-local.html",
        Path(r"C:\Users\Harry\Downloads\CleanRun-IQ-Report-Preview-5-Jul-2026.html"),
    ]
    for path in targets:
        path.write_text(html, encoding="utf-8")
        print(f"wrote {path} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
