from __future__ import annotations

from app.store_supabase import SupabaseCleanRunStore


class SupabaseCleanRunRepository(SupabaseCleanRunStore):
    """Production Supabase repository using normalized relational tables."""
