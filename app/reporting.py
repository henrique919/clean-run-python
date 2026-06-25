from __future__ import annotations

from datetime import date
from html import escape

from app.models import Item, ItemStatus, Settings, STATUS_LABEL, TYPE_LABEL

REPORT_TITLES = {"handover": "Closed / Handover Evidence", "open": "Open Items", "overdue": "Overdue Items", "subcontractor": "Subcontractor Summary", "client": "Client Defects", "incomplete": "Incomplete Works"}


def is_overdue(item: Item) -> bool:
    return item.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE} and item.due_date < date.today().isoformat()


def filter_items(items: list[Item], report_type: str) -> list[Item]:
    if report_type == "open":
        return [i for i in items if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    if report_type == "overdue":
        return [i for i in items if is_overdue(i)]
    if report_type == "subcontractor":
        return sorted(items, key=lambda i: (i.subcontractor or "", i.trade or ""))
    if report_type == "client":
        return [i for i in items if i.type == "client"]
    if report_type == "incomplete":
        return [i for i in items if i.type == "incomplete"]
    if report_type == "handover":
        return sorted(items, key=lambda i: (i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}, i.updated_at), reverse=False)
    return items


def location(item: Item) -> str:
    return " / ".join([p for p in [item.building, item.level, item.unit, item.room] if p]) or "Unassigned"


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
      <div class="item-head"><div><div class="code">{escape(item.code)}</div><div class="type">{escape(TYPE_LABEL[item.type])}</div></div><span class="status-badge status-{escape(status_class)}">{escape(STATUS_LABEL[item.status])}</span></div>
      <div class="register-line"><span>{escape(location(item))}</span><span>{escape(item.trade or 'No trade')}</span><span>{escape(item.subcontractor or 'Unassigned')}</span></div>
      <div class="desc">{escape(item.description)}</div>
      <div class="evidence-cols"><div class="col original"><div class="col-title">Original issue evidence</div>{original}</div><div class="col rectification"><div class="col-title">Subcontractor rectification</div>{rectification}</div><div class="col closeout"><div class="col-title">Supervisor closeout</div>{closeout_html}</div></div>
      {signoff}
      <div class="meta-line">{evidence_badge('Original', len(item.original_photos), 'original')}{evidence_badge('Rectification', len(item.rectification_evidence), 'rectification')}{evidence_badge('Closeout', len(item.closeout_evidence), 'closeout')}<span class="due{overdue_class}">Due {escape(item.due_date)}</span></div>
    </article>"""


def build_section(title: str, items: list[Item]) -> str:
    groups = group_by_location(items)
    if not groups:
        return '<div class="none block">No items in this section.</div>'
    body = "".join(f'<section class="group"><h3>{escape(key)}</h3>{"".join(item_card(i) for i in group)}</section>' for key, group in groups.items())
    return f'<section class="report-section"><h2>{escape(title)}</h2>{body}</section>'


def brand_mark() -> str:
    return '<span class="mark"><i></i><i></i></span><span class="word">CleanRun <b>IQ</b></span>'


def build_report_html(items: list[Item], settings: Settings, report_type: str = "handover") -> str:
    title = REPORT_TITLES.get(report_type, "CleanRun IQ")
    filtered = filter_items(items, report_type)
    closed = [i for i in filtered if i.status in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    outstanding = [i for i in filtered if i.status not in {ItemStatus.CLOSED, ItemStatus.COMPLETE}]
    main_html = build_section("Closed / Complete Evidence", closed) if report_type == "handover" else build_section(title, filtered)
    outstanding_html = build_section("Outstanding / Rejected", outstanding) if report_type == "handover" and outstanding else ""
    generated = date.today().isoformat()
    overdue = len([i for i in filtered if is_overdue(i)])
    client_count = len([i for i in filtered if i.type == "client"])
    return f"""<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>{escape(title)}</title><style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}body{{font-family:'Inter',system-ui,sans-serif;color:#161A1D;margin:0;padding:28px;background:#F4F6F8}}.report-shell{{background:#fff;border:1px solid #DDE3E8;border-radius:18px;padding:24px}}.header{{display:grid;grid-template-columns:1.2fr .8fr;gap:24px;border-bottom:3px solid #26C66A;padding-bottom:16px;margin-bottom:18px}}.logo{{display:flex;align-items:center;gap:12px}}.mark{{width:40px;height:40px;border-radius:13px;background:#283238;display:flex;align-items:center;justify-content:center}}.mark i{{display:block;width:14px;height:14px;border-top:5px solid #69747D;border-right:5px solid #69747D;transform:rotate(45deg);margin-left:-4px}}.mark i:last-child{{border-color:#26C66A}}.word,h1,h2,h3,.code,.num{{font-family:'Archivo',sans-serif}}.word{{font-size:31px;font-weight:800;letter-spacing:-.7px}}.word b{{color:#26C66A}}.tag,.meta,.subtitle{{color:#69747D}}.tag{{font-size:12px;font-weight:700;margin-top:5px}}.meta{{text-align:right;font-size:12px;line-height:1.5}}h1{{margin:0;font-size:33px;line-height:1}}.subtitle{{font-size:13px;margin:7px 0 18px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 22px}}.stat{{background:#F4F6F8;border:1px solid #DDE3E8;border-left:4px solid #161A1D;padding:12px;border-radius:12px}}.stat:nth-child(2){{border-left-color:#26C66A}}.stat:nth-child(3){{border-left-color:#C73535}}.stat:nth-child(4){{border-left-color:#2D6CDF}}.num{{font-size:29px;font-weight:800}}.lbl{{font-size:10px;color:#69747D;text-transform:uppercase;letter-spacing:.5px;font-weight:800;margin-top:5px}}.report-section{{margin-top:18px}}.report-section>h2{{background:#161A1D;color:#fff;padding:10px 12px;font-size:19px;margin:0 0 10px;border-left:5px solid #26C66A}}.group h3{{color:#283238;border-bottom:2px solid #DDE3E8;padding-bottom:5px;margin:16px 0 8px;font-size:16px}}.item{{border:1px solid #DDE3E8;border-left:6px solid #B8C0C8;border-radius:12px;padding:12px;margin-top:10px;page-break-inside:avoid}}.item.status-closed,.item.status-complete{{border-left-color:#26C66A}}.item.status-rejected{{border-left-color:#C73535}}.item.status-ready-for-review,.item.status-under-inspection{{border-left-color:#2D6CDF}}.item.status-issued,.item.status-in-progress{{border-left-color:#B66A14}}.item-head{{display:flex;justify-content:space-between;gap:12px}}.code{{font-size:21px;font-weight:800}}.type{{color:#69747D;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.55px}}.status-badge{{font-size:10px;font-weight:900;padding:5px 8px;border:1px solid #DDE3E8;background:#F4F6F8;text-transform:uppercase;border-radius:999px}}.status-badge.status-closed,.status-badge.status-complete{{background:#EAFBF1;color:#0B6E36}}.register-line{{display:grid;grid-template-columns:1.2fr .8fr 1fr;gap:8px;color:#69747D;font-size:11px;margin-top:7px}}.register-line span{{background:#F4F6F8;border:1px solid #DDE3E8;padding:6px 7px;border-radius:8px}}.desc{{font-size:13px;margin:10px 0;line-height:1.45}}.evidence-cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}}.col{{background:#F4F6F8;border:1px solid #DDE3E8;padding:9px;min-height:70px;border-radius:10px}}.col.original{{border-top:3px solid #161A1D}}.col.rectification{{border-top:3px solid #B66A14}}.col.closeout{{border-top:3px solid #26C66A}}.col-title{{color:#69747D;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}}.photo{{background:#fff;border:1px solid #DDE3E8;padding:7px;margin-bottom:5px;font-size:10px;border-radius:8px}}.by{{color:#69747D;font-size:9px;margin-top:2px}}.none{{color:#69747D;font-size:11px}}.none.block{{padding:12px;border:1px dashed #B8C0C8;background:#F4F6F8;border-radius:12px}}.signoff{{color:#0B6E36;font-weight:800;font-size:12px;margin-top:8px}}.meta-line{{display:flex;gap:6px;align-items:center;margin-top:8px;flex-wrap:wrap}}.ev{{font-size:9px;font-weight:900;padding:4px 7px;border:1px solid #DDE3E8;background:#fff;text-transform:uppercase;border-radius:999px}}.ev.closeout{{background:#EAFBF1}}.ev.rectification{{background:#FFF4DF}}.due{{margin-left:auto;font-size:10px;color:#69747D;font-weight:800}}.due.overdue{{color:#C73535}}.footer{{margin-top:24px;padding-top:12px;border-top:1px solid #DDE3E8;text-align:center;color:#69747D;font-size:10px;letter-spacing:.5px;font-weight:800}}
@media print{{body{{background:#fff;padding:0}}.report-shell{{border:0;border-radius:0}}}}
</style></head><body><div class="report-shell"><div class="header"><div><div class="logo">{brand_mark()}</div><div class="tag">The smarter way to handover · Evidence Register</div></div><div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(settings.active_project)}<br />Generated {escape(generated)}</div></div><h1>{escape(title)}</h1><div class="subtitle">CleanRun IQ field register export. Evidence first, accountable closeout.</div><div class="summary"><div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Items</div></div><div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed / Complete</div></div><div class="stat"><div class="num">{overdue}</div><div class="lbl">Overdue</div></div><div class="stat"><div class="num">{client_count}</div><div class="lbl">Client Defects</div></div></div>{main_html}{outstanding_html}<div class="footer">CleanRun IQ · The smarter way to handover.</div></div></body></html>"""
