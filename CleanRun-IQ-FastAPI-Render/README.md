# CleanRun IQ Field App

Render-ready Python/FastAPI implementation of the CleanRun IQ field capture,
QA, defect and handover workflow.

**Smarter Field. Cleaner Builds.**

## Included

- Photo-first defect, incomplete work and client defect capture
- Structured project, location, trade and subcontractor assignment
- Inline field and evidence validation
- Full issue, rectification, inspection, rejection and closeout lifecycle
- Original, rectification and closeout evidence chains
- Searchable field register and complete edit drawer
- Branded builder/client handover reports
- Local JSON storage with optional Render persistent disk
- Responsive Archivo/Inter interface using the approved CleanRun IQ identity

## Run locally

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Deploy on Render

Deploy the repository as a Blueprint using the root `render.yaml`. The build
installs `requirements.txt`, starts `uvicorn app.main:app`, checks `/health`,
and stores JSON data on the mounted `/var/data` disk.

The self-contained root `app.py` is retained as legacy source. The supported
application and branded interface are served by `app.main:app`.
