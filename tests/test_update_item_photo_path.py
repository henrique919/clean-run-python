"""Characterization tests for PATCH item photo update path (diagnostics only)."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from app.storage import normalize_photo


class UpdateItemPhotoPathTests(unittest.TestCase):
    def test_normalize_photo_uploads_only_data_urls_not_signed_paths(self) -> None:
        signed = (
            "https://project.supabase.co/storage/v1/object/sign/cleanrun-evidence/"
            "projects/jura/items/def-1001/original/existing.jpg?token=abc"
        )
        data_url = "data:image/jpeg;base64," + base64.b64encode(b"x" * 1200).decode()
        uploads: list[str] = []

        def fake_upload(value: str, *, folder: str = "evidence") -> str:
            uploads.append(value[:32])
            return f"{folder}/uploaded.jpg"

        with patch("app.storage.upload_data_url", side_effect=fake_upload):
            results = [
                normalize_photo(signed, folder="projects/demo/original"),
                normalize_photo(data_url, folder="projects/demo/original"),
                normalize_photo("projects/demo/original/existing.jpg", folder="projects/demo/original"),
            ]

        self.assertEqual(
            results,
            [
                "projects/jura/items/def-1001/original/existing.jpg",
                "projects/demo/original/uploaded.jpg",
                "projects/demo/original/existing.jpg",
            ],
        )
        self.assertEqual(len(uploads), 1)
