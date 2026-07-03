# CleanRun IQ — Claude Code onboarding

Python/FastAPI field workflow app for construction closeout: **capture the item, assign the trade, close it with proof.**

Production: https://app.cleanruniq.com (Render service `clean-run-python`).

## What to work on

| Active (edit these) | Legacy (reference only — do not fix or deploy) |
|---------------------|------------------------------------------------|
| `app/` — FastAPI backend | `CleanRun-IQ-Full-App-Render2/` |
| `CleanRun-IQ-Full-App-Render3/` — production UI at `/` | `CleanRun-IQ-FastAPI-Render/` |
| `tests/` — active test suite | `cleanrun-iq-python-html-render-ready/` |
| `supabase/` — migrations & RLS | `cleanrun_iq_python_port/` |
| `render.yaml`, `scripts/` | `rork-cleanrun-iq-3-v3-logo-250-bigger(1)/` |

See `CODE_HEALTH.md` and `README.md` for architecture detail. `AGENTS.md` has Cursor Cloud–specific notes (overlap is intentional).

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, Supabase (Postgres + Storage + Auth)
- **Frontend:** Static HTML/JS in `CleanRun-IQ-Full-App-Render3/` (`enhancements.js` + `index.html`; bump `cardsNN` cache-bust tag when shipping UI changes)
- **Deploy:** Render (`python app.py`), `render.yaml` at repo root

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Local dev (JSON storage, no Supabase)
CLEANRUN_STORAGE=local uvicorn app.main:app --reload

# Sanity checks before PR
python3 -m compileall app
python3 -m pytest tests/ -q          # scope to tests/ only — never bare pytest at repo root
node tests/voice-parser.test.js
```

Open `http://127.0.0.1:8000/` for Render3 (production shell). Modular dev UI with demo login buttons: `http://127.0.0.1:8000/static/index.html`.

## Auth (dev vs production)

- **Local:** `Authorization: Bearer dev-site-manager` (also `dev-project-manager`, `dev-subcontractor`, `dev-viewer`). Only works when `CLEANRUN_ENV` is not `production`.
- **Production:** Supabase JWT; claims in `app_metadata.cleanrun` (see `SECURITY.md`).
- **Open access (temporary launch window):** `CLEANRUN_LOGIN_REQUIRED=false` (default in code) skips the sign-in UI; server uses `CLEANRUN_OPEN_ACCESS_EMAIL` / `CLEANRUN_OPEN_ACCESS_PASSWORD` for Supabase writes. Set `CLEANRUN_LOGIN_REQUIRED=true` to restore login.

Never add `SUPABASE_SERVICE_ROLE_KEY` to the web app process.

## API surfaces

| Endpoint | Consumer |
|----------|----------|
| `/api/state` | Render3 UI (camelCase items) |
| `/api/bootstrap` | Modular `/static` UI |
| `/api/items`, `/api/reports/*` | Both UIs |
| `/api/auth/config` | Login / open-access flag |

Render3 is the production shell; do not switch `/` to `app/static/index.html` without explicit approval.

## Domain rules

- Item types: Defect, Incomplete Work, Client Defect — Defect/Client require photo evidence; Incomplete Work may save without photo (`app/validation.py`).
- Full lifecycle: open → issued → in progress → ready for review → inspection → closed/rejected.
- Signed URL cache + parallel signing in `app/storage.py`; prefetch on `/api/state` and item create/action responses.
- Save/issue perf: client merges API responses locally (no full `/api/state` reload); server uses lightweight reads on create/patch.

## Testing

- Run `python3 -m pytest tests/ -q` — 100+ tests; do not collect legacy folder tests.
- After UI changes: update `cardsNN` in `enhancements.js` and `index.html`; update matching assertions in `tests/test_*_checklist.py`, `test_recovery.py`, `test_auth_permissions.py`.
- Live smoke (optional): `CLEANRUN_LIVE_BASE_URL`, `CLEANRUN_LIVE_EMAIL`, `CLEANRUN_LIVE_PASSWORD`.

## Do not change without explicit approval

- Supabase RLS policies or storage path prefix (`cleanrun/public/...`)
- Auth verification / launch-admin bypass logic (`app/auth.py`)
- Removing legacy frontend folders
- Merging PRs to `main` without user approval on feature work (hotfixes excepted when asked)

## Git / PR workflow

- Branch prefix: `cursor/<descriptive-name>-0ad2`
- Push: `git push -u origin <branch>`
- Run tests before commit; clear commit messages; draft PR unless asked to merge
- Production deploy tracks `main` on Render automatically

## Key files

```
app/main.py                 Routes, auth, camelCase /api/state
app/store_supabase.py       Supabase persistence, create/patch perf
app/storage.py              Evidence upload, signed URL cache
app/auth.py                 JWT + open-access mode
CleanRun-IQ-Full-App-Render3/assets/enhancements.js   Production UI logic
CleanRun-IQ-Full-App-Render3/index.html               Boot, auth shell, cache tags
render.yaml                 Render env template (dashboard may not auto-sync)
```

## Gotchas

- Root `pytest` fails on legacy copies — always `pytest tests/`.
- `render.yaml` env vars are not automatically applied to an existing Render service; verify `/api/auth/config` on production after deploy.
- Plans UI references `/api/plans` which the backend does not implement (`plans: []` in state).
- Photo uploads use parallel workers; create uses `_read_create_context()` not full `_read()`.
