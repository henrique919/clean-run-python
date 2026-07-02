from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.datetime_format import format_field_date


class DateTimeFormatTests(unittest.TestCase):
    def test_formats_timestamp_like_field_ui(self) -> None:
        value = datetime(2026, 7, 1, 8, 4, tzinfo=timezone.utc)
        self.assertEqual(format_field_date(value), "1 Jul 2026, 8:04am")

    def test_formats_pm_timestamp(self) -> None:
        value = datetime(2026, 7, 1, 20, 4, tzinfo=timezone.utc)
        self.assertEqual(format_field_date(value), "1 Jul 2026, 8:04pm")

    def test_date_only_values_omit_time(self) -> None:
        self.assertEqual(format_field_date("2026-07-01"), "1 Jul 2026")

    def test_invalid_value_is_returned_unchanged(self) -> None:
        self.assertEqual(format_field_date("not-a-date"), "not-a-date")


if __name__ == "__main__":
    unittest.main()
