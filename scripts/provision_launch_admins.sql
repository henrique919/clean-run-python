-- =============================================================================
-- CleanRun IQ — provision launch admin + QA account claims (AUTH-02)
-- =============================================================================
-- Regenerated 16 Jul 2026 (the original copy was lost from the owner's
-- machine). Matches what the backend actually reads: app/auth.py
-- `_user_from_claims()` expects `app_metadata.cleanrun` with company_id,
-- company_role, project_roles, subcontractors, demo_admin (see SECURITY.md).
--
-- HOW TO USE (owner only — agents never run this):
--   1. Supabase Dashboard -> Authentication -> Users -> "Add user" and create
--      each account below with a password FIRST. This script does not create
--      users; it only stamps claims onto users that already exist.
--   2. Supabase Dashboard -> SQL Editor -> paste this file -> Run.
--   3. Check the output of the verification query at the bottom.
--
-- NOTES
--   * The two launch-admin emails do NOT strictly need claims: app/auth.py
--     auto-elevates any email in CLEANRUN_LAUNCH_ADMIN_EMAILS to full admin.
--     Stamping them anyway is belt-and-braces so nothing depends on an env var.
--   * The QA account gets site_manager on the sandbox project ONLY, per the
--     AUTH-01 audit (docs/AUTH-01-secure-login-audit.md, section 3).
--   * Change 'Beach Parade' below if your sandbox project is named differently
--     (it must match the project name in the app exactly).
-- =============================================================================

-- ---- 1. Launch admins (full admin across all projects) ---------------------

update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
  'cleanrun', jsonb_build_object(
    'company_id',    '00000000-0000-0000-0000-000000000001',
    'company_role',  'admin',
    'project_roles', jsonb_build_object('*', 'project_manager'),
    'subcontractors', jsonb_build_array(),
    'demo_admin',    true
  )
)
where lower(email) in ('info@cleanruniq.com', 'harrysfuel@outlook.com');

-- ---- 2. QA account (agent/phone testing — sandbox project only) ------------
-- Create qa@cleanruniq.com in the Auth dashboard first, with its own password.
-- Agents may use THIS account only; owner credentials are never shared.

update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
  'cleanrun', jsonb_build_object(
    'company_id',    '00000000-0000-0000-0000-000000000001',
    'company_role',  'site_manager',
    'project_roles', jsonb_build_object('Beach Parade', 'site_manager'),
    'subcontractors', jsonb_build_array(),
    'demo_admin',    false
  )
)
where lower(email) = 'qa@cleanruniq.com';

-- ---- 3. Verify (run after the updates; expect one row per account) ---------

select email,
       raw_app_meta_data -> 'cleanrun' ->> 'company_role'  as company_role,
       raw_app_meta_data -> 'cleanrun' ->  'project_roles' as project_roles,
       raw_app_meta_data -> 'cleanrun' ->> 'demo_admin'    as demo_admin
from auth.users
where lower(email) in ('info@cleanruniq.com', 'harrysfuel@outlook.com', 'qa@cleanruniq.com')
order by email;

-- IMPORTANT: claims are baked into tokens at sign-in. Anyone signed in before
-- this ran must sign out and back in to pick up the new claims.
