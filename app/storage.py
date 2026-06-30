from __future__ import annotations

import base64
import logging
import os
from uuid import uuid4

from app.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")
MAX_IMAGE_BYTES = int(os.getenv("CLEANRUN_MAX_IMAGE_BYTES", "8000000"))
SIGNED_URL_TTL_SECONDS = int(os.getenv("CLEANRUN_STORAGE_SIGNED_URL_TTL_SECONDS", "604800"))

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _is_production() -> bool:
    return os.getenv("CLEANRUN_ENV", "development").lower() == "production"


def is_data_url(value: str | None) -> bool:
    return bool(value and value.startswith("data:image/") and ";base64," in value)


def _split_data_url(value: str) -> tuple[str, bytes]:
    header, encoded = value.split(",", 1)
    content_type = header.replace("data:", "").split(";", 1)[0].lower()
    if content_type not in CONTENT_TYPE_EXT:
        raise ValueError(f"Unsupported image type: {content_type}")
    data = base64.b64decode(encoded)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image is too large for storage upload")
    return content_type, data


def _signed_url(client, path: str) -> str:
    result = client.storage.from_(BUCKET_NAME).create_signed_url(path, SIGNED_URL_TTL_SECONDS)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signed_url") or path
    return str(result)


def _ensure_bucket(client) -> None:
    try:
        client.storage.get_bucket(BUCKET_NAME)
        return
    except Exception:
        if _is_production():
            logger.info(
                "Skipping Supabase Storage bucket creation check in production; "
                "bucket %s must be managed by migrations.",
                BUCKET_NAME,
            )
            return

    try:
        client.storage.create_bucket(
            BUCKET_NAME,
            options={
                "public": False,
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                "file_size_limit": MAX_IMAGE_BYTES,
            },
        )
    except Exception:
        logger.exception("Could not create Supabase Storage bucket %s", BUCKET_NAME)
        raise


def _object_path(folder: str, ext: str) -> str:
    prefix = os.getenv("CLEANRUN_STORAGE_PATH_PREFIX", "").strip().strip("/")
    if not prefix:
        prefix = "cleanrun/public" if _is_production() else "local-dev/unlinked/unlinked"
    return f"{prefix}/{folder}/{uuid4().hex}{ext}"


def upload_data_url(value: str, *, folder: str = "evidence") -> str:
    """Upload a browser data URL to private Supabase Storage and return a signed URL."""
    content_type, data = _split_data_url(value)
    ext = CONTENT_TYPE_EXT[content_type]
    path = _object_path(folder, ext)
    client = get_supabase_client()
    _ensure_bucket(client)
    client.storage.from_(BUCKET_NAME).upload(
        path=path,
        file=data,
        file_options={
            "content-type": content_type,
            "cache-control": "31536000",
            "upsert": "false",
        },
    )
    return _signed_url(client, path)


def normalize_photo(value: str | None, *, folder: str = "evidence") -> str | None:
    if not value:
        return value
    if is_data_url(value):
        return upload_data_url(value, folder=folder)
    return value
