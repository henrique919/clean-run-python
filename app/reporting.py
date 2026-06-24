from __future__ import annotations

from datetime import date
from html import escape

from app.models import Item, ItemStatus, Settings, STATUS_LABEL, TYPE_LABEL


REPORT_TITLES = {
    "handover": "Closed / Handover Evidence",
    "open": "Open Items",
    "overdue": "Overdue Items",
    "subcontractor": "Subcontractor Report",
    "client": "Client Defects",
    "incomplete": "Incomplete Works",
}


def is_overdue(item: Item) -> bool:
    return item.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE} and item.due_date < date.today().isoformat()


def filter_items(items: list[Item], report_type: str) -> list[Item]:
    if report_type == "open":
        return [i for i in items if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    if report_type == "overdue":
        return [i for i in items if is_overdue(i)]
    if report_type == "handover":
        return sorted(items, key=lambda i: (i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}, i.updated_at), reverse=False)
    if report_type == "subcontractor":
        return sorted(items, key=lambda i: (i.subcontractor or "", i.trade or ""))
    if report_type == "client":
        return [i for i in items if i.type == "client"]
    if report_type == "incomplete":
        return [i for i in items if i.type == "incomplete"]
    return items


def location(item: Item) -> str:
    parts = [item.building, item.level, item.unit, item.room]
    return " / ".join([p for p in parts if p]) or "Unassigned"


def group_by_location(items: list[Item]) -> dict[str, list[Item]]:
    groups: dict[str, list[Item]] = {}
    for item in items:
        key = f"{item.building or 'Unassigned'} · {item.level or '—'}"
        groups.setdefault(key, []).append(item)
    return dict(sorted(groups.items(), key=lambda pair: pair[0]))


def evidence_chip(label: str, count: int, color: str) -> str:
    return f'<span class="ev" style="background:{color}1a;color:{color}">{escape(label)}: {count}</span>'


def photo_cell(value: str | None, caption: str | None = None, by: str | None = None) -> str:
    if not value and not caption:
        return ""
    label = caption or "Photo attached"
    if value and value.startswith("seed://"):
        label = caption or value.replace("seed://", "").replace("/", " · ")
    by_html = f'<div class="by">{escape(by)}</div>' if by else ""
    return f'<div class="photo"><div class="cap">📷 {escape(label)}</div>{by_html}</div>'


def item_card(item: Item) -> str:
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    original = "".join(photo_cell(p) for p in item.original_photos) or '<div class="none">No photos</div>'
    rectification = "".join(photo_cell(e.photo, e.comment, e.by) for e in item.rectification_evidence) or '<div class="none">—</div>'
    closeout_html = "".join(photo_cell(e.photo, e.note, f"{e.by} ({e.role})") for e in item.closeout_evidence) or '<div class="none">—</div>'
    signoff = f'<div class="signoff">✓ Signed off by {escape(closeout.by)} ({escape(closeout.role)})</div>' if closeout else ""
    return f"""
    <article class="item">
      <div class="item-head">
        <div><span class="code">{escape(item.code)}</span><span class="type">{escape(TYPE_LABEL[item.type])}</span></div>
        <span class="status status-{escape(item.status)}">{escape(STATUS_LABEL[item.status])}</span>
      </div>
      <div class="loc">{escape(location(item))} · {escape(item.trade or '—')} · {escape(item.subcontractor or 'Unassigned')}</div>
      <div class="desc">{escape(item.description)}</div>
      <div class="evidence-cols">
        <div class="col"><div class="col-title">Original issue</div>{original}</div>
        <div class="col"><div class="col-title">Rectification</div>{rectification}</div>
        <div class="col"><div class="col-title">Closeout</div>{closeout_html}</div>
      </div>
      {signoff}
      <div class="meta-line">
        {evidence_chip('Original', len(item.original_photos), '#0E1F3A')}
        {evidence_chip('Rectification', len(item.rectification_evidence), '#F59E0B')}
        {evidence_chip('Closeout', len(item.closeout_evidence), '#16A34A')}
        <span class="due {'overdue' if is_overdue(item) else ''}">Due {escape(item.due_date)}</span>
      </div>
    </article>
    """


def build_report_html(items: list[Item], settings: Settings, report_type: str = "handover") -> str:
    title = REPORT_TITLES.get(report_type, "CleanRun IQ")
    filtered = filter_items(items, report_type)
    closed = [i for i in filtered if i.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    outstanding = [i for i in filtered if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    main_items = closed if report_type == "handover" else filtered
    groups = group_by_location(main_items)

    group_html = "".join(
        f'<section class="group"><h2>{escape(key)}</h2>{"".join(item_card(i) for i in group)}</section>'
        for key, group in groups.items()
    )

    outstanding_html = ""
    if report_type == "handover" and outstanding:
        rows = "".join(
            f'<div class="out-row"><span class="code">{escape(i.code)}</span> {escape(location(i))} — <strong>{escape(STATUS_LABEL[i.status])}</strong>{" · " + escape(i.rejection_reason) if i.rejection_reason else ""}</div>'
            for i in outstanding
        )
        outstanding_html = f'<section class="outstanding"><h2>Outstanding / Rejected ({len(outstanding)})</h2>{rows}</section>'

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)} Report</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#0E1B2E; margin:0; padding:28px; background:#fff; }}
.header {{ display:flex; align-items:center; justify-content:space-between; border-bottom:3px solid #0E1F3A; padding-bottom:16px; margin-bottom:18px; }}
.logo {{ font-size:30px; font-weight:900; color:#0E1F3A; letter-spacing:-1px; }}
.logo span {{ color:#09B734; }}
.meta {{ text-align:right; color:#5A6B82; font-size:12px; }}
h1 {{ margin:0 0 4px; font-size:24px; color:#0E1F3A; }}
.subtitle {{ color:#5A6B82; font-size:13px; margin-bottom:18px; }}
.summary {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:18px 0; }}
.stat {{ background:#F4F6F9; border-radius:12px; padding:14px; text-align:center; }}
.num {{ font-size:26px; font-weight:900; color:#0E1F3A; }}
.lbl {{ font-size:10px; color:#5A6B82; text-transform:uppercase; letter-spacing:.4px; }}
.group h2 {{ background:#0E1F3A; color:#fff; border-radius:8px; padding:8px 12px; font-size:14px; }}
.item {{ border:1px solid #E3E8F0; border-radius:12px; padding:14px; margin-top:10px; page-break-inside:avoid; }}
.item-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; }}
.code {{ font-weight:900; color:#0E1F3A; }}
.type {{ margin-left:8px; color:#5A6B82; font-size:11px; }}
.status {{ font-size:11px; font-weight:800; padding:3px 9px; border-radius:999px; background:#EEF1F6; color:#5A6B82; }}
.status-closed,.status-complete {{ background:#DCFCE7; color:#15803D; }}
.status-rejected {{ background:#FEE2E2; color:#B91C1C; }}
.loc {{ color:#5A6B82; font-size:12px; margin-top:4px; }}
.desc {{ font-size:13px; margin:8px 0; }}
.evidence-cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:8px; }}
.col {{ background:#F8FAFC; border-radius:8px; padding:8px; }}
.col-title {{ color:#5A6B82; font-size:10px; font-weight:800; text-transform:uppercase; margin-bottom:6px; }}
.photo {{ background:#E7ECF5; border-radius:6px; padding:8px; margin-bottom:6px; font-size:11px; }}
.by {{ color:#64748B; font-size:10px; margin-top:2px; }}
.none {{ color:#94A3B8; font-size:11px; }}
.signoff {{ color:#15803D; font-weight:700; font-size:12px; margin-top:8px; }}
.meta-line {{ display:flex; gap:6px; align-items:center; margin-top:8px; }}
.ev {{ font-size:10px; font-weight:800; padding:2px 8px; border-radius:999px; }}
.due {{ margin-left:auto; font-size:11px; color:#5A6B82; }}
.due.overdue {{ color:#B91C1C; font-weight:900; }}
.outstanding {{ border-top:2px solid #FEE2E2; margin-top:22px; padding-top:12px; }}
.outstanding h2 {{ color:#B91C1C; font-size:15px; }}
.out-row {{ font-size:12px; padding:6px 0; border-bottom:1px solid #F1F5F9; }}
.footer {{ margin-top:24px; text-align:center; color:#94A3B8; font-size:11px; }}
</style>
</head>
<body>
  <div class="header"><div class="logo">CleanRun <span>IQ</span></div><div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(settings.active_project)}<br />Generated {escape(date.today().isoformat())}</div></div>
  <h1>{escape(title)} Report</h1>
  <div class="subtitle">Capture → Assign → Issue → Inspect → Close with Evidence → Report</div>
  <div class="summary">
    <div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Total items</div></div>
    <div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed</div></div>
    <div class="stat"><div class="num">{len([i for i in filtered if is_overdue(i)])}</div><div class="lbl">Overdue</div></div>
    <div class="stat"><div class="num">{len([i for i in filtered if i.type == 'client'])}</div><div class="lbl">Client defects</div></div>
  </div>
  {group_html or '<div class="none">No items match this report.</div>'}
  {outstanding_html}
  <div class="footer">Generated with CleanRun IQ</div>
</body>
</html>"""
