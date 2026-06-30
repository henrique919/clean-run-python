-- Temporary launch-mode repair.
--
-- The current Render app is a single-tenant launch build using the
-- cleanrun/public/* storage prefix and the default CleanRun company id.
-- Keep this migration narrow and reversible by only normalising rows into the
-- existing launch company boundary used by the public_full_app_* policies.

do $$
declare
  launch_company_id uuid := '00000000-0000-0000-0000-000000000001'::uuid;
begin
  insert into public.companies (id, name)
  values (launch_company_id, 'CleanRun IQ')
  on conflict (id) do nothing;

  update public.projects
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.locations
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.subcontractors
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.items
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.item_photos
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.item_comments
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.item_audit_events
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;

  update public.app_settings
     set company_id = launch_company_id
   where company_id is distinct from launch_company_id;
end $$;

drop policy if exists "public_full_app_storage_select_authenticated" on storage.objects;
create policy "public_full_app_storage_select_authenticated"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'cleanrun-evidence'
  and name like 'cleanrun/public/%'
);

drop policy if exists "public_full_app_storage_insert_authenticated" on storage.objects;
create policy "public_full_app_storage_insert_authenticated"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'cleanrun-evidence'
  and name like 'cleanrun/public/%'
);
