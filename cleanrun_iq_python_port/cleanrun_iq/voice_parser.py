"""Offline deterministic voice-to-fields parser translated from Rork `voiceParser.ts`."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import TypedDict

from cleanrun_iq.models import ItemType, Priority, TRADES
from cleanrun_iq.utils import add_days, today_iso


class ParsedFields(TypedDict, total=False):
    """Structured fields inferred from a spoken site note."""

    type: ItemType
    building: str
    level: str
    unit: str
    room: str
    title: str
    description: str
    trade: str
    subcontractor: str
    priority: Priority
    dueDate: str
    raisedBy: str


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "ground": 0,
}

ROOM_KEYWORDS = ["bathroom", "ensuite", "kitchen", "living", "laundry", "balcony", "hallway", "garage", "bedroom", "lobby", "lounge", "dining", "toilet", "wc", "pantry", "stairwell", "corridor"]
TRADE_HINTS = [
    (["paint"], "Painting"),
    (["plaster", "render"], "Plastering"),
    (["tile", "tiler", "tiling", "grout"], "Tiling"),
    (["waterproof", "membrane", "leak", "seal"], "Waterproofing"),
    (["joinery", "cabinet", "cabinetry", "bench"], "Joinery"),
    (["door", "hardware", "hinge", "lock"], "Doors / Hardware"),
    (["window", "glaz", "glass", "aluminium", "aluminum"], "Windows / Aluminium"),
    (["floor", "carpet", "timber floor", "vinyl"], "Flooring"),
    (["roof", "gutter"], "Roofing"),
    (["clad", "facade"], "Cladding"),
    (["electric", "power point", "gpo", "light", "switch"], "Electrical"),
    (["plumb", "hydraulic", "tap", "basin", "drain", "pipe"], "Hydraulic"),
    (["mechanical", "hvac", "air con", "aircon", "duct"], "Mechanical"),
    (["fire", "sprinkler", "smoke"], "Fire Services"),
    (["clean", "overspray"], "Cleaning"),
    (["landscap", "garden", "turf"], "Landscaping"),
    (["concrete", "slab"], "Concrete"),
    (["caulk", "sealant", "silicone"], "Caulking / Sealant"),
]
URGENT_WORDS = ["urgent", "critical", "immediate", "immediately", "safety", "stop work", "stop-work", "asap", "emergency"]
CLIENT_WORDS = ["client", "superintendent", "consultant", "architect", "buyer", "owner raised", "client raised", "client-side"]
INCOMPLETE_WORDS = ["not finished", "unfinished", "incomplete", "missing", "not installed", "pending", "not yet", "outstanding work", "not complete", "yet to"]
DEFECT_WORDS = ["damaged", "defective", "cracked", "crack", "scratched", "scratch", "broken", "chipped", "leak", "stain", "drummy", "lippage", "faulty"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_transcript(transcript: str, subcontractors: list[str] | None = None) -> ParsedFields:
    """Parse a spoken defect note into structured fields.

    Args:
        transcript: Spoken note transcript.
        subcontractors: Known subcontractor names for matching.

    Returns:
        Parsed field dictionary.
    """
    original = transcript.strip()
    if not original:
        return {}
    text = original.lower()
    fields: ParsedFields = {"description": original, "title": _first_sentence(original)}

    item_type = _detect_type(text)
    if item_type:
        fields["type"] = item_type
    building = _detect_building(text)
    if building:
        fields["building"] = building
    level = _detect_level(text)
    if level:
        fields["level"] = level
    unit = _detect_unit(text, original)
    if unit:
        fields["unit"] = unit
    room = _detect_room(text, original)
    if room:
        fields["room"] = room
    trade = _detect_trade(text)
    if trade:
        fields["trade"] = trade
    subcontractor = _match_from_list(text, subcontractors or [])
    if subcontractor:
        fields["subcontractor"] = subcontractor
    due_date = _detect_due_date(text)
    if due_date:
        fields["dueDate"] = due_date
    fields["priority"] = Priority.URGENT if any(word in text for word in URGENT_WORDS) else Priority.HIGH
    raised_by = _find_raised_by(text)
    if raised_by:
        fields["raisedBy"] = raised_by
    return fields


def _detect_type(text: str) -> ItemType | None:
    if any(word in text for word in CLIENT_WORDS):
        return ItemType.CLIENT
    if any(word in text for word in INCOMPLETE_WORDS):
        return ItemType.INCOMPLETE
    if any(word in text for word in DEFECT_WORDS):
        return ItemType.DEFECT
    return None


def _detect_building(text: str) -> str | None:
    block = re.search(r"\bblock\s+([a-z0-9]+)", text)
    if block:
        return f"Block {block.group(1).upper()}"
    tower = re.search(r"\btower\s+([a-z0-9]+)", text)
    if tower:
        return f"Tower {tower.group(1).upper()}"
    building = re.search(r"\bbuilding\s+([a-z0-9]+)", text)
    if building:
        value = building.group(1)
        return f"Building {NUMBER_WORDS.get(value, value.upper())}"
    return None


def _detect_level(text: str) -> str | None:
    match = re.search(r"\b(?:level|floor|l)\s*([0-9]{1,2})", text)
    if match:
        return f"L{int(match.group(1)):02d}"
    word = re.search(r"\b(?:level|floor)\s+(ground|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)", text)
    if word and word.group(1) in NUMBER_WORDS:
        return f"L{NUMBER_WORDS[word.group(1)]:02d}"
    return None


def _detect_unit(text: str, original: str) -> str | None:
    unit = re.search(r"\b(?:unit|apartment|apt|lot)\s+([a-z0-9-]+)", text)
    if unit:
        original_match = re.search(r"(?:unit|apartment|apt|lot)\s+([A-Za-z0-9-]+)", original, flags=re.I)
        return (original_match.group(1) if original_match else unit.group(1)).upper()
    dashed = re.search(r"\b([A-Za-z]{1,3}-?\d{2,4})\b", original)
    if dashed and "-" in dashed.group(1):
        return dashed.group(1).upper()
    return None


def _detect_room(text: str, original: str) -> str | None:
    for keyword in ROOM_KEYWORDS:
        if keyword in text:
            bedroom = re.search(r"bedroom\s*([0-9])", text)
            if keyword == "bedroom" and bedroom:
                return f"Bedroom {bedroom.group(1)}"
            phrase = re.search(rf"(master\s+)?{keyword}", original, flags=re.I)
            value = phrase.group(0) if phrase else keyword
            return value.lower().title()
    return None


def _detect_trade(text: str) -> str | None:
    for matches, trade in TRADE_HINTS:
        if any(match in text for match in matches):
            return trade
    return None


def _detect_due_date(text: str) -> str | None:
    if "today" in text:
        return today_iso()
    if "tomorrow" in text:
        return add_days(1)
    if "end of week" in text or "eow" in text:
        today = date.today()
        friday = 4
        diff = (friday - today.weekday()) % 7 or 5
        return (today + timedelta(days=diff)).isoformat()
    in_days = re.search(r"\bin\s+([0-9]{1,2})\s+days?", text)
    if in_days:
        return add_days(int(in_days.group(1)))
    for idx, weekday in enumerate(WEEKDAYS):
        if f"by {weekday}" in text or f"due {weekday}" in text or weekday in text:
            today = date.today()
            diff = (idx - today.weekday()) % 7 or 7
            return (today + timedelta(days=diff)).isoformat()
    return None


def _match_from_list(text: str, values: list[str]) -> str | None:
    lower_values = [(value, value.lower()) for value in values]
    for raw, lower in lower_values:
        if lower in text:
            return raw
    for raw, lower in lower_values:
        tokens = [token for token in re.split(r"\s+", lower) if len(token) > 3]
        if any(token in text for token in tokens):
            return raw
    return None


def _find_raised_by(text: str) -> str | None:
    if "superintendent" in text:
        return "Superintendent"
    if "consultant" in text:
        return "Consultant"
    if "architect" in text:
        return "Architect"
    if "buyer" in text:
        return "Buyer"
    if "client pm" in text or "client p m" in text or "client" in text:
        return "Client PM"
    return None


def _first_sentence(original: str) -> str:
    match = re.search(r"[^.!?]+", original.strip())
    candidate = (match.group(0) if match else original).strip()
    return f"{candidate[:57].strip()}…" if len(candidate) > 60 else candidate
