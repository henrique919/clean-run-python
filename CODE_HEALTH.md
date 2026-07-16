# CleanRun IQ Code Health

## Active Production Surface

Render deploys the root FastAPI app via `python app.py` (see `render.yaml`), which imports `app.main:app`.

Production browser UI at `/` is intentionally served from the legacy Render3 export:

- `CleanRun-IQ-Full-App-Render3/index.html`
- `CleanRun-IQ-Full-App-Render3/assets/enhancements.js`
- `CleanRun-IQ-Full-App-Render3/assets/enhancements.css`

The modular UI under `app/static/` is mounted at `/static` and used as a fallback if Render3 is missing. It is **not** the primary production shell.

Core backend modules:

- `app/main.py` — routes, auth wiring, Render3 root handler
- `app/db.py` — repository factory (`build_repository`)
- `app/repositories/` — local and Supabase persistence adapters
- `app/services/` — settings, item, and report orchestration
- `app/store.py` / `app/store_supabase.py` — shared store logic (used by repositories)
- `app/auth.py`, `app/permissions.py`, `app/storage.py`, `app/reporting.py`, `app/workflow.py`, `app/validation.py`

## API Surfaces

| Endpoint | Consumer |
|----------|----------|
| `/api/state` | Render3 production UI (camelCase payload) |
| `/api/bootstrap` | Modular `app/static` UI |
| `/api/items/*`, `/api/reports/*` | Both UIs |
| `/api/reset` and `/api/reset-demo` | Demo reset (gated by env) |

**Plans (deliberately deferred):** the Plans nav is intercepted with a "coming soon" toast (`CleanRun-IQ-Full-App-Render3/index.html`, `go()`), so the legacy Plans UI is unreachable in production. The backend `/api/plans` routes are intentionally absent and `/api/state` returns `"plans": []`. Do not build them — floor-plan pinning is on the deferred list in `CLAUDE.md`.

## Legacy Copies

Historical exports remain in the repo for reference. Do not delete or mix fixes across them unless a deployment is explicitly pointed at one:

- `CleanRun-IQ-Full-App-Render2/`
- `CleanRun-IQ-FastAPI-Render/`
- `cleanrun-iq-python-html-render-ready/`
- `cleanrun_iq_python_port/`
- `rork-cleanrun-iq-3-v3-logo-250-bigger(1)/`

## Stability Baseline

Recent stability work includes:

- Repository layer (`app/db.py`, `app/repositories/`, `app/services/`) over shared store logic
- Launch storage path repair (`cleanrun/public` prefix) and authenticated write migrations (`20260701*`)
- Client-side evidence compression in Render3 (`enhancements.js`)
- Workflow transition guards (`app/workflow.py`) and evidence validation (`app/validation.py`)
- Report scoping via `visible_items()` and subcontractor portal lock in Render3
- Lazy Supabase import and atomic local JSON writes for dev/demo mode

## Baseline Checks

Run these before any deploy candidate:

```text
python3 -m compileall app
python3 -m pytest tests/ -q
python3 app.py
```

Then smoke test against the served UI (Render3 when present):

- Load `http://127.0.0.1:8000/`
- Sign in and confirm `/api/state` loads project data
- Capture an item with photo evidence
- Issue → rectification → ready for review → inspect → close or reject
- Open `/api/reports/handover`
- Confirm `/health` returns `{"status":"ok"}` and `/api/health` returns `{"ok":true}`

## Do Not Change Without Explicit Approval

- Supabase RLS policies or anon/public launch policies
- Storage object path prefix (`cleanrun/public/...`)
- Auth token verification or launch-admin bypass logic
- Removing legacy frontend folders
- Switching `/` from Render3 to `app/static/index.html`
