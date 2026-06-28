alter table public.companies
  add column if not exists updated_at timestamptz not null default now();

alter table public.profiles
  add column if not exists updated_at timestamptz not null default now();

alter table public.projects
  add column if not exists updated_at timestamptz not null default now();

alter table public.subcontractors
  add column if not exists updated_at timestamptz not null default now();

alter table public.items
  add column if not exists updated_at timestamptz not null default now();
