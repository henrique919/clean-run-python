from __future__ import annotations

import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.db import build_repository
from app.repositories.local_repository import LocalCleanRunRepository


class StorageGuardrailTests(unittest.TestCase):
    def test_production_refuses_local_json_without_explicit_override(self) -> None:
        env = {
            "APP_ENV": "production",
            "CLEANRUN_ENV": "production",
            "CLEANRUN_STORAGE": "local",
            "ALLOW_LOCAL_STORAGE_IN_PRODUCTION": "false",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Local JSON storage is refused in production"):
                build_repository()

    def test_supabase_mode_does_not_fall_back_to_local_json(self) -> None:
        env = {
            "APP_ENV": "development",
            "CLEANRUN_ENV": "development",
            "CLEANRUN_STORAGE": "supabase",
        }
        fake_module = SimpleNamespace(SupabaseCleanRunRepository=lambda: (_ for _ in ()).throw(RuntimeError("supabase unavailable")))
        with patch.dict(os.environ, env, clear=False), patch.dict(sys.modules, {"app.repositories.supabase_repository": fake_module}):
            with self.assertRaisesRegex(RuntimeError, "CLEANRUN_STORAGE=supabase"):
                build_repository()

    def test_development_allows_explicit_local_storage(self) -> None:
        env = {
            "APP_ENV": "development",
            "CLEANRUN_ENV": "development",
            "CLEANRUN_STORAGE": "local",
        }
        with patch.dict(os.environ, env, clear=False):
            repository = build_repository()

        self.assertIsInstance(repository, LocalCleanRunRepository)


if __name__ == "__main__":
    unittest.main()
