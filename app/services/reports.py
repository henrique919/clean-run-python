from __future__ import annotations

from app.models import Item, Settings
from app.reporting import build_report_html, filter_items


def build_report(items: list[Item], settings: Settings, report_type: str) -> str:
    return build_report_html(items, settings, report_type=report_type)


def report_items(items: list[Item], report_type: str) -> list[Item]:
    return filter_items(items, report_type)
