"""Phase 2 capture flow speed — static source checks (local)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "CleanRun-IQ-Full-App-Render3"
ENHANCEMENTS = ROOT / "assets" / "enhancements.js"
STYLES = ROOT / "assets" / "enhancements.css"


class Phase2LocalChecklist(unittest.TestCase):
    def setUp(self) -> None:
        self.enh = ENHANCEMENTS.read_text(encoding="utf-8")
        self.css = STYLES.read_text(encoding="utf-8")

    def test_build_tag_cards51(self) -> None:
        self.assertIn('CLEANRUN_FRONTEND_BUILD="cards51"', self.enh)

    def test_defaults_strip_containment(self) -> None:
        for marker in (
            "buildCaptureDefaultsPanel",
            "capture-defaults-strip",
            "expandCaptureDefaultsSections",
            "collapseCaptureDefaultsSections",
            "updateCaptureDefaultsStrip",
            "hasProjectCaptureDefaults",
            "strip-draft-changed",
            "expandCaptureSectionForInvalid",
        ):
            self.assertIn(marker, self.enh)

    def test_recents_in_dropdowns(self) -> None:
        self.assertIn("cleanrun-capture-recents-v1", self.enh)
        self.assertIn("selectOptionsWithRecents", self.enh)
        self.assertIn('label="Recent"', self.enh)
        self.assertIn("recordCaptureRecents", self.enh)

    def test_markup_arrow_default(self) -> None:
        self.assertIn('<option value="arrow">Arrow</option>', self.enh)
        self.assertIn('tool.value="arrow"', self.enh)

    def test_prominent_markup_no_auto_open(self) -> None:
        self.assertIn("photo-markup-btn", self.enh)
        self.assertIn(".photo-markup-btn", self.css)
        self.assertNotIn("openWorkbench(src", self.enh.split("loadCapturePhotos")[1].split("appendCapturePreview")[0])

    def test_voice_draft_strip_hook(self) -> None:
        self.assertIn("captureDraftHighlights", self.enh)
        self.assertIn("captureDescriptionEdited", self.enh)
        self.assertIn("preserveDescription", self.enh)

    def test_save_skips_background_reload(self) -> None:
        self.assertIn("applyCardActionResult", self.enh)
        self.assertIn("stateNeedsGlobalRefresh=true", self.enh)
        self.assertNotIn("reload().then(fresh=>{state=fresh;walkMode=true", self.enh)

    def test_perf_signing_helpers_present(self) -> None:
        self.assertIn("stateNeedsGlobalRefresh", self.enh)
        self.assertIn("baseGo=go", self.enh)


if __name__ == "__main__":
    unittest.main()
