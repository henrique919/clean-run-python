from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.models import Item, ItemStatus, ItemType, Priority, SyncState, now_iso
from app.storage import (
    SIGNED_URL_CACHE_MAX_AGE_SECONDS,
    SIGNED_URL_TTL_SECONDS,
    SignedUrlCache,
    collect_item_sign_requests,
    signed_url_cache,
)


class FakeBucket:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    def create_signed_url(self, path, ttl, options=None):
        self.calls.append((path, (options or {}).get("transform")))
        transform = (options or {}).get("transform")
        if transform:
            return {"signedURL": f"https://signed.example/render/{path}?w={transform['width']}"}
        return {"signedURL": f"https://signed.example/object/{path}"}


class FakeStorage:
    def __init__(self) -> None:
        self.bucket = FakeBucket()

    def from_(self, bucket):
        return self.bucket


class FakeClient:
    def __init__(self) -> None:
        self.storage = FakeStorage()


class SignedUrlCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        signed_url_cache.clear()

    def test_cache_reuses_same_path_and_transform(self) -> None:
        client = FakeClient()
        with patch("app.storage._client_for_storage_path", return_value=client):
            first = signed_url_cache.get("projects/demo/photo.jpg")
            second = signed_url_cache.get("projects/demo/photo.jpg")
        self.assertEqual(first, second)
        self.assertEqual(len(client.storage.bucket.calls), 1)

    def test_full_and_thumb_variants_cached_separately(self) -> None:
        client = FakeClient()
        transform = {"width": 284, "height": 216, "resize": "cover"}
        with patch("app.storage._client_for_storage_path", return_value=client):
            full = signed_url_cache.get("projects/demo/photo.jpg")
            thumb = signed_url_cache.get("projects/demo/photo.jpg", transform=transform)
            full_again = signed_url_cache.get("projects/demo/photo.jpg")
        self.assertNotEqual(full, thumb)
        self.assertEqual(full, full_again)
        self.assertEqual(len(client.storage.bucket.calls), 2)

    def test_cache_expires_before_supabase_ttl(self) -> None:
        self.assertLess(SIGNED_URL_CACHE_MAX_AGE_SECONDS, SIGNED_URL_TTL_SECONDS)
        self.assertGreaterEqual(SIGNED_URL_CACHE_MAX_AGE_SECONDS, SIGNED_URL_TTL_SECONDS - 86400)

    def test_prefetch_signs_each_variant_once(self) -> None:
        item = Item(
            code="DEF-001",
            type=ItemType.DEFECT,
            project="Jura Noosa",
            due_date="2026-07-07",
            description="Probe",
            original_photos=["projects/jura/items/def-001/original/abc.jpg"],
            priority=Priority.HIGH,
            created_at=now_iso(),
            updated_at=now_iso(),
            sync=SyncState.SYNCED,
        )
        requests = collect_item_sign_requests(item)
        self.assertEqual(len(requests), 2)
        client = FakeClient()
        with patch("app.storage._client_for_storage_path", return_value=client):
            signed_url_cache.prefetch(requests)
            signed_url_cache.prefetch(requests)
        self.assertEqual(len(client.storage.bucket.calls), 2)

    def test_rate_limit_retries_once(self) -> None:
        cache = SignedUrlCache()
        attempts = {"count": 0}
        client = FakeClient()

        def flaky_create(client_arg, path, *, transform=None):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("429 Too Many Requests")
            return f"https://signed.example/{path}"

        with patch("app.storage._client_for_storage_path", return_value=client):
            with patch("app.storage._create_signed_url", side_effect=flaky_create):
                with patch("app.storage.time.sleep", return_value=None):
                    url = cache._sign_with_retry("projects/demo/photo.jpg", None)
        self.assertEqual(url, "https://signed.example/projects/demo/photo.jpg")
        self.assertEqual(attempts["count"], 2)


if __name__ == "__main__":
    unittest.main()
