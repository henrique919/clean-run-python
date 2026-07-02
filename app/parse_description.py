"""Clean capture descriptions from voice/typed notes after field extraction."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 8.0

DESCRIPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "description": {
            "type": "string",
            "description": "Defect statement only: what is wrong and what action is required.",
        }
    },
    "required": ["description"],
}

SYSTEM_PROMPT = """You rewrite Australian construction site notes into a short defect description for CleanRun IQ.

You receive the full note and fields already mapped from it. Write description containing ONLY the defect statement — what is wrong and what action is required.

Rules:
- Remove location phrases that were successfully mapped to building, level, unit, or room fields (including synonyms and variants).
- Remove trade names and subcontractor/assignee references that were successfully mapped to trade or subcontractor fields.
- KEEP location words that are part of the defect itself (e.g. "crack above the bathroom door" keeps "above the bathroom door").
- Tidy grammar lightly; do not change meaning or invent details.
- Use an em dash before a short action clause when natural (e.g. "Door frame cracked near the hinge — replace.").
- If the note is already only a defect statement, return it essentially unchanged (minor grammar only).

Return JSON with a single description field."""

_ASSIGNEE_TAIL_RE = re.compile(
    r"\b(?:carpenter|carpentry|tiler|painter|plumber|electrician|renderer|joiner|trade)\s+to\s+(.+)$",
    flags=re.I,
)
_ACTION_TAIL_RE = re.compile(
    r"^(?:to\s+)?(replace|repair|fix|regrout|rectify|make good|make-good|reinstall|re-seal|reseal)\b.*$",
    flags=re.I,
)
_LOCATION_PREAMBLE_RE = re.compile(
    r"\b(?:building|block|tower|level|floor|l\d|unit|apartment|apt|lot|bedroom\s*\d+)\b",
    flags=re.I,
)


def _looks_like_location_preamble(segment: str, mapped_fields: dict[str, Any]) -> bool:
    if _LOCATION_PREAMBLE_RE.search(segment):
        return True
    return bool(mapped_fields.get("level") or mapped_fields.get("unit") or mapped_fields.get("room")) and len(segment.split()) <= 8


def _finish_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" ,;.-")
    if not cleaned:
        return cleaned
    cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _strip_mapped_values(text: str, mapped_fields: dict[str, Any]) -> str:
    cleaned = text
    mapped_values = [
        str(mapped_fields[key]).strip()
        for key in ("building", "level", "unit", "room", "trade", "subcontractor")
        if mapped_fields.get(key)
    ]
    for value in sorted(mapped_values, key=len, reverse=True):
        cleaned = re.sub(re.escape(value), "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:level|floor|l)\s*\d{1,2}\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:unit|apartment|apt|lot)\s+[\w-]+\b", "", cleaned, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip(" ,;.-")


def _extract_action_tail(segment: str) -> str:
    assignee = _ASSIGNEE_TAIL_RE.search(segment)
    if assignee:
        return assignee.group(1).strip()
    action = _ACTION_TAIL_RE.match(segment.strip())
    if action:
        return action.group(1).strip()
    to_clause = re.search(r"\bto\s+(.+)$", segment, flags=re.I)
    return to_clause.group(1).strip() if to_clause else segment.strip()


def _is_assignee_tail(segment: str) -> bool:
    lower = segment.lower().strip()
    return bool(_ASSIGNEE_TAIL_RE.search(segment) or _ACTION_TAIL_RE.match(lower))


def rule_based_clean_description(transcript: str, mapped_fields: dict[str, Any]) -> str:
    """Strip mapped location/trade/assignee phrases without an LLM."""
    text = (transcript or "").strip()
    if not text:
        return text

    parts = [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    if not parts:
        return _finish_sentence(text)

    if len(parts) == 1:
        cleaned = _strip_mapped_values(parts[0], mapped_fields)
        return _finish_sentence(cleaned) or _finish_sentence(text)

    if len(parts) == 2 and not _looks_like_location_preamble(parts[0], mapped_fields):
        defect = _strip_mapped_values(parts[0], mapped_fields)
        action = parts[1].strip()
        if action and len(action.split()) <= 4:
            action_text = action[0].upper() + action[1:]
            return _finish_sentence(f"{defect.rstrip('.')} — {action_text}")

    action: str | None = None
    body_parts = parts[1:]
    if body_parts and _is_assignee_tail(body_parts[-1]):
        action = _extract_action_tail(body_parts.pop())

    if body_parts:
        defect = body_parts[0] if len(body_parts) == 1 else ". ".join(body_parts)
    else:
        defect = ""

    defect = _strip_mapped_values(defect, mapped_fields)
    if action:
        action_text = action[0].upper() + action[1:] if action else action
        defect = f"{defect.rstrip('.')} — {action_text}"

    finished = _finish_sentence(defect)
    return finished or _finish_sentence(text)


def _llm_clean_description(
    note: str,
    mapped_fields: dict[str, Any],
    *,
    timeout: float,
) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    mapped = {
        key: value
        for key, value in mapped_fields.items()
        if key not in {"description", "project", "raw_transcript"} and value
    }

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout)
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_PARSE_MODEL", "gpt-4o-mini"),
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"transcript": note, "mapped_fields": mapped}),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "cleanrun_description",
                "strict": True,
                "schema": DESCRIPTION_SCHEMA,
            },
        },
    )
    payload = json.loads(completion.choices[0].message.content or "{}")
    cleaned = str(payload.get("description", "")).strip()
    return cleaned or None


def clean_parsed_description(
    transcript: str,
    mapped_fields: dict[str, Any],
    *,
    timeout: float | None = None,
) -> str:
    """Return a cleaned defect description; rule-based always, LLM when configured."""
    note = (transcript or "").strip()
    if not note:
        return note

    rule_cleaned = rule_based_clean_description(note, mapped_fields)
    fallback = rule_cleaned or note

    if not os.getenv("OPENAI_API_KEY"):
        return fallback

    timeout_seconds = timeout if timeout is not None else float(
        os.getenv("OPENAI_PARSE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    try:
        llm_cleaned = _llm_clean_description(note, mapped_fields, timeout=timeout_seconds)
        return llm_cleaned or fallback
    except Exception:
        logger.warning("Description clean failed; using rule-based note", exc_info=True)
        return fallback
