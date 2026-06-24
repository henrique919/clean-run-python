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
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:#121619; margin:0; padding:28px; background:#F3F4F6; }}
.report-shell {{ background:#fff; border:1px solid #DDE1E5; padding:24px; }}
.header {{ display:grid; grid-template-columns:1.2fr .8fr; gap:24px; border-bottom:4px solid #20C55E; padding-bottom:16px; margin-bottom:18px; }}
.logo {{ display:block; width:230px; max-width:100%; height:auto; }}
.tag {{ color:#6B7280; font-family:'Archivo',sans-serif; font-size:10px; text-transform:uppercase; letter-spacing:1px; font-weight:700; margin-top:7px; }}
.meta {{ text-align:right; color:#6B7280; font-size:12px; line-height:1.55; }}
h1,h2,h3 {{ font-family:'Archivo',sans-serif; letter-spacing:-.02em; }}
h1 {{ margin:0; font-size:34px; color:#121619; line-height:1; }}
.subtitle {{ color:#6B7280; font-size:12px; margin:7px 0 18px; }}
.summary {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:18px 0 22px; }}
.stat {{ background:#F8F9FA; border:1px solid #DDE1E5; border-left:4px solid #121619; padding:12px; }}
.stat:nth-child(2) {{ border-left-color:#20C55E; }}
.stat:nth-child(3) {{ border-left-color:#B42318; }}
.stat:nth-child(4) {{ border-left-color:#6B7280; }}
.num {{ font-family:'Archivo',sans-serif; font-size:30px; line-height:.95; font-weight:800; color:#121619; }}
.lbl {{ font-family:'Archivo',sans-serif; font-size:9px; color:#6B7280; text-transform:uppercase; letter-spacing:.7px; font-weight:700; margin-top:5px; }}
.report-section {{ margin-top:18px; }}
.report-section > h2 {{ background:#121619; color:#fff; padding:9px 12px; font-size:19px; margin:0 0 10px; border-left:5px solid #20C55E; }}
.group h3 {{ color:#121619; border-bottom:2px solid #DDE1E5; padding-bottom:5px; margin:16px 0 8px; font-size:15px; }}
.item {{ border:1px solid #DDE1E5; border-left:6px solid #6B7280; padding:12px; margin-top:10px; page-break-inside:avoid; }}
.item.status-closed,.item.status-complete {{ border-left-color:#20C55E; }}
.item.status-rejected {{ border-left-color:#B42318; }}
.item.status-ready-for-review {{ border-left-color:#B45309; }}
.item.status-under-inspection {{ border-left-color:#121619; }}
.item.status-issued,.item.status-in-progress {{ border-left-color:#B45309; }}
.item-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
.code {{ font-family:'Archivo',sans-serif; font-size:21px; font-weight:800; color:#121619; }}
.type {{ color:#6B7280; font-family:'Archivo',sans-serif; font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; }}
.status-badge {{ font-family:'Archivo',sans-serif; font-size:9px; font-weight:700; padding:4px 8px; border:1px solid #DDE1E5; background:#F8F9FA; text-transform:uppercase; white-space:nowrap; }}
.status-badge.status-closed,.status-badge.status-complete {{ background:#E1F7E9; color:#0C7733; border-color:rgba(32,197,94,.3); }}
.status-badge.status-rejected {{ background:#FEE4E2; color:#B42318; border-color:rgba(180,35,24,.25); }}
.register-line {{ display:grid; grid-template-columns:1.2fr .8fr 1fr; gap:8px; color:#6B7280; font-size:11px; margin-top:6px; }}
.register-line span {{ background:#F8F9FA; border:1px solid #DDE1E5; padding:5px 6px; }}
.desc {{ font-size:13px; margin:9px 0; line-height:1.4; }}
.evidence-cols {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:8px; }}
.col {{ background:#F8F9FA; border:1px solid #DDE1E5; padding:8px; min-height:70px; }}
.col.original {{ border-top:3px solid #121619; }}
.col.rectification {{ border-top:3px solid #6B7280; }}
.col.closeout {{ border-top:3px solid #20C55E; }}
.col-title {{ color:#6B7280; font-family:'Archivo',sans-serif; font-size:8px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; margin-bottom:6px; }}
.photo {{ background:#fff; border:1px solid #DDE1E5; padding:7px; margin-bottom:5px; font-size:10px; }}
.by {{ color:#6B7280; font-size:9px; margin-top:2px; }}
.none {{ color:#6B7280; font-size:11px; }}
.none.block {{ padding:12px; border:1px dashed #B9C0C8; background:#F8F9FA; }}
.signoff {{ color:#0C7733; font-weight:700; font-size:12px; margin-top:8px; }}
.meta-line {{ display:flex; gap:6px; align-items:center; margin-top:8px; flex-wrap:wrap; }}
.ev {{ font-family:'Archivo',sans-serif; font-size:8px; font-weight:700; padding:3px 6px; border:1px solid #DDE1E5; background:#fff; text-transform:uppercase; }}
.ev.original {{ color:#121619; }}
.ev.rectification {{ color:#6B7280; }}
.ev.closeout {{ color:#0C7733; }}
.due {{ margin-left:auto; font-size:10px; color:#6B7280; font-weight:700; }}
.due.overdue {{ color:#B42318; }}
.footer {{ margin-top:24px; padding-top:12px; border-top:1px solid #DDE1E5; text-align:center; color:#6B7280; font-family:'Archivo',sans-serif; font-size:9px; text-transform:uppercase; letter-spacing:.7px; font-weight:700; }}
@media (max-width:700px) {{ body {{ padding:10px; }} .report-shell {{ padding:14px; }} .header {{ grid-template-columns:1fr; }} .meta {{ text-align:left; }} .summary {{ grid-template-columns:repeat(2,1fr); }} .evidence-cols {{ grid-template-columns:1fr; }} .register-line {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:#fff; padding:0; }} .report-shell {{ border:0; }} }}
</style>
</head>
<body>
  <div class="report-shell">
    <div class="header">
      <div>
        <img class="logo" src="/static/assets/brand/cleanrun-logo-horizontal.png" alt="CleanRun IQ" />
        <div class="tag">Smarter Field. Cleaner Builds.</div>
      </div>
      <div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(settings.active_project)}<br />Generated {escape(generated)}</div>
    </div>
    <h1>{escape(title)} Report</h1>
    <div class="subtitle">Capture &gt; Assign &gt; Issue &gt; In Progress &gt; Ready for Review &gt; Inspect &gt; Close with Evidence &gt; Report</div>
    <div class="summary">
      <div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Total items</div></div>
      <div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed / Complete</div></div>
      <div class="stat"><div class="num">{overdue}</div><div class="lbl">Overdue</div></div>
      <div class="stat"><div class="num">{client_count}</div><div class="lbl">Client defects</div></div>
    </div>
    {main_html}
    {outstanding_html}
    <div class="footer">CleanRun IQ - Smarter Field. Cleaner Builds. - Original Issue / Rectification / Supervisor Closeout Evidence</div>
  </div>
</body>
</html>"""
