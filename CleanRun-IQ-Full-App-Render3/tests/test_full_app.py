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

        guard_item = self.app.create_item(
            {
                "type": "defect",
                "project": "Jura Noosa",
                "description": "Workflow guard",
                "trade": "Tiling",
                "subcontractor": "Sterling Tiling",
                "dueDate": self.app.day_iso(2),
                "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
            }
        )
        with self.assertRaisesRegex(ValueError, "cannot perform 'rectification' while item is open"):
            self.app.apply_action(guard_item, "rectification", {"photo": "data:image/png;base64,iVBORw0KGgo=", "by": "Trade"})

        issued = self.app.create_item_from_request(
            {
                "id": "capture-repeat-001",
                "type": "defect",
                "project": "Jura Noosa",
                "description": "Repeated Issue Now tap",
                "trade": "Joinery",
                "subcontractor": "Endeavour Cleaning",
                "dueDate": self.app.day_iso(2),
                "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
                "createdBy": "Site Manager",
                "issueOnCreate": True,
                "issueTo": "Endeavour Cleaning",
            }
        )
        repeated = self.app.create_item_from_request(
            {
                "id": "capture-repeat-001",
                "type": "defect",
                "project": "Jura Noosa",
                "description": "Repeated Issue Now tap",
                "trade": "Joinery",
                "subcontractor": "Endeavour Cleaning",
                "dueDate": self.app.day_iso(2),
                "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
                "createdBy": "Site Manager",
                "issueOnCreate": True,
                "issueTo": "Endeavour Cleaning",
            }
        )
        self.assertIs(issued, repeated)
        self.assertEqual(issued["status"], "issued")
        self.assertEqual(len([i for i in self.app.STATE["items"] if i["id"] == "capture-repeat-001"]), 1)
        self.assertEqual(len(issued["issueHistory"]), 1)

        report = self.app.report_html("handover")
        self.assertIn("Smarter Field. Cleaner Builds.", report)
        self.assertIn('/assets/banner.png', report)
        self.assertIn('href="/"', report)
        self.assertIn("Print / Save PDF", report)
        self.assertIn("Executive Summary", report)
        self.assertIn("Item Index", report)

        page = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('const navs=["home","items","capture","review","more"]', page)
        self.assertIn("loading-shell", page)
        self.assertIn("Loading closeout record", page)
        for feature in ("Take Photo", "Upload Photo", "Voice-to-Note", "Subcontractor Mode", "Project Setup", "Reports & Handover"):
            self.assertIn(feature, page)
        self.assertIn("application/pdf,.pdf", page)
        self.assertIn("function isPdfPlan", page)
        self.assertIn("plan-pdf", page)
        self.assertIn("/assets/chevrons.svg", page)
        self.assertIn("siteStatus", page)
        self.assertIn("cr-item-card", page)
        self.assertIn("In Progress','Ready", page)
        self.assertIn("enhancements.css?v=cards53", page)
        self.assertIn("enhancements.js?v=cards53", page)
        self.assertIn("format-dates.js?v=cards53", page)
        self.assertIn("review:reviewView", page)
        self.assertIn("ready for supervisor review", page)
        self.assertIn("location.href='/api/reports/${id}'", page)
        self.assertIn("[hidden]{display:none!important}", page)
        self.assertNotIn("#FF6A00", page.upper())

    def test_photo_admin_report_and_offline_enhancements(self) -> None:
        photo = "data:image/png;base64,iVBORw0KGgo="
        meta = {"capturedAt": self.app.now_iso(), "latitude": -27.4698, "longitude": 153.0251, "accuracy": 8}
        item = self.app.create_item(
            {
                "id": "offline-retro-test",
                "type": "defect",
                "project": "Jura Noosa",
                "description": "Retrospective evidence and report gallery test",
                "trade": "Painting",
                "subcontractor": "Coastline Painting",
                "dueDate": self.app.day_iso(2),
                "originalPhotos": [photo, photo],
                "originalPhotoMeta": [meta, meta],
                "createdBy": "Site Manager",
            }
        )
        self.app.apply_action(item, "issue", {"to": "Coastline Painting", "by": "Site Manager"})
        self.app.apply_action(item, "in-progress", {"by": "Coastline Painting"})
        self.app.apply_action(item, "rectification", {"photo": photo, "photoMeta": meta, "comment": "Repaired", "by": "Trade"})
        report = self.app.report_html("open")
        self.assertIn('class="photo-grid', report)
        self.assertGreaterEqual(report.count('class="photo"'), 3)
        self.assertIn("Geo-tag -27.46980, 153.02510", report)
        self.assertIn("font-size:16px", report)

        register = self.app.report_html("register")
        self.assertIn("Project Defect Register", register)
        self.assertIn("Evidence completion", register)
        self.assertIn("Item Index", register)

        exceptions = self.app.report_html("exceptions")
        self.assertIn("Exceptions Report", exceptions)
        self.assertIn("Missing rectification evidence", exceptions)
        self.assertIn("Exception flags", exceptions)

        enhancements = (ROOT / "assets" / "enhancements.js").read_text(encoding="utf-8")
        styles = (ROOT / "assets" / "enhancements.css").read_text(encoding="utf-8")
        worker = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        for marker in ("addEditPhotos", "markupEvidencePhoto", "originalPhotoMeta", "navigator.geolocation", "cleanrun-offline-queue-v1", "format-dates.js", "issueHistoryForItem", "originalPhotoThumbnails", 'loading="lazy"', "shareReport", "supportsImageBitmapOrientation", "isImageFile", "returnToReports", "buildCaptureDefaultsPanel", "selectOptionsWithRecents", "cleanrun-capture-recents-v1", "photo-markup-btn", "expandCaptureDefaultsSections"):
            self.assertIn(marker, enhancements)
        for marker in ("markupTool", "circle", "box", "arrow", "Text box", "fileToUploadData", "MAX_PHOTO_EDGE", "openHomeBucket", "openDashboardSearch", "Closeout control room", "Subcontractor performance", "Trade pressure", "Today's schedule", "toggleDesktopTheme", "Subcontractor database", "THEME_KEY", "photoCount", "Incomplete Work", "LAST_CAPTURE_KEY", "reviewView", "renderMobileNav", "Closeout workflow", "captureSubmitting", "captureRequestId", "issueOnCreate", "oncancel", "controllerchange", "SKIP_WAITING", "subcontractorAdminPanel", "Dark / night mode", "No email", "Assigned work mode", "siteStatus", "CAPTURED", "IN PROGRESS", "cr-issue-cta", "Captured\",\"Issued\",\"In Progress", "cardAction", "reviewCloseout", "reviewReject", "signature-pad", "cardActionLocks", "openCommandPalette", "runCommand", "Command Palette", "Issue DEF-022 to AquaSeal", "Find all open items Block A L02", "commandHomeBar", "lockProjectCodePrefix", "toggleItemFilters", "labelIconButtons", "cardHeadline"):
            self.assertIn(marker, enhancements)
        self.assertIn("renderDesktopNav", enhancements)
        self.assertIn('"reports","Reports"', enhancements)
        self.assertIn('"subcontractor","Subcontractors"', enhancements)
        self.assertIn("@media(min-width:1024px)", styles)
        self.assertIn(".item-sub", styles)
        self.assertIn("graphiteDrift", styles)
        self.assertIn("border-left:6px solid #121619", styles)
        self.assertIn(".offline-pill{position:fixed;z-index:60;right:14px;top:14px", styles)
        self.assertIn(".offline-pill.waiting{opacity:.15", styles)
        self.assertIn(".photo-required-pulse", styles)
        self.assertIn(".capture-defaults-strip", styles)
        self.assertIn(".photo-markup-btn", styles)
        self.assertIn(".review-grid", styles)
        self.assertIn(".review-compare", styles)
        self.assertIn(".review-decision-row", styles)
        self.assertIn("border-left:6px solid", styles)
        self.assertNotIn("Location unavailable", enhancements)
        self.assertIn(".cr-card-band", styles)
        self.assertIn("background:#DDE1E5", styles)
        self.assertIn(".cr-card-location", styles)
        self.assertIn(".home-dashboard", styles)
        self.assertIn(".dashboard-kpi", styles)
        self.assertIn(".dashboard-row", styles)
        self.assertIn(".command-home", styles)
        self.assertIn(".command-palette", styles)
        self.assertIn(".cr-card-photo", styles)

    def test_repeated_actions_do_not_explode_audit_history(self) -> None:
        item = self.app.create_item(
            {
                "type": "defect",
                "project": "Jura Noosa",
                "description": "Repeated button press",
                "trade": "Painting",
                "subcontractor": "Coastline Painting",
                "dueDate": self.app.day_iso(2),
                "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
                "createdBy": "Site Manager",
            }
        )

        self.app.apply_action(item, "issue", {"to": "Coastline Painting", "by": "Site Manager"})
        self.app.apply_action(item, "issue", {"to": "Coastline Painting", "by": "Site Manager"})
        self.app.apply_action(item, "issue", {"to": "Coastline Painting", "by": "Site Manager"})
        self.assertEqual(len(item["issueHistory"]), 1)
        self.assertEqual(len([event for event in item["auditEvents"] if event["action"] == "Issued to Coastline Painting"]), 1)

        self.app.apply_action(item, "in-progress", {"by": "Site Manager"})
        self.app.apply_action(item, "in-progress", {"by": "Site Manager"})
        self.assertEqual(len([event for event in item["auditEvents"] if event["action"] == "Marked in progress"]), 1)

    def test_enhancement_source_contains_card_focus_and_plan_fit_controls(self) -> None:
        enhancements = (ROOT / "assets" / "enhancements.js").read_text(encoding="utf-8")
        styles = (ROOT / "assets" / "enhancements.css").read_text(encoding="utf-8")
        worker = (ROOT / "service-worker.js").read_text(encoding="utf-8")

        for marker in (
            "FOCUS_MODES",
            "Items page focus",
            "focus-controls",
            "itemProjectScope",
            "itemBuildingValue",
            "cr-card-date under-photo",
            "plan-fit-controls",
            "savePlanFit",
            "fitLocked",
            "toolbar=0",
        ):
            self.assertIn(marker, enhancements)
        for marker in (
            ".cr-card-date.under-photo",
            "border-top:var(--rail-width) solid var(--rail)",
            ".focus-controls",
            ".plan-fit-controls",
            ".plan.pdf .plan-pdf",
        ):
            self.assertIn(marker, styles)
        self.assertIn(".cr-card-sub{text-transform:none", styles)
        self.assertIn(".cr-item-card.status-rejected", styles)
        self.assertIn('html[data-theme="dark"]', styles)
        self.assertIn(".sub-profile-card", styles)
        self.assertIn('button[onclick="startDictation()"]', styles)
        self.assertIn("cleanrun-iq-shell-v22", worker)
        self.assertIn("client.navigate", worker)
        self.assertIn("NETWORK_FIRST", worker)
        self.assertIn("indexedDB", enhancements)

    def test_supabase_photo_uploads_replace_raw_base64_for_create_edit_and_actions(self) -> None:
        photo = "data:image/png;base64,iVBORw0KGgo="
        previous_storage = os.environ.get("CLEANRUN_STORAGE")
        os.environ["CLEANRUN_STORAGE"] = "supabase"

        class FakeBucket:
            def __init__(self) -> None:
                self.uploads = []

            def upload(self, path, file, file_options=None):
                self.uploads.append({"path": path, "file": file, "file_options": file_options or {}})
                return {"path": path}

            def get_public_url(self, path):
                return f"https://example.supabase.co/storage/v1/object/public/cleanrun-evidence/{path}"

        class FakeStorage:
            def __init__(self, bucket) -> None:
                self.bucket = bucket

            def from_(self, name):
                self.bucket.name = name
                return self.bucket

        class FakeClient:
            def __init__(self) -> None:
                self.bucket = FakeBucket()
                self.storage = FakeStorage(self.bucket)

        fake = FakeClient()
        original_get_client = self.app.get_supabase_client
        self.app.get_supabase_client = lambda: fake

        try:
            item = self.app.create_item(
                {
                    "type": "defect",
                    "project": "Jura Noosa",
                    "description": "Supabase evidence test",
                    "trade": "Electrical",
                    "subcontractor": "Northline Electrical",
                    "dueDate": self.app.day_iso(2),
                    "originalPhotos": [photo],
                    "createdBy": "Site Manager",
                }
            )
            self.assertTrue(item["originalPhotos"][0].startswith("https://example.supabase.co/"))
            self.assertIn(f"items/{item['id']}/original/", fake.bucket.uploads[0]["path"])
            self.assertIsInstance(fake.bucket.uploads[0]["file"], bytes)

            self.app.apply_action(item, "issue", {"to": "Northline Electrical", "by": "Site Manager"})
            self.app.apply_action(item, "in-progress", {"by": "Northline Electrical"})
            self.app.apply_action(item, "rectification", {"photo": photo, "comment": "Done", "by": "Trade"})
            self.assertTrue(item["rectificationEvidence"][0]["photo"].startswith("https://example.supabase.co/"))
            self.assertIn(f"items/{item['id']}/rectification/", fake.bucket.uploads[1]["path"])

            replacement = self.app.upload_photo_list(item["originalPhotos"] + [photo], folder=f"items/{item['id']}/original")
            item["originalPhotos"] = replacement
            self.assertEqual(len(item["originalPhotos"]), 2)
            self.assertTrue(item["originalPhotos"][1].startswith("https://example.supabase.co/"))
            self.assertNotIn("data:image", "".join(item["originalPhotos"]))
        finally:
            self.app.get_supabase_client = original_get_client
            if previous_storage is None:
                os.environ.pop("CLEANRUN_STORAGE", None)
            else:
                os.environ["CLEANRUN_STORAGE"] = previous_storage

    def test_supabase_plan_pdf_asset_upload_and_admin_profile_shape(self) -> None:
        previous_storage = os.environ.get("CLEANRUN_STORAGE")
        previous_url = os.environ.get("SUPABASE_URL")
        previous_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        os.environ.pop("CLEANRUN_STORAGE", None)
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "service-role"
        self.assertTrue(self.app.use_supabase_storage())

        os.environ["CLEANRUN_STORAGE"] = "supabase"

        class FakeBucket:
            def __init__(self) -> None:
                self.uploads = []

            def upload(self, path, file, file_options=None):
                self.uploads.append({"path": path, "file": file, "file_options": file_options or {}})
                return {"path": path}

            def get_public_url(self, path):
                return f"https://example.supabase.co/storage/v1/object/public/cleanrun-evidence/{path}"

        class FakeStorage:
            def __init__(self, bucket) -> None:
                self.bucket = bucket

            def from_(self, name):
                return self.bucket

        class FakeClient:
            def __init__(self) -> None:
                self.bucket = FakeBucket()
                self.storage = FakeStorage(self.bucket)

        fake = FakeClient()
        original_get_client = self.app.get_supabase_client
        self.app.get_supabase_client = lambda: fake

        try:
            url = self.app.maybe_upload_plan_asset("data:application/pdf;base64,JVBERi0xLjQ=", folder="plans/Jura Noosa")
            self.assertTrue(url.startswith("https://example.supabase.co/"))
            self.assertIn("plans/Jura Noosa/", fake.bucket.uploads[0]["path"])
            self.assertEqual(fake.bucket.uploads[0]["file_options"]["content-type"], "application/pdf")

            state = {
                "settings": {"activeProject": "Jura Noosa"},
                "items": [
                    {
                        "id": "inline-migration",
                        "originalPhotos": ["data:image/png;base64,iVBORw0KGgo="],
                        "rectificationEvidence": [{"photo": "data:image/png;base64,iVBORw0KGgo="}],
                        "closeoutEvidence": [{"photo": "data:image/png;base64,iVBORw0KGgo="}],
                    }
                ],
                "plans": [{"project": "Jura Noosa", "image": "data:application/pdf;base64,JVBERi0xLjQ="}],
            }
            changed = self.app.migrate_inline_state_assets(state)
            self.assertEqual(changed, 4)
            self.assertNotIn("data:", str(state))
            self.assertGreaterEqual(len(fake.bucket.uploads), 5)
        finally:
            self.app.get_supabase_client = original_get_client
            if previous_storage is None:
                os.environ.pop("CLEANRUN_STORAGE", None)
            else:
                os.environ["CLEANRUN_STORAGE"] = previous_storage
            if previous_url is None:
                os.environ.pop("SUPABASE_URL", None)
            else:
                os.environ["SUPABASE_URL"] = previous_url
            if previous_service_key is None:
                os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            else:
                os.environ["SUPABASE_SERVICE_ROLE_KEY"] = previous_service_key

        settings = self.app.default_settings()
        profile = settings["subProfiles"]["Coastline Painting"]
        self.assertIn("companyName", profile)
        self.assertIn("tradeType", profile)
        self.assertIn("mobile", profile)
        self.assertIsInstance(profile["contacts"], list)
        self.assertEqual(settings["theme"], "light")


if __name__ == "__main__":
    unittest.main()
