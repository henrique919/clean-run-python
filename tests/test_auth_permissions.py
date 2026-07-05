from __future__ import annotations

import os
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import urlsplit
from unittest.mock import patch

from app import main as app_main
from app.auth import _user_from_claims
from app.models import ItemCreate, RectificationEvidence
from app.store import CleanRunStore


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass
class AsgiResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


class AsgiClient:
    def __init__(self, app) -> None:
        self.app = app

    def request(self, method: str, path: str, *, headers: dict[str, str] | None = None, json_body=None) -> AsgiResponse:
        return asyncio.run(self._request(method, path, headers=headers or {}, json_body=json_body))

    async def _request(self, method: str, path: str, *, headers: dict[str, str], json_body) -> AsgiResponse:
        parsed = urlsplit(path)
        body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
        raw_headers = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()]
        if json_body is not None:
            raw_headers.append((b"content-type", b"application/json"))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": parsed.path,
            "raw_path": parsed.path.encode("ascii"),
            "query_string": parsed.query.encode("ascii"),
            "headers": raw_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        messages = []
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await self.app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        chunks = [message.get("body", b"") for message in messages if message["type"] == "http.response.body"]
        response_headers = {key.decode("latin-1"): value.decode("latin-1") for key, value in start.get("headers", [])}
        return AsgiResponse(status_code=start["status"], body=b"".join(chunks), headers=response_headers)

    def get(self, path: str, *, headers: dict[str, str] | None = None) -> AsgiResponse:
        return self.request("GET", path, headers=headers)

    def post(self, path: str, *, headers: dict[str, str] | None = None, json=None) -> AsgiResponse:
        return self.request("POST", path, headers=headers, json_body=json)

    def patch(self, path: str, *, headers: dict[str, str] | None = None, json=None) -> AsgiResponse:
        return self.request("PATCH", path, headers=headers, json_body=json)


class AuthPermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CleanRunStore(Path(self.temp_dir.name) / "cleanrun.json")
        self.store_patch = patch.object(app_main, "store", self.store)
        self.store_patch.start()
        self.client = AsgiClient(app_main.app)

    def tearDown(self) -> None:
        self.store_patch.stop()
        self.temp_dir.cleanup()

    def create_direct_item(self, *, project: str = "Jura Noosa", subcontractor: str = "ASTW Tiling"):
        return self.store.create_item(
            ItemCreate(
                project=project,
                building="B1",
                level="Level 1",
                unit="U101",
                room="Bathroom",
                trade="Tiling",
                subcontractor=subcontractor,
                due_date="2026-07-01",
                description="Tile lip at shower entry",
                original_photos=["seed://photo"],
                created_by="Fixture",
            )
        )

    def test_anonymous_workflow_requests_are_rejected(self) -> None:
        with patch.dict(os.environ, {"CLEANRUN_LOGIN_REQUIRED": "true"}, clear=False):
            self.assertEqual(self.client.get("/api/items").status_code, 401)
            response = self.client.post("/api/items", json={})
            self.assertEqual(response.status_code, 401)

    def test_open_access_is_default_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLEANRUN_LOGIN_REQUIRED", None)
            from app.config import login_required

            self.assertFalse(login_required())

    def test_anonymous_production_requests_are_rejected(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production", "CLEANRUN_ENV": "production", "CLEANRUN_LOGIN_REQUIRED": "true"}, clear=False):
            self.assertEqual(self.client.get("/api/bootstrap").status_code, 401)

    def test_open_access_when_login_not_required(self) -> None:
        with patch.dict(os.environ, {"CLEANRUN_LOGIN_REQUIRED": "false"}, clear=False):
            self.assertEqual(self.client.get("/api/bootstrap", headers=bearer("dev-site-manager")).status_code, 200)
            self.assertEqual(self.client.get("/api/bootstrap").status_code, 200)
            config = self.client.get("/api/auth/config").json()
            self.assertFalse(config["login_required"])

    def test_root_route_serves_restored_full_field_app(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="bottom-nav"', response.text)
        self.assertIn("/assets/enhancements.css?v=cards53", response.text)
        self.assertIn("/assets/enhancements.js?v=cards53", response.text)
        self.assertIn("renderLogin", response.text)

    def test_state_scope_active_returns_only_active_project(self) -> None:
        self.create_direct_item(project="Other Project", subcontractor="Other Trade")
        active = self.client.get("/api/state?scope=active&photos=lazy", headers=bearer("dev-site-manager")).json()
        full = self.client.get("/api/state?scope=all&photos=full", headers=bearer("dev-site-manager")).json()
        active_project = active["settings"]["activeProject"]

        self.assertTrue(all(item["project"] == active_project for item in active["items"]))
        self.assertGreaterEqual(len(full["items"]), len(active["items"]))
        if active["items"]:
            self.assertEqual(active["items"][0].get("originalPhotoThumbnails"), [])

    def test_anonymous_access_request_is_accepted_without_app_access(self) -> None:
        response = self.client.post(
            "/api/access-requests",
            json={
                "full_name": "Harry Site",
                "email": "harry@example.com",
                "company": "qld Built",
                "role_requested": "Project Manager",
                "project_site": "Jura Noosa",
                "message": "Please approve access.",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")
        with patch.dict(os.environ, {"CLEANRUN_LOGIN_REQUIRED": "true"}, clear=False):
            self.assertEqual(self.client.get("/api/bootstrap").status_code, 401)

    def test_project_scope_is_not_leaked_between_companies(self) -> None:
        other_item = self.create_direct_item(project="Other Project", subcontractor="Other Trade")

        response = self.client.get(f"/api/items/{other_item.id}", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 404)

    def test_viewer_can_read_but_not_mutate_project_item(self) -> None:
        item = self.store.snapshot().items[0]

        read_response = self.client.get(f"/api/items/{item.id}", headers=bearer("dev-viewer"))
        update_response = self.client.patch(
            f"/api/items/{item.id}",
            headers=bearer("dev-viewer"),
            json={"description": "Changed by viewer"},
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(update_response.status_code, 403)

    def test_subcontractor_only_sees_assigned_items_and_cannot_close(self) -> None:
        assigned = self.store.snapshot().items[0]
        hidden = self.create_direct_item(subcontractor="H&L Roofing")

        list_response = self.client.get("/api/items", headers=bearer("dev-subcontractor"))
        close_response = self.client.post(
            f"/api/items/{assigned.id}/closeout",
            headers=bearer("dev-subcontractor"),
            json={"by": "Attempt", "confirmation": "Close it"},
        )

        codes = {item["code"] for item in list_response.json()}
        self.assertIn(assigned.code, codes)
        self.assertNotIn(hidden.code, codes)
        self.assertEqual(close_response.status_code, 403)

    def test_assigned_subcontractor_can_add_rectification_evidence(self) -> None:
        item = self.store.snapshot().items[0]
        item = self.store.issue_item(item.id, to=item.subcontractor, by="Site Manager")

        response = self.client.post(
            f"/api/items/{item.id}/rectification",
            headers=bearer("dev-subcontractor"),
            json={"comment": "Tile replaced", "advance_to_ready": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rectification_evidence"][0]["by"], "astw.tiling@cleanrun.local")

    def test_create_item_audit_uses_authenticated_actor(self) -> None:
        response = self.client.post(
            "/api/items",
            headers=bearer("dev-site-manager"),
            json={
                "project": "Jura Noosa",
                "building": "B1",
                "level": "Level 1",
                "unit": "U101",
                "room": "Bathroom",
                "trade": "Tiling",
                "subcontractor": "ASTW Tiling",
                "due_date": "2026-07-01",
                "description": "Loose tile at vanity",
                "original_photos": ["seed://photo"],
                "created_by": "Spoofed Name",
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload["createdBy"], "site.manager@cleanrun.local")
        self.assertEqual(payload["auditEvents"][0]["user_id"], "dev-site-manager")
        self.assertEqual(payload["auditEvents"][0]["email"], "site.manager@cleanrun.local")

    def test_reports_require_project_access(self) -> None:
        with patch.dict(os.environ, {"CLEANRUN_LOGIN_REQUIRED": "true"}, clear=False):
            anonymous = self.client.get("/api/reports/handover")
            self.assertEqual(anonymous.status_code, 401)
        viewer = self.client.get("/api/reports/handover", headers=bearer("dev-viewer"))
        other_company = self.client.get(
            "/api/reports/handover?project=Jura%20Noosa",
            headers=bearer("dev-other-company"),
        )

        self.assertEqual(viewer.status_code, 200)
        self.assertEqual(other_company.status_code, 403)

    def test_report_route_applies_visible_item_scope(self) -> None:
        assigned = self.store.snapshot().items[0]
        hidden = self.create_direct_item(subcontractor="H&L Roofing")
        visible_ids = {assigned.id}
        original_visible_items = app_main.visible_items

        def fake_visible_items(user, items):
            return [item for item in original_visible_items(user, items) if item.id in visible_ids]

        with patch.object(app_main, "visible_items", fake_visible_items):
            report = self.client.get("/api/reports/handover", headers=bearer("dev-site-manager"))
            summary = self.client.get("/api/reports/handover/summary", headers=bearer("dev-site-manager"))

        self.assertEqual(report.status_code, 200)
        self.assertIn(assigned.code, report.text)
        self.assertNotIn(hidden.code, report.text)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["count"], 1)

    def test_viewer_cannot_add_rectification_or_comment(self) -> None:
        item = self.store.snapshot().items[0]

        rectification = self.client.post(
            f"/api/items/{item.id}/rectification",
            headers=bearer("dev-viewer"),
            json={"comment": "Viewer attempt"},
        )
        comment = self.client.post(
            f"/api/items/{item.id}/comments",
            headers=bearer("dev-viewer"),
            json={"text": "Viewer comment", "by": "Viewer"},
        )

        self.assertEqual(rectification.status_code, 403)
        self.assertEqual(comment.status_code, 403)

    def test_cannot_move_item_to_unauthorized_project(self) -> None:
        item = self.store.snapshot().items[0]

        response = self.client.patch(
            f"/api/items/{item.id}",
            headers=bearer("dev-site-manager"),
            json={"project": "Other Project"},
        )

        self.assertEqual(response.status_code, 403)

    def test_bootstrap_signs_storage_paths(self) -> None:
        item = self.store.snapshot().items[0]
        item.original_photos = ["cleanrun/public/projects/demo/items/def-1001/original/photo.jpg"]
        self.store._write(self.store._read().model_copy(update={"items": [item]}))

        with patch("app.main.resolve_photo_url", side_effect=lambda value: f"https://signed.example/{value}"):
            response = self.client.get("/api/bootstrap", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["items"][0]["original_photos"][0].startswith("https://signed.example/"))

    def test_bootstrap_falls_back_to_raw_path_when_evidence_signing_fails(self) -> None:
        item = self.store.snapshot().items[0]
        raw_path = "cleanrun/public/projects/demo/items/def-1001/rectification/photo.jpg"
        item = item.model_copy(
            update={
                "rectification_evidence": [
                    RectificationEvidence(photo=raw_path, comment="Fixed", by="Sterling Tiling")
                ]
            }
        )
        self.store._write(self.store._read().model_copy(update={"items": [item]}))

        with patch("app.main.resolve_photo_url", return_value=None):
            response = self.client.get("/api/bootstrap", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["rectification_evidence"][0]["photo"], raw_path)

    def test_report_endpoint_shows_placeholder_and_keeps_count_when_signing_fails(self) -> None:
        item = self.store.snapshot().items[0]
        item = item.model_copy(
            update={"original_photos": ["cleanrun/public/projects/demo/items/def-1001/original/photo.jpg"]}
        )
        self.store._write(self.store._read().model_copy(update={"items": [item]}))

        with patch("app.storage.get_supabase_client", side_effect=RuntimeError("signing failed")), patch(
            "app.storage.get_public_supabase_client", side_effect=RuntimeError("signing failed")
        ):
            response = self.client.get("/api/reports/register", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Evidence photo unavailable", response.text)
        self.assertNotIn("<img", response.text)
        self.assertIn(item.code, response.text)

    def _fake_signing_client(self):
        class FakeBucket:
            def create_signed_url(self, path, ttl, options=None):
                transform = (options or {}).get("transform")
                if transform:
                    return {"signedURL": f"https://fresh.example/storage/v1/render/image/sign/cleanrun-evidence/{path}?w={transform.get('width')}"}
                return {"signedURL": f"https://fresh.example/storage/v1/object/sign/cleanrun-evidence/{path}?token=full"}

        class FakeStorage:
            def from_(self, bucket):
                return FakeBucket()

        class FakeClient:
            storage = FakeStorage()

        return FakeClient()

    def _set_first_item_photo(self, path: str):
        item = self.store.snapshot().items[0]
        item = item.model_copy(update={"original_photos": [path]})
        data = self.store._read()
        items = [item if current.id == item.id else current for current in data.items]
        self.store._write(data.model_copy(update={"items": items}))
        return item

    def test_photo_refresh_requires_auth(self) -> None:
        with patch.dict(os.environ, {"CLEANRUN_LOGIN_REQUIRED": "true"}, clear=False):
            response = self.client.post("/api/photos/refresh-url", json={"url": "https://x.supabase.co/storage/v1/object/sign/cleanrun-evidence/p.jpg?token=old"})
        self.assertEqual(response.status_code, 401)

    def test_photo_refresh_resigns_full_and_thumbnail_variants(self) -> None:
        from app.storage import signed_url_cache

        signed_url_cache.clear()
        path = "cleanrun/public/projects/demo/items/def-2001/original/refresh.jpg"
        self._set_first_item_photo(path)
        stale_full = f"https://x.supabase.co/storage/v1/object/sign/cleanrun-evidence/{path}?token=expired"
        stale_thumb = f"https://x.supabase.co/storage/v1/render/image/sign/cleanrun-evidence/{path}?token=expired"

        with patch("app.storage._client_for_storage_path", return_value=self._fake_signing_client()):
            full = self.client.post("/api/photos/refresh-url", headers=bearer("dev-site-manager"), json={"url": stale_full})
            thumb = self.client.post("/api/photos/refresh-url", headers=bearer("dev-site-manager"), json={"url": stale_thumb})

        self.assertEqual(full.status_code, 200)
        self.assertIn("/object/sign/", full.json()["url"])
        self.assertIn(path, full.json()["url"])
        self.assertEqual(thumb.status_code, 200)
        self.assertIn("/render/image/sign/", thumb.json()["url"])

    def test_photo_refresh_rejects_paths_outside_visible_items(self) -> None:
        hidden = self.create_direct_item(project="Other Project", subcontractor="Other Trade")
        hidden_path = "cleanrun/public/projects/other/items/def-9001/original/secret.jpg"
        data = self.store._read()
        items = [
            current.model_copy(update={"original_photos": [hidden_path]}) if current.id == hidden.id else current
            for current in data.items
        ]
        self.store._write(data.model_copy(update={"items": items}))
        stale = f"https://x.supabase.co/storage/v1/object/sign/cleanrun-evidence/{hidden_path}?token=expired"

        with patch("app.storage._client_for_storage_path", return_value=self._fake_signing_client()):
            response = self.client.post("/api/photos/refresh-url", headers=bearer("dev-site-manager"), json={"url": stale})

        self.assertEqual(response.status_code, 404)

    def test_photo_refresh_rejects_non_storage_values(self) -> None:
        for value in ("https://evil.example/photo.jpg", "seed://amber/Cracked tile", "", "data:image/png;base64,aGk="):
            response = self.client.post("/api/photos/refresh-url", headers=bearer("dev-site-manager"), json={"url": value})
            self.assertEqual(response.status_code, 404, value)

    def test_photo_refresh_returns_502_when_signing_fails(self) -> None:
        from app.storage import signed_url_cache

        signed_url_cache.clear()
        path = "cleanrun/public/projects/demo/items/def-2002/original/broken.jpg"
        self._set_first_item_photo(path)
        stale = f"https://x.supabase.co/storage/v1/object/sign/cleanrun-evidence/{path}?token=expired"

        with patch("app.storage.get_supabase_client", side_effect=RuntimeError("signing failed")), patch(
            "app.storage.get_public_supabase_client", side_effect=RuntimeError("signing failed")
        ):
            response = self.client.post("/api/photos/refresh-url", headers=bearer("dev-site-manager"), json={"url": stale})

        self.assertEqual(response.status_code, 502)

    def test_report_images_carry_mid_size_share_variant(self) -> None:
        from app.storage import signed_url_cache

        signed_url_cache.clear()
        path = "cleanrun/public/projects/demo/items/def-2003/original/share.jpg"
        item = self._set_first_item_photo(path)

        with patch("app.storage._client_for_storage_path", return_value=self._fake_signing_client()):
            response = self.client.get("/api/reports/register", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(item.code, response.text)
        self.assertIn("data-share-src=", response.text)
        self.assertIn(f"/render/image/sign/cleanrun-evidence/{path}?w=1200", response.text)
        self.assertIn(f"/object/sign/cleanrun-evidence/{path}", response.text)

    def test_report_omits_share_variant_when_share_signing_fails(self) -> None:
        from app.storage import signed_url_cache

        signed_url_cache.clear()
        path = "cleanrun/public/projects/demo/items/def-2004/original/share-fail.jpg"
        self._set_first_item_photo(path)

        class FullOnlyBucket:
            def create_signed_url(self, bucket_path, ttl, options=None):
                if (options or {}).get("transform"):
                    raise RuntimeError("transforms unavailable")
                return {"signedURL": f"https://fresh.example/storage/v1/object/sign/cleanrun-evidence/{bucket_path}?token=full"}

        class FullOnlyStorage:
            def from_(self, bucket):
                return FullOnlyBucket()

        class FullOnlyClient:
            storage = FullOnlyStorage()

        with patch("app.storage._client_for_storage_path", return_value=FullOnlyClient()):
            response = self.client.get("/api/reports/register", headers=bearer("dev-site-manager"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/object/sign/cleanrun-evidence/{path}", response.text)
        self.assertNotIn("data-share-src=", response.text)

    def test_register_and_exceptions_reports_filter_items(self) -> None:
        overdue = self.create_direct_item(subcontractor="H&L Roofing")
        data = self.store._read()
        updated_items = []
        for current in data.items:
            if current.id == overdue.id:
                updated_items.append(current.model_copy(update={"due_date": "2020-01-01", "status": "issued"}))
            else:
                updated_items.append(current)
        self.store._write(data.model_copy(update={"items": updated_items}))

        register = self.client.get("/api/reports/register", headers=bearer("dev-site-manager"))
        exceptions = self.client.get("/api/reports/exceptions", headers=bearer("dev-site-manager"))

        self.assertEqual(register.status_code, 200)
        self.assertEqual(exceptions.status_code, 200)
        self.assertIn("Project Defect Register", register.text)
        self.assertIn("Exceptions Report", exceptions.text)
        self.assertIn(overdue.code, exceptions.text)

    def test_demo_reset_is_blocked_in_production_without_permission(self) -> None:
        token = "prod-token"
        claims = {
            "sub": "prod-user",
            "email": "prod.user@example.com",
            "app_metadata": {
                "cleanrun": {
                    "company_id": "demo-company",
                    "company_role": "admin",
                    "project_roles": {"Jura Noosa": "project_manager"},
                    "demo_admin": False,
                }
            },
        }

        class FakeJwt:
            @staticmethod
            def decode(value, *_args, **_kwargs):
                if value != token:
                    raise ValueError("unexpected token")
                return claims

        with patch.dict(
            os.environ,
            {"CLEANRUN_ENV": "production", "SUPABASE_JWT_SECRET": "test-secret", "CLEANRUN_ENABLE_DEMO_RESET": "false"},
            clear=False,
        ), patch("app.auth.jwt", FakeJwt):
            response = self.client.post("/api/reset-demo", headers=bearer(token))

        self.assertEqual(response.status_code, 403)

    def test_launch_admin_email_gets_write_roles_from_auth_claim(self) -> None:
        with patch.dict(os.environ, {"CLEANRUN_LAUNCH_ADMIN_EMAILS": "info@cleanruniq.com"}, clear=False):
            user = _user_from_claims(
                {
                    "sub": "launch-admin-id",
                    "email": "info@cleanruniq.com",
                    "app_metadata": {},
                }
            )

        self.assertEqual(user.company_id, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(user.company_role, "admin")
        self.assertEqual(user.project_roles["*"], "project_manager")
        self.assertTrue(user.is_demo_admin)


if __name__ == "__main__":
    unittest.main()
