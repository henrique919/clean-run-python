from __future__ import annotations

import base64
import json
import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from app.supabase_client import get_public_supabase_client, get_supabase_client

logger = logging.getLogger(__name__)

BUCKET_NAME = os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")
MAX_IMAGE_BYTES = int(os.getenv("CLEANRUN_MAX_IMAGE_BYTES", "8000000"))
SIGNED_URL_TTL_SECONDS = int(os.getenv("CLEANRUN_STORAGE_SIGNED_URL_TTL_SECONDS", "604800"))
# Re-sign before Supabase TTL expires so users never hold a URL that dies mid-session.
SIGNED_URL_CACHE_MAX_AGE_SECONDS = int(
    os.getenv(
        "CLEANRUN_SIGNED_URL_CACHE_SECONDS",
        str(max(60, SIGNED_URL_TTL_SECONDS - 86400)),
    )
)
SIGN_URL_MAX_WORKERS = int(os.getenv("CLEANRUN_SIGN_URL_MAX_WORKERS", "10"))
SIGN_URL_RETRY_BACKOFF_SECONDS = float(os.getenv("CLEANRUN_SIGN_URL_RETRY_BACKOFF_SECONDS", "0.75"))
# Item card is 142×108 CSS px; thumbnails are centre-cropped at 2× for retina.
LIST_CARD_THUMB_WIDTH = 284
LIST_CARD_THUMB_HEIGHT = 216

CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class StorageUploadError(ValueError):
    """Raised when browser evidence cannot be accepted by Supabase Storage."""


def _is_production() -> bool:
    return os.getenv("CLEANRUN_ENV", "development").lower() == "production"


def _storage_path_prefix() -> str:
    prefix = os.getenv("CLEANRUN_STORAGE_PATH_PREFIX", "").strip().strip("/")
    if prefix:
        return prefix
    return "cleanrun/public" if _is_production() else "local-dev/unlinked/unlinked"


def _uses_public_launch_prefix(path: str | None) -> bool:
    if not path:
        return False
    prefix = _storage_path_prefix()
    return path == prefix or path.startswith(f"{prefix}/")


def _client_for_storage_path(path: str):
    # Launch mode stores browser evidence under cleanrun/public/* with anon-only
    # RLS. Do not attach the user's JWT for these temporary public-mode paths.
    if _uses_public_launch_prefix(path):
        return get_public_supabase_client()
    return get_supabase_client()


def is_data_url(value: str | None) -> bool:
    return bool(value and value.startswith("data:image/") and ";base64," in value)


def _split_data_url(value: str) -> tuple[str, bytes]:
    header, encoded = value.split(",", 1)
    content_type = header.replace("data:", "").split(";", 1)[0].lower()
    if content_type not in CONTENT_TYPE_EXT:
        if content_type in {"image/heic", "image/heif"}:
            raise StorageUploadError(
                "HEIC photos are not supported. Change iPhone Camera settings to Most Compatible (JPEG) or export the photo as JPEG before uploading."
            )
        raise StorageUploadError(f"Unsupported image type: {content_type}. Use JPEG, PNG, or WebP.")
    data = base64.b64decode(encoded)
    if len(data) > MAX_IMAGE_BYTES:
        raise StorageUploadError("Image is too large for storage upload. Retake it or upload a smaller photo.")
    return content_type, data


def _transform_cache_key(transform: dict[str, object] | None) -> str:
    if not transform:
        return ""
    return json.dumps(transform, sort_keys=True, separators=(",", ":"))


def _sign_cache_key(path: str, transform: dict[str, object] | None) -> str:
    return f"{path}\0{_transform_cache_key(transform)}"


def _is_rate_limited(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429:
        return True
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "too many requests" in message


def _extract_signed_url(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signed_url") or ""
    return str(result)


def _create_signed_url(client, path: str, *, transform: dict[str, object] | None = None) -> str:
    options: dict[str, object] = {}
    if transform:
        options["transform"] = transform
    result = client.storage.from_(BUCKET_NAME).create_signed_url(path, SIGNED_URL_TTL_SECONDS, options)
    signed = _extract_signed_url(result)
    if not signed:
        raise RuntimeError(f"Supabase create_signed_url returned no URL for {path}")
    return signed


class SignedUrlCache:
    """In-memory signed URL cache for single-worker deployments."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._entries: dict[str, tuple[str, float]] = {}
        self._pending: dict[str, Future[str]] = {}
        self._executor = ThreadPoolExecutor(max_workers=SIGN_URL_MAX_WORKERS, thread_name_prefix="sign-url")

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"entries": len(self._entries), "pending": len(self._pending)}

    def _sign_with_retry(self, path: str, transform: dict[str, object] | None) -> str:
        client = _client_for_storage_path(path)
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                return _create_signed_url(client, path, transform=transform)
            except Exception as exc:
                last_error = exc
                if attempt == 0 and _is_rate_limited(exc):
                    time.sleep(SIGN_URL_RETRY_BACKOFF_SECONDS)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError(f"Could not sign URL for {path}")

    def _sign_and_store(self, key: str, path: str, transform: dict[str, object] | None) -> str:
        url = self._sign_with_retry(path, transform)
        expires_at = time.monotonic() + SIGNED_URL_CACHE_MAX_AGE_SECONDS
        with self._lock:
            self._entries[key] = (url, expires_at)
        return url

    def _pending_future(self, key: str, path: str, transform: dict[str, object] | None) -> Future[str]:
        pending = self._pending.get(key)
        if pending is None:
            pending = self._executor.submit(self._sign_and_store, key, path, transform)
            self._pending[key] = pending
        return pending

    def get(self, path: str, *, transform: dict[str, object] | None = None) -> str:
        key = _sign_cache_key(path, transform)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry[1] > now:
                return entry[0]
            pending = self._pending_future(key, path, transform)
        try:
            return pending.result()
        finally:
            with self._lock:
                if self._pending.get(key) is pending and pending.done():
                    self._pending.pop(key, None)

    def prefetch(self, requests: list[tuple[str, dict[str, object] | None]]) -> None:
        """Warm the cache for many paths using the signing thread pool."""
        unique: dict[str, tuple[str, dict[str, object] | None]] = {}
        now = time.monotonic()
        with self._lock:
            for path, transform in requests:
                if not path or path.startswith(("data:image/", "seed://")):
                    continue
                key = _sign_cache_key(path, transform)
                entry = self._entries.get(key)
                if entry and entry[1] > now:
                    continue
                unique[key] = (path, transform)
            futures = [
                (key, self._pending_future(key, path, transform))
                for key, (path, transform) in unique.items()
            ]
        for key, future in futures:
            try:
                future.result()
            except Exception:
                logger.exception("Signed URL prefetch failed")
            finally:
                with self._lock:
                    if self._pending.get(key) is future and future.done():
                        self._pending.pop(key, None)


signed_url_cache = SignedUrlCache()


def _signed_url(client, path: str, *, transform: dict[str, object] | None = None) -> str:
    del client  # client selection is path-based; cache owns signing
    return signed_url_cache.get(path, transform=transform)


def _path_from_signed_url(value: str) -> str | None:
    parsed = urlsplit(value)
    for marker in (
        f"/storage/v1/object/sign/{BUCKET_NAME}/",
        f"/storage/v1/render/image/sign/{BUCKET_NAME}/",
    ):
        if marker in parsed.path:
            return unquote(parsed.path.split(marker, 1)[1])
    return None


def storage_path_from_value(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith("data:image/") or value.startswith("seed://"):
        return value
    if value.startswith("http"):
        return _path_from_signed_url(value) or value
    return value


def list_thumbnail_transform(
    *,
    width: int = LIST_CARD_THUMB_WIDTH,
    height: int = LIST_CARD_THUMB_HEIGHT,
) -> dict[str, object]:
    return {
        "width": max(1, min(int(width), 2500)),
        "height": max(1, min(int(height), 2500)),
        "resize": "cover",
    }


def collect_item_sign_requests(item) -> list[tuple[str, dict[str, object] | None]]:
    """Collect unique storage paths and transform variants needed for one item."""
    requests: list[tuple[str, dict[str, object] | None]] = []
    thumb_transform = list_thumbnail_transform()

    def add(value: str | None, *, transform: dict[str, object] | None = None) -> None:
        path = storage_path_from_value(value)
        if not path or path.startswith(("data:image/", "seed://")):
            return
        requests.append((path, transform))

    for photo in item.original_photos:
        add(photo)
        add(photo, transform=thumb_transform)
    for evidence in item.rectification_evidence:
        if evidence.photo:
            add(evidence.photo)
    for evidence in item.closeout_evidence:
        if evidence.photo:
            add(evidence.photo)
    return requests


def prefetch_item_photo_urls(items) -> None:
    """Parallel prefetch for /api/state cold-cache loads."""
    requests: list[tuple[str, dict[str, object] | None]] = []
    for item in items:
        requests.extend(collect_item_sign_requests(item))
    signed_url_cache.prefetch(requests)


def resolve_photo_url(value: str | None) -> str | None:
    return _resolve_storage_url(value)


def resolve_thumbnail_url(
    value: str | None,
    *,
    width: int = LIST_CARD_THUMB_WIDTH,
    height: int = LIST_CARD_THUMB_HEIGHT,
) -> str | None:
    if not value or value.startswith(("data:image/", "seed://")):
        return value
    return _resolve_storage_url(value, transform=list_thumbnail_transform(width=width, height=height))


def _resolve_storage_url(value: str | None, *, transform: dict[str, object] | None = None) -> str | None:
    if not value:
        return value
    if value.startswith(("data:image/", "seed://")):
        return value
    if value.startswith("http"):
        path = _path_from_signed_url(value)
        if not path:
            return value
        value = path
    try:
        return signed_url_cache.get(value, transform=transform)
    except Exception:
        logger.exception("Could not create signed URL for Supabase Storage object %s", value)
        return None


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
    return f"{_storage_path_prefix()}/{folder}/{uuid4().hex}{ext}"


def upload_data_url(value: str, *, folder: str = "evidence") -> str:
    """Upload a browser data URL to private Supabase Storage and return the stable object path."""
    content_type, data = _split_data_url(value)
    ext = CONTENT_TYPE_EXT[content_type]
    path = _object_path(folder, ext)
    client = _client_for_storage_path(path)
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
    return path


def normalize_photo(value: str | None, *, folder: str = "evidence") -> str | None:
    if not value:
        return value
    if is_data_url(value):
        return upload_data_url(value, folder=folder)
    return storage_path_from_value(value)
