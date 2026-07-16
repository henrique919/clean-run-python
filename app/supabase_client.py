import importlib
import os
import sys
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any


_access_token: ContextVar[str | None] = ContextVar("supabase_access_token", default=None)


def set_supabase_access_token(token: str | None):
    return _access_token.set(token)


def reset_supabase_access_token(token) -> None:
    _access_token.reset(token)


@lru_cache
def get_public_supabase_client() -> Any:
    return _build_supabase_client()


def get_supabase_client() -> Any:
    token = _access_token.get()
    if token:
        return _build_supabase_client(token)
    return get_public_supabase_client()


def use_public_launch_data_client() -> bool:
    """True when production is still on the temporary public-launch Supabase path.

    Storage already writes evidence under cleanrun/public/* with the anon key
    (see app/storage.py). Table writes must match: attaching a user JWT switches
    PostgREST to the authenticated role, and if authenticated launch RLS is
    missing/incomplete, item create fails with a 503 after login is enabled.
    """
    if (os.getenv("CLEANRUN_ENV") or "").lower() != "production":
        return False
    prefix = (os.getenv("CLEANRUN_STORAGE_PATH_PREFIX") or "cleanrun/public").strip().strip("/")
    return prefix == "cleanrun/public" or prefix.startswith("cleanrun/public/")


def get_data_supabase_client() -> Any:
    """Client for item/settings table reads and writes in the active storage mode."""
    if use_public_launch_data_client():
        return get_public_supabase_client()
    return get_supabase_client()


def _build_supabase_client(access_token: str | None = None) -> Any:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    legacy_key = os.getenv("SUPABASE_KEY")

    if os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY must not be configured in the web app process")

    if not supabase_key and legacy_key and os.getenv("CLEANRUN_ENV", "development").lower() != "production":
        supabase_key = legacy_key

    if not supabase_url:
        raise RuntimeError("Missing SUPABASE_URL environment variable")

    if not supabase_key:
        raise RuntimeError("Missing SUPABASE_PUBLISHABLE_KEY environment variable")

    create_client = _load_supabase_create_client()
    client = create_client(supabase_url, supabase_key)
    if access_token:
        auth = getattr(getattr(client, "postgrest", None), "auth", None)
        if callable(auth):
            auth(access_token)
    return client


def _load_supabase_create_client() -> Any:
    repo_root = Path(__file__).resolve().parents[1]
    original_path = list(sys.path)
    existing = sys.modules.get("supabase")
    if existing is not None and not hasattr(existing, "create_client"):
        sys.modules.pop("supabase", None)

    try:
        sys.path = [
            path
            for path in original_path
            if path and Path(path).resolve() != repo_root
        ]
        module = importlib.import_module("supabase")
    except Exception as exc:
        raise RuntimeError("Supabase Python client is unavailable. Check requirements.txt installation.") from exc
    finally:
        sys.path = original_path

    create_client = getattr(module, "create_client", None)
    if create_client is None:
        raise RuntimeError("Installed Supabase Python client does not expose create_client")

    return create_client
