from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_root_app(data_file: Path):
    os.environ["CLEANRUN_DATA_FILE"] = str(data_file)
    spec = importlib.util.spec_from_file_location("cleanrun_root_app", ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FullFieldAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.app = load_root_app(Path(cls.temp_dir.name) / "cleanrun.json")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self.app.STATE = self.app.default_state()

    def test_voice_capture_assignment_and_full_closeout_lifecycle(self) -> None:
        parsed = self.app.parse_transcript(
            "Urgent cracked tile in Block B level two unit B-204 bathroom. "
            "Assign Tiling to Sterling Tiling due tomorrow."
        )
        self.assertEqual(parsed["building"], "Block B")
        self.assertEqual(parsed["level"], "L02")
        self.assertEqual(parsed["unit"], "B-204")
        self.assertEqual(parsed["room"], "Bathroom")
        self.assertEqual(parsed["trade"], "Tiling")
        self.assertEqual(parsed["subcontractor"], "Sterling Tiling")
        self.assertEqual(parsed["priority"], "urgent")

        payload = {
            **parsed,
            "type": "defect",
            "project": "Jura Noosa",
            "dueDate": self.app.day_iso(1),
            "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
            "voiceTranscript": "Cracked tile voice note",
            "createdBy": "Site Manager",
        }
        item = self.app.create_item(payload)
        self.app.apply_action(item, "issue", {"to": "Sterling Tiling", "by": "Site Manager"})
        self.app.apply_action(item, "in-progress", {"by": "Sterling Tiling"})
        self.app.apply_action(
            item,
            "rectification",
            {"photo": "data:image/png;base64,iVBORw0KGgo=", "comment": "Tile replaced", "by": "Sterling Tiling", "advanceToReady": True},
        )
        self.app.apply_action(item, "inspect", {"by": "Site Manager"})
        self.app.apply_action(item, "reject", {"by": "Site Manager", "reason": "Regrout edge"})
        self.app.apply_action(item, "issue", {"to": "Sterling Tiling", "by": "Site Manager", "reissue": True})
        self.app.apply_action(item, "in-progress", {"by": "Sterling Tiling"})
        self.app.apply_action(item, "ready", {"by": "Sterling Tiling"})
        self.app.apply_action(item, "inspect", {"by": "Site Manager"})
        self.app.apply_action(item, "comment", {"by": "Site Manager", "text": "Final inspection passed"})
        self.app.apply_action(
            item,
            "close",
            {"by": "Site Manager", "role": "Supervisor", "note": "Accepted", "photo": "data:image/png;base64,iVBORw0KGgo=", "confirmed": True},
        )

        self.assertEqual(item["status"], "closed")
        self.assertEqual(len(item["originalPhotos"]), 1)
        self.assertEqual(len(item["rectificationEvidence"]), 1)
        self.assertEqual(len(item["closeoutEvidence"]), 1)
        self.assertEqual(len(item["comments"]), 1)
        self.assertGreaterEqual(len(item["issueHistory"]), 2)
        self.assertGreaterEqual(len(item["inspectionHistory"]), 3)
        self.assertGreaterEqual(len(item["auditEvents"]), 10)

    def test_photo_validation_reports_and_complete_taskbar_ui(self) -> None:
        with self.assertRaisesRegex(ValueError, "require at least one original photo"):
            self.app.create_item(
                {
                    "type": "defect",
                    "project": "Jura Noosa",
                    "description": "Missing evidence",
                    "dueDate": self.app.day_iso(2),
                    "originalPhotos": [],
                }
            )

        report = self.app.report_html("handover")
        self.assertIn("Smarter Field. Cleaner Builds.", report)
        self.assertIn('/assets/banner.png', report)
        self.assertIn('href="/"', report)
        self.assertIn("Print / Save PDF", report)

        page = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('const navs=["home","items","capture","plans","more"]', page)
        for feature in ("Take Photo", "Upload Photo", "Voice-to-Note", "Subcontractor Mode", "Project Setup", "Reports & Handover"):
            self.assertIn(feature, page)
        self.assertIn("application/pdf,.pdf", page)
        self.assertIn("function isPdfPlan", page)
        self.assertIn("plan-pdf", page)
        self.assertIn("/assets/chevrons.svg", page)
        self.assertIn("location.href='/api/reports/${id}'", page)
        self.assertIn("[hidden]{display:none!important}", page)
        self.assertNotIn("#FF6A00", page.upper())


if __name__ == "__main__":
    unittest.main()
