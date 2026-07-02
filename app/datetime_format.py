from __future__ import annotations

import re
from datetime import datetime

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def format_field_date(value: str | datetime | None) -> str:
    """Format timestamps for field UI and reports: ``1 Jul 2026, 8:04am``."""
    if not value:
        return ""
    date_only = False
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        date_only = bool(_DATE_ONLY.fullmatch(text))
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if date_only:
        return f"{parsed.day} {_MONTHS[parsed.month - 1]} {parsed.year}"
    hour = parsed.hour % 12 or 12
    minute = parsed.minute
    suffix = "am" if parsed.hour < 12 else "pm"
    return f"{parsed.day} {_MONTHS[parsed.month - 1]} {parsed.year}, {hour}:{minute:02d}{suffix}"
