"""Core verification tests for the CleanRun IQ Python port."""

from __future__ import annotations

from cleanrun_iq.models import CreateItemInput, ItemStatus, ItemType, Priority, UpdateItemInput
from cleanrun_iq.report_builder import build_report_html, filter_items
from cleanrun_iq.services import CleanRunService
from cleanrun_iq.store import JsonStore
from cleanrun_iq.utils import add_days
from cleanrun_iq.voice_parser import parse_transcript


def test_voice_parser_extracts_location_trade_and_due_date() -> None:
    parsed = parse_transcript(
        "Block B level two unit B-204 bathroom cracked tile assign to Sterling Tiling urgent due tomorrow",
        ["Sterling Tiling"],
    )
    assert parsed["type"] == ItemType.DEFECT
    assert parsed["building"] == "Block B"
    assert parsed["level"] == "L02"
    assert parsed["unit"] == "B-204"
    assert parsed["room"] == "Bathroom"
    assert parsed["trade"] == "Tiling"
    assert parsed["subcontractor"] == "Sterling Tiling"
    assert parsed["priority"] == Priority.URGENT


def test_workflow_create_issue_review_close(tmp_path) -> None:
    store = JsonStore(tmp_path)
    service = CleanRunService(store)
    item = service.create_item(
        CreateItemInput(
            type=ItemType.DEFECT,
            project="Jura Noosa",
            building="Block B",
            level="L02",
            unit="B-204",
            room="Bathroom",
            trade="Tiling",
            subcontractor="Sterling Tiling",
            priority=Priority.HIGH,
            dueDate=add_days(2),
            description="Cracked tile beside vanity",
            createdBy="Site Manager",
            originalPhotos=["seed://amber/Cracked%20tile"],
        )
    )
    assert item.code.startswith("DEF-")
    issued = service.issue_item(item.id, "Sterling Tiling", by="Site Manager")
    assert issued.status == ItemStatus.ISSUED
    service.mark_in_progress(item.id, by="Sterling Tiling")
    service.add_rectification_evidence(item.id, by="Sterling Tiling", comment="Tile replaced")
    ready = service.mark_ready_for_review(item.id, by="Sterling Tiling")
    assert ready.status == ItemStatus.READY_FOR_REVIEW
    service.start_inspection(item.id, by="Supervisor")
    closed = service.close_with_evidence(item.id, by="Supervisor", role="Supervisor", note="Accepted")
    assert closed.status == ItemStatus.CLOSED
    assert closed.closeout_evidence


def test_update_item_logs_audit_event(tmp_path) -> None:
    store = JsonStore(tmp_path)
    service = CleanRunService(store)
    item = store.get_items()[0]
    updated = service.update_item(item.id, UpdateItemInput(description="Updated description"), by="Tester")
    assert updated.description == "Updated description"
    assert updated.audit_events[-1].action == "Item details edited"


def test_report_html_builds(tmp_path) -> None:
    store = JsonStore(tmp_path)
    items = filter_items(store.get_items(), "open")
    html = build_report_html(items, "open", store.get_settings())
    assert "CleanRun IQ" in html
    assert "Open Items" in html
