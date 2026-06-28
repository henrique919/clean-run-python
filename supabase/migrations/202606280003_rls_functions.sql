-- Security-definer helpers keep policies simple and prevent recursive policy
-- lookups against project_members.

create or replace function app.current_user_id()
returns uuid
language sql
stable
as $$
  select auth.uid()
$$;

create or replace function app.is_project_member(target_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.project_members pm
    where pm.project_id = target_project_id
      and pm.user_id = auth.uid()
  )
$$;

create or replace function app.has_project_role(target_project_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.project_members pm
    where pm.project_id = target_project_id
      and pm.user_id = auth.uid()
      and pm.role = any(allowed_roles)
  )
$$;

create or replace function app.can_view_profile(target_profile_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select target_profile_id = auth.uid()
    or exists (
      select 1
      from public.project_members viewer
      join public.project_members subject_member
        on subject_member.project_id = viewer.project_id
      where viewer.user_id = auth.uid()
        and subject_member.user_id = target_profile_id
    )
$$;

create or replace function app.project_id_for_name(project_name text)
returns uuid
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select p.id
  from public.projects p
  where p.name = project_name
  order by p.created_at asc
  limit 1
$$;

create or replace function app.item_project_id(target_item_id uuid)
returns uuid
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select coalesce(i.project_id, app.project_id_for_name(i.project))
  from public.items i
  where i.id = target_item_id
$$;

create or replace function app.can_access_item(target_item_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select app.is_project_member(app.item_project_id(target_item_id))
$$;

create or replace function app.can_manage_item(target_item_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select app.has_project_role(
    app.item_project_id(target_item_id),
    array['owner', 'admin', 'project_manager', 'site_manager']
  )
$$;

create or replace function app.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function app.hydrate_item_project_id()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if new.project_id is null and new.project is not null then
    new.project_id := app.project_id_for_name(new.project);
  end if;
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function app.set_updated_at();

drop trigger if exists projects_set_updated_at on public.projects;
create trigger projects_set_updated_at
before update on public.projects
for each row execute function app.set_updated_at();

drop trigger if exists subcontractors_set_updated_at on public.subcontractors;
create trigger subcontractors_set_updated_at
before update on public.subcontractors
for each row execute function app.set_updated_at();

drop trigger if exists items_set_updated_at on public.items;
create trigger items_set_updated_at
before update on public.items
for each row execute function app.set_updated_at();

drop trigger if exists items_hydrate_project_id on public.items;
create trigger items_hydrate_project_id
before insert or update on public.items
for each row execute function app.hydrate_item_project_id();
