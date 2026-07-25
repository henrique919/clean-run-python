-- Close anonymous (anon-key) access to production data and evidence photos.
--
-- Verified against production 2026-07-25: the anon/publishable key alone
-- (no login, no JWT) could SELECT all rows on items/item_photos/projects/
-- subcontractors/etc, INSERT into items, and list+read every object in the
-- cleanrun-evidence storage bucket. FastAPI's login screen (AUTH-03) never
-- protected this — it authenticates the API layer, but the server always
-- talked to Supabase's REST/Storage API with the anon key
-- (use_public_launch_data_client() in app/supabase_client.py), which
-- PostgREST evaluates as the `anon` role regardless of whether the caller
-- is logged in. `/api/auth/config` hands the publishable key + URL to
-- anyone who loads the page, so this was reachable directly, bypassing the
-- app entirely.
--
-- This migration and the paired code change in app/supabase_client.py and
-- app/storage.py (see SAFETY-BATCH-03 commit) must ship together: this
-- migration alone would break capture (the server would still be calling
-- as anon, which this migration makes powerless), and the code change
-- alone would do nothing (anon can already do everything, so forwarding
-- the JWT instead just makes the server use a different role that could
-- previously do the same anon-scoped things anyway).
--
-- Scope: this keeps launch-mode's existing single-company scoping
-- (company_id = '00000000-0000-0000-0000-000000000001') for `authenticated`
-- — it does not attempt to rebuild the per-project relational RLS model
-- (app.can_access_item / app.is_project_member), because that model reads
-- from `project_members`/`company_members`, which the app never writes to
-- (the app's real authorization is done in Python, in app/permissions.py,
-- against JWT app_metadata.cleanrun claims — see AUTH-01 audit). Rebuilding
-- that into RLS is a larger, separate hardening task for whenever this
-- product has more than one tenant; logged as a follow-up, not attempted
-- here. This migration's job is narrower and unambiguous: nobody without a
-- valid Supabase session should be able to touch this data at all.

-- ---------------------------------------------------------------------
-- 1. Table grants: anon loses all access. authenticated keeps what it had.
-- ---------------------------------------------------------------------
revoke select, insert, update on public.companies from anon;
revoke select, insert, update on public.projects from anon;
revoke select, insert, update on public.locations from anon;
revoke select, insert, update on public.subcontractors from anon;
revoke select, insert, update on public.project_subcontractors from anon;
revoke select, insert, update on public.items from anon;
revoke select, insert, update on public.item_photos from anon;
revoke select, insert, update on public.item_comments from anon;
revoke select, insert, update on public.item_audit_events from anon;
revoke select, insert, update on public.app_settings from anon;

-- ---------------------------------------------------------------------
-- 2. Table policies: same predicate, `authenticated` only (was
--    `anon, authenticated`). Belt-and-suspenders with the grant revoke
--    above — either alone would close the hole, both together mean a
--    future accidental re-grant doesn't silently reopen it.
-- ---------------------------------------------------------------------
drop policy if exists "public_full_app_companies" on public.companies;
create policy "public_full_app_companies"
on public.companies
for all
to authenticated
using (id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_projects" on public.projects;
create policy "public_full_app_projects"
on public.projects
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_locations" on public.locations;
create policy "public_full_app_locations"
on public.locations
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_subcontractors" on public.subcontractors;
create policy "public_full_app_subcontractors"
on public.subcontractors
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_project_subcontractors" on public.project_subcontractors;
create policy "public_full_app_project_subcontractors"
on public.project_subcontractors
for all
to authenticated
using (
  exists (
    select 1 from public.projects p
    where p.id = project_subcontractors.project_id
      and p.company_id = '00000000-0000-0000-0000-000000000001'::uuid
  )
)
with check (
  exists (
    select 1 from public.projects p
    where p.id = project_subcontractors.project_id
      and p.company_id = '00000000-0000-0000-0000-000000000001'::uuid
  )
);

drop policy if exists "public_full_app_items" on public.items;
create policy "public_full_app_items"
on public.items
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_photos" on public.item_photos;
create policy "public_full_app_item_photos"
on public.item_photos
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_comments" on public.item_comments;
create policy "public_full_app_item_comments"
on public.item_comments
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_audit_events" on public.item_audit_events;
create policy "public_full_app_item_audit_events"
on public.item_audit_events
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_app_settings" on public.app_settings;
create policy "public_full_app_app_settings"
on public.app_settings
for all
to authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

-- ---------------------------------------------------------------------
-- 3. Storage: drop every policy that grants the `anon`/`public` role
--    access to the cleanrun-evidence bucket. The authenticated,
--    prefix-scoped policies (public_full_app_storage_select_authenticated /
--    public_full_app_storage_insert_authenticated, added in
--    202607010001/202607010002) already exist and are untouched by this
--    migration — they become the only way in once these are gone.
-- ---------------------------------------------------------------------
drop policy if exists "Allow public read from cleanrun evidence" on storage.objects;
drop policy if exists "Public read evidence files" on storage.objects;
drop policy if exists "public_full_app_storage_select" on storage.objects;
drop policy if exists "public_full_app_storage_insert" on storage.objects;
