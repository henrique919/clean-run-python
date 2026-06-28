from __future__ import annotations

import logging

from app.config import app_env, bool_env, is_production, storage_backend
from app.repositories.base import CleanRunRepository
from app.repositories.local_repository import LocalCleanRunRepository

logger = logging.getLogger(__name__)


def build_repository() -> CleanRunRepository:
    backend = storage_backend()
    environment = app_env()
    logger.info("CleanRun IQ starting with storage backend=%s environment=%s", backend, environment)

    if backend == "supabase":
        from app.repositories.supabase_repository import SupabaseCleanRunRepository

        try:
            repository = SupabaseCleanRunRepository()
        except Exception as exc:
            logger.exception("Supabase storage startup failed. Refusing to fall back to local JSON storage.")
            raise RuntimeError("CLEANRUN_STORAGE=supabase but Supabase is unavailable or misconfigured") from exc
        logger.info("CleanRun IQ active repository=SupabaseCleanRunRepository")
        return repository

    if backend in {"local", "json", "demo"}:
        if is_production() and not bool_env("ALLOW_LOCAL_STORAGE_IN_PRODUCTION"):
            logger.critical(
                "Unsafe production storage refused: CLEANRUN_STORAGE=%s with APP_ENV/CLEANRUN_ENV=production.",
                backend,
            )
            raise RuntimeError("Local JSON storage is refused in production")
        logger.warning("CleanRun IQ active repository=LocalCleanRunRepository. Use only for local/demo environments.")
        return LocalCleanRunRepository()

    raise RuntimeError(f"Unsupported CLEANRUN_STORAGE value: {backend}")
