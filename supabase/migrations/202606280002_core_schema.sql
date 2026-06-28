-- Core CleanRun IQ schema.
-- Existing Python code still writes a JSON payload for compatibility, while normalized
-- relational columns give Supabase RLS, reporting, and indexing a secure foundation.

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '',
  role text not null default 'site_manager',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_role_check check (role in ('owner', 'admin', 'project_manager', 'site_manager', 'subcontractor', 'viewer'))
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  address text,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.project_members (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null,
  created_at timestamptz not null default now(),
  constraint project_members_role_check check (role in ('owner', 'admin', 'project_manager', 'site_manager', 'subcontractor', 'viewer')),
  constraint project_members_unique_member unique (project_id, user_id)
);

create table if not exists public.subcontractors (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references public.projects(id) on delete cascade,
  name text not null,
  trade text,
  email text,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint subcontractors_unique_project_name unique (project_id, name)
);

create table if not exists public.items (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  type text not null,
  status text not null default 'open',
  project_id uuid references public.projects(id) on delete restrict,
  project text not null,
  building text,
  level text,
  unit text,
  room text,
  trade text,
  subcontractor_id uuid references public.subcontractors(id) on delete set null,
  subcontractor text,
  priority text,
  due_date date,
  description text,
  raised_by text,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  rejection_reason text,
  issued_at timestamptz,
  started_at timestamptz,
  ready_at timestamptz,
  inspected_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb,
  constraint items_type_check check (type in ('defect', 'incomplete', 'client')),
  constraint items_status_check check (status in ('open', 'issued', 'in_progress', 'ready_for_review', 'under_inspection', 'rejected', 'closed', 'complete')),
  constraint items_priority_check check (priority is null or priority in ('high', 'urgent'))
);

create table if not exists public.evidence (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items(id) on delete cascade,
  evidence_type text not null,
  storage_path text,
  photo text,
  comment text,
  note text,
  role text,
  confirmation text,
  uploaded_by uuid references public.profiles(id) on delete set null,
  uploaded_by_label text,
  created_at timestamptz not null default now(),
  constraint evidence_type_check check (evidence_type in ('original', 'rectification', 'closeout'))
);

create table if not exists public.comments (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items(id) on delete cascade,
  text text not null,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  created_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references public.items(id) on delete cascade,
  event_type text not null,
  message text not null,
  created_by uuid references public.profiles(id) on delete set null,
  created_by_label text,
  created_at timestamptz not null default now(),
  idempotency_key text,
  constraint audit_events_unique_idempotency unique (item_id, idempotency_key)
);

create table if not exists public.app_settings (
  id text primary key default 'default',
  project_id uuid references public.projects(id) on delete cascade,
  payload jsonb not null,
  updated_at timestamptz not null default now()
);
