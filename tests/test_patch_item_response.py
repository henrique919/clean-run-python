"""PATCH /api/items/{id} response shape and timing diagnostics."""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer


class PatchItemResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_patch_returns_camel_case_with_prefetched_photos(self) -> None:
        item = self.store.snapshot().items[0]

        with patch.object(app_main, "prefetch_item_photo_urls") as prefetch:
            response = self.client.patch(
                f"/api/items/{item.id}",
                headers=bearer("dev-site-manager"),
                json={"description": "Updated via PATCH"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["description"], "Updated via PATCH")
        self.assertIn("originalPhotos", payload)
        self.assertIn("updatedAt", payload)
        self.assertNotIn("original_photos", payload)
        prefetch.assert_called_once()

    def test_patch_logs_structured_timing(self) -> None:
        item = self.store.snapshot().items[0]

        with self.assertLogs("app.main", level="INFO") as logs:
            response = self.client.patch(
                f"/api/items/{item.id}",
                headers=bearer("dev-site-manager"),
                json={"description": "Timing check"},
            )

        self.assertEqual(response.status_code, 200)
        joined = "\n".join(logs.output)
        self.assertIn("PATCH item timing", joined)
        self.assertIn("prefetch_sign=", joined)


if __name__ == "__main__":
    unittest.main()
