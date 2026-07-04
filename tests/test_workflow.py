from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.models import CloseoutEvidence, ItemCreate, ItemUpdate
from app.storage import StorageUploadError, _split_data_url
from app.store import CleanRunStore
from app.validation import ValidationError
from app.workflow import WorkflowError
from tests.test_auth_permissions import AsgiClient, bearer


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_open_item(self):
        return self.store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="B1",
                level="Level 1",
                unit="U101",
                room="Bathroom",
                trade="Tiling",
                subcontractor="ASTW Tiling",
                due_date="2026-07-01",
                description="Workflow test item",
                original_photos=["seed://photo"],
                created_by="Site Manager",
            )
        )

    def test_append_original_photos_on_update(self) -> None:
        item = self.create_open_item()
        updated = self.store.update_item(
            item.id,
            ItemUpdate(append_original_photos=["seed://extra-photo"]),
            by="Site Manager",
        )
        self.assertEqual(len(updated.original_photos), 2)

    def test_replace_original_photos_on_update(self) -> None:
        item = self.create_open_item()
        marked_up = "data:image/jpeg;base64,ZmFrZS1tYXJrLXVw"
        updated = self.store.update_item(
            item.id,
            ItemUpdate(original_photos=[marked_up]),
            by="Site Manager",
        )
        self.assertEqual(updated.original_photos, [marked_up])

    def test_cannot_close_from_open_status(self) -> None:
        item = self.create_open_item()
        with self.assertRaises(WorkflowError):
            self.store.close_with_evidence(
                item.id,
                CloseoutEvidence(
                    photo="seed://closeout",
                    by="Supervisor",
                    confirmation="Confirmed",
                ),
            )

    def test_cannot_mark_ready_without_rectification(self) -> None:
        item = self.create_open_item()
        item = self.store.issue_item(item.id, to="ASTW Tiling", by="Site Manager")
        item = self.store.mark_in_progress(item.id, by="ASTW Tiling")
        with self.assertRaises(ValidationError):
            self.store.mark_ready(item.id, by="ASTW Tiling")


class WorkflowApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_close_from_open_returns_409(self) -> None:
        item = self.store.snapshot().items[0]
        response = self.client.post(
            f"/api/items/{item.id}/closeout",
            headers=bearer("dev-site-manager"),
            json={"photo": "seed://closeout", "confirmation": "Confirmed", "by": "Supervisor"},
        )
        self.assertEqual(response.status_code, 409)

    def test_rectification_without_photo_or_comment_returns_422(self) -> None:
        item = self.store.issue_item(self.store.snapshot().items[0].id, to="ASTW Tiling", by="Site Manager")
        response = self.client.post(
            f"/api/items/{item.id}/rectification",
            headers=bearer("dev-subcontractor"),
            json={"comment": "", "photo": None},
        )
        self.assertEqual(response.status_code, 422)

    def test_in_progress_action_alias_matches_start(self) -> None:
        item = self.store.issue_item(self.store.snapshot().items[0].id, to="ASTW Tiling", by="Site Manager")
        start = self.client.post(
            f"/api/items/{item.id}/actions/start",
            headers=bearer("dev-site-manager"),
            json={"by": "Site Manager"},
        )
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["status"], "in_progress")

        item2 = self.store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="B1",
                level="Level 1",
                unit="U103",
                room="Bathroom",
                trade="Tiling",
                subcontractor="ASTW Tiling",
                due_date="2026-07-01",
                description="Alias route test",
                original_photos=["seed://photo"],
                created_by="Site Manager",
            )
        )
        item2 = self.store.issue_item(item2.id, to="ASTW Tiling", by="Site Manager")
        alias = self.client.post(
            f"/api/items/{item2.id}/actions/in-progress",
            headers=bearer("dev-site-manager"),
            json={"by": "Site Manager"},
        )
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.json()["status"], "in_progress")
        self.assertEqual(alias.json()["status"], start.json()["status"])


class StorageValidationTests(unittest.TestCase):
    def test_heic_upload_returns_clear_error(self) -> None:
        payload = "data:image/heic;base64,AAAA"
        with self.assertRaises(StorageUploadError) as ctx:
            _split_data_url(payload)
        self.assertIn("HEIC", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
