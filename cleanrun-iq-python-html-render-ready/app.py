"""CleanRun IQ web backend translated from the supplied Rork/Expo TypeScript app.

Run with: python app.py
Then open: http://127.0.0.1:8000

Assumptions made during translation:
* React Native AsyncStorage is replaced by an atomic local JSON data file.
* Device photos/plan images are sent by the HTML client as data URLs.
* Native sharing/printing is replaced by a printable HTML report endpoint.
* Voice transcription remains deterministic and offline: typed/browser-transcribed
  text is parsed with the same rules as the original application's fallback.
"""

from __future__ import annotations

import copy
import html
import json
import os
import re
import tempfile
import threading
import uuid
import webbrowser
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
# Render filesystems are ephemeral unless a persistent disk is mounted. Set
# CLEANRUN_DATA_FILE=/var/data/cleanrun_data.json when using such a disk.
DATA_FILE = Path(os.environ.get("CLEANRUN_DATA_FILE", ROOT / "cleanrun_data.json"))
INDEX_FILE = ROOT / "index.html"
LOCK = threading.RLock()
STATE_VERSION = 3

TRADES = [
    "Painting", "Plastering", "Tiling", "Waterproofing", "Joinery",
    "Doors / Hardware", "Windows / Aluminium", "Flooring", "Roofing",
    "Cladding", "Electrical", "Hydraulic", "Mechanical", "Fire Services",
    "Cleaning", "Landscaping", "Concrete", "Render",
    "Caulking / Sealant", "General Damage",
]
TYPE_LABEL = {"defect": "Defect", "incomplete": "Incomplete Work", "client": "Client Defect"}
STATUS_LABEL = {
    "open": "Open", "issued": "Issued", "in_progress": "In Progress",
    "ready_for_review": "Ready for Review", "under_inspection": "Under Inspection",
    "rejected": "Rejected", "closed": "Closed", "complete": "Complete",
}
CODE_PREFIX = {"defect": "DEF", "incomplete": "INC", "client": "CLD"}
CLOSED = {"closed", "complete"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def day_iso(offset: int = 0) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def default_settings() -> dict[str, Any]:
    subs = {
        "Apex Plastering": "Plastering", "AquaSeal Waterproofing": "Waterproofing",
        "Coastline Painting": "Painting", "Endeavour Cleaning": "Cleaning",
        "Northline Electrical": "Electrical", "Pacific Plumbing": "Hydraulic",
        "Premier Flooring": "Flooring", "Skyline Glazing": "Windows / Aluminium",
        "Sterling Tiling": "Tiling", "TrueLine Joinery": "Joinery",
    }
    profiles = {name: {"name": name, "trade": trade, "contact": "Site Contact",
                 "email": re.sub(r"[^a-z]+", "", name.lower()) + "@example.com",
                 "phone": "0400 000 000"} for name, trade in subs.items()}
    return {
        "projects": ["Jura Noosa", "Meta Street"],
        "projectConfigs": {
            "Jura Noosa": {"name": "Jura Noosa", "address": "Jura · Noosa Heads QLD",
                "buildings": ["Block A", "Block B"], "levels": ["L01", "L02", "L03"],
                "units": ["A-304", "A-305", "B-112", "B-204"],
                "rooms": ["Kitchen", "Living", "Bathroom", "Ensuite", "Bedroom 1", "Bedroom 2", "Laundry", "Balcony", "Hallway", "Garage"], "defaultDueDays": 7},
            "Meta Street": {"name": "Meta Street", "address": "Meta Street · Mooloolaba QLD",
                "buildings": ["Tower 1"], "levels": ["L01", "L02", "L05", "L08", "L10"],
                "units": ["T1-502", "T1-803", "T1-1004"],
                "rooms": ["Kitchen", "Living", "Bathroom", "Ensuite", "Bedroom 1", "Bedroom 2", "Laundry", "Balcony", "Hallway", "Garage"], "defaultDueDays": 7},
        },
        "subcontractors": sorted(subs), "subProfiles": profiles,
        "activeProject": "Jura Noosa", "company": "CleanRun Construction",
        "preparedBy": "Site Manager",
    }


def blank_item(item_id: str, code: str, kind: str, status: str, description: str,
               room: str, trade: str, sub: str, due: int, priority: str = "high",
               **overrides: Any) -> dict[str, Any]:
    created = (datetime.now(timezone.utc) - timedelta(days=overrides.pop("age", 1))).isoformat().replace("+00:00", "Z")
    item = {
        "id": item_id, "code": code, "type": kind, "project": "Jura Noosa",
        "building": "Block A", "level": "L03", "unit": "A-304", "room": room,
        "trade": trade, "subcontractor": sub, "priority": priority,
        "dueDate": day_iso(due), "description": description, "status": status,
        "createdAt": created, "updatedAt": created, "createdBy": "Site Manager",
        "originalPhotos": [f"seed://{overrides.pop('tone', 'amber')}/{overrides.pop('photo', description[:28])}"],
        "rectificationEvidence": [], "closeoutEvidence": [], "comments": [],
        "issueHistory": [], "inspectionHistory": [],
        "auditEvents": [{"at": created, "action": f"Created ({code})", "by": "Site Manager"}],
        "sync": "synced",
    }
    item.update(overrides)
    if status != "open" and not item.get("issueHistory"):
        item["issuedAt"] = created
        item["issueHistory"] = [{"at": created, "by": "Site Manager", "to": sub}]
    if status in {"in_progress", "ready_for_review", "under_inspection", "rejected"}:
        item["inProgressAt"] = created
    if status in {"ready_for_review", "under_inspection"} and not item.get("rectificationEvidence"):
        item["rectificationEvidence"] = [{
            "id": new_id(), "photo": "seed://green/Rectification photo",
            "comment": "Rectification complete.", "by": sub, "at": created,
        }]
        item["readyForReviewAt"] = created
    if status == "under_inspection":
        item["underInspectionAt"] = created
        item["inspectionHistory"] = [{"at": created, "by": "Site Manager", "action": "started"}]
    if status in CLOSED:
        item["closedAt"] = created
        item["closeoutEvidence"] = [{
            "id": new_id(), "photo": "seed://green/Closeout photo", "by": "Site Manager",
            "role": "Site Manager", "note": "Checked and accepted.",
            "confirmation": "I confirm the work is complete and acceptable.", "at": created,
        }]
    return item


def default_state() -> dict[str, Any]:
    items = [
        blank_item("demo-def-open-jura", "DEF-001", "defect", "open", "Cracked floor tile beside vanity unit. Chip on adjacent skirting tile.", "Bathroom", "Tiling", "Sterling Tiling", 2, building="Block B", level="L02", unit="B-204", originalPhotos=["seed://amber/Cracked tile", "seed://amber/Skirting chip"]),
        blank_item("demo-def-issued-jura", "DEF-002", "defect", "issued", "Active moisture behind shower wall — membrane suspected compromised.", "Ensuite", "Waterproofing", "AquaSeal Waterproofing", 1, "urgent", unit="A-305", tone="red", photo="Moisture stain"),
        blank_item("demo-def-inprogress-meta", "DEF-003", "defect", "in_progress", "Lippage on splashback tiles exceeds tolerance near rangehood.", "Kitchen", "Tiling", "Sterling Tiling", 4, project="Meta Street", building="Tower 1", level="L05", unit="T1-502", photo="Tile lippage"),
        blank_item("demo-def-ready-jura", "DEF-004", "defect", "ready_for_review", "Grout discolouration along bath hob, re-grout required.", "Bathroom", "Tiling", "Sterling Tiling", 1, photo="Grout staining"),
        blank_item("demo-def-inspection-meta", "DEF-005", "defect", "under_inspection", "Scratch on living room window glass, full pane replacement.", "Living", "Windows / Aluminium", "Skyline Glazing", 0, project="Meta Street", building="Tower 1", level="L08", unit="T1-803", photo="Scratched glass"),
        blank_item("demo-def-rejected-jura", "DEF-006", "defect", "rejected", "Hollow tiles to ensuite floor, multiple drummy areas.", "Ensuite", "Tiling", "Sterling Tiling", -1, "urgent", building="Block B", level="L01", unit="B-112", tone="red", photo="Drummy tiles", rejectionReason="Two tiles still drummy near drain. Re-fix and re-present."),
        blank_item("demo-def-closed-jura", "DEF-007", "defect", "closed", "Paint scuff and roller marks to kitchen feature wall.", "Kitchen", "Painting", "Coastline Painting", -2, photo="Roller marks"),
        blank_item("demo-inc-open-jura", "INC-001", "incomplete", "open", "Laundry overhead cabinet doors not yet hung. Hinges on site.", "Laundry", "Joinery", "TrueLine Joinery", 5, unit="A-305", tone="sky", photo="Missing doors"),
        blank_item("demo-inc-complete-meta", "INC-002", "incomplete", "complete", "Carpet edge trim to bedroom doorway not installed.", "Bedroom 1", "Flooring", "Premier Flooring", -3, project="Meta Street", building="Tower 1", level="L10", unit="T1-1004", originalPhotos=[]),
        blank_item("demo-inc-complete-jura", "INC-003", "incomplete", "complete", "Two GPO face plates pending in living area.", "Living", "Electrical", "Northline Electrical", -1, building="Block B", level="L02", unit="B-204", originalPhotos=[]),
        blank_item("demo-cld-ready-meta", "CLD-001", "client", "ready_for_review", "Superintendent flagged paint overspray on balcony glass balustrade.", "Balcony", "Cleaning", "Endeavour Cleaning", 1, project="Meta Street", building="Tower 1", level="L02", unit="T1-502", tone="violet", photo="Overspray", raisedBy="Superintendent"),
        blank_item("demo-cld-closed-meta", "CLD-002", "client", "closed", "Client PM raised slow-draining basin in main bathroom.", "Bathroom", "Hydraulic", "Pacific Plumbing", -4, "urgent", project="Meta Street", building="Tower 1", level="L05", unit="T1-502", tone="violet", photo="Slow drain", raisedBy="Client PM"),
        blank_item("demo-def-voice-jura", "DEF-008", "defect", "open", "Damaged tile beside vanity in Block B level two, unit B-204 bathroom.", "Bathroom", "Tiling", "Sterling Tiling", 4, building="Block B", level="L02", unit="B-204", photo="Damaged tile", voiceTranscript="Block B, level two, unit B-204 bathroom. Damaged tile beside vanity. Assign to Sterling Tiling. Medium priority. Due Friday."),
        blank_item("demo-def-issued-meta", "DEF-009", "defect", "issued", "Cornice crack to hallway ceiling, approx 600mm.", "Hallway", "Plastering", "Apex Plastering", 3, project="Meta Street", building="Tower 1", level="L01", unit="T1-502", photo="Cornice crack"),
    ]
    # Preserve the original seed's evidence distinctions and named events.
    by_code = {item["code"]: item for item in items}
    for code in ("INC-002", "INC-003"):
        by_code[code]["closeoutEvidence"] = []
        by_code[code]["auditEvents"].append({"at": now_iso(), "action": "Completed (no photo required)", "by": "Site Manager"})
    rejected = by_code["DEF-006"]
    rejected["rectificationEvidence"] = [{"id": new_id(), "photo": "seed://amber/Re-fixed tiles", "comment": "Re-fixed two tiles.", "by": "Sterling Tiling", "at": rejected["createdAt"]}]
    rejected["inspectionHistory"] = [{"at": rejected["createdAt"], "by": "Site Manager", "action": "started"}, {"at": rejected["createdAt"], "by": "Site Manager", "action": "rejected", "reason": rejected["rejectionReason"]}]
    by_code["DEF-007"]["rectificationEvidence"] = [{"id": new_id(), "photo": "seed://green/Repainted wall", "comment": "Cut in and rolled two coats. Wall consistent.", "by": "Coastline Painting", "at": by_code["DEF-007"]["createdAt"]}]
    by_code["CLD-002"]["rectificationEvidence"] = [{"id": new_id(), "photo": "seed://green/Cleared trap", "comment": "Cleared trap, re-tested flow. Draining freely.", "by": "Pacific Plumbing", "at": by_code["CLD-002"]["createdAt"]}]
    plan = {
        "id": "demo-plan-jura-a-l03", "project": "Jura Noosa", "building": "Block A",
        "level": "L03", "name": "Block A · Level 3 floor plan", "image": "seed-plan://jura-a-l03",
        "pins": [{"id": "pin-1", "x": .7, "y": .34, "itemId": "demo-def-ready-jura", "label": "DEF-004"}, {"id": "pin-2", "x": .32, "y": .46, "itemId": "demo-def-closed-jura", "label": "DEF-007"}, {"id": "pin-3", "x": .5, "y": .7, "itemId": "demo-inc-open-jura", "label": "INC-001"}],
        "createdAt": now_iso(),
    }
    return {"version": STATE_VERSION, "items": items, "settings": default_settings(), "plans": [plan]}


def save_state(state: dict[str, Any]) -> None:
    """Write atomically so interruption cannot corrupt the user's field data."""
    with LOCK:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="cleanrun-", suffix=".json", dir=DATA_FILE.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
            os.replace(name, DATA_FILE)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def load_state() -> dict[str, Any]:
    with LOCK:
        try:
            with DATA_FILE.open(encoding="utf-8") as stream:
                state = json.load(stream)
            if state.get("version") != STATE_VERSION or not all(key in state for key in ("items", "settings", "plans")):
                raise ValueError("incomplete state")
            return state
        except (OSError, ValueError, json.JSONDecodeError):
            state = default_state()
            save_state(state)
            return state


STATE = load_state()


def get_item(item_id: str) -> dict[str, Any]:
    for item in STATE["items"]:
        if item["id"] == item_id:
            return item
    raise KeyError("Item not found")


def audit(item: dict[str, Any], action: str, by: str | None = None, note: str | None = None) -> None:
    at = now_iso()
    event = {"at": at, "action": action}
    if by:
        event["by"] = by
    if note:
        event["note"] = note
    item.setdefault("auditEvents", []).append(event)
    item["updatedAt"] = at
    item["sync"] = "synced"


def next_code(kind: str) -> str:
    prefix = CODE_PREFIX[kind]
    nums = []
    for item in STATE["items"]:
        match = re.fullmatch(rf"{prefix}-(\d+)", item.get("code", ""))
        if match:
            nums.append(int(match.group(1)))
    return f"{prefix}-{max(nums, default=0) + 1:03d}"


ROOMS = ["kitchen", "living room", "living", "bathroom", "ensuite", "bedroom", "balcony", "laundry", "hallway", "corridor", "stairwell", "pantry"]
TRADE_HINTS = {
    "Painting": ["paint"], "Plastering": ["plaster", "render"],
    "Tiling": ["tile", "tiler", "tiling", "grout"],
    "Waterproofing": ["waterproof", "membrane", "leak", "seal"],
    "Joinery": ["joinery", "cabinet", "bench"], "Doors / Hardware": ["door", "hinge", "lock"],
    "Windows / Aluminium": ["window", "glaz", "glass", "aluminium", "aluminum"],
    "Flooring": ["floor", "carpet", "vinyl"], "Electrical": ["electric", "power point", "gpo", "light", "switch"],
    "Hydraulic": ["plumb", "hydraulic", "tap", "basin", "drain", "pipe"],
    "Mechanical": ["mechanical", "hvac", "air con", "aircon", "duct"],
    "Fire Services": ["fire", "sprinkler", "smoke"], "Cleaning": ["clean", "overspray"],
    "Concrete": ["concrete", "slab"], "Caulking / Sealant": ["caulk", "sealant", "silicone"],
}


def parse_transcript(transcript: str) -> dict[str, Any]:
    """Rule-for-rule Python equivalent of the original offline voice parser."""
    original, text = transcript.strip(), transcript.strip().lower()
    if not text:
        return {}
    result: dict[str, Any] = {"priority": "high", "description": original}
    client_words = ["client", "superintendent", "consultant", "architect", "buyer", "owner raised", "client raised"]
    incomplete_words = ["not finished", "unfinished", "incomplete", "missing", "not installed", "pending", "not yet", "outstanding work", "not complete", "yet to"]
    defect_words = ["damaged", "defective", "cracked", "crack", "scratched", "broken", "chipped", "leak", "stain", "drummy", "lippage", "faulty"]
    if any(word in text for word in client_words): result["type"] = "client"
    elif any(word in text for word in incomplete_words): result["type"] = "incomplete"
    elif any(word in text for word in defect_words): result["type"] = "defect"
    numbers = {"ground": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
               "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
               "eleven": 11, "twelve": 12}
    match = re.search(r"\b(block|tower|building)\s+([a-z0-9]+)", text)
    if match:
        value = numbers.get(match.group(2), match.group(2).upper())
        result["building"] = f"{match.group(1).title()} {value}"
    match = re.search(r"\b(?:level|floor|l)\s*([0-9]{1,2})", text)
    if match: result["level"] = f"L{int(match.group(1)):02d}"
    else:
        match = re.search(r"\b(?:level|floor)\s+(ground|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)", text)
        if match: result["level"] = f"L{numbers[match.group(1)]:02d}"
    match = re.search(r"\b(?:unit|apartment|apt|lot)\s+([a-z0-9-]+)", text)
    if match: result["unit"] = match.group(1).upper()
    for room in ROOMS:
        if room in text:
            bed = re.search(r"bedroom\s*([0-9])", text)
            result["room"] = f"Bedroom {bed.group(1)}" if room == "bedroom" and bed else room.title()
            break
    for trade, hints in TRADE_HINTS.items():
        if any(hint in text for hint in hints):
            result["trade"] = trade
            break
    for sub in STATE["settings"]["subcontractors"]:
        tokens = [token for token in sub.lower().split() if len(token) > 3]
        if sub.lower() in text or any(token in text for token in tokens):
            result["subcontractor"] = sub
            break
    if any(word in text for word in ["urgent", "critical", "immediate", "safety", "stop work", "asap", "emergency"]):
        result["priority"] = "urgent"
    if "today" in text: result["dueDate"] = day_iso()
    elif "tomorrow" in text: result["dueDate"] = day_iso(1)
    elif "end of week" in text or "eow" in text:
        result["dueDate"] = day_iso((4 - date.today().weekday()) % 7 or 7)
    else:
        match = re.search(r"\bin\s+([0-9]{1,2})\s+days?", text)
        if match: result["dueDate"] = day_iso(int(match.group(1)))
        else:
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for index, weekday in enumerate(weekdays):
                if weekday in text:
                    result["dueDate"] = day_iso((index - date.today().weekday()) % 7 or 7)
                    break
    if result.get("type") == "client":
        for needle, label in [("superintendent", "Superintendent"), ("consultant", "Consultant"), ("architect", "Architect"), ("buyer", "Buyer"), ("client", "Client PM")]:
            if needle in text:
                result["raisedBy"] = label
                break
    sentence = re.split(r"[.!?]", original, maxsplit=1)[0].strip()
    result["title"] = sentence if len(sentence) <= 60 else sentence[:57].rstrip() + "…"
    return result


def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    required = ("type", "project", "description", "dueDate")
    if any(not payload.get(field) for field in required):
        raise ValueError("type, project, description and dueDate are required")
    if payload["type"] not in CODE_PREFIX:
        raise ValueError("invalid item type")
    if payload["type"] in {"defect", "client"} and not payload.get("originalPhotos"):
        raise ValueError("defects and client defects require at least one original photo")
    at = now_iso()
    code = next_code(payload["type"])
    item = {
        "id": new_id(), "code": code, "status": payload.get("status", "open"),
        "createdAt": at, "updatedAt": at, "rectificationEvidence": [],
        "closeoutEvidence": [], "comments": [], "issueHistory": [],
        "inspectionHistory": [], "auditEvents": [], "sync": "synced",
        **payload,
    }
    item["auditEvents"] = [{"at": at, "action": f"Created ({code})" + (" via Voice-to-Note" if payload.get("voiceTranscript") else ""), "by": payload.get("createdBy")}]
    STATE["items"].insert(0, item)
    return item


def apply_action(item: dict[str, Any], action: str, body: dict[str, Any]) -> None:
    by = body.get("by") or STATE["settings"].get("preparedBy") or "Site Manager"
    at = now_iso()
    if action == "issue":
        target = body.get("to") or item.get("subcontractor")
        if not target or not item.get("trade"):
            raise ValueError("issuing requires a trade and subcontractor")
        reissue = bool(body.get("reissue"))
        item.update(status="issued", subcontractor=target)
        item.setdefault("issuedAt", at)
        item.setdefault("issueHistory", []).append({"at": at, "to": target, "by": by, "note": body.get("note"), "reissue": reissue})
        if not reissue: item.pop("rejectionReason", None)
        audit(item, f"{'Re-issued' if reissue else 'Issued'} to {target}", by, body.get("note"))
    elif action == "in-progress":
        item["status"] = "in_progress"; item.setdefault("inProgressAt", at); audit(item, "Marked in progress", by)
    elif action == "ready":
        item.update(status="ready_for_review", readyForReviewAt=at); audit(item, "Marked ready for review", by, body.get("note"))
    elif action == "inspect":
        item.update(status="under_inspection", underInspectionAt=at)
        item.setdefault("inspectionHistory", []).append({"at": at, "by": by, "action": "started"}); audit(item, "Inspection started", by)
    elif action == "reject":
        reason = str(body.get("reason", "")).strip()
        if not reason: raise ValueError("a rejection reason is required")
        item.update(status="rejected", rejectionReason=reason)
        item.setdefault("inspectionHistory", []).append({"at": at, "by": by, "action": "rejected", "reason": reason}); audit(item, "Rejected on inspection", by, reason)
    elif action == "rectification":
        if not body.get("photo") and not str(body.get("comment", "")).strip():
            raise ValueError("attach a photo or add a comment")
        item.setdefault("rectificationEvidence", []).append({"id": new_id(), "at": at, "photo": body.get("photo"), "comment": body.get("comment"), "by": by})
        if item["status"] == "issued": item.update(status="in_progress", inProgressAt=at)
        audit(item, "Rectification evidence added", by, body.get("comment"))
        if body.get("advanceToReady"):
            item.update(status="ready_for_review", readyForReviewAt=at); audit(item, "Marked ready for review", by)
    elif action == "close":
        if not body.get("confirmed"):
            raise ValueError("closeout confirmation is required")
        if item["type"] != "incomplete" and not body.get("photo"):
            raise ValueError("a closeout photo is required")
        item["status"] = "complete" if item["type"] == "incomplete" else "closed"
        item["closedAt"] = at
        if body.get("photo") or body.get("note"):
            item.setdefault("closeoutEvidence", []).append({"id": new_id(), "at": at, "photo": body.get("photo"), "by": by, "role": body.get("role", "Site Manager"), "note": body.get("note"), "confirmation": "I confirm the work is complete and acceptable." if body.get("confirmed") else None})
        if item.get("inspectionHistory") is not None and body.get("accepted", True):
            item["inspectionHistory"].append({"at": at, "by": by, "action": "accepted"})
        audit(item, "Closed with evidence" if item["type"] != "incomplete" else "Completed", by)
    elif action == "reopen":
        reason = str(body.get("reason", "")).strip()
        if not reason: raise ValueError("a reopen reason is required")
        item.update(status="in_progress", inProgressAt=at); item.pop("closedAt", None); audit(item, "Reopened", by, reason)
    elif action == "comment":
        text = str(body.get("text", "")).strip()
        if not text: raise ValueError("comment text is required")
        item.setdefault("comments", []).append({"id": new_id(), "at": at, "text": text, "by": by}); audit(item, "Comment added", by, text)
    else:
        raise ValueError("unknown action")


def is_overdue(item: dict[str, Any]) -> bool:
    return item.get("status") not in CLOSED and item.get("dueDate", "9999") < day_iso()


def report_items(kind: str) -> list[dict[str, Any]]:
    active = STATE["settings"]["activeProject"]
    items = [copy.deepcopy(item) for item in STATE["items"] if item.get("project") == active]
    if kind == "open": return [i for i in items if i["status"] not in CLOSED]
    if kind == "overdue": return [i for i in items if is_overdue(i)]
    if kind == "client": return [i for i in items if i["type"] == "client"]
    if kind == "incomplete": return [i for i in items if i["type"] == "incomplete"]
    if kind == "subcontractor": return sorted(items, key=lambda i: i.get("subcontractor", ""))
    if kind == "handover": return sorted(items, key=lambda i: (i["status"] not in CLOSED, i["updatedAt"]), reverse=False)
    raise ValueError("unknown report type")


def report_html(kind: str) -> str:
    titles = {"open": "Open Items", "overdue": "Overdue Items", "handover": "Closed / Handover Evidence", "subcontractor": "Subcontractor", "client": "Client Defects", "incomplete": "Incomplete Works"}
    items = report_items(kind); settings = STATE["settings"]
    def esc(value: Any) -> str: return html.escape(str(value or "—"))
    rows = []
    for item in items:
        evidence = f"Original {len(item.get('originalPhotos', []))} · Rectification {len(item.get('rectificationEvidence', []))} · Closeout {len(item.get('closeoutEvidence', []))}"
        location = " · ".join(filter(None, [item.get("building"), item.get("level"), item.get("unit"), item.get("room")]))
        rows.append(f"<article><header><b>{esc(item['code'])}</b><span class='status {esc(item['status'])}'>{esc(STATUS_LABEL.get(item['status'], item['status']))}</span></header><small>{esc(TYPE_LABEL[item['type']])} · {esc(location)} · {esc(item.get('trade'))} · {esc(item.get('subcontractor'))}</small><p>{esc(item['description'])}</p><footer>{esc(evidence)}<span class='due'>Due {esc(item['dueDate'])}</span></footer></article>")
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(titles[kind])}</title><style>*{{box-sizing:border-box}}body{{font:14px system-ui;color:#10213b;margin:32px;max-width:1000px}}.brand{{border-bottom:4px solid #10213b;padding-bottom:18px}}h1{{margin-bottom:4px}}.summary{{display:flex;gap:12px;margin:20px 0}}.stat{{background:#f1f4f8;padding:16px;border-radius:12px;flex:1;text-align:center}}article{{border:1px solid #dce3ec;border-radius:12px;padding:15px;margin:12px 0;break-inside:avoid}}article header,article footer{{display:flex;justify-content:space-between;gap:12px}}small{{color:#637086}}.status{{padding:4px 9px;background:#e9edf3;border-radius:999px}}.closed,.complete{{background:#dcfce7;color:#15803d}}.rejected{{background:#fee2e2;color:#b91c1c}}.due{{margin-left:auto}}@media print{{button{{display:none}}body{{margin:15mm}}}}</style></head><body><div class='brand'><strong>CLEANRUN IQ</strong><span style='float:right'>{esc(settings['company'])}</span></div><h1>{esc(titles[kind])} Report</h1><p>{esc(settings['activeProject'])} · Prepared by {esc(settings['preparedBy'])} · {datetime.now().strftime('%d %b %Y %H:%M')}</p><button onclick='print()'>Print / Save PDF</button><div class='summary'><div class='stat'><b>{len(items)}</b><br>Total</div><div class='stat'><b>{sum(i['status'] in CLOSED for i in items)}</b><br>Closed</div><div class='stat'><b>{sum(is_overdue(i) for i in items)}</b><br>Overdue</div><div class='stat'><b>{sum(i['type']=='client' for i in items)}</b><br>Client defects</div></div>{''.join(rows) or '<p>No items match this report.</p>'}<p><small>Generated with CleanRun IQ · Capture → Assign → Issue → Inspect → Close with Evidence → Report</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "CleanRunIQ/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def send_json(self, value: Any, status: int = 200) -> None:
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length > 20_000_000: raise ValueError("request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in {"/", "/index.html"}:
                self.send_bytes(INDEX_FILE.read_bytes(), "text/html; charset=utf-8")
            elif path in {"/assets/banner.png", "/assets/icon-mark.png"}:
                self.send_bytes((ROOT / path.lstrip("/")).read_bytes(), "image/png")
            elif path == "/api/state": self.send_json(STATE)
            elif path.startswith("/api/items/"): self.send_json(get_item(unquote(path.split("/")[-1])))
            elif path.startswith("/api/reports/"):
                self.send_bytes(report_html(path.split("/")[-1]).encode(), "text/html; charset=utf-8")
            elif path == "/api/health": self.send_json({"ok": True})
            else: self.send_json({"error": "Not found"}, 404)
        except (KeyError, ValueError) as exc: self.send_json({"error": str(exc)}, 404)
        except Exception as exc: self.send_json({"error": f"Server error: {exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self.body()
            with LOCK:
                if path == "/api/items": result = create_item(body)
                elif path == "/api/parse": result = parse_transcript(str(body.get("transcript", "")))
                elif path == "/api/reset":
                    global STATE
                    STATE = default_state(); result = STATE
                elif path == "/api/settings":
                    allowed = {"company", "preparedBy", "activeProject", "projects", "projectConfigs", "subcontractors", "subProfiles"}
                    STATE["settings"].update({k: v for k, v in body.items() if k in allowed}); result = STATE["settings"]
                elif path == "/api/plans":
                    result = {"id": new_id(), "pins": [], "createdAt": now_iso(), **body}; STATE["plans"].insert(0, result)
                elif re.fullmatch(r"/api/plans/[^/]+/pins", path):
                    plan_id = path.split("/")[3]; plan = next(p for p in STATE["plans"] if p["id"] == plan_id)
                    result = {"id": new_id(), **body}; plan["pins"].append(result)
                elif re.fullmatch(r"/api/items/[^/]+/actions/[^/]+", path):
                    parts = path.split("/"); result = get_item(unquote(parts[3])); apply_action(result, parts[5], body)
                else: self.send_json({"error": "Not found"}, 404); return
                save_state(STATE)
            self.send_json(result, 201 if path in {"/api/items", "/api/plans"} else 200)
        except StopIteration: self.send_json({"error": "Plan not found"}, 404)
        except (KeyError, ValueError, json.JSONDecodeError) as exc: self.send_json({"error": str(exc)}, 400)
        except Exception as exc: self.send_json({"error": f"Server error: {exc}"}, 500)

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self.body()
            with LOCK:
                match = re.fullmatch(r"/api/items/([^/]+)", path)
                pin_match = re.fullmatch(r"/api/plans/([^/]+)/pins/([^/]+)", path)
                if match:
                    result = get_item(unquote(match.group(1)))
                    allowed = {"type", "project", "building", "level", "unit", "room", "trade", "subcontractor", "priority", "dueDate", "description", "raisedBy"}
                    result.update({k: v for k, v in body.items() if k in allowed}); audit(result, "Item details edited", body.get("by"))
                elif pin_match:
                    plan = next(p for p in STATE["plans"] if p["id"] == pin_match.group(1)); result = next(p for p in plan["pins"] if p["id"] == pin_match.group(2)); result.update(body)
                else: self.send_json({"error": "Not found"}, 404); return
                save_state(STATE)
            self.send_json(result)
        except (KeyError, ValueError, StopIteration) as exc: self.send_json({"error": str(exc) or "Not found"}, 404)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            with LOCK:
                plan_match = re.fullmatch(r"/api/plans/([^/]+)", path)
                pin_match = re.fullmatch(r"/api/plans/([^/]+)/pins/([^/]+)", path)
                if pin_match:
                    plan = next(p for p in STATE["plans"] if p["id"] == pin_match.group(1)); plan["pins"] = [p for p in plan["pins"] if p["id"] != pin_match.group(2)]
                elif plan_match: STATE["plans"] = [p for p in STATE["plans"] if p["id"] != plan_match.group(1)]
                else: self.send_json({"error": "Not found"}, 404); return
                save_state(STATE)
            self.send_json({"ok": True})
        except StopIteration: self.send_json({"error": "Not found"}, 404)


def main() -> None:
    if not INDEX_FILE.exists(): raise SystemExit(f"Missing frontend: {INDEX_FILE}")
    # Render injects PORT and requires the service to listen on all interfaces.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{port}"
    print(f"CleanRun IQ running at {url} (Ctrl+C to stop)")
    if os.environ.get("CLEANRUN_OPEN_BROWSER") == "1": threading.Timer(.5, webbrowser.open, args=(url,)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")
    finally: server.server_close()


if __name__ == "__main__":
    main()
