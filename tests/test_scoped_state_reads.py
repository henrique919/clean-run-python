from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer


class SnapshotProjectScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_snapshot_with_project_returns_only_that_project(self) -> None:
        data = self.store.snapshot()
        projects = {item.project for item in data.items}
        self.assertGreater(len(projects), 1, "seed data must span projects for this test")
        target = sorted(projects)[0]

        scoped = self.store.snapshot(project=target)

        self.assertTrue(scoped.items)
        self.assertEqual({item.project for item in scoped.items}, {target})
        self.assertEqual(
            len(scoped.items),
            sum(1 for item in data.items if item.project == target),
        )

    def test_snapshot_without_project_is_unchanged(self) -> None:
        self.assertEqual(
            [item.id for item in self.store.snapshot().items],
            [item.id for item in self.store.snapshot(project=None).items],
        )

    def test_settings_snapshot_matches_full_snapshot_settings(self) -> None:
        self.assertEqual(
            self.store.settings_snapshot().model_dump(),
            self.store.snapshot().settings.model_dump(),
        )


class ActiveScopeStateRouteTests(unittest.TestCase):
    """scope=active must return the same items as the old read-everything-
    then-filter implementation, now that the read itself is scoped."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def test_active_scope_returns_only_active_project_items(self) -> None:
        response = self.client.get(
            "/api/state?scope=active&photos=lazy",
            headers=bearer("dev-site-manager"),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        active = payload["settings"]["activeProject"]
        self.assertTrue(active)
        self.assertTrue(payload["items"])
        self.assertEqual({item["project"] for item in payload["items"]}, {active})

    def test_all_scope_still_returns_every_visible_project(self) -> None:
        response = self.client.get(
            "/api/state?scope=all&photos=lazy",
            headers=bearer("dev-site-manager"),
        )
        self.assertEqual(response.status_code, 200)
        projects = {item["project"] for item in response.json()["items"]}
        self.assertGreater(len(projects), 1)


if __name__ == "__main__":
    unittest.main()
