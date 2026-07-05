"""Batch H — capture draft persistence (UX-03) and visible sync pill (UX-04)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENHANCEMENTS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.js"
CSS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.css"


class BatchHCaptureDraftChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.enh = ENHANCEMENTS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")

    def test_capture_draft_persistence_markers(self) -> None:
        for marker in (
            "cleanrun-capture-draft-v1",
            "CAPTURE_DRAFT_KEY",
            "scheduleCaptureDraftSave",
            "persistCaptureDraft",
            "clearCaptureDraft",
            "restoreCaptureDraft",
            "discardCaptureDraft",
            "refreshCaptureDraftBar",
            "Unsaved item from",
            "capture-draft-bar",
            "MAX_CAPTURE_DRAFT_PHOTOS",
            "dbDelete",
        ):
            self.assertIn(marker, self.enh, marker)

    def test_draft_hooks_do_not_block_save_path(self) -> None:
        self.assertIn("scheduleCaptureDraftSave()", self.enh)
        self.assertIn("CAPTURE_DRAFT_DEBOUNCE_MS", self.enh)
        self.assertIn("captureDraftRestoring", self.enh)
        self.assertIn("await clearCaptureDraft()", self.enh)
        save_at = self.enh.index("saveCapture=async function")
        save_block = self.enh[save_at : save_at + 3200]
        self.assertIn("await clearCaptureDraft()", save_block)
        self.assertIn("resetCaptureForNext", save_block)

    def test_restore_bar_styles(self) -> None:
        for marker in (
            ".capture-draft-bar",
            ".capture-draft-bar__actions",
        ):
            self.assertIn(marker, self.css, marker)


class BatchHSyncPillChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.enh = ENHANCEMENTS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")

    def test_sync_pill_states(self) -> None:
        for marker in (
            "Synced ✓",
            "Syncing ${count}…",
            "Offline · ${count} queued",
            "openSyncQueueSheet",
            "queueEntrySummary",
            "item${sent===1?\"\":\"s\"} synced",
        ):
            self.assertIn(marker, self.enh, marker)

    def test_sync_pill_always_visible_css(self) -> None:
        self.assertIn(".offline-pill.synced", self.css)
        self.assertNotIn(".offline-pill.waiting{opacity:.15", self.css)
        self.assertIn("opacity:1", self.css)

    def test_sync_queue_sheet_uses_bottom_sheet(self) -> None:
        self.assertIn('$("#bottomSheetTitle").textContent="Queued to sync"', self.enh)
        self.assertIn("sync-queue-row", self.enh)
