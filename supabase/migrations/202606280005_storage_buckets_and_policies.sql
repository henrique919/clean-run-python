-- Private evidence storage. Object paths must follow:
--   {auth.uid()}/{project_id}/{item_id}/{evidence_type}/{file_id}.{ext}

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'cleanrun-evidence',
  'cleanrun-evidence',
  false,
  8388608,
  array['image/jpeg', 'image/png', 'image/webp']::text[]
)
on conflict (id) do update
set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "cleanrun_evidence_select_project_members" on storage.objects;
create policy "cleanrun_evidence_select_project_members"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'cleanrun-evidence'
  and (storage.foldername(name))[1] = auth.uid()::text
  and app.is_project_member(((storage.foldername(name))[2])::uuid)
);

drop policy if exists "cleanrun_evidence_insert_project_members" on storage.objects;
create policy "cleanrun_evidence_insert_project_members"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'cleanrun-evidence'
  and (storage.foldername(name))[1] = auth.uid()::text
  and app.has_project_role(
    ((storage.foldername(name))[2])::uuid,
    array['owner', 'admin', 'project_manager', 'site_manager', 'subcontractor']
  )
  and ((storage.foldername(name))[4]) in ('original', 'rectification', 'closeout')
);

drop policy if exists "cleanrun_evidence_update_owner_only" on storage.objects;
create policy "cleanrun_evidence_update_owner_only"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'cleanrun-evidence'
  and owner = auth.uid()
)
with check (
  bucket_id = 'cleanrun-evidence'
  and owner = auth.uid()
);

drop policy if exists "cleanrun_evidence_delete_project_admins" on storage.objects;
create policy "cleanrun_evidence_delete_project_admins"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'cleanrun-evidence'
  and app.has_project_role(((storage.foldername(name))[2])::uuid, array['owner', 'admin', 'project_manager'])
);
