from __future__ import annotations

import base64
import logging
import os
from uuid import uuid4

from app.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")
MAX_IMAGE_BYTES = int(os.getenv("CLEANRUN_MAX_IMAGE_BYTES", "8000000"))

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


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


def _public_url(client, path: str) -> str:
    result = client.storage.from_(BUCKET_NAME).get_public_url(path)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("publicUrl") or result.get("public_url") or result.get("signedURL") or path
    return str(result)


def _ensure_bucket(client) -> None:
    try:
        client.storage.get_bucket(BUCKET_NAME)
        return
    except Exception:
        pass

    try:
        client.storage.create_bucket(
            BUCKET_NAME,
            options={
                "public": True,
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                "file_size_limit": MAX_IMAGE_BYTES,
            },
        )
    except Exception:
        logger.exception("Could not create Supabase Storage bucket %s", BUCKET_NAME)
        raise


def upload_data_url(value: str, *, folder: str = "evidence") -> str:
    """Upload a browser data URL to Supabase Storage and return its public URL."""
    content_type, data = _split_data_url(value)
    ext = CONTENT_TYPE_EXT[content_type]
    path = f"{folder}/{uuid4().hex}{ext}"
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
    return _public_url(client, path)


def normalize_photo(value: str | None, *, folder: str = "evidence") -> str | None:
    if not value:
        return value
    if is_data_url(value):
        return upload_data_url(value, folder=folder)
    return value
