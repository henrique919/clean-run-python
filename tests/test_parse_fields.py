"""Tests for rule-based parse field helpers."""

from __future__ import annotations

import unittest

from app.parse_description import rule_based_clean_description
from app.parse_fields import match_level, match_room, match_trade, match_unit


class ParseFieldTests(unittest.TestCase):
    def test_match_level_synonym(self) -> None:
        self.assertEqual(match_level("Level 1 unit 101", ["L01", "L02"]), "L01")

    def test_match_room_from_preamble_only(self) -> None:
        rooms = ["Kitchen", "Bedroom 1", "Bathroom"]
        self.assertEqual(
            match_room("L01 A-304 Bedroom 1, crack above the bathroom door", rooms),
            "Bedroom 1",
        )

    def test_match_trade_from_carpenter_hint(self) -> None:
        trades = ["Joinery", "Tiling", "Painting"]
        self.assertEqual(match_trade("carpenter to replace", trades), "Joinery")

    def test_rule_clean_example_note(self) -> None:
        note = "Level 1 unit 101 bedroom 1, door frame cracked near the hinge, carpenter to replace"
        cleaned = rule_based_clean_description(
            note,
            {"level": "L01", "room": "Bedroom 1", "trade": "Joinery"},
        )
        self.assertEqual(cleaned, "Door frame cracked near the hinge — Replace.")

    def test_rule_clean_keeps_defect_location_words(self) -> None:
        note = "L01 A-304 Bedroom 1, crack above the bathroom door, tiler to repair grout"
        cleaned = rule_based_clean_description(
            note,
            {"level": "L01", "unit": "A-304", "room": "Bedroom 1", "trade": "Tiling"},
        )
        self.assertIn("bathroom door", cleaned.lower())


if __name__ == "__main__":
    unittest.main()
