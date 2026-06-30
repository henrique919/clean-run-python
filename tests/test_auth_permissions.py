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
from app.models import ItemCreate
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
        self.assertEqual(self.client.get("/api/items").status_code, 401)
        response = self.client.post("/api/items", json={})
        self.assertEqual(response.status_code, 401)

    def test_anonymous_production_requests_are_rejected(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production", "CLEANRUN_ENV": "production"}, clear=False):
            self.assertEqual(self.client.get("/api/bootstrap").status_code, 401)

    def test_root_route_serves_restored_full_field_app(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="bottom-nav"', response.text)
        self.assertIn("/assets/enhancements.css?v=cards23", response.text)
        self.assertIn("/assets/enhancements.js?v=cards23", response.text)
        self.assertIn("renderLogin", response.text)

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
        self.assertEqual(payload["created_by"], "site.manager@cleanrun.local")
        self.assertEqual(payload["audit_events"][0]["user_id"], "dev-site-manager")
        self.assertEqual(payload["audit_events"][0]["email"], "site.manager@cleanrun.local")

    def test_reports_require_project_access(self) -> None:
        anonymous = self.client.get("/api/reports/handover")
        viewer = self.client.get("/api/reports/handover", headers=bearer("dev-viewer"))
        other_company = self.client.get(
            "/api/reports/handover?project=Jura%20Noosa",
            headers=bearer("dev-other-company"),
        )

        self.assertEqual(anonymous.status_code, 401)
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
