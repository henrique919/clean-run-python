"""HTML report builder translated from Rork `reportBuilder.ts`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from operator import attrgetter

from cleanrun_iq.models import Item, ItemStatus, ItemType, Settings
from cleanrun_iq.utils import format_date, format_location, html_escape, is_overdue, item_type_label, status_label

ReportType = str


@dataclass(frozen=True, slots=True)
class ReportMeta:
    """Report metadata."""

    title: str
    description: str


REPORT_META: dict[ReportType, ReportMeta] = {
    "handover": ReportMeta("Closed / Handover Evidence", "Closed-out items with original, rectification and closeout evidence."),
    "open": ReportMeta("Open Items", "Current open items requiring action."),
    "client": ReportMeta("Client Defects", "Items raised by client-side parties."),
    "incomplete": ReportMeta("Incomplete Works", "Incomplete work items by trade and location."),
}


def filter_items(items: list[Item], report_type: ReportType) -> list[Item]:
    """Filter items for a report.

    Args:
        items: Items to filter.
        report_type: Report type.

    Returns:
        Filtered item list.

    Raises:
        ValueError: If report type is unsupported.
    """
    if report_type == "handover":
        return [item for item in items if item.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE} or item.status == ItemStatus.REJECTED or is_overdue(item)]
    if report_type == "open":
        return [item for item in items if item.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    if report_type == "client":
        return [item for item in items if item.type == ItemType.CLIENT]
    if report_type == "incomplete":
        return [item for item in items if item.type == ItemType.INCOMPLETE]
    raise ValueError(f"Unsupported report type: {report_type}")


def group_by_location(items: list[Item]) -> list[tuple[str, list[Item]]]:
    """Group items by building and level."""
    sorted_items = sorted(items, key=lambda item: f"{item.building or 'Unassigned'} · {item.level or '—'}")
    return [(key, list(group)) for key, group in groupby(sorted_items, key=lambda item: f"{item.building or 'Unassigned'} · {item.level or '—'}")]


def build_report_html(items: list[Item], report_type: ReportType, settings: Settings, banner_data_uri: str = "") -> str:
    """Build a print-ready HTML report.

    Args:
        items: Items to report.
        report_type: Report type.
        settings: App settings.
        banner_data_uri: Optional logo data URI.

    Returns:
        HTML string.
    """
    meta = REPORT_META[report_type]
    evidence_items = [item for item in items if item.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}] if report_type == "handover" else items
    outstanding = [item for item in items if item.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}] if report_type == "handover" else []
    groups = group_by_location(evidence_items)
    now = datetime.now().strftime("%d %b %Y %H:%M")
    summary = _summary_html(items)
    group_html = "".join(_group_html(key, grouped) for key, grouped in groups) or '<div class="none">No items match this report.</div>'
    outstanding_html = _outstanding_html(outstanding) if outstanding else ""
    logo_html = f'<img src="{banner_data_uri}" alt="CleanRun IQ" style="max-width:160px;"/>' if banner_data_uri else "<strong>CleanRun IQ</strong>"
    return f"""<!doctype html><html><head><meta charset="utf-8"/><style>{_css()}</style></head><body>
<div class="header"><div>{logo_html}</div><div class="meta"><strong>{html_escape(settings.company)}</strong><br/>Generated {now}<br/>Prepared by {html_escape(settings.prepared_by)}</div></div>
<h1>{html_escape(meta.title)} Report</h1><div class="subtitle">{html_escape(settings.active_project)} · {html_escape(meta.description)}</div>{summary}{group_html}{outstanding_html}
<div class="footer">Generated with CleanRun IQ · Capture → Assign → Issue → Inspect → Close with Evidence → Report</div></body></html>"""


def _summary_html(items: list[Item]) -> str:
    return f"""<div class="summary"><div class="stat"><div class="num">{len(items)}</div><div class="lbl">Total items</div></div><div class="stat"><div class="num">{sum(1 for item in items if item.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE})}</div><div class="lbl">Closed</div></div><div class="stat"><div class="num">{sum(1 for item in items if is_overdue(item))}</div><div class="lbl">Overdue</div></div><div class="stat"><div class="num">{sum(1 for item in items if item.type == ItemType.CLIENT)}</div><div class="lbl">Client defects</div></div></div>"""


def _group_html(key: str, items: list[Item]) -> str:
    rows = "".join(_item_html(item) for item in items)
    return f'<div class="group"><h2>{html_escape(key)}</h2>{rows}</div>'


def _item_html(item: Item) -> str:
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    return f"""<div class="item"><div class="item-head"><div><span class="code">{html_escape(item.code)}</span><span class="type">{html_escape(item_type_label(item.type))}</span></div><span class="status status-{item.status}">{html_escape(status_label(item.status))}</span></div><div class="loc">{html_escape(format_location(item))} · {html_escape(item.trade or '—')} · {html_escape(item.subcontractor or 'Unassigned')}</div><div class="desc">{html_escape(item.description)}</div><div class="evidence-cols"><div class="col"><div class="col-title">Original issue</div>{''.join(_photo_cell(photo) for photo in item.original_photos) or '<div class="none">No photos</div>'}</div><div class="col"><div class="col-title">Rectification</div>{''.join(_photo_cell(e.photo, e.comment, e.by) for e in item.rectification_evidence) or '<div class="none">—</div>'}</div><div class="col"><div class="col-title">Closeout</div>{''.join(_photo_cell(e.photo, e.note, f'{e.by} ({e.role})') for e in item.closeout_evidence) or '<div class="none">—</div>'}</div></div>{f'<div class="signoff">✓ Signed off by {html_escape(closeout.by)} ({html_escape(closeout.role)}) · {html_escape(format_date(closeout.at))}</div>' if closeout else ''}<div class="meta-line"><span>Original: {len(item.original_photos)}</span><span>Rectification: {len(item.rectification_evidence)}</span><span>Closeout: {len(item.closeout_evidence)}</span><span class="due">Due {html_escape(format_date(item.due_date))}</span></div></div>"""


def _outstanding_html(items: list[Item]) -> str:
    rows = "".join(f'<div class="out-row"><span class="code">{html_escape(item.code)}</span> {html_escape(format_location(item))} — <strong>{html_escape(status_label(item.status))}</strong>{f" · {html_escape(item.rejection_reason)}" if item.rejection_reason else ""}</div>' for item in items)
    return f'<div class="outstanding"><h2>Outstanding / Rejected ({len(items)})</h2>{rows}</div>'


def _photo_cell(uri: str | None = None, caption: str | None = None, by: str | None = None) -> str:
    if not uri and not caption:
        return ""
    label = caption or "Photo"
    if uri and uri.startswith("seed://"):
        label = caption or uri.split("/", 3)[-1].replace("%20", " ")
        return f'<div class="photo"><div class="cap">📷 {html_escape(label)}</div>{f"<div class=\"by\">{html_escape(by)}</div>" if by else ""}</div>'
    if uri:
        return f'<div class="photo"><img src="{html_escape(uri)}" style="width:100%;display:block"/>{f"<div class=\"cap\">{html_escape(caption)}</div>" if caption else ""}{f"<div class=\"by\">{html_escape(by)}</div>" if by else ""}</div>'
    return f'<div class="photo"><div class="cap">{html_escape(label)}</div>{f"<div class=\"by\">{html_escape(by)}</div>" if by else ""}</div>'


def _css() -> str:
    return """
*{box-sizing:border-box}body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0E1B2E;margin:0;padding:24px;background:#fff}.header{display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid #0E1F3A;padding-bottom:16px;margin-bottom:16px}.header img{height:34px}.meta{text-align:right;font-size:12px;color:#5A6B82}h1{font-size:22px;margin:4px 0;color:#0E1F3A}.subtitle{color:#5A6B82;font-size:13px;margin-bottom:16px}.summary{display:flex;gap:12px;margin-bottom:20px}.stat{flex:1;background:#F4F6F9;border-radius:12px;padding:14px;text-align:center}.num{font-size:26px;font-weight:800;color:#0E1F3A}.lbl{font-size:11px;color:#5A6B82;text-transform:uppercase;letter-spacing:.4px}.group{margin-bottom:18px}.group h2{font-size:14px;background:#0E1F3A;color:#fff;padding:8px 12px;border-radius:8px}.item{border:1px solid #E3E8F0;border-radius:12px;padding:14px;margin-top:10px;page-break-inside:avoid}.item-head{display:flex;justify-content:space-between;align-items:center}.code{font-weight:800;font-size:15px;color:#0E1F3A}.type{font-size:11px;color:#5A6B82;margin-left:8px}.status{font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;background:#EEF1F6;color:#5A6B82}.status-closed,.status-complete{background:#DCFCE7;color:#15803D}.status-rejected{background:#FEE2E2;color:#B91C1C}.loc{font-size:12px;color:#5A6B82;margin-top:4px}.desc{font-size:13px;margin:8px 0}.evidence-cols{display:flex;gap:10px;margin-top:8px}.col{flex:1;background:#F8FAFC;border-radius:8px;padding:8px}.col-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#5A6B82;margin-bottom:6px}.photo{border-radius:6px;padding:10px;margin-bottom:6px;font-size:11px;background:#E7ECF5}.by{color:#64748B;font-size:10px;margin-top:2px}.none{font-size:11px;color:#94A3B8}.signoff{margin-top:8px;font-size:12px;color:#15803D;font-weight:600}.meta-line{margin-top:8px;display:flex;gap:10px;align-items:center;font-size:10px;color:#5A6B82}.due{margin-left:auto}.outstanding{margin-top:20px;border-top:2px solid #FEE2E2;padding-top:12px}.outstanding h2{color:#B91C1C;font-size:14px}.out-row{font-size:12px;padding:4px 0;border-bottom:1px solid #F1F5F9}.footer{margin-top:24px;text-align:center;font-size:11px;color:#94A3B8}
"""
