from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, RectificationEvidence
from app.reporting import build_report_html
from app.store import CleanRunStore


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_item(self):
        return self.store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="Block B",
                level="L02",
                unit="B-204",
                room="Bathroom",
                trade="Tiling",
                subcontractor="Sterling Tiling",
                due_date="2026-07-01",
                description="Cracked tile beside vanity",
                original_photos=["seed://amber/Cracked-tile"],
                created_by="Site Manager",
            )
        )

    def test_complete_item_lifecycle_and_report(self) -> None:
        item = self.create_item()
        item = self.store.issue_item(item.id, to=item.subcontractor, by="Site Manager")
        self.assertEqual(item.status, ItemStatus.ISSUED)
        item = self.store.mark_in_progress(item.id, by="Sterling Tiling")
        item = self.store.add_rectification(
            item.id,
            RectificationEvidence(comment="Tile replaced and regrouted", by="Sterling Tiling"),
            advance_to_ready=True,
        )
        self.assertEqual(item.status, ItemStatus.READY_FOR_REVIEW)
        item = self.store.start_inspection(item.id, by="Supervisor")
        item = self.store.add_comment(item.id, Comment(text="Checked on site", by="Supervisor"))
        item = self.store.close_with_evidence(
            item.id,
            CloseoutEvidence(by="Supervisor", note="Accepted", confirmation="Confirmed acceptable for closeout"),
        )
        self.assertEqual(item.status, ItemStatus.CLOSED)
        self.assertEqual(len(item.rectification_evidence), 1)
        self.assertEqual(len(item.closeout_evidence), 1)
        self.assertEqual(len(item.comments), 1)

        snapshot = self.store.snapshot()
        report = build_report_html(snapshot.items, snapshot.settings, "handover")
        self.assertIn("Smarter Field. Cleaner Builds.", report)
        self.assertIn("cleanrun-logo-horizontal.png", report)
        self.assertIn(item.code, report)
        self.assertIn("Closed / Complete Evidence", report)

    def test_restored_ui_contains_register_tools_and_lifecycle_actions(self) -> None:
        root = Path(__file__).resolve().parents[1]
        html = (root / "app/static/index.html").read_text(encoding="utf-8")
        script = (root / "app/static/app.js").read_text(encoding="utf-8")
        styles = (root / "app/static/styles.css").read_text(encoding="utf-8")

        for element_id in ("statsBar", "searchInput", "statusFilter", "clearFilters", "saveBtn", "issueBtn"):
            self.assertIn(f'id="{element_id}"', html)
        for action in ("data-rectify", "data-reject", "data-close", "data-comment"):
            self.assertIn(action, script)
        self.assertIn(".action-bar", styles)
        self.assertIn("position: sticky", styles)
        self.assertIn('family=Archivo:wght@500;600;700;800&family=Inter', styles)
        self.assertIn("#20C55E", styles)
        self.assertNotIn("#FF6A00", styles.upper())
        self.assertIn("cleanrun-logo-horizontal.png", html)
        self.assertTrue((root / "app/static/assets/brand/favicon.png").exists())


if __name__ == "__main__":
    unittest.main()
