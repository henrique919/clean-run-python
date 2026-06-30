-- Launch-mode RLS repair.
--
-- These older authenticated policies recursively inspect subcontractor_users
-- through project/subcontractor access checks. The temporary launch app now has
-- explicit public_full_app_* policies scoped to the default launch company for
-- anon and authenticated roles, so remove the recursive policy paths that can
-- fail item creation before the launch policy can admit the row.

drop policy if exists "subcontractors_select_project_scope" on public.subcontractors;
drop policy if exists "subcontractors_manage_project_managers" on public.subcontractors;

drop policy if exists "project_subcontractors_select_project_scope" on public.project_subcontractors;
drop policy if exists "project_subcontractors_manage_project_managers" on public.project_subcontractors;

drop policy if exists "subcontractor_users_select_self_or_managers" on public.subcontractor_users;
drop policy if exists "subcontractor_users_manage_project_managers" on public.subcontractor_users;

drop policy if exists "locations_select_project_scope" on public.locations;
drop policy if exists "locations_manage_project_team" on public.locations;

drop policy if exists "subcontractor_project_access_select_scope" on public.subcontractor_project_access;
drop policy if exists "subcontractor_project_access_manage_project_team" on public.subcontractor_project_access;

drop policy if exists "item_photos_select_authorized_scope" on public.item_photos;
drop policy if exists "item_photos_insert_authorized_scope" on public.item_photos;

drop policy if exists "item_comments_select_authorized_scope" on public.item_comments;
drop policy if exists "item_comments_insert_authorized_scope" on public.item_comments;

drop policy if exists "item_audit_events_select_authorized_scope" on public.item_audit_events;
drop policy if exists "item_audit_events_insert_append_only" on public.item_audit_events;
