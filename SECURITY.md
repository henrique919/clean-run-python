# CleanRun IQ Security Foundation

CleanRun IQ uses Supabase as the production identity, database, and storage boundary.
The FastAPI app must never run with a Supabase `service_role` key.

## Authentication

- Browser/API requests use `Authorization: Bearer <Supabase access token>`.
- Production validates the token with `SUPABASE_JWT_SECRET`.
- Authorization claims come from `app_metadata.cleanrun`, not `user_metadata`.
- Local development can use dev tokens such as `dev-site-manager` only when `CLEANRUN_ENV` is not `production`.

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

Core security tables:

- `companies`
- `company_members`
- `projects`
- `project_members`
- `subcontractors`
- `project_subcontractors`
- `subcontractor_users`
- `items`
- `evidence`
- `comments`
- `audit_events`

Every table has RLS enabled. Project and item access are checked through
security-definer helper functions in the private `app` schema to avoid recursive
policy lookups.

## Storage

The `cleanrun-evidence` bucket is private. Object paths must start with:

```text
<auth.uid>/<project_id>/...
```

Storage RLS checks the first path segment against `auth.uid()` and checks project
access with `app.is_project_member(project_id)`.

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
