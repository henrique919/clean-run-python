"""client_request_id idempotency (Fix 3 of the offline-sync/session P0 batch).

Covers the local JSON store (app/store.py) directly and the HTTP round trip
through /api/items. The Supabase-backed store (app/store_supabase.py) is not
covered here — this suite has no live Supabase fixture (see
tests/test_supabase_contract.py for the migration-file contract check
instead, following that file's existing static-text-only pattern).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.models import ItemCreate
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer


class ClientRequestIdLocalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_payload(self, **overrides) -> ItemCreate:
        fields = dict(
            project="Jura Noosa",
            building="B1",
            level="Level 1",
            unit="U101",
            room="Bathroom",
            trade="Tiling",
            subcontractor="ASTW Tiling",
            due_date="2026-07-01",
            description="Cracked tile under vanity",
            original_photos=["seed://photo"],
            created_by="Site Manager",
        )
        fields.update(overrides)
        return ItemCreate(**fields)

    def test_same_client_request_id_returns_existing_item_not_a_duplicate(self) -> None:
        baseline = len(self.store.snapshot().items)
        first = self.store.create_item(self.make_payload(client_request_id="offline-abc123"))
        second = self.store.create_item(self.make_payload(client_request_id="offline-abc123"))

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.code, second.code)
        self.assertEqual(len(self.store.snapshot().items) - baseline, 1)

    def test_different_client_request_id_creates_distinct_items_despite_matching_fingerprint(self) -> None:
        # Same type/project/building/level/unit/room/trade/subcontractor/due_date/
        # description/created_by (the fingerprint tuple) but different capture
        # request ids: two genuinely distinct captures that happen to share a
        # short description must NOT collapse into one item.
        baseline = len(self.store.snapshot().items)
        first = self.store.create_item(self.make_payload(client_request_id="offline-walk-1"))
        second = self.store.create_item(self.make_payload(client_request_id="offline-walk-2"))

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(self.store.snapshot().items) - baseline, 2)

    def test_no_client_request_id_falls_back_to_existing_fingerprint_dedupe(self) -> None:
        # Regression guard: omitting client_request_id must preserve the
        # pre-existing 300s fingerprint dedupe behaviour unchanged.
        baseline = len(self.store.snapshot().items)
        first = self.store.create_item(self.make_payload())
        second = self.store.create_item(self.make_payload())

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.store.snapshot().items) - baseline, 1)

    def test_blank_client_request_id_does_not_bypass_fingerprint_dedupe(self) -> None:
        baseline = len(self.store.snapshot().items)
        first = self.store.create_item(self.make_payload(client_request_id=""))
        second = self.store.create_item(self.make_payload(client_request_id=""))

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.store.snapshot().items) - baseline, 1)


class ClientRequestIdHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def base_body(self, **overrides) -> dict:
        body = {
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
        }
        body.update(overrides)
        return body

    def test_retried_post_with_same_client_request_id_returns_same_item(self) -> None:
        body = self.base_body(clientRequestId="offline-http-retry-1")

        first = self.client.post("/api/items", headers=bearer("dev-site-manager"), json=body)
        second = self.client.post("/api/items", headers=bearer("dev-site-manager"), json=body)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["code"], second.json()["code"])

        state = self.client.get("/api/state", headers=bearer("dev-site-manager")).json()
        matching = [item for item in state["items"] if item["code"] == first.json()["code"]]
        self.assertEqual(len(matching), 1)

    def test_different_client_request_id_creates_two_items(self) -> None:
        first = self.client.post(
            "/api/items",
            headers=bearer("dev-site-manager"),
            json=self.base_body(clientRequestId="offline-http-a"),
        )
        second = self.client.post(
            "/api/items",
            headers=bearer("dev-site-manager"),
            json=self.base_body(clientRequestId="offline-http-b"),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.json()["id"], second.json()["id"])


if __name__ == "__main__":
    unittest.main()
