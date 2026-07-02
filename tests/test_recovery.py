from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from os import chdir
from pathlib import Path

from pydantic import ValidationError

from app.main import import_subcontractors_from_rows, import_units_from_rows
from app.models import CloseoutEvidence, Comment, ItemCreate, ItemStatus, ProjectConfig, RectificationEvidence
from app.reporting import build_report_html
from app.services.projects import SettingsLockError, validate_settings_update
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
            CloseoutEvidence(
                photo="seed://closeout/accepted",
                by="Supervisor",
                note="Accepted",
                confirmation="Confirmed acceptable for closeout",
            ),
        )
        self.assertEqual(item.status, ItemStatus.CLOSED)
        self.assertEqual(len(item.rectification_evidence), 1)
        self.assertEqual(len(item.closeout_evidence), 1)
        self.assertEqual(len(item.comments), 1)

        snapshot = self.store.snapshot()
        report = build_report_html(snapshot.items, snapshot.settings, "handover")
        self.assertIn("Site QA Control", report)
        self.assertIn(item.code, report)
        self.assertIn("Print Report", report)
        self.assertIn("Share Report", report)
        self.assertIn("Closeout / signed-off evidence", report)

    def test_settings_preferred_items_view_persists(self) -> None:
        settings = self.store.snapshot().settings
        updated_configs = dict(settings.project_configs)
        updated_configs[settings.active_project] = updated_configs[settings.active_project].model_copy(
            update={"preferred_items_view": "subcontractor"}
        )

        self.store.update_settings(settings.model_copy(update={"project_configs": updated_configs}))
        saved = self.store.snapshot().settings

        self.assertEqual(saved.project_configs[saved.active_project].preferred_items_view, "subcontractor")

    def test_project_code_prefix_numbers_are_project_scoped(self) -> None:
        settings = self.store.snapshot().settings
        updated_configs = dict(settings.project_configs)
        updated_configs["Jura Noosa"] = updated_configs["Jura Noosa"].model_copy(
            update={"code_prefix": "JUR", "code_prefix_locked": True}
        )
        updated_configs["Meta Street"] = updated_configs["Meta Street"].model_copy(
            update={"code_prefix": "MET", "code_prefix_locked": True}
        )
        self.store.update_settings(settings.model_copy(update={"project_configs": updated_configs}))

        first_jura = self.create_item()
        second_jura = self.store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="Block B",
                level="L02",
                unit="B-205",
                room="Bathroom",
                trade="Tiling",
                subcontractor="Sterling Tiling",
                due_date="2026-07-01",
                description="Second Jura defect",
                original_photos=["seed://amber/Second"],
                created_by="Site Manager",
            )
        )
        first_meta = self.store.create_item(
            ItemCreate(
                project="Meta Street",
                building="Main Building",
                level="Ground",
                unit="Unit 1",
                room="Kitchen",
                trade="Painting",
                subcontractor="CLP Painting",
                due_date="2026-07-02",
                description="First Meta defect",
                original_photos=["seed://amber/Meta"],
                created_by="Site Manager",
            )
        )
        first_jura_incomplete = self.store.create_item(
            ItemCreate(
                type="incomplete",
                project="Jura Noosa",
                building="Block B",
                level="L02",
                unit="B-206",
                room="Bedroom",
                trade="Joinery",
                subcontractor="TrueLine Joinery",
                due_date="2026-07-03",
                description="First Jura incomplete work",
                created_by="Site Manager",
            )
        )

        self.assertEqual(first_jura.code, "JUR-DEF-1001")
        self.assertEqual(second_jura.code, "JUR-DEF-1002")
        self.assertEqual(first_meta.code, "MET-DEF-1001")
        self.assertEqual(first_jura_incomplete.code, "JUR-INC-1001")

    def test_locked_project_code_prefix_cannot_change(self) -> None:
        settings = self.store.snapshot().settings
        current_configs = dict(settings.project_configs)
        current_configs["Jura Noosa"] = current_configs["Jura Noosa"].model_copy(
            update={"code_prefix": "JUR", "code_prefix_locked": True}
        )
        current = settings.model_copy(update={"project_configs": current_configs})
        proposed_configs = dict(current.project_configs)
        proposed_configs["Jura Noosa"] = proposed_configs["Jura Noosa"].model_copy(update={"code_prefix": "JNO"})

        with self.assertRaises(SettingsLockError):
            validate_settings_update(current, current.model_copy(update={"project_configs": proposed_configs}))

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
        item = self.store.issue_item(item.id, to=item.subcontractor, by="Site Manager")
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

    def test_spreadsheet_import_helpers_parse_units_and_subcontractors(self) -> None:
        units = import_units_from_rows([["Unit", "Ignore"], ["U101", "x"], ["U102", "y"]])
        names, profiles = import_subcontractors_from_rows(
            [["Subcontractor", "Trade", "Contact", "Email", "Phone"], ["Acme Tiling", "Tiling", "A. Contact", "acme@example.com", "0400 000 000"]]
        )

        self.assertEqual(units, ["U101", "U102"])
        self.assertEqual(names, ["Acme Tiling"])
        self.assertEqual(profiles["Acme Tiling"].trade, "Tiling")
        self.assertEqual(profiles["Acme Tiling"].email, "acme@example.com")

    def test_report_actions_heading_layout_and_subcontractor_filter(self) -> None:
        item = self.create_item()
        other = self.store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="Block B",
                level="L02",
                unit="B-205",
                room="Bathroom",
                trade="Joinery",
                subcontractor="TrueLine Joinery",
                due_date="2026-07-01",
                description="Joinery item for another subcontractor",
                original_photos=["seed://amber/Joinery"],
                created_by="Site Manager",
            )
        )
        snapshot = self.store.snapshot()

        report = build_report_html(snapshot.items, snapshot.settings, "subcontractor", subcontractor="Sterling Tiling")

        self.assertIn("Return to reports", report)
        self.assertIn("Print Report", report)
        self.assertIn("Share Report", report)
        self.assertIn("Jura Noosa", report)
        self.assertIn("Noosa Heads", report)
        self.assertIn(item.code, report)
        self.assertNotIn(other.code, report)
        self.assertNotIn("<h2>Subcontractor Summary</h2>", report)

    def test_restored_ui_contains_register_tools_and_lifecycle_actions(self) -> None:
        root = Path(__file__).resolve().parents[1]
        html = (root / "app/static/index.html").read_text(encoding="utf-8")
        entry_script = (root / "app/static/app.js").read_text(encoding="utf-8")
        script = (root / "app/static/js/main.js").read_text(encoding="utf-8")
        styles = (root / "app/static/styles.css").read_text(encoding="utf-8")

        for element_id in ("statsBar", "searchInput", "statusFilter", "clearFilters", "saveBtn", "issueBtn"):
            self.assertIn(f'id="{element_id}"', html)
        for element_id in ("unitsImport", "subcontractorsImport", "reportSubcontractor"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('<script src="/static/voice-parser.js?v=3"></script>', html)
        self.assertIn('<script src="/static/voice-capture.js?v=3"></script>', html)
        self.assertIn('<link rel="stylesheet" href="/static/styles.css?v=4" />', html)
        self.assertIn('<body class="signed-out">', html)
        self.assertIn('<script src="/static/app.js?v=4"></script>', html)
        self.assertEqual(entry_script.strip(), 'import("/static/js/main.js?v=4");')
        self.assertIn("window.VoiceParser", (root / "app/static/voice-parser.js").read_text(encoding="utf-8"))
        self.assertIn("voiceRecordBtn", html)
        self.assertIn("projectCodePrefix", html)
        self.assertIn("lockProjectCodePrefix", script)
        self.assertIn("uploadSettingsSheet", script)
        self.assertIn('document.body.classList.toggle("signed-out"', script)
        self.assertIn("body.signed-out .hero-card", styles)
        self.assertIn("project: projectName()", script)
        self.assertIn("groupedItems(items).forEach", script)
        self.assertNotIn("groupedItems(items.slice(0, 30))", script)
        for action in ("data-rectify", "data-reject", "data-close", "data-comment"):
            self.assertIn(action, script)
        self.assertEqual(script.count("function renderItems()"), 1)
        self.assertIn(".action-bar", styles)
        self.assertIn("position: sticky", styles)

    def test_root_serves_full_field_app_by_default(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main = (root / "app/main.py").read_text(encoding="utf-8")
        full_app = (root / "CleanRun-IQ-Full-App-Render3/index.html").read_text(encoding="utf-8")

        self.assertIn('app.mount("/assets"', main)
        self.assertIn('legacy_app = LEGACY_EXPORT_DIR / "index.html"', main)
        self.assertNotIn("CLEANRUN_SERVE_LEGACY_EXPORT", main)
        self.assertIn("renderLogin", full_app)
        self.assertIn("bottom-nav", full_app)
        self.assertIn("enhancements.js?v=cards30", full_app)

    def test_plans_navigation_is_disabled_in_production_ui(self) -> None:
        root = Path(__file__).resolve().parents[1]
        index = (root / "CleanRun-IQ-Full-App-Render3/index.html").read_text(encoding="utf-8")
        enhancements = (root / "CleanRun-IQ-Full-App-Render3/assets/enhancements.js").read_text(encoding="utf-8")

        self.assertIn('next==="plans"', index)
        self.assertIn("Plans is coming soon", index)
        self.assertNotIn('PDF plans & pinned issue locations","plans"]', index)
        self.assertNotIn('["plans","Plans","⌖"]', enhancements)
        self.assertNotIn('PDF plans & pinned issue locations","plans"]', enhancements)

    def test_full_field_issue_now_uses_atomic_create(self) -> None:
        root = Path(__file__).resolve().parents[1]
        enhancements = (root / "CleanRun-IQ-Full-App-Render3/assets/enhancements.js").read_text(encoding="utf-8")
        full_app = (root / "CleanRun-IQ-Full-App-Render3/index.html").read_text(encoding="utf-8")

        for source in (enhancements, full_app):
            self.assertIn("/api/items?issue_now=true", source)
            self.assertNotIn('if(mode==="issue")await api(`/api/items/${item.id}/actions/issue`', source)


if __name__ == "__main__":
    unittest.main()
