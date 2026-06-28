create table if not exists public.access_requests (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text not null,
  company text not null,
  role_requested text not null,
  project_site text not null,
  message text,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references public.profiles(id) on delete set null,
  constraint access_requests_status_check check (status in ('pending', 'approved', 'rejected')),
  constraint access_requests_email_shape check (position('@' in email) > 1)
);

alter table public.access_requests enable row level security;

drop policy if exists "access_requests_insert_public_pending" on public.access_requests;
create policy "access_requests_insert_public_pending"
on public.access_requests
for insert
to anon, authenticated
with check (
  status = 'pending'
  and reviewed_at is null
  and reviewed_by is null
);

drop policy if exists "access_requests_select_admins" on public.access_requests;
create policy "access_requests_select_admins"
on public.access_requests
for select
to authenticated
using (
  exists (
    select 1
    from public.company_members cm
    where cm.user_id = auth.uid()
      and cm.role in ('owner', 'admin', 'company_admin', 'project_manager')
  )
);

drop policy if exists "access_requests_update_admins" on public.access_requests;
create policy "access_requests_update_admins"
on public.access_requests
for update
to authenticated
using (
  exists (
    select 1
    from public.company_members cm
    where cm.user_id = auth.uid()
      and cm.role in ('owner', 'admin', 'company_admin', 'project_manager')
  )
)
with check (
  exists (
    select 1
    from public.company_members cm
    where cm.user_id = auth.uid()
      and cm.role in ('owner', 'admin', 'company_admin', 'project_manager')
  )
);

create index if not exists idx_access_requests_status_created_at on public.access_requests(status, created_at desc);
create index if not exists idx_access_requests_email on public.access_requests(lower(email));

grant insert on public.access_requests to anon, authenticated;
grant select, update on public.access_requests to authenticated;
