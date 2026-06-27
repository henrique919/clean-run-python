-- Tenant, role, subcontractor, and audit hardening foundation.
-- This migration keeps the current app-compatible tables while adding the
-- normalized security surfaces needed for production Supabase RLS.

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint companies_status_check check (status in ('active', 'suspended', 'archived'))
);

create table if not exists public.company_members (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null,
  created_at timestamptz not null default now(),
  constraint company_members_role_check check (role in ('owner', 'admin', 'project_manager', 'quality_manager', 'viewer')),
  constraint company_members_unique_member unique (company_id, user_id)
);

alter table public.projects
  add column if not exists company_id uuid references public.companies(id) on delete restrict,
  add column if not exists status text not null default 'active';

alter table public.projects
  drop constraint if exists projects_status_check;

alter table public.projects
  add constraint projects_status_check check (status in ('active', 'archived'));

alter table public.subcontractors
  add column if not exists company_id uuid references public.companies(id) on delete restrict,
  add column if not exists status text not null default 'active';

alter table public.subcontractors
  drop constraint if exists subcontractors_status_check;

alter table public.subcontractors
  add constraint subcontractors_status_check check (status in ('active', 'inactive', 'archived'));

create table if not exists public.project_subcontractors (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  subcontractor_id uuid not null references public.subcontractors(id) on delete cascade,
  trade text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  constraint project_subcontractors_status_check check (status in ('active', 'inactive', 'archived')),
  constraint project_subcontractors_unique_link unique (project_id, subcontractor_id)
);

create table if not exists public.subcontractor_users (
  id uuid primary key default gen_random_uuid(),
  subcontractor_id uuid not null references public.subcontractors(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  constraint subcontractor_users_role_check check (role in ('owner', 'admin', 'member')),
  constraint subcontractor_users_unique_member unique (subcontractor_id, user_id)
);

alter table public.items
  add column if not exists company_id uuid references public.companies(id) on delete restrict;

alter table public.evidence
  add column if not exists company_id uuid references public.companies(id) on delete restrict,
  add column if not exists project_id uuid references public.projects(id) on delete cascade,
  add column if not exists context jsonb not null default '{}'::jsonb;

alter table public.comments
  add column if not exists company_id uuid references public.companies(id) on delete restrict,
  add column if not exists project_id uuid references public.projects(id) on delete cascade,
  add column if not exists context jsonb not null default '{}'::jsonb;

alter table public.audit_events
  add column if not exists company_id uuid references public.companies(id) on delete restrict,
  add column if not exists project_id uuid references public.projects(id) on delete cascade,
  add column if not exists context jsonb not null default '{}'::jsonb;

alter table public.app_settings
  add column if not exists company_id uuid references public.companies(id) on delete cascade;

insert into public.companies (id, name)
values ('00000000-0000-0000-0000-000000000001', 'CleanRun Demo')
on conflict (id) do nothing;

update public.projects
set company_id = '00000000-0000-0000-0000-000000000001'
where company_id is null;

update public.subcontractors s
set company_id = p.company_id
from public.projects p
where s.project_id = p.id
  and s.company_id is null;

insert into public.project_subcontractors (project_id, subcontractor_id, trade)
select s.project_id, s.id, s.trade
from public.subcontractors s
where s.project_id is not null
on conflict (project_id, subcontractor_id) do nothing;

update public.items i
set company_id = p.company_id
from public.projects p
where coalesce(i.project_id, app.project_id_for_name(i.project)) = p.id
  and i.company_id is null;

update public.evidence e
set project_id = i.project_id,
    company_id = i.company_id
from public.items i
where e.item_id = i.id
  and (e.project_id is null or e.company_id is null);

update public.comments c
set project_id = i.project_id,
    company_id = i.company_id
from public.items i
where c.item_id = i.id
  and (c.project_id is null or c.company_id is null);

update public.audit_events a
set project_id = i.project_id,
    company_id = i.company_id
from public.items i
where a.item_id = i.id
  and (a.project_id is null or a.company_id is null);

drop trigger if exists companies_set_updated_at on public.companies;
create trigger companies_set_updated_at
before update on public.companies
for each row execute function app.set_updated_at();

create or replace function app.is_company_member(target_company_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.company_members cm
    where cm.company_id = target_company_id
      and cm.user_id = auth.uid()
  )
$$;

create or replace function app.has_company_role(target_company_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.company_members cm
    where cm.company_id = target_company_id
      and cm.user_id = auth.uid()
      and cm.role = any(allowed_roles)
  )
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
  or exists (
    select 1
    from public.projects p
    join public.company_members cm on cm.company_id = p.company_id
    where p.id = target_project_id
      and cm.user_id = auth.uid()
      and cm.role in ('owner', 'admin', 'project_manager', 'quality_manager', 'viewer')
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
  or exists (
    select 1
    from public.projects p
    join public.company_members cm on cm.company_id = p.company_id
    where p.id = target_project_id
      and cm.user_id = auth.uid()
      and cm.role = any(allowed_roles)
  )
$$;

create or replace function app.is_subcontractor_for_item(target_item_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.items i
    join public.subcontractor_users su on su.subcontractor_id = i.subcontractor_id
    where i.id = target_item_id
      and su.user_id = auth.uid()
  )
  or exists (
    select 1
    from public.items i
    join public.subcontractors s
      on s.project_id = coalesce(i.project_id, app.project_id_for_name(i.project))
     and s.name = i.subcontractor
    join public.subcontractor_users su on su.subcontractor_id = s.id
    where i.id = target_item_id
      and su.user_id = auth.uid()
  )
$$;

create or replace function app.can_access_item(target_item_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select app.is_project_member(app.item_project_id(target_item_id))
    or app.is_subcontractor_for_item(target_item_id)
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
    array['owner', 'admin', 'project_manager', 'site_manager', 'quality_manager']
  )
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

  if new.company_id is null and new.project_id is not null then
    select p.company_id into new.company_id
    from public.projects p
    where p.id = new.project_id;
  end if;

  if new.subcontractor_id is null and new.project_id is not null and new.subcontractor is not null then
    select s.id into new.subcontractor_id
    from public.subcontractors s
    where s.project_id = new.project_id
      and s.name = new.subcontractor
    order by s.created_at asc
    limit 1;
  end if;

  return new;
end;
$$;

create or replace function app.hydrate_item_child_scope()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if new.item_id is not null then
    select i.project_id, i.company_id
      into new.project_id, new.company_id
    from public.items i
    where i.id = new.item_id;
  end if;
  return new;
end;
$$;

drop trigger if exists evidence_hydrate_scope on public.evidence;
create trigger evidence_hydrate_scope
before insert or update on public.evidence
for each row execute function app.hydrate_item_child_scope();

drop trigger if exists comments_hydrate_scope on public.comments;
create trigger comments_hydrate_scope
before insert or update on public.comments
for each row execute function app.hydrate_item_child_scope();

drop trigger if exists audit_events_hydrate_scope on public.audit_events;
create trigger audit_events_hydrate_scope
before insert or update on public.audit_events
for each row execute function app.hydrate_item_child_scope();

alter table public.companies enable row level security;
alter table public.company_members enable row level security;
alter table public.project_subcontractors enable row level security;
alter table public.subcontractor_users enable row level security;

drop policy if exists "companies_select_members" on public.companies;
create policy "companies_select_members"
on public.companies
for select
to authenticated
using (app.is_company_member(id));

drop policy if exists "companies_manage_admins" on public.companies;
create policy "companies_manage_admins"
on public.companies
for update
to authenticated
using (app.has_company_role(id, array['owner', 'admin']))
with check (app.has_company_role(id, array['owner', 'admin']));

drop policy if exists "company_members_select_self_or_company_admin" on public.company_members;
create policy "company_members_select_self_or_company_admin"
on public.company_members
for select
to authenticated
using (
  user_id = auth.uid()
  or app.has_company_role(company_id, array['owner', 'admin', 'project_manager'])
);

drop policy if exists "company_members_manage_company_admins" on public.company_members;
create policy "company_members_manage_company_admins"
on public.company_members
for all
to authenticated
using (app.has_company_role(company_id, array['owner', 'admin']))
with check (app.has_company_role(company_id, array['owner', 'admin']));

drop policy if exists "projects_select_members" on public.projects;
create policy "projects_select_members"
on public.projects
for select
to authenticated
using (app.is_project_member(id));

drop policy if exists "projects_insert_authenticated" on public.projects;
create policy "projects_insert_company_admins"
on public.projects
for insert
to authenticated
with check (company_id is not null and app.has_company_role(company_id, array['owner', 'admin']));

drop policy if exists "projects_update_managers" on public.projects;
create policy "projects_update_managers"
on public.projects
for update
to authenticated
using (app.has_project_role(id, array['owner', 'admin', 'project_manager', 'quality_manager']))
with check (app.has_project_role(id, array['owner', 'admin', 'project_manager', 'quality_manager']));

drop policy if exists "subcontractors_select_project_members" on public.subcontractors;
create policy "subcontractors_select_project_scope"
on public.subcontractors
for select
to authenticated
using (
  (project_id is not null and app.is_project_member(project_id))
  or exists (
    select 1
    from public.subcontractor_users su
    where su.subcontractor_id = id
      and su.user_id = auth.uid()
  )
);

drop policy if exists "subcontractors_manage_project_managers" on public.subcontractors;
create policy "subcontractors_manage_project_managers"
on public.subcontractors
for all
to authenticated
using (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']))
with check (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']));

drop policy if exists "project_subcontractors_select_project_scope" on public.project_subcontractors;
create policy "project_subcontractors_select_project_scope"
on public.project_subcontractors
for select
to authenticated
using (
  app.is_project_member(project_id)
  or exists (
    select 1
    from public.subcontractor_users su
    where su.subcontractor_id = project_subcontractors.subcontractor_id
      and su.user_id = auth.uid()
  )
);

drop policy if exists "project_subcontractors_manage_project_managers" on public.project_subcontractors;
create policy "project_subcontractors_manage_project_managers"
on public.project_subcontractors
for all
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']))
with check (app.has_project_role(project_id, array['owner', 'admin', 'project_manager', 'site_manager']));

drop policy if exists "subcontractor_users_select_self_or_managers" on public.subcontractor_users;
create policy "subcontractor_users_select_self_or_managers"
on public.subcontractor_users
for select
to authenticated
using (
  user_id = auth.uid()
  or exists (
    select 1
    from public.project_subcontractors ps
    where ps.subcontractor_id = subcontractor_users.subcontractor_id
      and app.has_project_role(ps.project_id, array['owner', 'admin', 'project_manager', 'site_manager'])
  )
);

drop policy if exists "subcontractor_users_manage_project_managers" on public.subcontractor_users;
create policy "subcontractor_users_manage_project_managers"
on public.subcontractor_users
for all
to authenticated
using (
  exists (
    select 1
    from public.project_subcontractors ps
    where ps.subcontractor_id = subcontractor_users.subcontractor_id
      and app.has_project_role(ps.project_id, array['owner', 'admin', 'project_manager'])
  )
)
with check (
  exists (
    select 1
    from public.project_subcontractors ps
    where ps.subcontractor_id = subcontractor_users.subcontractor_id
      and app.has_project_role(ps.project_id, array['owner', 'admin', 'project_manager'])
  )
);

drop policy if exists "items_select_project_members" on public.items;
create policy "items_select_authorized_scope"
on public.items
for select
to authenticated
using (app.can_access_item(id));

drop policy if exists "items_insert_project_site_team" on public.items;
create policy "items_insert_project_site_team"
on public.items
for insert
to authenticated
with check (
  app.has_project_role(
    coalesce(project_id, app.project_id_for_name(project)),
    array['owner', 'admin', 'project_manager', 'site_manager', 'quality_manager']
  )
);

drop policy if exists "items_update_project_site_team" on public.items;
create policy "items_update_project_site_team"
on public.items
for update
to authenticated
using (app.can_manage_item(id))
with check (
  app.has_project_role(
    coalesce(project_id, app.project_id_for_name(project)),
    array['owner', 'admin', 'project_manager', 'site_manager', 'quality_manager']
  )
);

drop policy if exists "evidence_select_project_members" on public.evidence;
create policy "evidence_select_authorized_scope"
on public.evidence
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "evidence_insert_item_managers" on public.evidence;
create policy "evidence_insert_item_managers_or_assigned_subcontractor"
on public.evidence
for insert
to authenticated
with check (
  app.can_manage_item(item_id)
  or (evidence_type = 'rectification' and app.is_subcontractor_for_item(item_id))
);

drop policy if exists "comments_select_project_members" on public.comments;
create policy "comments_select_authorized_scope"
on public.comments
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "comments_insert_project_members" on public.comments;
create policy "comments_insert_authorized_scope"
on public.comments
for insert
to authenticated
with check (app.can_access_item(item_id));

drop policy if exists "audit_events_select_project_members" on public.audit_events;
create policy "audit_events_select_authorized_scope"
on public.audit_events
for select
to authenticated
using (item_id is null or app.can_access_item(item_id));

drop policy if exists "audit_events_insert_item_managers" on public.audit_events;
create policy "audit_events_insert_authorized_append_only"
on public.audit_events
for insert
to authenticated
with check (item_id is null or app.can_access_item(item_id));

drop policy if exists "app_settings_select_project_members" on public.app_settings;
create policy "app_settings_select_project_members"
on public.app_settings
for select
to authenticated
using (
  (project_id is not null and app.is_project_member(project_id))
  or (company_id is not null and app.has_company_role(company_id, array['owner', 'admin', 'project_manager']))
);

drop policy if exists "app_settings_update_project_admins" on public.app_settings;
create policy "app_settings_update_project_admins"
on public.app_settings
for all
to authenticated
using (
  (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager']))
  or (company_id is not null and app.has_company_role(company_id, array['owner', 'admin']))
)
with check (
  (project_id is not null and app.has_project_role(project_id, array['owner', 'admin', 'project_manager']))
  or (company_id is not null and app.has_company_role(company_id, array['owner', 'admin']))
);

create index if not exists idx_company_members_company_id on public.company_members(company_id);
create index if not exists idx_company_members_user_id on public.company_members(user_id);
create index if not exists idx_projects_company_id on public.projects(company_id);
create index if not exists idx_project_subcontractors_project_id on public.project_subcontractors(project_id);
create index if not exists idx_project_subcontractors_subcontractor_id on public.project_subcontractors(subcontractor_id);
create index if not exists idx_subcontractor_users_subcontractor_id on public.subcontractor_users(subcontractor_id);
create index if not exists idx_subcontractor_users_user_id on public.subcontractor_users(user_id);
create index if not exists idx_subcontractors_company_id on public.subcontractors(company_id);
create index if not exists idx_items_company_id on public.items(company_id);
create index if not exists idx_evidence_company_id on public.evidence(company_id);
create index if not exists idx_evidence_project_id on public.evidence(project_id);
create index if not exists idx_comments_company_id on public.comments(company_id);
create index if not exists idx_comments_project_id on public.comments(project_id);
create index if not exists idx_audit_events_company_id on public.audit_events(company_id);
create index if not exists idx_audit_events_project_id on public.audit_events(project_id);
create index if not exists idx_app_settings_company_id on public.app_settings(company_id);
