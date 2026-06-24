# CleanRun IQ Field App

Render-ready Python implementation of the complete CleanRun IQ field workflow.
The production entry point is the self-contained root `app.py`, which includes
the mobile-first five-tab interface and its backend.

Core principle:

**Capture the item. Assign the trade. Close it with proof.**

The deployed app includes:

- Photo-first item capture
- Defect / Incomplete Work / Client Defect item types
- Strict capture validation
- Task / Location / Assign dropdown-style form structure
- Full item lifecycle
- Original, rectification and closeout evidence chains
- Item edit support
- Keyboard dismiss helper for mobile web
- Local JSON storage layer
- Handover report HTML with closed evidence and outstanding/rejected section
- Home dashboard, item register, raised Capture action, Plans and More taskbar
- Project setup, subcontractor mode, reports and administration tools

## Run locally

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Render deployment

Deploy the repository as a Blueprint using the root `render.yaml`. It runs
`python app.py` and stores persistent data at `/var/data/cleanrun_data.json`.

## Notes

The `app/` directory is an alternate FastAPI prototype retained for reference;
it is not the Render production entry point.
