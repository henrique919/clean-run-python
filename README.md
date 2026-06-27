# CleanRun IQ Python

Python/FastAPI implementation of the CleanRun IQ field workflow.

Core principle:

**Capture the item. Assign the trade. Close it with proof.**

This scaffold implements:

- Photo-first item capture
- Defect / Incomplete Work / Client Defect item types
- Strict capture validation
- Task / Location / Assign dropdown-style form structure
- Full item lifecycle
- Original, rectification and closeout evidence chains
- Item edit support
- Keyboard dismiss helper for mobile web
- Local JSON storage layer for development plus strict Supabase-backed production storage
- Handover report HTML with closed evidence and outstanding/rejected section
- Supabase CLI migrations, RLS policies, private storage bucket rules, and generated TypeScript type target

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Main files

```text
app/main.py          FastAPI routes and static app server
app/models.py        CleanRun IQ domain models
app/store.py         JSON persistence layer
app/validation.py    Capture/update validation
app/reporting.py     HTML report builder
app/static/          Mobile-first browser UI
supabase/            Supabase CLI config, migrations, seed, storage/RLS policies, generated type target
```

## Supabase local-first workflow

Install the Supabase CLI, then run:

```bash
supabase start
supabase db reset
supabase gen types typescript --local > supabase/types/database.types.ts
```

On Windows with Docker Desktop per-user installs, use the repo scripts so the
Supabase CLI can find Docker and the local TCP daemon:

```bash
npm.cmd run supabase:win -- start
npm.cmd run supabase:win -- db reset
npm.cmd run supabase:types
```

Production database deploy:

```bash
supabase link --project-ref <project-ref>
supabase db push
supabase gen types typescript --project-id <project-ref> > supabase/types/database.types.ts
```

Production environment:

```text
CLEANRUN_ENV=production
CLEANRUN_STORAGE=supabase
CLEANRUN_REQUIRE_SUPABASE=true
SUPABASE_URL=<project-url>
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
SUPABASE_JWT_SECRET=<project-jwt-secret>
CLEANRUN_ENABLE_DEMO_RESET=false
```

Never configure `SUPABASE_SERVICE_ROLE_KEY` in the web app process. If privileged work is needed later, place it behind Supabase Edge Functions or security-definer database functions.

See `SECURITY.md` for the current auth, tenant/RLS, storage, audit, and demo reset rules.

See `CODE_HEALTH.md` before deploying so the Render service targets the active FastAPI app surface.
