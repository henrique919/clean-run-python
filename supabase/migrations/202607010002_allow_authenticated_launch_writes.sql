-- Launch-mode repair for the temporary full-app production surface.
--
-- The current Render app authenticates users with Supabase Auth, then writes
-- via the publishable key plus the user's JWT. That makes PostgREST evaluate
-- table policies as the authenticated role, while the earlier public launch
-- policies only allowed anon. Keep this scoped to the single launch company.

grant usage on schema public to anon, authenticated;

grant select, insert, update on public.companies to anon, authenticated;
grant select, insert, update on public.projects to anon, authenticated;
grant select, insert, update on public.locations to anon, authenticated;
grant select, insert, update on public.subcontractors to anon, authenticated;
grant select, insert, update on public.project_subcontractors to anon, authenticated;
grant select, insert, update on public.items to anon, authenticated;
grant select, insert, update on public.item_photos to anon, authenticated;
grant select, insert, update on public.item_comments to anon, authenticated;
grant select, insert, update on public.item_audit_events to anon, authenticated;
grant select, insert, update on public.app_settings to anon, authenticated;

drop policy if exists "public_full_app_companies" on public.companies;
create policy "public_full_app_companies"
on public.companies
for all
to anon, authenticated
using (id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_projects" on public.projects;
create policy "public_full_app_projects"
on public.projects
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_locations" on public.locations;
create policy "public_full_app_locations"
on public.locations
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_subcontractors" on public.subcontractors;
create policy "public_full_app_subcontractors"
on public.subcontractors
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_project_subcontractors" on public.project_subcontractors;
create policy "public_full_app_project_subcontractors"
on public.project_subcontractors
for all
to anon, authenticated
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
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_photos" on public.item_photos;
create policy "public_full_app_item_photos"
on public.item_photos
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_comments" on public.item_comments;
create policy "public_full_app_item_comments"
on public.item_comments
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_item_audit_events" on public.item_audit_events;
create policy "public_full_app_item_audit_events"
on public.item_audit_events
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);

drop policy if exists "public_full_app_app_settings" on public.app_settings;
create policy "public_full_app_app_settings"
on public.app_settings
for all
to anon, authenticated
using (company_id = '00000000-0000-0000-0000-000000000001'::uuid)
with check (company_id = '00000000-0000-0000-0000-000000000001'::uuid);
