from __future__ import annotations

import unittest

from app.models import ItemStatus
from app.store_supabase import SupabaseCleanRunStore


class SupabaseHistoryHydrationTests(unittest.TestCase):
    def test_item_from_rows_hydrates_issue_and_inspection_history_from_payload(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)
        row = {
            "id": "11111111-1111-1111-1111-111111111111",
            "code": "DEF-1001",
            "type": "defect",
            "status": ItemStatus.REJECTED,
            "project": "Jura Noosa",
            "building": "B1",
            "level": "Level 1",
            "unit": "U101",
            "room": "Bathroom",
            "trade": "Tiling",
            "subcontractor": "ASTW Tiling",
            "priority": "high",
            "due_date": "2026-07-01",
            "description": "Tile lip",
            "raised_by": None,
            "created_by_label": "Site Manager",
            "rejection_reason": "Not acceptable",
            "issued_at": "2026-06-01T00:00:00Z",
            "started_at": None,
            "ready_at": None,
            "inspected_at": None,
            "closed_at": None,
            "created_at": "2026-06-01T00:00:00Z",
            "updated_at": "2026-06-02T00:00:00Z",
            "payload": {
                "issue_history": [
                    {
                        "at": "2026-06-01T00:00:00Z",
                        "to": "ASTW Tiling",
                        "by": "Site Manager",
                        "note": "Please fix",
                        "reissue": False,
                    }
                ],
                "inspection_history": [
                    {
                        "at": "2026-06-02T00:00:00Z",
                        "by": "Supervisor",
                        "action": "rejected",
                        "reason": "Not acceptable",
                    }
                ],
            },
        }

        item = store._item_from_rows(row, [], [], [])

        self.assertEqual(len(item.issue_history), 1)
        self.assertEqual(item.issue_history[0].to, "ASTW Tiling")
        self.assertEqual(len(item.inspection_history), 1)
        self.assertEqual(item.inspection_history[0].action, "rejected")
        self.assertEqual(item.inspection_history[0].reason, "Not acceptable")

    def test_issue_history_rebuilt_from_audit_when_payload_missing(self) -> None:
        store = SupabaseCleanRunStore.__new__(SupabaseCleanRunStore)
        row = {
            "id": "22222222-2222-2222-2222-222222222222",
            "code": "DEF-1002",
            "type": "defect",
            "status": ItemStatus.ISSUED,
            "project": "Jura Noosa",
            "subcontractor": "ASTW Tiling",
            "issued_at": "2026-06-01T08:04:00Z",
            "created_by_label": "Site Manager",
            "created_at": "2026-06-01T08:04:00Z",
            "updated_at": "2026-06-01T08:04:00Z",
            "payload": {},
        }
        audit_rows = [
            {
                "message": "Issued to ASTW Tiling",
                "created_by_label": "Site Manager",
                "created_at": "2026-06-01T08:04:00Z",
            }
        ]

        item = store._item_from_rows(row, [], [], audit_rows)

        self.assertEqual(len(item.issue_history), 1)
        self.assertEqual(item.issue_history[0].to, "ASTW Tiling")
        self.assertEqual(item.issue_history[0].by, "Site Manager")


if __name__ == "__main__":
    unittest.main()
