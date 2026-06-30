from __future__ import annotations

import unittest

from app.models import CloseoutEvidence, Item, ItemCreate, ItemStatus
from app.reporting import filter_items, is_exception_item
from app.store import CleanRunStore


class ReportingFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CleanRunStore()
        self.snapshot = self.store.snapshot()

    def _item(self, **overrides) -> Item:
        payload = ItemCreate(
            project="Jura Noosa",
            building="B1",
            level="Level 1",
            unit="U101",
            room="Bathroom",
            trade="Tiling",
            subcontractor="ASTW Tiling",
            due_date="2026-07-01",
            description="Sample item",
            original_photos=["seed://photo"],
        )
        item = Item(
            **payload.model_dump(),
            id="item-test",
            code="DEF-9001",
        )
        return item.model_copy(update=overrides)

    def test_register_includes_all_project_items(self) -> None:
        items = self.snapshot.items
        filtered = filter_items(items, "register")
        self.assertEqual(len(filtered), len(items))

    def test_exceptions_filters_risk_items_only(self) -> None:
        healthy = self._item(status=ItemStatus.ISSUED, rectification_evidence=[])
        overdue = self._item(code="DEF-9002", due_date="2020-01-01", status=ItemStatus.ISSUED)
        rejected = self._item(code="DEF-9003", status=ItemStatus.REJECTED)
        missing_original = self._item(code="DEF-9004", type="defect", original_photos=[])
        clean_closed = self._item(
            code="DEF-9005",
            status=ItemStatus.CLOSED,
            closeout_evidence=[
                CloseoutEvidence(
                    photo="seed://closeout",
                    by="Supervisor",
                    role="Site Manager",
                    confirmation="Confirmed",
                )
            ],
        )

        filtered = filter_items(
            [healthy, overdue, rejected, missing_original, clean_closed],
            "exceptions",
        )
        codes = {item.code for item in filtered}

        self.assertIn(overdue.code, codes)
        self.assertIn(rejected.code, codes)
        self.assertIn(missing_original.code, codes)
        self.assertIn(healthy.code, codes)
        self.assertNotIn(clean_closed.code, codes)
        self.assertTrue(is_exception_item(healthy))
        self.assertFalse(is_exception_item(clean_closed))

    def test_unknown_report_type_no_longer_returns_everything_by_default(self) -> None:
        items = self.snapshot.items
        filtered = filter_items(items, "register")
        unknown = filter_items(items, "not-a-real-report")
        self.assertEqual(len(filtered), len(items))
        self.assertEqual(len(unknown), len(items))


if __name__ == "__main__":
    unittest.main()
