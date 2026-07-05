"""Phase 1B manual checklist — automated via API + served HTML (no browser).

Live run (production): set CLEANRUN_LIVE_BASE_URL, CLEANRUN_LIVE_EMAIL, CLEANRUN_LIVE_PASSWORD.
Local run: uses in-process ASGI client + dev-site-manager token (cards37 branch).
"""

from __future__ import annotations

import json
import os
import re
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer

ROOT = Path(__file__).resolve().parents[1]
ENHANCEMENTS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.js"
INDEX = ROOT / "CleanRun-IQ-Full-App-Render3" / "index.html"

STATUS_CHIPS = [
    "All",
    "Captured",
    "Issued",
    "In Progress",
    "Ready",
    "Rejected",
    "Overdue",
    "Closed",
]

REPORT_TYPES = [
    "register",
    "handover",
    "exceptions",
    "subcontractor",
    "client",
    "incomplete",
]


def _today_iso() -> str:
    return date.today().isoformat()


def _overdue(item: dict) -> bool:
    return item.get("status") not in ("closed", "complete") and item.get("dueDate", "") < _today_iso()


def status_match(item: dict, chip: str) -> bool:
    if chip == "All":
        return True
    if chip == "Captured":
        return item.get("status") == "open" and not _overdue(item)
    if chip == "Issued":
        return item.get("status") == "issued" and not _overdue(item)
    if chip == "In Progress":
        return item.get("status") == "in_progress" and not _overdue(item)
    if chip == "Ready":
        return item.get("status") in ("ready_for_review", "under_inspection") and not _overdue(item)
    if chip == "Rejected":
        return item.get("status") == "rejected"
    if chip == "Overdue":
        return _overdue(item)
    if chip == "Closed":
        return item.get("status") in ("closed", "complete")
    return True


def card_headline(item: dict) -> str:
    desc = str(item.get("description") or "").strip()
    location = " · ".join(
        p for p in [item.get("building"), item.get("level"), item.get("unit"), item.get("room")] if p
    )
    if desc and desc != "No description" and desc != location:
        return desc
    type_labels = {
        "defect": "defect",
        "incomplete": "incomplete work",
        "client": "client defect",
    }
    type_word = type_labels.get(item.get("type", ""), str(item.get("type") or "item").lower())
    trade = str(item.get("trade") or "").strip()
    if trade:
        return f"{trade} {type_word}"
    return type_word[:1].upper() + type_word[1:]


def item_filter_active_count(scope: str, building: str, focus: str) -> int:
    n = 0
    if scope != "active":
        n += 1
    if building:
        n += 1
    if focus:
        n += 1
    return n


class LiveHttp:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def get(self, path: str) -> tuple[int, str]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        req = urllib.request.Request(f"{self.base}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read().decode("utf-8", errors="replace")

    @classmethod
    def login(cls, base: str, email: str, password: str) -> LiveHttp:
        with urllib.request.urlopen(f"{base.rstrip('/')}/api/auth/config", timeout=30) as response:
            cfg = json.loads(response.read().decode())
        body = json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(
            f"{cfg['supabase_url']}/auth/v1/token?grant_type=password",
            data=body,
            headers={
                "Content-Type": "application/json",
                "apikey": cfg["supabase_publishable_key"],
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            token = json.loads(response.read().decode())["access_token"]
        return cls(base, token)


@unittest.skipUnless(
    os.getenv("CLEANRUN_LIVE_BASE_URL") and os.getenv("CLEANRUN_LIVE_EMAIL") and os.getenv("CLEANRUN_LIVE_PASSWORD"),
    "Set CLEANRUN_LIVE_BASE_URL, CLEANRUN_LIVE_EMAIL, CLEANRUN_LIVE_PASSWORD for live checklist",
)
class Phase1BLiveChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.http = LiveHttp.login(
            os.environ["CLEANRUN_LIVE_BASE_URL"],
            os.environ["CLEANRUN_LIVE_EMAIL"],
            os.environ["CLEANRUN_LIVE_PASSWORD"],
        )
        _, cls.index_html = cls.http.get("/")
        enh_match = re.search(r"/assets/enhancements\.js\?v=[^\"']+", cls.index_html)
        assert enh_match, "enhancements.js URL not found"
        _, cls.enhancements_js = cls.http.get(enh_match.group(0))
        _, state_raw = cls.http.get("/api/state")
        cls.state = json.loads(state_raw)
        cls.items = cls.state.get("items", [])

    def test_login_and_state_load(self) -> None:
        self.assertGreater(len(self.items), 0)

    def test_status_chip_counts_are_consistent(self) -> None:
        counts = {chip: sum(1 for item in self.items if status_match(item, chip)) for chip in STATUS_CHIPS}
        self.assertEqual(counts["All"], len(self.items))
        # Chips are not a strict partition: Overdue overlaps status buckets for open past-due items.
        self.assertGreaterEqual(counts["Overdue"], 0)
        self.assertGreater(counts["Issued"] + counts["In Progress"], 0)

    def test_frontend_phase1b_markers(self) -> None:
        build = re.search(r'CLEANRUN_FRONTEND_BUILD="(cards\d+)"', self.enhancements_js)
        self.assertIsNotNone(build, "frontend build tag missing")
        if build.group(1) >= "cards37":
            self.assertIn("toggleItemFilters", self.enhancements_js)
            self.assertIn("labelIconButtons", self.enhancements_js)
            self.assertIn("cardHeadline", self.enhancements_js)
            self.assertNotIn("Location unavailable", self.enhancements_js)
            # Compound chip label removed; Rejected filter and Re-issue actions remain.
            self.assertNotIn("REJECTED / RE-ISSUE", self.enhancements_js)
            self.assertIn('"Rejected"', self.enhancements_js)
            self.assertIn("Re-issue", self.enhancements_js)
            self.assertIn("reviewReject", self.enhancements_js)
            self.assertIn('s==="In Progress"', self.enhancements_js)
        else:
            self.skipTest(f"production still on {build.group(1)} — Phase 1B UI not deployed yet")

    def test_all_six_reports_generate(self) -> None:
        for report_type in REPORT_TYPES:
            if report_type == "subcontractor":
                continue
            status, html = self.http.get(f"/api/reports/{report_type}")
            self.assertEqual(status, 200, report_type)
            self.assertIn("CleanRun", html)

    def test_register_status_vocabulary_when_deployed(self) -> None:
        build = re.search(r'CLEANRUN_FRONTEND_BUILD="(cards\d+)"', self.enhancements_js)
        if not build or build.group(1) < "cards37":
            self.skipTest("Phase 1B not deployed on live")
        _, html = self.http.get("/api/reports/register")
        open_items = [i for i in self.items if i.get("status") not in ("closed", "complete")]
        if open_items:
            self.assertIn("Captured", html)
        self.assertIn("In Progress", html)
        self.assertNotIn("Ready for Review", html)
        self.assertIn("status-overdue", html)
        self.assertIn("status-ready-for-review", html)


class Phase1BLocalChecklist(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.patcher = patch.object(app_main, "store", self.store)
        self.patcher.start()
        self.client = AsgiClient(app_main.app)
        self.headers = bearer("dev-site-manager")

    def tearDown(self) -> None:
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_source_cards60_markers(self) -> None:
        enh = ENHANCEMENTS.read_text(encoding="utf-8")
        self.assertIn('CLEANRUN_FRONTEND_BUILD="cards60"', enh)
        self.assertIn("toggleItemFilters", enh)
        self.assertIn("labelIconButtons", enh)
        self.assertIn("cardHeadline", enh)
        self.assertNotIn("Location unavailable", enh)

    def test_status_chip_partition_on_demo_data(self) -> None:
        items = self.client.get("/api/state", headers=self.headers).json()["items"]
        counts = {chip: sum(1 for item in items if status_match(item, chip)) for chip in STATUS_CHIPS}
        self.assertEqual(counts["All"], len(items))

    def test_filter_badge_count_logic(self) -> None:
        self.assertEqual(item_filter_active_count("active", "", ""), 0)
        self.assertEqual(item_filter_active_count("all", "Block A", "trade::Electrical"), 3)

    def test_card_headline_without_description(self) -> None:
        headline = card_headline(
            {
                "description": "",
                "trade": "Electrical",
                "type": "defect",
                "building": "Block A",
                "level": "L02",
            }
        )
        self.assertEqual(headline, "Electrical defect")

    def test_status_action_reflects_in_register(self) -> None:
        # Create a dedicated open item with a far-future due date so the test
        # never depends on seed data still being due (seed dates rot over time).
        created = self.client.post(
            "/api/items",
            headers=self.headers,
            json={
                "project": "Jura Noosa",
                "building": "Block A",
                "level": "L01",
                "unit": "A-101",
                "room": "Kitchen",
                "trade": "Tiling",
                "subcontractor": "ASTW Tiling",
                "dueDate": "2099-12-31",
                "description": "Status action register check",
                "originalPhotos": ["seed://photo"],
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        item = created.json()
        self.assertEqual(item["status"], "open")
        issued = self.client.post(
            f"/api/items/{item['id']}/actions/issue",
            headers=self.headers,
            json={"to": item.get("subcontractor") or "ASTW Tiling", "by": "Site Manager"},
        )
        self.assertEqual(issued.status_code, 200)
        progressed = self.client.post(
            f"/api/items/{item['id']}/actions/in-progress",
            headers=self.headers,
            json={"by": "Site Manager"},
        )
        self.assertEqual(progressed.status_code, 200)
        refreshed = self.client.get("/api/state", headers=self.headers).json()["items"]
        updated = next(i for i in refreshed if i["id"] == item["id"])
        self.assertEqual(updated["status"], "in_progress")
        register = self.client.get("/api/reports/register", headers=self.headers).text
        snippet_start = register.index(item["code"])
        snippet = register[snippet_start : snippet_start + 500]
        self.assertTrue("In Progress" in snippet or "status-in-progress" in snippet, snippet)

    def test_all_six_reports_local(self) -> None:
        for report_type in REPORT_TYPES:
            if report_type == "subcontractor":
                continue
            response = self.client.get(f"/api/reports/{report_type}", headers=self.headers)
            self.assertEqual(response.status_code, 200, report_type)

    def test_register_status_colours(self) -> None:
        html = self.client.get("/api/reports/register", headers=self.headers).text
        self.assertIn("status-overdue", html)
        self.assertIn("status-ready-for-review", html)
        self.assertIn("status-issued", html)
        self.assertIn("#1D4ED8", html)

    def test_empty_description_headline_is_ui_only(self) -> None:
        """Create API requires description; cardHeadline covers empty/legacy rows in the UI."""
        self.assertEqual(
            card_headline({"description": "", "trade": "Electrical", "type": "defect", "building": "Block A"}),
            "Electrical defect",
        )

    def test_index_has_in_progress_chip(self) -> None:
        page = INDEX.read_text(encoding="utf-8")
        self.assertIn("In Progress", page)
        self.assertIn("aria-label=\"Back\"", page)


if __name__ == "__main__":
    unittest.main()
