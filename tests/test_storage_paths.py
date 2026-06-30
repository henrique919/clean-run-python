from __future__ import annotations

import unittest
from threading import RLock
from unittest.mock import patch

from app.models import AppData, Item, ItemCreate
from app.storage import normalize_photo, resolve_photo_url, upload_data_url
from app.store import seed_settings
from app.store_supabase import SupabaseCleanRunStore, _child_db_id, _item_db_id, _stable_uuid, _storage_folder


class StoragePathTests(unittest.TestCase):
    def test_storage_upload_returns_object_path_not_signed_url(self) -> None:
        uploaded = {}

        class FakeBucket:
            def upload(self, *, path, file, file_options):
                uploaded["path"] = path

            def create_signed_url(self, path, ttl):
                return {"signedURL": f"https://signed.example/{path}?ttl={ttl}"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

            def get_bucket(self, bucket):
                return {"id": bucket}

        class FakeClient:
            storage = FakeStorage()

        with patch.dict("os.environ", {"CLEANRUN_STORAGE_PATH_PREFIX": "projects/jura/items/def-1005"}, clear=False), patch(
            "app.storage.get_supabase_client", return_value=FakeClient()
        ):
            path = upload_data_url("data:image/png;base64,aGVsbG8=", folder="original")

        self.assertEqual(path, uploaded["path"])
        self.assertTrue(path.startswith("projects/jura/items/def-1005/original/"))
        self.assertNotIn("signed.example", path)

    def test_signed_storage_urls_are_normalized_and_resigned(self) -> None:
        class FakeBucket:
            def create_signed_url(self, path, ttl):
                return {"signedURL": f"https://fresh.example/{path}"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

        class FakeClient:
            storage = FakeStorage()

        expired = "https://project.supabase.co/storage/v1/object/sign/cleanrun-evidence/projects/jura/photo.jpg?token=old"

        self.assertEqual(normalize_photo(expired), "projects/jura/photo.jpg")
        with patch("app.storage.get_supabase_client", return_value=FakeClient()):
            self.assertEqual(resolve_photo_url(expired), "https://fresh.example/projects/jura/photo.jpg")

    def test_storage_folder_includes_project_item_and_evidence_type(self) -> None:
        item = Item(
            id="item-1",
            code="DEF-1004",
            type="defect",
            project="Jura Noosa",
            building="B2",
            level="Ground",
            unit="U201",
            room="Bathroom",
            trade="Waterproofing",
            subcontractor="I-Inject Waterproofing",
            due_date="2026-07-07",
            description="Waterproof membrane not thick enough in areas",
            original_photos=[],
        )

        self.assertEqual(_storage_folder(item, "original"), "projects/jura-noosa/items/def-1004/original")

    def test_photo_row_always_has_created_at(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)

        row = store._photo_row(
            "00000000-0000-0000-0000-000000000001",
            "project-id",
            "item-id",
            "original",
            "seed://amber/Cracked tile",
            0,
            "Site Manager",
        )

        self.assertTrue(row["created_at"])

    def test_existing_supabase_item_uuid_is_not_rewritten(self) -> None:
        item = Item(
            id="06496ca3-45b0-560e-b21a-fe1aa9450453",
            code="DEF-1002",
            type="defect",
            project="Jura Noosa",
            building="B2",
            level="Ground",
            unit="U201",
            room="Bathroom",
            trade="Waterproofing",
            subcontractor="I-Inject Waterproofing",
            due_date="2026-07-07",
            description="Waterproof membrane not thick enough in areas",
            original_photos=[],
        )

        self.assertEqual(_item_db_id(item), item.id)

    def test_local_item_id_is_mapped_to_stable_supabase_uuid(self) -> None:
        item = Item(
            id="offline-local-item",
            code="DEF-1005",
            type="defect",
            project="Jura Noosa",
            building="B2",
            level="Ground",
            unit="U201",
            room="Bathroom",
            trade="Waterproofing",
            subcontractor="I-Inject Waterproofing",
            due_date="2026-07-07",
            description="Waterproof membrane not thick enough in areas",
            original_photos=[],
        )

        self.assertEqual(_item_db_id(item), _stable_uuid("item", item.id))

    def test_existing_child_uuid_is_not_rewritten(self) -> None:
        child_id = "efe41cea-5849-53bd-a215-6748fc643b3e"

        self.assertEqual(_child_db_id("photo", "item-id", child_id, "rectification"), child_id)

    def test_duplicate_photo_rows_are_collapsed_on_read(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)
        rows = [
            {
                "id": "efe41cea-5849-53bd-a215-6748fc643b3e",
                "photo_type": "rectification",
                "storage_path": "seed://green/Rectification photo",
                "caption": "Rectification complete.",
                "created_by_label": "Sterling Tiling",
                "created_at": "2026-06-26T16:27:10.480146+00:00",
            },
            {
                "id": "b78f5708-9796-58de-9e6e-7e030deb5c83",
                "photo_type": "rectification",
                "storage_path": "seed://green/Rectification photo",
                "caption": "Rectification complete.",
                "created_by_label": "Sterling Tiling",
                "created_at": "2026-06-26T16:27:10.480146+00:00",
            },
        ]

        self.assertEqual(len(store._dedupe_child_rows("item_photos", rows)), 1)

    def test_patch_upserts_only_changed_item(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)
        settings = seed_settings()
        items = [
            Item(code="DEF-1001", project="Jura Noosa", due_date="2026-07-07", description="One"),
            Item(code="DEF-1002", project="Jura Noosa", due_date="2026-07-07", description="Two"),
        ]
        calls = []
        store.lock = RLock()
        store._read = lambda: AppData(items=items, settings=settings)
        store._upsert_item = lambda item, current_settings: calls.append((item.code, current_settings))

        changed = store._patch(items[1].id, lambda item: item.model_copy(update={"description": "Changed"}))

        self.assertEqual(changed.description, "Changed")
        self.assertEqual([code for code, _settings in calls], ["DEF-1002"])
        self.assertIs(calls[0][1], settings)

    def test_create_item_upserts_only_new_item(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)
        settings = seed_settings()
        existing = Item(code="DEF-1001", project="Jura Noosa", due_date="2026-07-07", description="One")
        calls = []
        store.lock = RLock()
        store._read = lambda: AppData(items=[existing], settings=settings)
        store._upsert_item = lambda item, current_settings: calls.append((item.code, current_settings))

        created = store.create_item(
            ItemCreate(
                project="Jura Noosa",
                building="B5",
                level="Ground",
                unit="U101",
                room="Bathroom",
                trade="Waterproofing",
                subcontractor="CLP Painting",
                due_date="2026-07-07",
                description="New defect",
                original_photos=["seed://photo"],
            )
        )

        self.assertEqual(created.code, "DEF-1002")
        self.assertEqual([code for code, _settings in calls], ["DEF-1002"])
        self.assertIs(calls[0][1], settings)


if __name__ == "__main__":
    unittest.main()
