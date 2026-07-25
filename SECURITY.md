# CleanRun IQ Security Foundation

CleanRun IQ uses Supabase as the production identity, database, and storage boundary.
The FastAPI app must never run with a Supabase `service_role` key.

**This file describes the actual current implementation, verified against
production 2026-07-25 — not the original per-project relational design.
The two diverged: the RLS helper-function model described in earlier
versions of this doc (`app.is_project_member`, per-`auth.uid()` storage
paths) was never wired up to how the app actually grants access (JWT
`app_metadata.cleanrun` claims — see Authentication below), and the app
never writes to the `project_members`/`company_members` tables that model
depends on. What's actually enforced today is described below; the
relational model is a real follow-up for when this product has more than
one tenant (see `LOOP_BACKLOG.md`), not something currently in effect.**

## Authentication

- Browser/API requests use `Authorization: Bearer <Supabase access token>`.
- Production validates the token with `SUPABASE_JWT_SECRET` (algorithm HS256,
  audience `authenticated`, 30s leeway) and falls back to a live call to
  Supabase's `/auth/v1/user` if local verification fails for any reason
  (falls back on a rotated/misconfigured secret too — this fallback is
  logged, not silent).
- Authorization claims come from `app_metadata.cleanrun`, not `user_metadata`.
  This is checked entirely in Python (`app/permissions.py`, against the
  `AuthUser` built from those claims) — Postgres RLS does not enforce
  per-project or per-role access; see Tenant Model below.
- Local development can use dev tokens such as `dev-site-manager` only when `CLEANRUN_ENV` is not `production`.
- `CLEANRUN_LOGIN_REQUIRED` defaults to `true` (fails closed). Setting it
  to `false` grants every unauthenticated caller a full-admin
  `_open_access_user()` (`app/auth.py`) — local dev only; production pins
  `true` explicitly in `render.yaml` regardless of this default.

Expected JWT claim shape:

```json
{
  "app_metadata": {
    "cleanrun": {
      "company_id": "uuid",
      "company_role": "admin",
      "project_roles": {
        "Jura Noosa": "site_manager"
      },
      "subcontractors": ["ASTW Tiling"],
      "demo_admin": false
    }
  }
}
```

## Tenant Model

The Supabase schema is managed only through `/supabase/migrations`.

The app is currently **single-tenant in practice**: every row is stamped
with one hardcoded company id (`00000000-0000-0000-0000-000000000001`),
and the tables the app actually reads/writes are `companies`, `projects`,
`locations`, `subcontractors`, `project_subcontractors`, `items`,
`item_photos`, `item_comments`, `item_audit_events`, and a single global
`app_settings` row. (`company_members`, `project_members`,
`subcontractor_users`, `evidence`, `comments`, `audit_events` exist in the
schema from the original relational design but are unused — 0 rows — do
not assume they reflect real access grants.)

Every table has RLS enabled. As of `supabase/migrations/
202607250001_close_anon_data_access.sql` (see that file's comments for
full rationale — **pending application to production**, see
`LOOP_BACKLOG.md`/open PRs), the `public_full_app_*` policies restrict
every launch-mode table to the `authenticated` role, scoped to the single
company id above. RLS does **not** enforce per-project or per-role access
within that company — that's done in `app/permissions.py`, in Python,
after the request is already authenticated. Before that migration is
applied, these same tables also grant the `anon` role full access, scoped
only by the same company id — i.e. no login required at all at the
database layer, only at the FastAPI layer (`/api/auth/config` hands the
anon/publishable key to anyone who loads the page). Do not treat "the
login screen is on" as equivalent to "the data is protected" until that
migration has been applied and verified.

The `app.is_project_member`/`app.can_access_item` security-definer
functions still exist in the `app` schema from the original design but are
not part of the currently-enforced policy set for the launch-mode tables
above (they read `project_members`, which the app never populates).

## Storage

The `cleanrun-evidence` bucket is private (`public = false`). In practice,
all production objects live under a single shared prefix:

```text
cleanrun/public/<folder>/<uuid4>.<ext>
```

**Not** `<auth.uid>/<project_id>/...` — that per-user path scheme was the
original design but was never what the app actually writes
(`app/storage.py::_object_path`). Storage RLS policies match on this
prefix, restricted to the `authenticated` role (once the migration above
is applied — previously `anon`/`public` could also read and, for inserts,
write under this prefix). Per-item access control for photos is enforced
in Python at the FastAPI layer, from the caller's visible-items allowlist
— **with one known gap**: `/api/photos/markup-source` has a bypass that
admits any path under the shared prefix regardless of the allowlist (see
`IDOR-01` in `LOOP_BACKLOG.md`).

## Audit Trail

API routes ignore client-supplied actor names for security-sensitive mutations.
The server stamps audit events with the authenticated user id, email, role, and
request context.

Audit rows are append-only from the client side. There are no update/delete RLS
policies for `audit_events`.

## Demo Reset

`/api/reset-demo` requires an authenticated demo admin. In production it is blocked
unless `CLEANRUN_ENABLE_DEMO_RESET=true`, which should remain false for real
deployments.

## Verification

```powershell
python -m unittest discover -s tests
npm.cmd run supabase:win -- db reset
npm.cmd run supabase:types
```

Production deploys should run:

```bash
supabase db push
supabase gen types typescript --project-id <project-ref> > supabase/types/database.types.ts
```
