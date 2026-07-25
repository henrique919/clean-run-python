"""Production must never re-seed demo data unless explicitly opted in.

CLEANRUN_BOOTSTRAP_SEED_DATA defaulted to "true", so a missing env var on a
fresh Render deploy re-upserted the 14 demo items (cleanrun_data.json) over
real production data on every restart, and deleted item_photos rows not in
the seed set. The default must be "false" so a missing/misconfigured env var
fails safe.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.store_supabase import SupabaseCleanRunStore

ROOT = Path(__file__).resolve().parents[1]


class SeedBootstrapDefaultTests(unittest.TestCase):
    def test_render_yaml_pins_seed_backfill_off(self) -> None:
        render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("CLEANRUN_BOOTSTRAP_SEED_DATA", render_yaml)
        seed_line_index = render_yaml.index("CLEANRUN_BOOTSTRAP_SEED_DATA")
        following_text = render_yaml[seed_line_index : seed_line_index + 80]
        self.assertIn('value: "false"', following_text)

    def test_production_default_skips_seed_backfill(self) -> None:
        env = {"CLEANRUN_ENV": "production"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLEANRUN_BOOTSTRAP_SEED_DATA", None)
            with patch.object(SupabaseCleanRunStore, "_backfill_seed_data", MagicMock()) as backfill:
                with patch.object(SupabaseCleanRunStore, "_bootstrap_if_empty", MagicMock()) as bootstrap:
                    SupabaseCleanRunStore()
                    backfill.assert_not_called()
                    bootstrap.assert_not_called()

    def test_production_explicit_false_skips_seed_backfill(self) -> None:
        env = {"CLEANRUN_ENV": "production", "CLEANRUN_BOOTSTRAP_SEED_DATA": "false"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(SupabaseCleanRunStore, "_backfill_seed_data", MagicMock()) as backfill:
                SupabaseCleanRunStore()
                backfill.assert_not_called()

    def test_production_explicit_true_still_runs_seed_backfill(self) -> None:
        env = {"CLEANRUN_ENV": "production", "CLEANRUN_BOOTSTRAP_SEED_DATA": "true"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(SupabaseCleanRunStore, "_backfill_seed_data", MagicMock()) as backfill:
                SupabaseCleanRunStore()
                backfill.assert_called_once()

    def test_non_production_bootstraps_if_empty_regardless_of_flag(self) -> None:
        env = {"CLEANRUN_ENV": "development"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLEANRUN_BOOTSTRAP_SEED_DATA", None)
            with patch.object(SupabaseCleanRunStore, "_bootstrap_if_empty", MagicMock()) as bootstrap:
                SupabaseCleanRunStore()
                bootstrap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
