"""Launch-mode Supabase data client selection (create-after-login hotfix)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.supabase_client import get_data_supabase_client, use_public_launch_data_client


class LaunchDataClientTests(unittest.TestCase):
    def test_production_public_prefix_uses_launch_data_client(self) -> None:
        with patch.dict(
            os.environ,
            {"CLEANRUN_ENV": "production", "CLEANRUN_STORAGE_PATH_PREFIX": "cleanrun/public"},
            clear=False,
        ):
            self.assertTrue(use_public_launch_data_client())

    def test_production_default_prefix_is_public_launch(self) -> None:
        env = {"CLEANRUN_ENV": "production"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("CLEANRUN_STORAGE_PATH_PREFIX", None)
            self.assertTrue(use_public_launch_data_client())

    def test_non_production_does_not_force_public_client(self) -> None:
        with patch.dict(
            os.environ,
            {"CLEANRUN_ENV": "development", "CLEANRUN_STORAGE_PATH_PREFIX": "cleanrun/public"},
            clear=False,
        ):
            self.assertFalse(use_public_launch_data_client())

    def test_get_data_client_uses_public_in_launch_mode(self) -> None:
        sentinel = object()
        with patch.dict(os.environ, {"CLEANRUN_ENV": "production"}, clear=False):
            os.environ.pop("CLEANRUN_STORAGE_PATH_PREFIX", None)
            with patch("app.supabase_client.get_public_supabase_client", return_value=sentinel) as public:
                with patch("app.supabase_client.get_supabase_client") as authed:
                    self.assertIs(get_data_supabase_client(), sentinel)
                    public.assert_called_once()
                    authed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
