from __future__ import annotations

from app.models import Item, Settings
from app.reporting import build_report_html, filter_items


def build_report(items: list[Item], settings: Settings, report_type: str, *, subcontractor: str | None = None) -> str:
    return build_report_html(items, settings, report_type=report_type, subcontractor=subcontractor)


def report_items(items: list[Item], report_type: str, *, subcontractor: str | None = None) -> list[Item]:
    return filter_items(items, report_type, subcontractor=subcontractor)
