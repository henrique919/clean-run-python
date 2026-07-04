"""Phase 2.1 — clean descriptions from parsed voice/typed notes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import main as app_main
from app.parse_description import clean_parsed_description
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer

ROOT = Path(__file__).resolve().parents[1]
ENHANCEMENTS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.js"


class ParseDescriptionTests(unittest.TestCase):
    def test_no_api_key_returns_rule_cleaned_note(self) -> None:
        with patch("app.parse_description.os.getenv", return_value=None):
            note = "Level 1 unit 101 bedroom 1, door frame cracked near the hinge, carpenter to replace"
            cleaned = clean_parsed_description(
                note,
                {"level": "Level 1", "room": "Bedroom 1", "trade": "Joinery"},
            )
        self.assertIn("door frame cracked", cleaned.lower())
        self.assertNotIn("level 1", cleaned.lower())
        self.assertIn("replace", cleaned.lower())

    def test_defect_only_note_mostly_unchanged(self) -> None:
        with patch("app.parse_description.os.getenv", return_value=None):
            note = "cracked tile under vanity, regrout"
            cleaned = clean_parsed_description(note, {"trade": "Tiling"})
        self.assertIn("cracked tile under vanity", cleaned.lower())
        self.assertIn("regrout", cleaned.lower())

    def test_openai_failure_returns_rule_cleaned_note(self) -> None:
        note = "Level 1 unit 101 bedroom 1, door frame cracked near the hinge, carpenter to replace"
        with patch("app.parse_description.os.getenv", side_effect=lambda key, default=None: "sk-test" if key == "OPENAI_API_KEY" else default):
            with patch("openai.OpenAI", side_effect=RuntimeError("timeout")):
                cleaned = clean_parsed_description(note, {"level": "L01", "room": "Bedroom 1", "trade": "Joinery"})
        self.assertIn("door frame cracked", cleaned.lower())
        self.assertNotIn("level 1", cleaned.lower())

    def test_openai_success_returns_cleaned_description(self) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({"description": "Door frame cracked near the hinge — replace."})))]
        )
        with patch("app.parse_description.os.getenv", side_effect=lambda key, default=None: "sk-test" if key == "OPENAI_API_KEY" else default):
            with patch("openai.OpenAI", return_value=mock_client):
                cleaned = clean_parsed_description(
                    "Level 1 U101 Bedroom, door frame cracked near the hinge, carpenter to replace",
                    {"level": "Level 1", "unit": "U101", "room": "Bedroom", "trade": "Joinery"},
                )
        self.assertEqual(cleaned, "Door frame cracked near the hinge — replace.")


class LegacyParseEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.patcher = patch.object(app_main, "store", self.store)
        self.patcher.start()
        self.client = AsgiClient(app_main.app)
        self.headers = bearer("dev-site-manager")

    def tearDown(self) -> None:
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_parse_without_ai_keeps_rule_cleaned_description(self) -> None:
        note = "cracked tile under vanity, regrout"
        with patch("app.main.clean_parsed_description", side_effect=lambda transcript, fields: __import__("app.parse_description", fromlist=["rule_based_clean_description"]).rule_based_clean_description(transcript, fields)):
            response = self.client.post("/api/parse", headers=self.headers, json={"transcript": note})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("Cracked tile under vanity", body["description"])
        self.assertIn("Regrout", body["description"])

    def test_parse_applies_cleaned_description_when_available(self) -> None:
        note = "L01 A-304 Bedroom 1, door frame cracked near the hinge, carpenter to replace"
        cleaned = "Door frame cracked near the hinge — replace."
        with patch("app.main.clean_parsed_description", return_value=cleaned):
            response = self.client.post("/api/parse", headers=self.headers, json={"transcript": note})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body.get("level"), "L01")
        self.assertEqual(body.get("unit"), "A-304")
        self.assertEqual(body.get("room"), "Bedroom 1")
        self.assertEqual(body["description"], cleaned)

    def test_parse_still_extracts_location_and_trade_fields(self) -> None:
        note = "L01 A-304 Bedroom 1, cracked tile under vanity, regrout"
        with patch("app.main.clean_parsed_description", return_value="Cracked tile under vanity, regrout."):
            response = self.client.post("/api/parse", headers=self.headers, json={"transcript": note})
        body = response.json()
        self.assertEqual(body.get("level"), "L01")
        self.assertEqual(body.get("unit"), "A-304")
        self.assertEqual(body.get("room"), "Bedroom 1")


class Phase21FrontendMarkers(unittest.TestCase):
    def test_draft_handler_preserves_manual_description(self) -> None:
        enh = ENHANCEMENTS.read_text(encoding="utf-8")
        self.assertIn("captureDescriptionEdited", enh)
        self.assertIn('k==="description"&&preserveDescription', enh)
        self.assertIn("Draft applied — review before saving", enh)
        self.assertIn('CLEANRUN_FRONTEND_BUILD="cards52"', enh)


if __name__ == "__main__":
    unittest.main()
