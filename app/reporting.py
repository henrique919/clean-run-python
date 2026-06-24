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


def evidence_badge(label: str, count: int, klass: str) -> str:
    return f'<span class="ev {klass}">{escape(label)} {count}</span>'


def photo_cell(value: str | None, caption: str | None = None, by: str | None = None) -> str:
    if not value and not caption:
        return ""
    label = caption or "Photo attached"
    if value and value.startswith("seed://"):
        label = caption or value.replace("seed://", "").replace("/", " · ")
    by_html = f'<div class="by">{escape(by)}</div>' if by else ""
    return f'<div class="photo"><div class="cap">Photo · {escape(label)}</div>{by_html}</div>'


def item_card(item: Item) -> str:
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    status_class = str(item.status).replace("_", "-")
    original = "".join(photo_cell(p) for p in item.original_photos) or '<div class="none">No original evidence</div>'
    rectification = "".join(photo_cell(e.photo, e.comment, e.by) for e in item.rectification_evidence) or '<div class="none">No rectification evidence</div>'
    closeout_html = "".join(photo_cell(e.photo, e.note, f"{e.by} ({e.role})") for e in item.closeout_evidence) or '<div class="none">No closeout evidence</div>'
    signoff = f'<div class="signoff">Signed off by {escape(closeout.by)} · {escape(closeout.role)}</div>' if closeout else ""
    overdue_class = " overdue" if is_overdue(item) else ""
    return f"""
    <article class="item status-{escape(status_class)}">
      <div class="item-head">
        <div>
          <div class="code">{escape(item.code)}</div>
          <div class="type">{escape(TYPE_LABEL[item.type])}</div>
        </div>
        <span class="status-badge status-{escape(status_class)}">{escape(STATUS_LABEL[item.status])}</span>
      </div>
      <div class="register-line">
        <span>{escape(location(item))}</span>
        <span>{escape(item.trade or 'No trade')}</span>
        <span>{escape(item.subcontractor or 'Unassigned')}</span>
      </div>
      <div class="desc">{escape(item.description)}</div>
      <div class="evidence-cols">
        <div class="col original"><div class="col-title">Original issue evidence</div>{original}</div>
        <div class="col rectification"><div class="col-title">Subcontractor rectification</div>{rectification}</div>
        <div class="col closeout"><div class="col-title">Supervisor closeout</div>{closeout_html}</div>
      </div>
      {signoff}
      <div class="meta-line">
        {evidence_badge('Original', len(item.original_photos), 'original')}
        {evidence_badge('Rectification', len(item.rectification_evidence), 'rectification')}
        {evidence_badge('Closeout', len(item.closeout_evidence), 'closeout')}
        <span class="due{overdue_class}">Due {escape(item.due_date)}</span>
      </div>
    </article>
    """


def build_section(title: str, items: list[Item]) -> str:
    groups = group_by_location(items)
    if not groups:
        return '<div class="none block">No items in this section.</div>'
    body = "".join(
        f'<section class="group"><h3>{escape(key)}</h3>{"".join(item_card(i) for i in group)}</section>'
        for key, group in groups.items()
    )
    return f'<section class="report-section"><h2>{escape(title)}</h2>{body}</section>'


def build_report_html(items: list[Item], settings: Settings, report_type: str = "handover") -> str:
    title = REPORT_TITLES.get(report_type, "CleanRun IQ")
    filtered = filter_items(items, report_type)
    closed = [i for i in filtered if i.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    outstanding = [i for i in filtered if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]

    if report_type == "handover":
        main_html = build_section("Closed / Complete Evidence", closed)
        outstanding_html = build_section("Outstanding / Rejected", outstanding) if outstanding else ""
    else:
        main_html = build_section(title, filtered)
        outstanding_html = ""

    generated = date.today().isoformat()
    overdue = len([i for i in filtered if is_overdue(i)])
    client_count = len([i for i in filtered if i.type == "client"])

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(title)} Report</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#1E2328; margin:0; padding:28px; background:#F3F1EC; }}
.report-shell {{ background:#fff; border:1px solid #D8D3C8; padding:24px; }}
.header {{ display:grid; grid-template-columns:1.2fr .8fr; gap:24px; border-bottom:4px solid #E86D24; padding-bottom:16px; margin-bottom:18px; }}
.logo {{ font-family:'Barlow Condensed', 'Arial Narrow', sans-serif; font-size:36px; font-weight:800; letter-spacing:.2px; color:#20252B; text-transform:uppercase; }}
.logo span {{ color:#E86D24; }}
.tag {{ color:#667085; font-size:12px; text-transform:uppercase; letter-spacing:1px; font-weight:800; margin-top:2px; }}
.meta {{ text-align:right; color:#667085; font-size:12px; line-height:1.5; }}
h1,h2,h3 {{ font-family:'Barlow Condensed', 'Arial Narrow', sans-serif; text-transform:uppercase; letter-spacing:.3px; }}
h1 {{ margin:0; font-size:34px; color:#20252B; line-height:.95; }}
.subtitle {{ color:#667085; font-size:13px; margin:6px 0 18px; }}
.summary {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:18px 0 22px; }}
.stat {{ background:#FAF8F2; border:1px solid #D8D3C8; border-left:4px solid #20252B; padding:12px; }}
.stat:nth-child(2) {{ border-left-color:#15803D; }}
.stat:nth-child(3) {{ border-left-color:#B42318; }}
.stat:nth-child(4) {{ border-left-color:#2F80ED; }}
.num {{ font-family:'Barlow Condensed', sans-serif; font-size:30px; line-height:.9; font-weight:800; color:#20252B; }}
.lbl {{ font-size:10px; color:#667085; text-transform:uppercase; letter-spacing:.6px; font-weight:800; margin-top:5px; }}
.report-section {{ margin-top:18px; }}
.report-section > h2 {{ background:#20252B; color:#fff; padding:8px 12px; font-size:20px; margin:0 0 10px; border-left:5px solid #E86D24; }}
.group h3 {{ color:#20252B; border-bottom:2px solid #D8D3C8; padding-bottom:5px; margin:16px 0 8px; font-size:16px; }}
.item {{ border:1px solid #D8D3C8; border-left:6px solid #BDB6A7; padding:12px; margin-top:10px; page-break-inside:avoid; }}
.item.status-closed,.item.status-complete {{ border-left-color:#15803D; }}
.item.status-rejected {{ border-left-color:#B42318; }}
.item.status-ready-for-review,.item.status-under-inspection {{ border-left-color:#2F80ED; }}
.item.status-issued,.item.status-in-progress {{ border-left-color:#B45309; }}
.item-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
.code {{ font-family:'Barlow Condensed', sans-serif; font-size:22px; font-weight:800; color:#20252B; }}
.type {{ color:#667085; font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.6px; }}
.status-badge {{ font-size:10px; font-weight:900; padding:4px 8px; border:1px solid #D8D3C8; background:#FAF8F2; text-transform:uppercase; white-space:nowrap; }}
.status-badge.status-closed,.status-badge.status-complete {{ background:#DCFCE7; color:#15803D; border-color:rgba(21,128,61,.25); }}
.status-badge.status-rejected {{ background:#FEE4E2; color:#B42318; border-color:rgba(180,35,24,.25); }}
.register-line {{ display:grid; grid-template-columns:1.2fr .8fr 1fr; gap:8px; color:#667085; font-size:11px; margin-top:6px; }}
.register-line span {{ background:#FAF8F2; border:1px solid #D8D3C8; padding:5px 6px; }}
.desc {{ font-size:13px; margin:9px 0; line-height:1.4; }}
.evidence-cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:8px; }}
.col {{ background:#FAF8F2; border:1px solid #D8D3C8; padding:8px; min-height:70px; }}
.col.original {{ border-top:3px solid #20252B; }}
.col.rectification {{ border-top:3px solid #B45309; }}
.col.closeout {{ border-top:3px solid #15803D; }}
.col-title {{ color:#667085; font-size:9px; font-weight:900; text-transform:uppercase; letter-spacing:.6px; margin-bottom:6px; }}
.photo {{ background:#fff; border:1px solid #D8D3C8; padding:7px; margin-bottom:5px; font-size:10px; }}
.by {{ color:#667085; font-size:9px; margin-top:2px; }}
.none {{ color:#8B9380; font-size:11px; }}
.none.block {{ padding:12px; border:1px dashed #D8D3C8; background:#FAF8F2; }}
.signoff {{ color:#15803D; font-weight:800; font-size:12px; margin-top:8px; }}
.meta-line {{ display:flex; gap:6px; align-items:center; margin-top:8px; flex-wrap:wrap; }}
.ev {{ font-size:9px; font-weight:900; padding:3px 6px; border:1px solid #D8D3C8; background:#fff; text-transform:uppercase; }}
.ev.original {{ color:#20252B; }}
.ev.rectification {{ color:#B45309; }}
.ev.closeout {{ color:#15803D; }}
.due {{ margin-left:auto; font-size:10px; color:#667085; font-weight:800; }}
.due.overdue {{ color:#B42318; }}
.footer {{ margin-top:24px; padding-top:12px; border-top:1px solid #D8D3C8; text-align:center; color:#8B9380; font-size:10px; text-transform:uppercase; letter-spacing:.7px; font-weight:800; }}
@media print {{ body {{ background:#fff; padding:0; }} .report-shell {{ border:0; }} }}
</style>
</head>
<body>
  <div class="report-shell">
    <div class="header">
      <div>
        <div class="logo">CleanRun <span>IQ</span></div>
        <div class="tag">Site QA Control · Evidence Register</div>
      </div>
      <div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(settings.active_project)}<br />Generated {escape(generated)}</div>
    </div>
    <h1>{escape(title)} Report</h1>
    <div class="subtitle">Capture → Assign → Issue → In Progress → Ready for Review → Inspect → Close with Evidence → Report</div>
    <div class="summary">
      <div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Total items</div></div>
      <div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed / Complete</div></div>
      <div class="stat"><div class="num">{overdue}</div><div class="lbl">Overdue</div></div>
      <div class="stat"><div class="num">{client_count}</div><div class="lbl">Client defects</div></div>
    </div>
    {main_html}
    {outstanding_html}
    <div class="footer">Generated with CleanRun IQ · Original Issue Evidence / Rectification Evidence / Supervisor Closeout Evidence</div>
  </div>
</body>
</html>"""
