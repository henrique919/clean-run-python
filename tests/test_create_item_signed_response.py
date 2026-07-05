from __future__ import annotations

import unittest
from unittest.mock import patch

from app import main as app_main
from app.models import canonical_item_id
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer


class CreateItemSignedResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_create_item_returns_camel_case_signed_payload(self) -> None:
        with patch("app.main.resolve_photo_url", return_value="https://signed.example/full.jpg"):
            with patch("app.main.resolve_thumbnail_url", return_value="https://signed.example/thumb.jpg"):
                response = self.client.post(
                    "/api/items",
                    headers=bearer("dev-site-manager"),
                    json={
                        "project": "Jura Noosa",
                        "building": "Block A",
                        "level": "L01",
                        "unit": "A-101",
                        "room": "Kitchen",
                        "trade": "Tiling",
                        "subcontractor": "Demo Sub",
                        "dueDate": "2026-07-15",
                        "description": "Cracked tile",
                        "originalPhotos": ["projects/demo/photo.jpg"],
                        "createdBy": "Site Manager",
                    },
                )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertIn("originalPhotos", payload)
        self.assertIn("originalPhotoThumbnails", payload)
        self.assertEqual(payload["originalPhotos"], ["https://signed.example/full.jpg"])
        self.assertEqual(payload["originalPhotoThumbnails"], ["https://signed.example/thumb.jpg"])
        self.assertNotIn("original_photos", payload)

    def test_create_item_id_matches_state_and_issue_succeeds(self) -> None:
        response = self.client.post(
            "/api/items",
            headers=bearer("dev-site-manager"),
            json={
                "project": "Jura Noosa",
                "building": "Block A",
                "level": "L01",
                "unit": "A-101",
                "room": "Kitchen",
                "trade": "Tiling",
                "subcontractor": "Demo Sub",
                "dueDate": "2026-07-15",
                "description": "Fresh capture detail action",
                "type": "incomplete",
                "createdBy": "Site Manager",
            },
        )
        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertIn("-", created["id"])
        self.assertEqual(created["id"], canonical_item_id(created["id"]))

        state = self.client.get("/api/state", headers=bearer("dev-site-manager")).json()
        state_item = next(item for item in state["items"] if item["code"] == created["code"])
        self.assertEqual(created["id"], state_item["id"])

        issue = self.client.post(
            f'/api/items/{created["id"]}/actions/issue',
            headers=bearer("dev-site-manager"),
            json={"to": "Demo Sub", "by": "Site Manager"},
        )
        self.assertEqual(issue.status_code, 200)
        self.assertEqual(issue.json()["status"], "issued")

    def test_issue_accepts_hex_id_from_stale_client(self) -> None:
        created = self.client.post(
            "/api/items",
            headers=bearer("dev-site-manager"),
            json={
                "project": "Jura Noosa",
                "building": "Block A",
                "level": "L01",
                "unit": "A-101",
                "room": "Kitchen",
                "trade": "Tiling",
                "subcontractor": "Demo Sub",
                "dueDate": "2026-07-15",
                "description": "Hex id compatibility",
                "type": "incomplete",
                "createdBy": "Site Manager",
            },
        ).json()
        hex_id = created["id"].replace("-", "")
        issue = self.client.post(
            f"/api/items/{hex_id}/actions/issue",
            headers=bearer("dev-site-manager"),
            json={"to": "Demo Sub", "by": "Site Manager"},
        )
        self.assertEqual(issue.status_code, 200)
        self.assertEqual(issue.json()["status"], "issued")


if __name__ == "__main__":
    unittest.main()
