"""Utility functions equivalent to the Rork `lib/format.ts` module."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
from uuid import uuid4

from cleanrun_iq.models import CODE_PREFIX, ESCALATION_DAYS, STATUS_LABEL, TYPE_LABEL, Item, ItemStatus, ItemType


def make_id() -> str:
    """Create a random unique identifier.

    Returns:
        A UUID4 string.
    """
    return str(uuid4())


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format.

    Returns:
        Current timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    """Return today's date as YYYY-MM-DD.

    Returns:
        Current local date in ISO format.
    """
    return date.today().isoformat()


def add_days(days: int) -> str:
    """Return a date offset from today.

    Args:
        days: Number of days to add.

    Returns:
        Date in YYYY-MM-DD format.
    """
    return (date.today() + timedelta(days=days)).isoformat()


def next_code(items: list[Item], item_type: ItemType) -> str:
    """Generate the next item code for an item type.

    Args:
        items: Existing items.
        item_type: Item type.

    Returns:
        A code such as DEF-001.
    """
    prefix = CODE_PREFIX[item_type]
    max_num = 0
    for item in items:
        if item.code.startswith(f"{prefix}-"):
            try:
                max_num = max(max_num, int(item.code[len(prefix) + 1 :]))
            except ValueError:
                continue
    return f"{prefix}-{max_num + 1:03d}"


def item_type_label(item_type: ItemType) -> str:
    """Map item type to display label."""
    return TYPE_LABEL.get(item_type, "Item")


def status_label(status: ItemStatus) -> str:
    """Map item status to display label."""
    return STATUS_LABEL.get(status, str(status))


def format_location(item: Item) -> str:
    """Format an item location.

    Args:
        item: Item instance.

    Returns:
        Human-friendly location string.
    """
    parts = [item.building, item.level, item.unit, item.room]
    clean = [part for part in parts if part]
    return " · ".join(clean) if clean else "Location not set"


def is_overdue(item: Item) -> bool:
    """Check whether an item is overdue.

    Args:
        item: Item instance.

    Returns:
        True when the due date is before today and item is not closed/complete.
    """
    if item.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}:
        return False
    return item.due_date < today_iso()


def is_due_soon(item: Item) -> bool:
    """Check whether item is due soon.

    Args:
        item: Item instance.

    Returns:
        True if due within the escalation window and not overdue/closed.
    """
    if item.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE} or is_overdue(item):
        return False
    try:
        due_date = date.fromisoformat(item.due_date)
    except ValueError:
        return False
    return 0 <= (due_date - date.today()).days <= ESCALATION_DAYS


def format_date(iso_value: str) -> str:
    """Format ISO date or timestamp for display.

    Args:
        iso_value: ISO date/timestamp string.

    Returns:
        Formatted date string, or original value if parsing fails.
    """
    try:
        parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(iso_value)
            return parsed_date.strftime("%-d %b %Y")
        except ValueError:
            return iso_value
    return parsed.strftime("%-d %b %Y")


def html_escape(value: str | None) -> str:
    """Safely escape HTML.

    Args:
        value: Optional string.

    Returns:
        Escaped string.
    """
    return escape(value or "")
