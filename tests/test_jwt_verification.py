"""Local Supabase JWT verification: audience check and clock-skew leeway.

Previously `verify_aud` was only enabled when SUPABASE_JWT_AUDIENCE was
set, and render.yaml never set it — so the `aud` claim was never actually
checked locally. Any local verification failure also silently fell
through to a live network call with no log line, which would make every
authenticated request pay a synchronous round-trip if the configured
secret were ever wrong, with nothing in the logs explaining why.
"""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

import jwt as pyjwt

from app.auth import _decode_supabase_jwt

SECRET = "test-jwt-secret"


def _token(*, aud: str = "authenticated", exp_offset: int = 3600, sub: str = "user-123") -> str:
    payload = {
        "sub": sub,
        "email": "site.manager@example.com",
        "aud": aud,
        "exp": int(time.time()) + exp_offset,
        "app_metadata": {},
    }
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


class JwtVerificationTests(unittest.TestCase):
    def test_correct_audience_verifies_locally_without_network_fallback(self) -> None:
        env = {"SUPABASE_JWT_SECRET": SECRET, "SUPABASE_JWT_AUDIENCE": "authenticated"}
        with patch.dict(os.environ, env, clear=False):
            with patch("app.auth._fetch_supabase_auth_user", side_effect=AssertionError("should not reach network fallback")):
                user = _decode_supabase_jwt(_token(aud="authenticated"))
        self.assertEqual(user.id, "user-123")

    def test_wrong_audience_is_rejected_locally_and_falls_through(self) -> None:
        env = {"SUPABASE_JWT_SECRET": SECRET, "SUPABASE_JWT_AUDIENCE": "authenticated"}
        fallback_claims = {"sub": "fallback-user", "email": "fallback@example.com", "app_metadata": {}}
        with patch.dict(os.environ, env, clear=False):
            with patch("app.auth._fetch_supabase_auth_user", return_value=fallback_claims) as fallback:
                user = _decode_supabase_jwt(_token(aud="some-other-audience"))
        fallback.assert_called_once()
        self.assertEqual(user.id, "fallback-user")

    def test_audience_not_checked_when_env_var_unset(self) -> None:
        # Matches pre-existing behaviour when SUPABASE_JWT_AUDIENCE isn't
        # configured at all — still verify_aud=False, so a mismatched aud
        # doesn't (by itself) force the network fallback.
        env = {"SUPABASE_JWT_SECRET": SECRET}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("SUPABASE_JWT_AUDIENCE", None)
            with patch("app.auth._fetch_supabase_auth_user", side_effect=AssertionError("should not reach network fallback")):
                user = _decode_supabase_jwt(_token(aud="some-other-audience"))
        self.assertEqual(user.id, "user-123")

    def test_leeway_tolerates_small_clock_skew(self) -> None:
        env = {"SUPABASE_JWT_SECRET": SECRET, "SUPABASE_JWT_AUDIENCE": "authenticated"}
        with patch.dict(os.environ, env, clear=False):
            with patch("app.auth._fetch_supabase_auth_user", side_effect=AssertionError("should not reach network fallback")):
                user = _decode_supabase_jwt(_token(exp_offset=-10))
        self.assertEqual(user.id, "user-123")

    def test_expired_beyond_leeway_falls_through_to_network(self) -> None:
        env = {"SUPABASE_JWT_SECRET": SECRET, "SUPABASE_JWT_AUDIENCE": "authenticated"}
        fallback_claims = {"sub": "fallback-user", "email": "fallback@example.com", "app_metadata": {}}
        with patch.dict(os.environ, env, clear=False):
            with patch("app.auth._fetch_supabase_auth_user", return_value=fallback_claims) as fallback:
                user = _decode_supabase_jwt(_token(exp_offset=-120))
        fallback.assert_called_once()
        self.assertEqual(user.id, "fallback-user")

    def test_local_verification_failure_is_logged_not_silent(self) -> None:
        env = {"SUPABASE_JWT_SECRET": SECRET, "SUPABASE_JWT_AUDIENCE": "authenticated"}
        fallback_claims = {"sub": "fallback-user", "email": "fallback@example.com", "app_metadata": {}}
        with patch.dict(os.environ, env, clear=False):
            with patch("app.auth._fetch_supabase_auth_user", return_value=fallback_claims):
                with self.assertLogs("app.auth", level="WARNING") as captured:
                    _decode_supabase_jwt(_token(aud="wrong-audience"))
        self.assertTrue(any("falling back to Supabase Auth API" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
