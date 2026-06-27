from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPABASE = ROOT / "supabase"
MIGRATIONS = SUPABASE / "migrations"


def read_migrations() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql")))


class SupabaseContractTests(unittest.TestCase):
    def test_supabase_uses_cli_migrations_only(self) -> None:
        self.assertTrue((SUPABASE / "config.toml").exists())
        self.assertTrue(MIGRATIONS.exists())
        self.assertFalse((SUPABASE / "schema.sql").exists())
        self.assertFalse((SUPABASE / "add_items_payload.sql").exists())
        self.assertGreaterEqual(len(list(MIGRATIONS.glob("*.sql"))), 7)

    def test_all_application_tables_enable_rls(self) -> None:
        migrations = read_migrations().lower()
        tables = [
            "companies",
            "company_members",
            "profiles",
            "projects",
            "project_members",
            "subcontractors",
            "project_subcontractors",
            "subcontractor_users",
            "items",
            "evidence",
            "comments",
            "audit_events",
            "app_settings",
        ]
        for table in tables:
            self.assertIn(f"alter table public.{table} enable row level security;", migrations)

    def test_storage_bucket_is_private_and_path_policy_is_user_scoped(self) -> None:
        migrations = read_migrations().lower()
        self.assertIn("'cleanrun-evidence'", migrations)
        self.assertIn("public = false", migrations)
        self.assertIn("(storage.foldername(name))[1] = auth.uid()::text", migrations)
        self.assertIn("app.is_project_member(((storage.foldername(name))[2])::uuid)", migrations)

    def test_tenant_security_functions_and_policies_exist(self) -> None:
        migrations = read_migrations().lower()
        expected = [
            "create or replace function app.is_company_member",
            "create or replace function app.has_company_role",
            "create or replace function app.is_subcontractor_for_item",
            "create policy \"items_select_authorized_scope\"",
            "create policy \"evidence_insert_item_managers_or_assigned_subcontractor\"",
            "create policy \"audit_events_insert_authorized_append_only\"",
        ]
        for text in expected:
            self.assertIn(text, migrations)

    def test_foreign_key_columns_are_indexed(self) -> None:
        migrations = read_migrations().lower()
        indexed_columns = [
            "company_members(company_id)",
            "company_members(user_id)",
            "projects(company_id)",
            "project_subcontractors(project_id)",
            "project_subcontractors(subcontractor_id)",
            "subcontractor_users(subcontractor_id)",
            "subcontractor_users(user_id)",
            "items(company_id)",
            "evidence(project_id)",
            "comments(project_id)",
            "audit_events(project_id)",
        ]
        for column in indexed_columns:
            self.assertIn(column, migrations)

    def test_no_service_role_configuration_in_runtime_examples(self) -> None:
        checked_files = [
            ROOT / ".env.example",
            ROOT / "render.yaml",
            ROOT / "README.md",
        ]
        for path in checked_files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY=", text)


if __name__ == "__main__":
    unittest.main()
