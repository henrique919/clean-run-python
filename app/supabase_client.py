import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url:
        raise RuntimeError("Missing SUPABASE_URL environment variable")

    if not supabase_key:
        raise RuntimeError("Missing SUPABASE_KEY environment variable")

    return create_client(supabase_url, supabase_key)
