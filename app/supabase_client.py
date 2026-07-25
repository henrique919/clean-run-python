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


# Keyed by the exact JWT so clients (and their pooled HTTP connections) are
# reused across the many storage/table calls a single request fans out to,
# instead of paying client + connection setup per call. Distinct tokens get
# distinct entries, so no cross-user reuse; expired-token entries just 401
# and age out of the LRU.
@lru_cache(maxsize=32)
def _authenticated_supabase_client(access_token: str) -> Any:
    return _build_supabase_client(access_token)


def get_supabase_client() -> Any:
    token = _access_token.get()
    if token:
        return _authenticated_supabase_client(token)
    return get_public_supabase_client()


def get_data_supabase_client() -> Any:
    """Client for item/settings table reads and writes.

    Always forwards the caller's JWT (falls back to the anon/public client
    only when no request token is set, e.g. no caller context). Table RLS
    requires `authenticated` for every launch-mode table — see supabase/
    migrations/202607250001_close_anon_data_access.sql. Do not special-case
    a public/anon path here again: the anon role has no grants left.
    """
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

    create_client, client_options_cls = _load_supabase_create_client()
    if access_token:
        # The Authorization header must be set at construction: every
        # sub-client (postgrest AND storage) copies options.headers when it
        # is created. The previous postgrest.auth(access_token) call only
        # updated postgrest, so storage requests (upload, sign) kept going
        # out as the anon key — which storage RLS now rejects (migration
        # 202607250001_close_anon_data_access.sql).
        options = client_options_cls(headers={"Authorization": f"Bearer {access_token}"})
        return create_client(supabase_url, supabase_key, options)
    return create_client(supabase_url, supabase_key)


def _load_supabase_create_client() -> tuple[Any, Any]:
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

    client_options_cls = getattr(module, "ClientOptions", None)
    if client_options_cls is None:
        raise RuntimeError("Installed Supabase Python client does not expose ClientOptions")

    return create_client, client_options_cls
