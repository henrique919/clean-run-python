-- Default-deny RLS: every table has RLS enabled before policies are added.

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.project_members enable row level security;
alter table public.subcontractors enable row level security;
alter table public.items enable row level security;
alter table public.evidence enable row level security;
alter table public.comments enable row level security;
alter table public.audit_events enable row level security;
alter table public.app_settings enable row level security;

drop policy if exists "profiles_select_own_or_project_peer" on public.profiles;
create policy "profiles_select_own_or_project_peer"
on public.profiles
for select
to authenticated
using (
  id = auth.uid()
  or app.can_view_profile(id)
);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "projects_select_members" on public.projects;
create policy "projects_select_members"
on public.projects
for select
to authenticated
using (app.is_project_member(id));

drop policy if exists "projects_insert_authenticated" on public.projects;
create policy "projects_insert_authenticated"
on public.projects
for insert
to authenticated
with check (created_by = auth.uid());

drop policy if exists "projects_update_managers" on public.projects;
create policy "projects_update_managers"
on public.projects
for update
to authenticated
using (app.has_project_role(id, array['owner', 'admin', 'project_manager']))
with check (app.has_project_role(id, array['owner', 'admin', 'project_manager']));

drop policy if exists "project_members_select_self_or_manager" on public.project_members;
create policy "project_members_select_self_or_manager"
on public.project_members
for select
to authenticated
using (
  user_id = auth.uid()
  or app.has_project_role(project_id, array['owner', 'admin', 'project_manager'])
);

drop policy if exists "project_members_manage_project_admins" on public.project_members;
create policy "project_members_manage_project_admins"
on public.project_members
for all
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'project_manager']))
with check (app.has_project_role(project_id, array['owner', 'admin', 'project_manager']));

drop policy if exists "subcontractors_select_project_members" on public.subcontractors;
create policy "subcontractors_select_project_members"
on public.subcontractors
for select
to authenticated
using (project_id is null or app.is_project_member(project_id));

drop policy if exists "subcontractors_manage_project_managers" on public.subcontractors;
create policy "subcontractors_manage_project_managers"
on public.subcontractors
for all
to authenticated
using (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']))
with check (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']));

drop policy if exists "items_select_project_members" on public.items;
create policy "items_select_project_members"
on public.items
for select
to authenticated
using (app.is_project_member(coalesce(project_id, app.project_id_for_name(project))));

drop policy if exists "items_insert_project_site_team" on public.items;
create policy "items_insert_project_site_team"
on public.items
for insert
to authenticated
with check (
  app.has_project_role(
    coalesce(project_id, app.project_id_for_name(project)),
    array['owner', 'admin', 'project_manager', 'site_manager']
  )
);

drop policy if exists "items_update_project_site_team" on public.items;
create policy "items_update_project_site_team"
on public.items
for update
to authenticated
using (
  app.has_project_role(
    coalesce(project_id, app.project_id_for_name(project)),
    array['owner', 'admin', 'project_manager', 'site_manager']
  )
)
with check (
  app.has_project_role(
    coalesce(project_id, app.project_id_for_name(project)),
    array['owner', 'admin', 'project_manager', 'site_manager']
  )
);

drop policy if exists "evidence_select_project_members" on public.evidence;
create policy "evidence_select_project_members"
on public.evidence
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "evidence_insert_item_managers" on public.evidence;
create policy "evidence_insert_item_managers"
on public.evidence
for insert
to authenticated
with check (app.can_manage_item(item_id));

drop policy if exists "comments_select_project_members" on public.comments;
create policy "comments_select_project_members"
on public.comments
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "comments_insert_project_members" on public.comments;
create policy "comments_insert_project_members"
on public.comments
for insert
to authenticated
with check (app.can_access_item(item_id));

drop policy if exists "audit_events_select_project_members" on public.audit_events;
create policy "audit_events_select_project_members"
on public.audit_events
for select
to authenticated
using (item_id is null or app.can_access_item(item_id));

drop policy if exists "audit_events_insert_item_managers" on public.audit_events;
create policy "audit_events_insert_item_managers"
on public.audit_events
for insert
to authenticated
with check (item_id is null or app.can_manage_item(item_id));

drop policy if exists "app_settings_select_project_members" on public.app_settings;
create policy "app_settings_select_project_members"
on public.app_settings
for select
to authenticated
using (project_id is null or app.is_project_member(project_id));

drop policy if exists "app_settings_update_project_admins" on public.app_settings;
create policy "app_settings_update_project_admins"
on public.app_settings
for all
to authenticated
using (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager']))
with check (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager']));
