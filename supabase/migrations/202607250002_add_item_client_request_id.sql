-- Client-generated idempotency token for item creation.
--
-- The offline capture queue can retry a create-item POST — a permanently
-- failing entry that used to block the whole queue (poison-pill), a
-- concurrent flush racing the init flush (both draining at once), or a
-- plain double-tap-after-timeout — and resend the exact same capture. The
-- client already sends a stable per-capture id (clientRequestId), but
-- nothing on the server stored or looked it up, so these retries created
-- duplicate items. The existing 300-second fingerprint dedupe
-- (app/store.py _recent_duplicate) does not help here: it excludes photos
-- from the fingerprint, so it also wrongly collapses distinct captures that
-- happen to share a short description.
--
-- This column plus the lookup in app/store_supabase.py
-- (_find_by_client_request_id) let create_item() return the original item
-- for a matching retry instead of inserting a second one, checked before
-- (and instead of) the fingerprint check whenever a client sends this id.
--
-- Nullable, additive column + partial unique index — no data migration, no
-- change to existing rows.
--
-- IMPORTANT — deploy ordering: unlike a typical additive column, this one
-- is NOT safe to leave unapplied once the paired app code ships. The item
-- create/update write path (app/store_supabase.py _upsert_item) always
-- includes a client_request_id key in the row it upserts; PostgREST/
-- Supabase rejects an upsert containing a key with no matching column. So
-- this migration must be applied to the target Supabase project BEFORE (or
-- atomically with) the app code from this batch reaches any environment
-- backed by that project — including Render PR previews, which share
-- production Supabase per this repo's CLAUDE.md. It was intentionally not
-- run against the live project by the agent that wrote it (no
-- apply_migration / live Supabase calls) — the owner needs to run it.
-- The app/store.py local JSON store has no such dependency (client_request_id
-- is just a plain model field there, nothing schema-backed).

alter table public.items
  add column if not exists client_request_id text;

create unique index if not exists idx_items_company_client_request_id_unique
  on public.items (company_id, client_request_id)
  where client_request_id is not null;
