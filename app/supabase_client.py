import importlib
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache
def get_supabase_client() -> Any:
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
    return create_client(supabase_url, supabase_key)


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
