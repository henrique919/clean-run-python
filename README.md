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
- Local JSON storage layer
- Handover report HTML with closed evidence and outstanding/rejected section

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
```

## Notes

This is intentionally local-first for the Python version. A later production pass should replace the JSON store with Postgres/Supabase and object storage for photos.
