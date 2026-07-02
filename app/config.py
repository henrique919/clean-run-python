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
    # Default off for the current launch window; set CLEANRUN_LOGIN_REQUIRED=true to restore sign-in.
    return bool_env("CLEANRUN_LOGIN_REQUIRED", default=False)
