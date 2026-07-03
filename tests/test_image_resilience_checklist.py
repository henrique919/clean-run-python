"""Image resilience batch — static source checks (local).

Covers the client half of expired-photo recovery and the Share Report
mid-size inline path, which have no server-side execution to unit test.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from app.reporting import SHARE_REPORT_SCRIPT

ROOT = Path(__file__).resolve().parents[1] / "CleanRun-IQ-Full-App-Render3"
ENHANCEMENTS = ROOT / "assets" / "enhancements.js"


class ImageResilienceChecklist(unittest.TestCase):
    def setUp(self) -> None:
        self.enh = ENHANCEMENTS.read_text(encoding="utf-8")

    def test_error_recovery_handler_present(self) -> None:
        self.assertIn('document.addEventListener("error"', self.enh)
        self.assertIn("/api/photos/refresh-url", self.enh)
        self.assertIn("crPhotoRetry", self.enh)
        self.assertIn("patchStatePhotoUrl", self.enh)
        self.assertIn("photoUnavailablePlaceholder", self.enh)

    def test_refresh_call_bypasses_offline_queue_wrapper(self) -> None:
        # The offline wrapper fakes success ({queued:true}) for unknown POSTs;
        # the refresh call must use the raw networkApi so failures placeholder.
        self.assertIn('networkApi("/api/photos/refresh-url"', self.enh)

    def test_placeholders_reuse_existing_styles(self) -> None:
        self.assertIn('"cr-card-photo empty"', self.enh)
        self.assertIn('"review-photo-placeholder"', self.enh)

    def test_share_script_prefers_mid_size_and_falls_back(self) -> None:
        self.assertIn('img.getAttribute("data-share-src")', SHARE_REPORT_SCRIPT)
        self.assertIn("candidates", SHARE_REPORT_SCRIPT)
        # Original src stays a candidate so a failed transform fetch degrades gracefully.
        self.assertIn('[img.getAttribute("data-share-src"),src]', SHARE_REPORT_SCRIPT)
        # Print path: original srcs restored after the share file is built.
        self.assertIn("restore.forEach(([img,src])=>img.setAttribute(\"src\",src))", SHARE_REPORT_SCRIPT)


if __name__ == "__main__":
    unittest.main()
