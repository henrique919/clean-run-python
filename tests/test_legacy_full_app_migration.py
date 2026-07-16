"""Coverage migrated from the retired legacy suite (issue #67).

CleanRun-IQ-Full-App-Render3/tests/test_full_app.py targeted the obsolete
monolithic root app (`cleanrun_root_app.default_state` etc.) and failed 7/13
against the current backend. Per LOOP_BACKLOG.md TEST-01, still-relevant
coverage moves here against the canonical `app/` backend and the live Render3
sources; everything else is either already covered in `tests/` (cited in the
TEST-01 PR) or obsolete (Plans UI is deferred and unreachable in production).
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from app.models import ItemCreate, ItemType
from app.store import CleanRunStore
from app.validation import ValidationError
from app.workflow import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
RENDER3 = ROOT / "CleanRun-IQ-Full-App-Render3"


def _capture_payload(**overrides) -> ItemCreate:
    data = dict(
        type=ItemType.DEFECT,
        project="Jura Noosa",
        building="B1",
        level="Level 1",
        unit="U101",
        room="Bathroom",
        trade="Tiling",
        subcontractor="ASTW Tiling",
        due_date="2026-08-01",
        description="Migrated validation test item",
        original_photos=["seed://photo"],
        created_by="Site Manager",
    )
    data.update(overrides)
    return ItemCreate(**data)


class CaptureValidationMigrationTests(unittest.TestCase):
    """Photo-required validation + repeated-action stability (legacy tests 2 and 4)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_defect_without_photo_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "requires at least one original photo"):
            self.store.create_item(_capture_payload(original_photos=[]))

    def test_client_defect_without_photo_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "requires at least one original photo"):
            self.store.create_item(
                _capture_payload(type=ItemType.CLIENT, raised_by="Client walkthrough", original_photos=[])
            )

    def test_incomplete_work_saves_without_photo(self) -> None:
        item = self.store.create_item(_capture_payload(type=ItemType.INCOMPLETE, original_photos=[]))
        self.assertEqual(item.original_photos, [])

    def test_repeated_issue_is_blocked_and_history_stays_stable(self) -> None:
        item = self.store.create_item(_capture_payload())
        item = self.store.issue_item(item.id, to="ASTW Tiling", by="Site Manager")
        self.assertEqual(len(item.issue_history), 1)
        # The legacy monolith silently de-duplicated repeats; the canonical
        # workflow guard rejects them outright — either way history must not grow.
        with self.assertRaises(WorkflowError):
            self.store.issue_item(item.id, to="ASTW Tiling", by="Site Manager")
        current = next(i for i in self.store.snapshot().items if i.id == item.id)
        self.assertEqual(len(current.issue_history), 1)
        issue_audits = [e for e in current.audit_events if e.action == "Issued to ASTW Tiling"]
        self.assertEqual(len(issue_audits), 1)


class CaptureDueDateSourceTests(unittest.TestCase):
    """Migrated verbatim: capture due date defaults to today + 7 (cards59)."""

    def test_capture_due_date_defaults_to_today_plus_seven(self) -> None:
        enhancements = (RENDER3 / "assets" / "enhancements.js").read_text(encoding="utf-8")
        self.assertIn("const CAPTURE_DUE_DAYS=7", enhancements)
        self.assertIn("function ensureCaptureDueDate", enhancements)
        self.assertIn("function localIsoDate", enhancements)
        self.assertRegex(enhancements, r"due\.setDate\(due\.getDate\(\)\+days\)")
        self.assertIn("ensureCaptureDueDate(form)", enhancements)
        self.assertIn('el?.name==="project"', enhancements)
        self.assertIn('ensureCaptureDueDate($("#app form"),el.value)', enhancements)
        self.assertIn('if(route==="capture")applyCaptureDefaults()', enhancements)
        self.assertIn('name="dueDate" value="${due}"', enhancements)
        self.assertIn("const due=defaultCaptureDueDate()", enhancements)
        self.assertIn(
            "data.dueDate=defaultCaptureDueDate(data.project||state.settings.activeProject)", enhancements
        )


class ReportScopePickerSourceTests(unittest.TestCase):
    """Migrated verbatim: report scope picker stays compact on desktop (cards59)."""

    def test_report_scope_picker_stays_compact_on_desktop(self) -> None:
        styles = (RENDER3 / "assets" / "enhancements.css").read_text(encoding="utf-8")
        self.assertIn(".report-scope-option,", styles)
        self.assertIn("grid-template-columns:18px minmax(0,1fr)!important", styles)
        self.assertIn('.report-scope-option input[type="radio"]', styles)
        self.assertIn("width:18px", styles)


class ItemsFocusSourceTests(unittest.TestCase):
    """Salvaged from legacy test 5: Items focus controls (plan-fit markers dropped — Plans is deferred)."""

    def test_items_focus_controls_present(self) -> None:
        enhancements = (RENDER3 / "assets" / "enhancements.js").read_text(encoding="utf-8")
        for marker in ("FOCUS_MODES", "focus-controls", "itemProjectScope", "itemBuildingValue"):
            self.assertIn(marker, enhancements)
        styles = (RENDER3 / "assets" / "enhancements.css").read_text(encoding="utf-8")
        self.assertIn(".focus-controls", styles)


class SignOffModalSourceTests(unittest.TestCase):
    """Migrated verbatim: sign-off ceremony avoids native dialogs (cards61)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.enhancements = (RENDER3 / "assets" / "enhancements.js").read_text(encoding="utf-8")

    def _fn_body(self, name: str) -> str:
        patterns = [
            rf"{re.escape(name)}=(?:async )?function\([^)]*\)\{{",
            rf"window\.{re.escape(name)}=(?:async )?function\([^)]*\)\{{",
        ]
        start = None
        for pattern in patterns:
            match = re.search(pattern, self.enhancements)
            if match:
                start = match.end() - 1
                break
        self.assertIsNotNone(start, f"missing function {name}")
        depth = 0
        for index in range(start, len(self.enhancements)):
            char = self.enhancements[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return self.enhancements[start : index + 1]
        self.fail(f"unclosed function body for {name}")

    def test_issue_close_reject_avoid_native_dialogs(self) -> None:
        for fn in ("cardAction", "reviewReject", "submitReviewRejectForm"):
            body = self._fn_body(fn)
            self.assertNotIn("prompt(", body, fn)
            self.assertNotIn("confirm(", body, fn)
        item_body = self._fn_body("itemAction")
        self.assertNotIn('prompt("Subcontractor name:', item_body)
        self.assertNotIn('prompt("Why is this being rejected?', item_body)
        self.assertNotIn('prompt("Signed off by role:', item_body)
        self.assertNotIn("confirm(`I confirm this item", item_body)
        self.assertIn('act==="close")return reviewCloseout', item_body)
        self.assertIn('act==="reject")return reviewReject', item_body)

    def test_close_routes_through_signature_modal(self) -> None:
        body = self._fn_body("itemAction")
        self.assertIn('act==="close")return reviewCloseout', body)

    def test_edit_priority_no_change_default(self) -> None:
        self.assertIn("editPrioritySelectHtml", self.enhancements)
        self.assertIn('value="" selected>— No change —', self.enhancements)
        self.assertIn("if(!data.priority)delete data.priority", self.enhancements)
        self.assertIn('if(current==="high")', self.enhancements)

    def test_reject_outline_and_subcontractor_sheet(self) -> None:
        self.assertIn("review-reject-outline", self.enhancements)
        self.assertIn("pickSubcontractor", self.enhancements)
        self.assertIn("bottomSheet", self.enhancements)
        styles = (RENDER3 / "assets" / "enhancements.css").read_text(encoding="utf-8")
        self.assertIn(".review-reject-outline", styles)
        self.assertIn("border:2px solid #B42318", styles)


if __name__ == "__main__":
    unittest.main()
