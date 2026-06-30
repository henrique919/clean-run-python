from __future__ import annotations

import unittest

from app.models import Item
from app.store_supabase import SupabaseCleanRunStore, _child_db_id, _item_db_id, _stable_uuid, _storage_folder


class StoragePathTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
