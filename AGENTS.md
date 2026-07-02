# AGENTS.md

## Cursor Cloud specific instructions

The active, deployable product is the **CleanRun IQ FastAPI + static-UI** app at the repo root
(`app/`). See `README.md` and `CODE_HEALTH.md` for the full picture. The sibling folders
(`CleanRun-IQ-*`, `cleanrun-iq-python-html-render-ready/`, `cleanrun_iq_python_port/`, and the
Expo app under `rork-cleanrun-iq-3-*`) are legacy/reference copies — do not run or test them for
end-to-end validation.

### Environment
- Python **3.12** in a local `.venv` (gitignored). The update script creates the venv and installs
  `requirements.txt`. Activate with `source .venv/bin/activate` or call binaries via `.venv/bin/...`.
- No linter is configured for the Python code. The documented build/compile sanity check is
  `python -m compileall app` (see `CODE_HEALTH.md`).

### Running the app (dev)
- Run with local JSON storage (no external services needed):
  `CLEANRUN_STORAGE=local .venv/bin/uvicorn app.main:app --reload` (serves on port 8000).
  Data persists to `.cleanrun-data/`. `python app.py` is the Render-style launcher (honors `$PORT`).
- Supabase storage mode (`CLEANRUN_STORAGE=supabase`) and the Supabase CLI (`supabase start`)
  require Docker and are only needed to exercise the production storage/auth path.
- OpenAI voice parsing (`/api/voice/*`) is optional and degrades gracefully (503) without
  `OPENAI_API_KEY`.

### Non-obvious gotchas
- **The root `/` route serves the *legacy* UI** from `CleanRun-IQ-Full-App-Render3/index.html`
  (Supabase-only login, no dev login buttons) whenever that directory exists — see `index()` in
  `app/main.py`. For the modern local-dev UI with dev login buttons, open
  **`http://127.0.0.1:8000/static/index.html`** directly.
- **Dev auth:** outside production, pass `Authorization: Bearer dev-site-manager` (or
  `dev-project-manager`, `dev-subcontractor`, `dev-viewer`) on API requests. The modern
  `/static/index.html` login screen exposes "Site Manager demo" / "Subcontractor demo" buttons
  that set this token. Most `/api/*` routes return `401 Authentication required` without it.
- Item capture validation is strict: Defect/Client Defect require an original photo, but
  **Incomplete Work** items can be saved without a photo (see `app/validation.py`) — handy for
  quick UI smoke tests.

### Tests
- **Do not run bare `pytest` from the repo root** — it also collects the legacy copies and fails
  with import-file-mismatch/`ModuleNotFoundError` collection errors. Scope to the active suite:
  `.venv/bin/python -m pytest tests/`.
- Baseline unittest check: `.venv/bin/python -m unittest tests.test_recovery`.
- One JS unit test (no npm script): `node tests/voice-parser.test.js`.
