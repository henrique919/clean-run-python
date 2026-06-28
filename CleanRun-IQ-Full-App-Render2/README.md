# CleanRun IQ Field App

Render-ready Python field capture, QA, defect and handover application.

**Smarter Field. Cleaner Builds.**

The supported deployment is the root `app.py` service and `index.html`
interface. It includes the complete five-tab field experience:

- Home dashboard and searchable item register
- Photo-first defect, incomplete work and client defect capture
- Voice-to-note drafting with typed-note fallback
- Project, location, trade and subcontractor assignment
- Issue, rectification, inspection, rejection and closeout lifecycle
- Original, rectification and closeout evidence chains
- Item editing, comments and audit history
- Image/PDF plan uploads with plan pins, subcontractor mode, project setup and administration
- Branded report previews with Print / Save PDF
- Local JSON storage with optional Render persistent disk

## Run locally

```bash
python app.py
```

Open `http://127.0.0.1:8000`.

## Deploy on Render

Deploy the repository as a Blueprint using `render.yaml`. Render runs
`python app.py`, checks `/api/health`, and stores JSON data at
`/var/data/cleanrun_data.json` on the mounted persistent disk.

The `app/` FastAPI package is retained as an alternate implementation, but the
root service is the deployment that contains the full taskbar and toolset.
