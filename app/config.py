from __future__ import annotations

import os


def app_env() -> str:
    return (os.getenv("APP_ENV") or os.getenv("CLEANRUN_ENV") or "development").lower()


def is_production() -> bool:
    return app_env() == "production"


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def storage_backend() -> str:
    return (os.getenv("CLEANRUN_STORAGE") or "local").lower()


def login_required() -> bool:
    # Default ON: a missing/misconfigured env var must fail closed, not grant
    # anonymous callers open-access admin (see _open_access_user in auth.py).
    # Set CLEANRUN_LOGIN_REQUIRED=false to explicitly opt into open access
    # (local dev only; render.yaml pins "true" in production regardless).
    return bool_env("CLEANRUN_LOGIN_REQUIRED", default=True)
