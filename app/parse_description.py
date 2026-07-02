"""Clean capture descriptions from voice/typed notes after field extraction."""

from __future__ import annotations

import json
import logging
import os
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


def clean_parsed_description(
    transcript: str,
    mapped_fields: dict[str, Any],
    *,
    timeout: float | None = None,
) -> str:
    """Return a cleaned defect description, or the full transcript on failure."""
    note = (transcript or "").strip()
    if not note:
        return note

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return note

    timeout_seconds = timeout if timeout is not None else float(
        os.getenv("OPENAI_PARSE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    mapped = {
        key: value
        for key, value in mapped_fields.items()
        if key not in {"description", "project", "raw_transcript"} and value
    }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=timeout_seconds)
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
        return cleaned or note
    except Exception:
        logger.warning("Description clean failed; using full note", exc_info=True)
        return note
