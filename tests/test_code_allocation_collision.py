from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.models import Item, ItemCreate, ProjectConfig, Settings
from app.store import CleanRunStore


def _item(code: str, project: str) -> Item:
    return Item(code=code, project=project, due_date="", description="")


class NextCodeGlobalStemTests(unittest.TestCase):
    """Reproduces the 25 Jul production incident: ESP-DEF-1029 existed under
    project "Speed Tesst (Codex#1)" (cross-project rogue row), so every
    Esplanade Drive capture re-allocated ESP-DEF-1029 and died on the global
    unique constraint. The stem max must be global, like the constraint."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.settings = self.store.snapshot().settings.model_copy(
            update={
                "project_configs": {
                    "Esplanade Drive": ProjectConfig(
                        name="Esplanade Drive", code_prefix="ESP", code_prefix_locked=True
                    ),
                }
            }
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rogue_cross_project_code_is_counted(self) -> None:
        items = [
            _item("ESP-DEF-1027", "Esplanade Drive"),
            _item("ESP-DEF-1028", "Esplanade Drive"),
            # The rogue row: right stem, wrong project.
            _item("ESP-DEF-1029", "Speed Tesst (Codex#1)"),
        ]
        code = self.store.next_code(
            items, "defect", project="Esplanade Drive", settings=self.settings
        )
        self.assertEqual(code, "ESP-DEF-1030")

    def test_normal_sequence_unaffected(self) -> None:
        items = [
            _item("ESP-DEF-1001", "Esplanade Drive"),
            _item("ESP-DEF-1002", "Esplanade Drive"),
            _item("SPE-DEF-1055", "Speed Tesst (Codex#1)"),
        ]
        code = self.store.next_code(
            items, "defect", project="Esplanade Drive", settings=self.settings
        )
        self.assertEqual(code, "ESP-DEF-1003")

    def test_prefixless_project_unchanged(self) -> None:
        items = [
            _item("DEF-009", "Meta Street"),
            _item("DEF-1005", "Jura Noosa"),
        ]
        code = self.store.next_code(items, "defect", project="Meta Street", settings=self.settings)
        self.assertEqual(code, "DEF-1006")

    def test_empty_index_starts_at_base(self) -> None:
        code = self.store.next_code(
            [], "defect", project="Esplanade Drive", settings=self.settings
        )
        self.assertEqual(code, "ESP-DEF-1001")


if __name__ == "__main__":
    unittest.main()
