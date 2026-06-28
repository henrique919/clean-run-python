-- Normalized SaaS tables for production CleanRun IQ workflows.
-- The older items.payload column remains only as a legacy compatibility field;
-- new Supabase writes should use these relational columns and child tables.

alter table public.profiles
  drop constraint if exists profiles_role_check;

alter table public.profiles
  add constraint profiles_role_check check (role in ('owner', 'admin', 'company_admin', 'project_manager', 'site_manager', 'foreman', 'subcontractor', 'viewer'));

alter table public.project_members
  drop constraint if exists project_members_role_check;

alter table public.project_members
  add constraint project_members_role_check check (role in ('owner', 'admin', 'company_admin', 'project_manager', 'site_manager', 'foreman', 'subcontractor', 'viewer'));

alter table public.company_members
  drop constraint if exists company_members_role_check;

alter table public.company_members
  add constraint company_members_role_check check (role in ('owner', 'admin', 'company_admin', 'project_manager', 'quality_manager', 'viewer'));

create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  company_id uuid references public.companies(id) on delete set null,
  email text,
  display_name text not null default '',
  role text not null default 'viewer',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_profiles_role_check check (role in ('company_admin', 'project_manager', 'site_manager', 'foreman', 'subcontractor', 'viewer'))
);

create table if not exists public.locations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  building text not null default '',
  level text not null default '',
  unit text not null default '',
  room text not null default '',
  label text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint locations_unique_path unique (project_id, building, level, unit, room)
);

create table if not exists public.subcontractor_project_access (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  subcontractor_id uuid not null references public.subcontractors(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete cascade,
  access_role text not null default 'member',
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint subcontractor_project_access_role_check check (access_role in ('owner', 'admin', 'member')),
  constraint subcontractor_project_access_status_check check (status in ('active', 'inactive', 'revoked')),
  constraint subcontractor_project_access_unique unique (project_id, subcontractor_id, user_id)
);

create table if not exists public.item_photos (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  item_id uuid not null references public.items(id) on delete cascade,
  photo_type text not null,
  storage_path text,
  photo text,
  caption text,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  created_at timestamptz not null default now(),
  constraint item_photos_type_check check (photo_type in ('original', 'rectification', 'closeout'))
);

create table if not exists public.item_comments (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  item_id uuid not null references public.items(id) on delete cascade,
  text text not null,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  created_at timestamptz not null default now()
);

create table if not exists public.item_audit_events (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  item_id uuid references public.items(id) on delete cascade,
  event_type text not null,
  message text not null,
  note text,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  context jsonb not null default '{}'::jsonb,
  idempotency_key text,
  created_at timestamptz not null default now(),
  constraint item_audit_events_unique_idempotency unique (item_id, idempotency_key)
);

create table if not exists public.subcontractor_invites (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  subcontractor_id uuid references public.subcontractors(id) on delete cascade,
  email text not null,
  invited_by uuid references public.profiles(id) on delete set null,
  status text not null default 'pending',
  token_hash text,
  expires_at timestamptz,
  accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint subcontractor_invites_status_check check (status in ('pending', 'accepted', 'revoked', 'expired'))
);

alter table public.items
  add column if not exists location_id uuid references public.locations(id) on delete set null;

comment on column public.items.payload is
  'Legacy compatibility snapshot only. Do not use as the source of truth for new production records.';

create or replace function app.is_subcontractor_for_project(target_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.subcontractor_project_access spa
    where spa.project_id = target_project_id
      and spa.status = 'active'
      and spa.user_id = auth.uid()
  )
  or exists (
    select 1
    from public.subcontractor_project_access spa
    join public.subcontractor_users su on su.subcontractor_id = spa.subcontractor_id
    where spa.project_id = target_project_id
      and spa.status = 'active'
      and su.user_id = auth.uid()
  )
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
    array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager', 'foreman', 'quality_manager']
  )
$$;

create or replace function app.hydrate_normalized_item_child_scope()
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

drop trigger if exists user_profiles_set_updated_at on public.user_profiles;
create trigger user_profiles_set_updated_at
before update on public.user_profiles
for each row execute function app.set_updated_at();

drop trigger if exists locations_set_updated_at on public.locations;
create trigger locations_set_updated_at
before update on public.locations
for each row execute function app.set_updated_at();

drop trigger if exists subcontractor_project_access_set_updated_at on public.subcontractor_project_access;
create trigger subcontractor_project_access_set_updated_at
before update on public.subcontractor_project_access
for each row execute function app.set_updated_at();

drop trigger if exists subcontractor_invites_set_updated_at on public.subcontractor_invites;
create trigger subcontractor_invites_set_updated_at
before update on public.subcontractor_invites
for each row execute function app.set_updated_at();

drop trigger if exists item_photos_hydrate_scope on public.item_photos;
create trigger item_photos_hydrate_scope
before insert or update on public.item_photos
for each row execute function app.hydrate_normalized_item_child_scope();

drop trigger if exists item_comments_hydrate_scope on public.item_comments;
create trigger item_comments_hydrate_scope
before insert or update on public.item_comments
for each row execute function app.hydrate_normalized_item_child_scope();

drop trigger if exists item_audit_events_hydrate_scope on public.item_audit_events;
create trigger item_audit_events_hydrate_scope
before insert or update on public.item_audit_events
for each row execute function app.hydrate_normalized_item_child_scope();

alter table public.user_profiles enable row level security;
alter table public.locations enable row level security;
alter table public.subcontractor_project_access enable row level security;
alter table public.item_photos enable row level security;
alter table public.item_comments enable row level security;
alter table public.item_audit_events enable row level security;
alter table public.subcontractor_invites enable row level security;

drop policy if exists "user_profiles_select_company_or_self" on public.user_profiles;
create policy "user_profiles_select_company_or_self"
on public.user_profiles
for select
to authenticated
using (id = auth.uid() or (company_id is not null and app.is_company_member(company_id)));

drop policy if exists "user_profiles_update_self" on public.user_profiles;
create policy "user_profiles_update_self"
on public.user_profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "locations_select_project_scope" on public.locations;
create policy "locations_select_project_scope"
on public.locations
for select
to authenticated
using (app.is_project_member(project_id) or app.is_subcontractor_for_project(project_id));

drop policy if exists "locations_manage_project_team" on public.locations;
create policy "locations_manage_project_team"
on public.locations
for all
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager', 'foreman']))
with check (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager', 'foreman']));

drop policy if exists "subcontractor_project_access_select_scope" on public.subcontractor_project_access;
create policy "subcontractor_project_access_select_scope"
on public.subcontractor_project_access
for select
to authenticated
using (
  app.is_project_member(project_id)
  or user_id = auth.uid()
  or exists (
    select 1
    from public.subcontractor_users su
    where su.subcontractor_id = subcontractor_project_access.subcontractor_id
      and su.user_id = auth.uid()
  )
);

drop policy if exists "subcontractor_project_access_manage_project_team" on public.subcontractor_project_access;
create policy "subcontractor_project_access_manage_project_team"
on public.subcontractor_project_access
for all
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager']))
with check (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager']));

drop policy if exists "item_photos_select_authorized_scope" on public.item_photos;
create policy "item_photos_select_authorized_scope"
on public.item_photos
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "item_photos_insert_authorized_scope" on public.item_photos;
create policy "item_photos_insert_authorized_scope"
on public.item_photos
for insert
to authenticated
with check (
  app.can_manage_item(item_id)
  or (photo_type = 'rectification' and app.is_subcontractor_for_item(item_id))
);

drop policy if exists "item_comments_select_authorized_scope" on public.item_comments;
create policy "item_comments_select_authorized_scope"
on public.item_comments
for select
to authenticated
using (app.can_access_item(item_id));

drop policy if exists "item_comments_insert_authorized_scope" on public.item_comments;
create policy "item_comments_insert_authorized_scope"
on public.item_comments
for insert
to authenticated
with check (app.can_access_item(item_id));

drop policy if exists "item_audit_events_select_authorized_scope" on public.item_audit_events;
create policy "item_audit_events_select_authorized_scope"
on public.item_audit_events
for select
to authenticated
using (item_id is null or app.can_access_item(item_id));

drop policy if exists "item_audit_events_insert_append_only" on public.item_audit_events;
create policy "item_audit_events_insert_append_only"
on public.item_audit_events
for insert
to authenticated
with check (item_id is null or app.can_access_item(item_id));

drop policy if exists "subcontractor_invites_select_project_team" on public.subcontractor_invites;
create policy "subcontractor_invites_select_project_team"
on public.subcontractor_invites
for select
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager', 'site_manager']));

drop policy if exists "subcontractor_invites_manage_project_team" on public.subcontractor_invites;
create policy "subcontractor_invites_manage_project_team"
on public.subcontractor_invites
for all
to authenticated
using (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager']))
with check (app.has_project_role(project_id, array['owner', 'admin', 'company_admin', 'project_manager']));

create index if not exists idx_user_profiles_company_id on public.user_profiles(company_id);
create index if not exists idx_locations_company_id on public.locations(company_id);
create index if not exists idx_locations_project_id on public.locations(project_id);
create index if not exists idx_subcontractor_project_access_company_id on public.subcontractor_project_access(company_id);
create index if not exists idx_subcontractor_project_access_project_id on public.subcontractor_project_access(project_id);
create index if not exists idx_subcontractor_project_access_subcontractor_id on public.subcontractor_project_access(subcontractor_id);
create index if not exists idx_subcontractor_project_access_user_id on public.subcontractor_project_access(user_id);
create index if not exists idx_items_location_id on public.items(location_id);
create index if not exists idx_items_status_due_date on public.items(status, due_date);
create index if not exists idx_items_trade on public.items(trade);
create index if not exists idx_items_subcontractor_id on public.items(subcontractor_id);
create index if not exists idx_item_photos_company_id on public.item_photos(company_id);
create index if not exists idx_item_photos_project_id on public.item_photos(project_id);
create index if not exists idx_item_photos_item_id on public.item_photos(item_id);
create index if not exists idx_item_comments_company_id on public.item_comments(company_id);
create index if not exists idx_item_comments_project_id on public.item_comments(project_id);
create index if not exists idx_item_comments_item_id on public.item_comments(item_id);
create index if not exists idx_item_audit_events_company_id on public.item_audit_events(company_id);
create index if not exists idx_item_audit_events_project_id on public.item_audit_events(project_id);
create index if not exists idx_item_audit_events_item_id on public.item_audit_events(item_id);
create index if not exists idx_subcontractor_invites_company_id on public.subcontractor_invites(company_id);
create index if not exists idx_subcontractor_invites_project_id on public.subcontractor_invites(project_id);
create index if not exists idx_subcontractor_invites_email on public.subcontractor_invites(email);
