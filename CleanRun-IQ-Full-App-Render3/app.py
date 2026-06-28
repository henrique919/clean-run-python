import json
import os
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from openai import OpenAI
except Exception:  # dependency may be absent until Render rebuilds
    OpenAI = None

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CLEANRUN_DATA_DIR", ROOT / ".data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA_DIR / "state.json"

app = FastAPI(title="CleanRun IQ", version="render3-ai-voice")

if (ROOT / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="assets")

TRADES = ["Painting", "Plastering", "Tiling", "Waterproofing", "Joinery", "Doors / Hardware", "Windows / Aluminium", "Flooring", "Roofing", "Cladding", "Electrical", "Hydraulic", "Mechanical", "Fire Services", "Cleaning", "Landscaping", "Concrete", "Render", "Caulking / Sealant", "General Damage"]
SUBS = ["Coastline Painting", "AquaSeal Waterproofing", "ASTW Tiling", "H&L Roofing", "King Truss", "ANCO", "Reliable Plastering", "Coastal Joinery"]


def now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def seed_state():
    today = date.today()
    return {"settings": {"activeProject": "Jura Noosa", "preparedBy": "CleanRun IQ", "projects": ["Jura Noosa", "Meta Street"], "trades": TRADES, "subcontractors": SUBS}, "items": [{"id": "seed-def-022", "code": "DEF-022", "project": "Jura Noosa", "type": "defect", "status": "open", "priority": "high", "building": "Building 3", "level": "Level 1", "unit": "Unit 305", "room": "Balcony", "trade": "Tiling", "subcontractor": "ASTW Tiling", "description": "Balcony tiling to be repaired.", "dueDate": (today + timedelta(days=3)).isoformat(), "createdAt": now(), "updatedAt": now(), "originalPhotos": [], "rectificationPhotos": [], "comments": [], "events": []}]}


def load_state():
    if not STATE_FILE.exists():
        save_state(seed_state())
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        state = seed_state()
        save_state(state)
        return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def first(pattern, text):
    m = re.search(pattern, text, flags=re.I)
    return m.group(1).strip() if m else ""


def clean_description(text):
    value = text or ""
    for pattern in [r"\bbuilding\s*\d+\b", r"\blevel\s*\d+\b", r"\bunit\s*\d+[a-z]?\b", r"\bblock\s*[a-z0-9]+\b"]:
        value = re.sub(pattern, " ", value, flags=re.I)
    value = re.sub(r"\b(on|in|at|for)\s*(,|$)", " ", value, flags=re.I)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"^[\s,.-]+|[\s,.-]+$", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return (value[:1].upper() + value[1:]) if value else text


def parse_note(transcript):
    raw = (transcript or "").strip()
    text = raw.lower()
    fields = {"voiceTranscript": raw, "voice_transcript": raw, "raw_transcript": raw}
    b = first(r"\bbuilding\s*(\d+)\b", raw)
    if b:
        fields["building"] = f"Building {b}"
    l = first(r"\blevel\s*(\d+)\b", raw)
    if l:
        fields["level"] = f"Level {l}"
    u = first(r"\bunit\s*(\d+[a-z]?)\b", raw)
    if u:
        fields["unit"] = f"Unit {u.upper()}"
    for room in ["balcony", "kitchen", "bathroom", "ensuite", "bedroom", "living", "garage", "laundry"]:
        if room in text:
            fields["room"] = room.title()
            break
    hints = {"Tiling": ["tile", "tiling", "grout"], "Painting": ["paint"], "Waterproofing": ["waterproof", "membrane"], "Plastering": ["plaster"], "Joinery": ["joinery", "cabinet"], "Electrical": ["light", "switch", "power", "gpo"]}
    for trade, words in hints.items():
        if any(w in text for w in words):
            fields["trade"] = trade
            break
    fields["priority"] = "urgent" if "urgent" in text or "asap" in text else "medium"
    fields["type"] = "incomplete" if "incomplete" in text or "missing" in text or "not finished" in text else "defect"
    fields["description"] = clean_description(raw)
    fields["voiceNote"] = {"transcript": raw, "parsed_fields": dict(fields), "created_at": now(), "status": "parsed"}
    fields["voice_note"] = fields["voiceNote"]
    return fields


def ai_available():
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


def ai_parse_note(transcript):
    base = parse_note(transcript)
    if not ai_available():
        return base
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini")
        prompt = "Extract CleanRun IQ defect fields as compact JSON only. Allowed keys: building, level, unit, room, trade, subcontractor, priority, type, description. Do not invent unknown fields. Description must be the actual issue only, not the location words."
        res = client.chat.completions.create(model=model, response_format={"type": "json_object"}, messages=[{"role": "system", "content": prompt}, {"role": "user", "content": transcript}])
        data = json.loads(res.choices[0].message.content or "{}")
        for key in ["building", "level", "unit", "room", "trade", "subcontractor", "priority", "type", "description"]:
            if data.get(key):
                base[key] = data[key]
        base["voiceNote"] = {"transcript": transcript, "parsed_fields": dict(base), "created_at": now(), "status": "ai_parsed"}
        base["voice_note"] = base["voiceNote"]
    except Exception as exc:
        base["voice_warning"] = f"AI parse fallback used: {exc}"
    return base


async def transcribe_upload(upload):
    if not ai_available():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured on Render")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Audio recording is empty")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    name = getattr(upload, "filename", None) or "voice.webm"
    mime = getattr(upload, "content_type", None) or "audio/webm"
    result = client.audio.transcriptions.create(model=model, file=(name, data, mime))
    return getattr(result, "text", "") or str(result)


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "manifest.webmanifest")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"ok": True, "version": "render3-ai-voice"}


@app.get("/api/voice/status")
def voice_status():
    return {"ai_voice_enabled": ai_available(), "deterministic_parser_enabled": True, "transcribe_model": os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"), "parse_model": os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini")}


@app.post("/api/parse")
def parse(payload: dict = Body(default_factory=dict)):
    transcript = str(payload.get("transcript") or payload.get("text") or "")
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")
    return ai_parse_note(transcript)


@app.post("/api/voice/parse")
async def voice_parse(request: Request):
    ctype = (request.headers.get("content-type") or "").lower()
    transcript = ""
    if "multipart/form-data" in ctype:
        form = await request.form()
        transcript = str(form.get("transcript") or "")
        audio = form.get("audio") or form.get("file") or form.get("recording")
        if audio is not None and hasattr(audio, "read"):
            transcript = await transcribe_upload(audio)
    elif "application/json" in ctype:
        data = await request.json()
        transcript = str(data.get("transcript") or data.get("text") or "")
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="No transcript or audio supplied")
    return {"transcript": transcript, "parsed": ai_parse_note(transcript), "warnings": []}


@app.get("/api/state")
def get_state():
    return load_state()


@app.post("/api/items")
def create_item(payload: dict = Body(default_factory=dict)):
    state = load_state()
    kind = payload.get("type") or "defect"
    prefix = "INC" if kind == "incomplete" else "DEF"
    n = 1 + sum(1 for i in state.get("items", []) if str(i.get("code", "")).startswith(prefix + "-"))
    item = {"id": str(uuid.uuid4()), "code": f"{prefix}-{n:03d}", "project": payload.get("project") or state["settings"]["activeProject"], "type": kind, "status": payload.get("status") or "open", "priority": payload.get("priority") or "medium", "building": payload.get("building") or "", "level": payload.get("level") or "", "unit": payload.get("unit") or "", "room": payload.get("room") or "", "trade": payload.get("trade") or "", "subcontractor": payload.get("subcontractor") or "", "description": payload.get("description") or "", "dueDate": payload.get("dueDate") or (date.today() + timedelta(days=7)).isoformat(), "createdAt": now(), "updatedAt": now(), "originalPhotos": payload.get("originalPhotos") or payload.get("photos") or [], "rectificationPhotos": [], "comments": [], "events": [], "voiceTranscript": payload.get("voiceTranscript") or payload.get("voice_transcript") or "", "voiceNote": payload.get("voiceNote") or payload.get("voice_note")}
    state.setdefault("items", []).append(item)
    save_state(state)
    return item


@app.post("/api/items/{item_id}/actions/{action}")
def item_action(item_id: str, action: str, payload: dict = Body(default_factory=dict)):
    state = load_state()
    next_status = {"issue": "issued", "start": "in_progress", "ready": "ready_for_review", "inspect": "under_inspection", "close": "closed", "reject": "rejected", "reopen": "open"}.get(action)
    for item in state.get("items", []):
        if item.get("id") == item_id:
            if next_status:
                item["status"] = next_status
            if payload.get("to"):
                item["subcontractor"] = payload["to"]
            item["updatedAt"] = now()
            item.setdefault("events", []).append({"at": now(), "action": action, "by": payload.get("by") or "CleanRun IQ"})
            save_state(state)
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.exception_handler(HTTPException)
def http_error(_, exc):
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
