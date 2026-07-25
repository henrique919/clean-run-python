from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.supabase_client import (
    _authenticated_supabase_client,
    get_public_supabase_client,
    get_supabase_client,
    reset_supabase_access_token,
    set_supabase_access_token,
)

ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiJ9.test-anon"
USER_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.test-user"
OTHER_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYXV0aGVudGljYXRlZCJ9.other-user"

ENV = {
    "SUPABASE_URL": "https://unit-test.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": ANON_KEY,
}


def _clear_caches() -> None:
    get_public_supabase_client.cache_clear()
    _authenticated_supabase_client.cache_clear()


class SupabaseClientAuthHeaderTests(unittest.TestCase):
    """The user's JWT must reach EVERY sub-client, storage included.

    Regression guard for the launch-week incident where storage RLS was
    locked to authenticated callers but the server's storage client kept
    sending the anon key: table writes worked while photo upload/signing
    failed with 400s. Asserting on the storage sub-client's real headers
    (not on our own wrapper) is the point of these tests.
    """

    def setUp(self) -> None:
        _clear_caches()
        self.addCleanup(_clear_caches)

    def test_token_client_sends_jwt_on_storage_and_postgrest(self) -> None:
        with patch.dict(os.environ, ENV, clear=False):
            token_ref = set_supabase_access_token(USER_JWT)
            try:
                client = get_supabase_client()
            finally:
                reset_supabase_access_token(token_ref)
        self.assertEqual(
            client.storage._client.headers.get("authorization"),
            f"Bearer {USER_JWT}",
        )
        self.assertEqual(
            client.postgrest.session.headers.get("authorization"),
            f"Bearer {USER_JWT}",
        )
        self.assertEqual(client.storage._client.headers.get("apikey"), ANON_KEY)

    def test_no_token_falls_back_to_anon_client(self) -> None:
        with patch.dict(os.environ, ENV, clear=False):
            client = get_supabase_client()
        self.assertEqual(
            client.storage._client.headers.get("authorization"),
            f"Bearer {ANON_KEY}",
        )

    def test_same_token_reuses_client_and_tokens_do_not_cross(self) -> None:
        with patch.dict(os.environ, ENV, clear=False):
            ref = set_supabase_access_token(USER_JWT)
            try:
                first = get_supabase_client()
                second = get_supabase_client()
            finally:
                reset_supabase_access_token(ref)
            ref = set_supabase_access_token(OTHER_JWT)
            try:
                other = get_supabase_client()
            finally:
                reset_supabase_access_token(ref)
        self.assertIs(first, second)
        self.assertIsNot(first, other)
        self.assertEqual(
            other.storage._client.headers.get("authorization"),
            f"Bearer {OTHER_JWT}",
        )


if __name__ == "__main__":
    unittest.main()
