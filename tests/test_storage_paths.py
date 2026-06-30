from __future__ import annotations

import unittest

from app.models import Item
from app.store_supabase import _storage_folder


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


if __name__ == "__main__":
    unittest.main()
