import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase_client() -> Client:
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

    return create_client(supabase_url, supabase_key)
