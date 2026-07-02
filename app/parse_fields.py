"""Rule-based field extraction helpers for /api/parse."""

from __future__ import annotations

import re

TRADE_HINTS: list[tuple[list[str], str]] = [
    (["paint", "painter"], "Painting"),
    (["plaster"], "Plastering"),
    (["tile", "tiler", "tiling", "grout"], "Tiling"),
    (["waterproof", "membrane"], "Waterproofing"),
    (["joinery", "cabinet", "carpenter", "carpentry"], "Joinery"),
    (["door", "hardware", "hinge"], "Doors / Hardware"),
    (["window", "glaz", "glass", "aluminium", "aluminum"], "Windows / Aluminium"),
    (["floor", "carpet", "vinyl"], "Flooring"),
    (["roof", "gutter"], "Roofing"),
    (["clad", "facade"], "Cladding"),
    (["electric", "gpo", "lighting"], "Electrical"),
    (["plumb", "hydraulic", "tap", "basin", "drain", "pipe"], "Hydraulic"),
    (["mechanical", "hvac", "air con", "aircon"], "Mechanical"),
    (["fire", "sprinkler"], "Fire Services"),
    (["clean", "overspray"], "Cleaning"),
    (["landscap", "garden"], "Landscaping"),
    (["concrete", "slab"], "Concrete"),
    (["render"], "Render"),
    (["caulk", "sealant", "silicone"], "Caulking / Sealant"),
]


def match_config_value(text: str, values: list[str]) -> str | None:
    lowered = text.lower()
    for value in values:
        if value and value.lower() in lowered:
            return value
    return None


def match_level(text: str, values: list[str]) -> str | None:
    hit = match_config_value(text, values)
    if hit:
        return hit
    match = re.search(r"\b(?:level|floor|l)\s*(\d{1,2})\b", text, flags=re.I)
    if not match:
        return None
    num = int(match.group(1))
    by_lower = {value.lower(): value for value in values}
    for candidate in (f"L{num:02d}", f"L{num}", f"Level {num}"):
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    for value in values:
        if re.search(rf"(?<!\d){num}(?!\d)", value):
            return value
    return None


def match_unit(text: str, values: list[str]) -> str | None:
    hit = match_config_value(text, values)
    if hit:
        return hit
    match = re.search(r"\b(?:unit|apartment|apt|lot)\s+([\w-]+)\b", text, flags=re.I)
    if not match:
        return None
    token = re.sub(r"[^a-z0-9]", "", match.group(1).lower())
    for value in values:
        normalized = re.sub(r"[^a-z0-9]", "", value.lower())
        if token and (token == normalized or token in normalized or normalized.endswith(token)):
            return value
    return None


def match_room(text: str, values: list[str]) -> str | None:
    preamble = text.split(",")[0]
    hit = match_config_value(preamble, values)
    if hit:
        return hit
    match = re.search(
        r"\b(bedroom\s*\d+|kitchen|bathroom|ensuite|balcony|living(?:\s+room)?|laundry|garage|hallway|stairwell|corridor|wc|toilet|pantry)\b",
        preamble,
        flags=re.I,
    )
    if not match:
        return None
    phrase = match.group(1)
    by_lower = {value.lower(): value for value in values}
    if phrase.lower() in by_lower:
        return by_lower[phrase.lower()]
    bedroom = re.search(r"bedroom\s*(\d+)", phrase, flags=re.I)
    if bedroom:
        candidate = f"Bedroom {bedroom.group(1)}"
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    titled = phrase.strip().title()
    if titled.lower() in by_lower:
        return by_lower[titled.lower()]
    return None


def match_trade(text: str, trades: list[str]) -> str | None:
    hit = match_config_value(text, trades)
    if hit:
        return hit
    lowered = text.lower()
    trade_set = set(trades)
    for keywords, trade in TRADE_HINTS:
        if trade in trade_set and any(keyword in lowered for keyword in keywords):
            return trade
    return None
