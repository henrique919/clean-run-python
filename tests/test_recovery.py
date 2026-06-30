from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from os import chdir
from pathlib import Path

from pydantic import ValidationError

from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, ProjectConfig, RectificationEvidence
from app.reporting import build_report_html
from app.store import CleanRunStore, seed_data


@contextmanager
def changed_directory(path: Path):
    original = Path.cwd()
    chdir(path)
    try:
        yield
    finally:
        chdir(original)


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
        self.assertIn("Site QA Control", report)
        self.assertIn(item.code, report)
        self.assertIn("Closed / Complete Evidence", report)

    def test_settings_preferred_items_view_persists(self) -> None:
        settings = self.store.snapshot().settings
        updated_configs = dict(settings.project_configs)
        updated_configs[settings.active_project] = updated_configs[settings.active_project].model_copy(
            update={"preferred_items_view": "subcontractor"}
        )

        self.store.update_settings(settings.model_copy(update={"project_configs": updated_configs}))
        saved = self.store.snapshot().settings

        self.assertEqual(saved.project_configs[saved.active_project].preferred_items_view, "subcontractor")

    def test_repeated_capture_submit_returns_existing_item(self) -> None:
        first = self.create_item()
        second = self.create_item()
        snapshot = self.store.snapshot()

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.code, first.code)
        self.assertEqual(len([item for item in snapshot.items if item.description == "Cracked tile beside vanity"]), 1)

    def test_seed_data_loads_snapshot_outside_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir:
            with changed_directory(Path(other_dir)):
                data = seed_data()

        self.assertEqual(len(data.items), 14)
        self.assertEqual(data.items[0].code, "DEF-001")

    def test_project_config_rejects_unknown_items_view(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectConfig(name="Bad View", preferred_items_view="surprise")

    def test_report_renders_uploaded_evidence_images(self) -> None:
        item = self.create_item()
        data_url = "data:image/png;base64,iVBORw0KGgo="
        item = self.store.add_rectification(
            item.id,
            RectificationEvidence(photo=data_url, comment="Fixed", by="Sterling Tiling"),
            advance_to_ready=True,
        )
        item = self.store.start_inspection(item.id, by="Supervisor")
        self.store.close_with_evidence(
            item.id,
            CloseoutEvidence(photo=data_url, by="Supervisor", note="Accepted", confirmation="Confirmed"),
        )

        report = build_report_html(self.store.snapshot().items, self.store.snapshot().settings, "handover")

        self.assertIn('src="data:image/png;base64,iVBORw0KGgo="', report)
        self.assertIn("Original photo / issue evidence", report)
        self.assertIn("Rectification photo / trade evidence", report)
        self.assertIn("Closeout / signed-off evidence", report)

    def test_restored_ui_contains_register_tools_and_lifecycle_actions(self) -> None:
        root = Path(__file__).resolve().parents[1]
        html = (root / "app/static/index.html").read_text(encoding="utf-8")
        entry_script = (root / "app/static/app.js").read_text(encoding="utf-8")
        script = (root / "app/static/js/main.js").read_text(encoding="utf-8")
        styles = (root / "app/static/styles.css").read_text(encoding="utf-8")

        for element_id in ("statsBar", "searchInput", "statusFilter", "clearFilters", "saveBtn", "issueBtn"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('<script src="/static/voice-parser.js?v=3"></script>', html)
        self.assertIn('<script src="/static/voice-capture.js?v=3"></script>', html)
        self.assertIn('<script src="/static/app.js?v=3"></script>', html)
        self.assertEqual(entry_script.strip(), 'import("/static/js/main.js");')
        self.assertIn("window.VoiceParser", (root / "app/static/voice-parser.js").read_text(encoding="utf-8"))
        self.assertIn("voiceRecordBtn", html)
        for action in ("data-rectify", "data-reject", "data-close", "data-comment"):
            self.assertIn(action, script)
        self.assertEqual(script.count("function renderItems()"), 1)
        self.assertIn(".action-bar", styles)
        self.assertIn("position: sticky", styles)


if __name__ == "__main__":
    unittest.main()
