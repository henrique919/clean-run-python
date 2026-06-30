-- Temporary public full-app mode storage access.
--
-- The production web app is currently running without the dedicated Supabase
-- login gate while launch issues are being repaired. Browser uploads therefore
-- use the anon key and are constrained to this single public-mode prefix.

drop policy if exists "public_full_app_storage_select" on storage.objects;
create policy "public_full_app_storage_select"
on storage.objects
for select
to anon
using (
  bucket_id = 'cleanrun-evidence'
  and name like 'cleanrun/public/%'
);

drop policy if exists "public_full_app_storage_insert" on storage.objects;
create policy "public_full_app_storage_insert"
on storage.objects
for insert
to anon
with check (
  bucket_id = 'cleanrun-evidence'
  and name like 'cleanrun/public/%'
);
