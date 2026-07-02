"""Regression tests for Render3 session UX and workflow action aliases."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.models import ItemCreate
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer

ROOT = Path(__file__).resolve().parents[1]
RENDER3 = ROOT / "CleanRun-IQ-Full-App-Render3"
INDEX = RENDER3 / "index.html"
ENHANCEMENTS = RENDER3 / "assets" / "enhancements.js"


def _issue_item(client: AsgiClient, item_id: str) -> None:
    response = client.post(
        f"/api/items/{item_id}/actions/issue",
        headers=bearer("dev-site-manager"),
        json={"to": "ASTW Tiling", "by": "Site Manager"},
    )
    assert response.status_code == 200


def test_in_progress_action_alias_matches_start():
    """POST /actions/in-progress must reuse the same start workflow as /actions/start."""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = CleanRunStore(Path(temp_dir) / "cleanrun.json")
        with patch.object(app_main, "store", store):
            client = AsgiClient(app_main.app)
            item = store.snapshot().items[0]
            _issue_item(client, item.id)

            start = client.post(
                f"/api/items/{item.id}/actions/start",
                headers=bearer("dev-site-manager"),
                json={"by": "Site Manager"},
            )
            assert start.status_code == 200
            assert start.json()["status"] == "in_progress"

            item2 = store.create_item(
                ItemCreate(
                    project="Jura Noosa",
                    building="B1",
                    level="Level 1",
                    unit="U102",
                    room="Bathroom",
                    trade="Tiling",
                    subcontractor="ASTW Tiling",
                    due_date="2026-07-01",
                    description="In-progress alias test",
                    original_photos=["seed://photo"],
                    created_by="Site Manager",
                )
            )
            _issue_item(client, item2.id)

            alias = client.post(
                f"/api/items/{item2.id}/actions/in-progress",
                headers=bearer("dev-site-manager"),
                json={"by": "Site Manager"},
            )
            assert alias.status_code == 200
            assert alias.json()["status"] == "in_progress"
            assert alias.json()["status"] == start.json()["status"]


def test_render3_reopen_admin_not_reachable_from_normal_ui():
    """Reopen (Admin) must not appear in nextButtons; guards block reopen itemAction."""
    index = INDEX.read_text(encoding="utf-8")
    enhancements = ENHANCEMENTS.read_text(encoding="utf-8")

    assert "Reopen (Admin)" not in index
    assert "Reopen (Admin)" not in enhancements
    assert "act==='reopen'" in index
    assert "reopen is not available" in index.lower()
    assert 'act==="reopen"' in enhancements


def test_render3_logout_control_present():
    """Production shell must expose sign-out that clears session and returns to login."""
    index = INDEX.read_text(encoding="utf-8")
    enhancements = ENHANCEMENTS.read_text(encoding="utf-8")

    assert "function logout()" in index
    assert "Sign out" in index
    assert "cleanrun_auth_token" in index
    assert "renderLogin(" in index
    assert 'onclick="logout()"' in enhancements
    assert "Sign out" in enhancements


def test_render3_phase1_field_speed_ux_markers():
    """Phase 1 speed UX: quick capture, sticky location, scan cards, capture-next."""
    enhancements = ENHANCEMENTS.read_text(encoding="utf-8")

    assert 'CLEANRUN_FRONTEND_BUILD="cards32"' in enhancements
    assert "window.openReport=async function" in enhancements
    assert "Speak Item" in enhancements or "Speak Item" in (ROOT / "CleanRun-IQ-Full-App-Render3/index.html").read_text(encoding="utf-8")
    assert "Draft form from note" in (ROOT / "CleanRun-IQ-Full-App-Render3/index.html").read_text(encoding="utf-8")
    assert "cr-scan-card" not in enhancements


def test_render3_demo_reset_hidden_in_production_markup():
    """Demo reset must be gated by isProductionApp(); production shows disabled label."""
    index = INDEX.read_text(encoding="utf-8")
    enhancements = ENHANCEMENTS.read_text(encoding="utf-8")

    assert "function isProductionApp()" in index
    assert "Demo reset is disabled in production" in index
    assert "isProductionApp()" in index
    assert 'onclick="resetDemo()"' in index
    assert "isProductionApp()" in enhancements
    assert "Demo reset is disabled in production" in enhancements
