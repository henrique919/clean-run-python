import os
from functools import lru_cache
from supabase import create_client, Client


@lru_cache
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not url:
        raise RuntimeError("Missing SUPABASE_URL")

    if not key:
        raise RuntimeError("Missing SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")

    return create_client(url, key)
