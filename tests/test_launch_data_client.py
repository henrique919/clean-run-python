"""Data-plane Supabase client selection always forwards the caller's JWT.

Previously, production launch mode forced table reads/writes through the
anon/public client regardless of login (use_public_launch_data_client()),
because the `authenticated` RLS policies were incomplete when this was
written. Verified against production 2026-07-25: the anon key alone could
read and write every table with no login at all. supabase/migrations/
202607250001_close_anon_data_access.sql closes that at the RLS layer;
get_data_supabase_client() must always forward the JWT so authenticated
users still have data-plane access once anon is revoked.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.supabase_client import get_data_supabase_client


class LaunchDataClientTests(unittest.TestCase):
    def test_get_data_client_always_forwards_to_authenticated_client(self) -> None:
        sentinel = object()
        for env in ({"CLEANRUN_ENV": "production"}, {"CLEANRUN_ENV": "development"}):
            with patch.dict(os.environ, env, clear=False):
                with patch("app.supabase_client.get_supabase_client", return_value=sentinel) as authed:
                    with patch("app.supabase_client.get_public_supabase_client") as public:
                        self.assertIs(get_data_supabase_client(), sentinel)
                        authed.assert_called_once()
                        public.assert_not_called()

    def test_use_public_launch_data_client_is_removed(self) -> None:
        import app.supabase_client as supabase_client_module

        self.assertFalse(hasattr(supabase_client_module, "use_public_launch_data_client"))


if __name__ == "__main__":
    unittest.main()
