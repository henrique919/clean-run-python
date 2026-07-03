from __future__ import annotations

import unittest
from threading import RLock
from unittest.mock import patch

from app.models import AppData, Item, ItemCreate
from app.storage import (
    is_markup_source_path_allowed,
    is_staging_storage_path,
    normalize_photo,
    promote_staged_photo,
    read_markup_bytes,
    resolve_photo_url,
    storage_path_from_value,
    upload_data_url,
)
from app.store import seed_settings
from app.store_supabase import SupabaseCleanRunStore, _child_db_id, _item_db_id, _stable_uuid, _storage_folder


class StoragePathTests(unittest.TestCase):
    def test_staging_storage_paths_are_detected(self) -> None:
        self.assertTrue(is_staging_storage_path("cleanrun/public/staging/abc123.jpg"))
        self.assertFalse(is_staging_storage_path("cleanrun/public/projects/demo/items/def-1001/original/abc.jpg"))

    def test_markup_source_paths_allow_staging_and_project_evidence(self) -> None:
        self.assertTrue(is_markup_source_path_allowed("cleanrun/public/staging/abc.jpg"))
        with patch.dict("os.environ", {"CLEANRUN_ENV": "production"}, clear=False):
            self.assertTrue(is_markup_source_path_allowed("cleanrun/public/projects/demo/items/def-1001/original/abc.jpg"))
        self.assertFalse(is_markup_source_path_allowed("projects/demo/items/def-1001/original/abc.jpg"))
        self.assertFalse(is_markup_source_path_allowed("https://example.com/photo.jpg"))

    def test_storage_path_from_signed_render_url(self) -> None:
        signed = (
            "https://project.supabase.co/storage/v1/render/image/sign/cleanrun-evidence/"
            "cleanrun/public/projects/demo/items/def-1001/original/abc.jpg?token=thumb"
        )
        self.assertEqual(
            storage_path_from_value(signed),
            "cleanrun/public/projects/demo/items/def-1001/original/abc.jpg",
        )

    def test_read_markup_bytes_downloads_storage_path(self) -> None:
        class FakeBucket:
            def download(self, path):
                assert path == "cleanrun/public/projects/demo/items/def-1001/original/abc.jpg"
                return b"jpeg-bytes"

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

        class FakeClient:
            storage = FakeStorage()

        with patch("app.storage.get_supabase_client", return_value=FakeClient()), patch(
            "app.storage.get_public_supabase_client", return_value=FakeClient()
        ):
            data, content_type = read_markup_bytes("cleanrun/public/projects/demo/items/def-1001/original/abc.jpg")

        self.assertEqual(data, b"jpeg-bytes")
        self.assertEqual(content_type, "image/jpeg")

    def test_normalize_photo_promotes_staging_path_into_item_folder(self) -> None:
        staged_path = "cleanrun/public/staging/abc123.jpg"
        item_folder = "projects/jura-noosa/items/def-1005/original"
        uploaded: dict[str, object] = {}

        class FakeBucket:
            def upload(self, *, path, file, file_options):
                uploaded["path"] = path
                uploaded["file"] = file
                uploaded["options"] = file_options

            def download(self, path):
                assert path == staged_path
                return b"fake-image"

            def create_signed_url(self, path, ttl, options=None):
                return {"signedURL": f"https://signed.example/{path}"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

            def get_bucket(self, bucket):
                return {"id": bucket}

        class FakeClient:
            storage = FakeStorage()

        with patch.dict("os.environ", {"CLEANRUN_STORAGE_PATH_PREFIX": "cleanrun/public"}, clear=False), patch(
            "app.storage.get_supabase_client", return_value=FakeClient()
        ), patch(
            "app.storage.get_public_supabase_client", return_value=FakeClient()
        ):
            promoted = normalize_photo(staged_path, folder=item_folder)

        self.assertTrue(str(uploaded["path"]).startswith("cleanrun/public/projects/jura-noosa/items/def-1005/original/"))
        self.assertEqual(promoted, uploaded["path"])
        self.assertNotIn("/staging/", promoted)

    def test_storage_upload_returns_object_path_not_signed_url(self) -> None:
        uploaded = {}

        class FakeBucket:
            def upload(self, *, path, file, file_options):
                uploaded["path"] = path

            def create_signed_url(self, path, ttl, options=None):
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
        ), patch(
            "app.storage.get_public_supabase_client", return_value=FakeClient()
        ):
            path = upload_data_url("data:image/png;base64,aGVsbG8=", folder="original")

        self.assertEqual(path, uploaded["path"])
        self.assertTrue(path.startswith("projects/jura/items/def-1005/original/"))
        self.assertNotIn("signed.example", path)

    def test_signed_storage_urls_are_normalized_and_resigned(self) -> None:
        class FakeBucket:
            def create_signed_url(self, path, ttl, options=None):
                options = options or {}
                transform = options.get("transform")
                if transform:
                    return {"signedURL": f"https://fresh.example/storage/v1/render/image/sign/cleanrun-evidence/{path}?token=thumb"}
                return {"signedURL": f"https://fresh.example/storage/v1/object/sign/cleanrun-evidence/{path}?token=full"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

        class FakeClient:
            storage = FakeStorage()

        expired = "https://project.supabase.co/storage/v1/object/sign/cleanrun-evidence/projects/jura/photo.jpg?token=old"

        self.assertEqual(normalize_photo(expired), "projects/jura/photo.jpg")
        with patch("app.storage.get_supabase_client", return_value=FakeClient()):
            self.assertEqual(resolve_photo_url(expired), "https://fresh.example/storage/v1/object/sign/cleanrun-evidence/projects/jura/photo.jpg?token=full")
            from app.storage import resolve_thumbnail_url

            thumb = resolve_thumbnail_url("projects/jura/photo.jpg")
            self.assertIn("/render/image/sign/", thumb)
            self.assertIn("projects/jura/photo.jpg", thumb)

    def test_report_share_transform_is_mid_size_width_and_capture_quality(self) -> None:
        from app.storage import report_share_transform

        self.assertEqual(report_share_transform(), {"width": 1200, "quality": 75})

    def test_resolve_share_photo_url_signs_transform_variant(self) -> None:
        from app.storage import resolve_share_photo_url, signed_url_cache

        class FakeBucket:
            def create_signed_url(self, path, ttl, options=None):
                transform = (options or {}).get("transform")
                assert transform == {"width": 1200, "quality": 75}
                return {"signedURL": f"https://fresh.example/storage/v1/render/image/sign/cleanrun-evidence/{path}?token=share"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

        class FakeClient:
            storage = FakeStorage()

        signed_url_cache.clear()
        with patch("app.storage.get_supabase_client", return_value=FakeClient()):
            share = resolve_share_photo_url("projects/jura/share-photo.jpg")
        self.assertIn("/render/image/sign/", share)
        self.assertIn("projects/jura/share-photo.jpg", share)
        self.assertEqual(resolve_share_photo_url("seed://amber/Cracked tile"), "seed://amber/Cracked tile")

    def test_resolve_share_photo_url_returns_none_when_signing_fails(self) -> None:
        from app.storage import resolve_share_photo_url, signed_url_cache

        class FailingBucket:
            def create_signed_url(self, path, ttl, options=None):
                raise RuntimeError("signing failed")

        class FailingStorage:
            def from_(self, bucket):
                return FailingBucket()

        class FailingClient:
            storage = FailingStorage()

        signed_url_cache.clear()
        with patch("app.storage.get_supabase_client", return_value=FailingClient()):
            self.assertIsNone(resolve_share_photo_url("projects/jura/share-fail.jpg"))

    def test_resolve_photo_url_returns_none_when_signing_fails(self) -> None:
        class FailingBucket:
            def create_signed_url(self, path, ttl, options=None):
                raise RuntimeError("signing failed")

        class FailingStorage:
            def from_(self, bucket):
                return FailingBucket()

        class FailingClient:
            storage = FailingStorage()

        with patch("app.storage.get_supabase_client", return_value=FailingClient()):
            self.assertIsNone(resolve_photo_url("projects/jura/photo.jpg"))

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
        store._read_settings = lambda: settings
        store._read_item_by_id = lambda item_id: next((item for item in items if item.id == item_id), None)
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
        store._read_create_context = lambda: AppData(items=[existing], settings=settings)
        store._read_code_index = lambda: [existing]
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

    def test_read_code_index_builds_valid_items(self) -> None:
        rows = [{"code": "DEF-1044", "project": "Esplanade Drive"}]
        items = [
            Item(
                code=row["code"],
                project=row.get("project") or "",
                due_date="",
                description="",
            )
            for row in rows
            if row.get("code")
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].code, "DEF-1044")
        code = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore).next_code(
            items,
            "defect",
            project="Esplanade Drive",
            settings=seed_settings(),
        )
        self.assertEqual(code, "DEF-1045")


if __name__ == "__main__":
    unittest.main()
