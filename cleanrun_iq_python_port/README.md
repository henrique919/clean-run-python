# CleanRun IQ Python Port

This is a Python 3.10+ port of the CleanRun IQ Rork/Expo app's domain layer. It converts the React Native local store, models, item workflow, voice-note parser, and report generator into a FastAPI-ready Python service.

Important: the original Rork ZIP is a mobile React Native/Expo app. Python cannot run the native mobile UI one-for-one, so this port focuses on the reusable backend/domain logic and exposes it as a Python API.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn cleanrun_iq.api:app --reload
```

Open: http://127.0.0.1:8000/docs

## Verify

```bash
pytest
```

## Main files

- `cleanrun_iq/models.py` — domain models/enums translated from TypeScript.
- `cleanrun_iq/services.py` — item workflow: create, issue, rectify, review, reject, close.
- `cleanrun_iq/store.py` — JSON persistence replacing AsyncStorage.
- `cleanrun_iq/voice_parser.py` — offline deterministic voice-to-fields parser.
- `cleanrun_iq/report_builder.py` — HTML report generation.
- `cleanrun_iq/api.py` — FastAPI endpoints.
