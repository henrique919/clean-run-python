# CleanRun IQ Code Health

## Active Surface

The deployable root app is the FastAPI/static implementation:

- `app/main.py`
- `app/models.py`
- `app/store.py`
- `app/store_supabase.py`
- `app/reporting.py`
- `app/static/`

Root `render.yaml` starts this surface with:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Legacy Copies

The repository also contains historical app exports:

- `app.py`
- `CleanRun-IQ-Full-App-Render2/`
- `CleanRun-IQ-Full-App-Render3/`
- `CleanRun-IQ-FastAPI-Render/`
- `cleanrun-iq-python-html-render-ready/`
- `cleanrun_iq_python_port/`

Treat these as reference material unless a deployment is explicitly pointed at one of them. Mixing fixes across these copies is the fastest way to ship a change that is invisible in production.

## Deployment Mismatch To Resolve

The current live app at `https://app.cleanruniq.com/` appears to serve a legacy inline app surface, while the root repo deployment config points at `app.main:app`. Deployment should stay on hold until the Render service is confirmed to deploy the intended root FastAPI surface.

Expected root FastAPI checks:

- `/health` returns `{"status":"ok"}`
- `/api/health` returns `{"ok":true}`
- `/api/bootstrap` returns settings, items, trades, and raised-by options
- `/static/app.js` returns the browser app bundle

## Stability Baseline

Current stability work includes:

- Lazy Supabase import so local JSON startup is not blocked by optional Supabase dependency issues.
- Atomic local JSON writes to reduce risk of corrupt state after an interrupted write.
- Recoverable browser bootstrap/reset error UI.
- Supabase settings persistence through `app_settings`, with seeded fallback if unavailable.
- Self-contained Supabase schema for `items.payload`, `items_payload_idx`, and `app_settings`.

## Baseline Checks

Run these before any deploy candidate:

```text
python -m compileall app
python -m unittest tests.test_recovery
uvicorn app.main:app --host 127.0.0.1 --port 8012
```

Then smoke test:

- Load `http://127.0.0.1:8012/`
- Reset demo data
- Capture an item
- Issue Now
- Submit rectification and send ready for review
- Start inspection
- Close or reject
- Open `/api/reports/handover`
