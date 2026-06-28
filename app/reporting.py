from __future__ import annotations

from datetime import date
from html import escape

from app.models import Item, ItemStatus, Settings, STATUS_LABEL, TYPE_LABEL

REPORT_TITLES = {
    "handover": "Closed / Handover Evidence",
    "open": "Open Items",
    "overdue": "Overdue Items",
    "subcontractor": "Subcontractor Summary",
    "client": "Client Defects",
    "incomplete": "Incomplete Works",
}

CLOSED_STATUSES = {ItemStatus.CLOSED, ItemStatus.COMPLETE}


def is_overdue(item: Item) -> bool:
    return item.status not in CLOSED_STATUSES and item.due_date < date.today().isoformat()


def filter_items(items: list[Item], report_type: str) -> list[Item]:
    if report_type == "open":
        return [i for i in items if i.status not in CLOSED_STATUSES]
    if report_type == "overdue":
        return [i for i in items if is_overdue(i)]
    if report_type == "subcontractor":
        return sorted(items, key=lambda i: (i.subcontractor or "", i.trade or ""))
    if report_type == "client":
        return [i for i in items if i.type == "client"]
    if report_type == "incomplete":
        return [i for i in items if i.type == "incomplete"]
    if report_type == "handover":
        return sorted(items, key=lambda i: (i.status not in CLOSED_STATUSES, i.updated_at))
    return items


def location(item: Item) -> str:
    return " / ".join([p for p in [item.building, item.level, item.unit, item.room] if p]) or "Unassigned"


def group_by_location(items: list[Item]) -> dict[str, list[Item]]:
    groups: dict[str, list[Item]] = {}
    for item in items:
        key = f"{item.building or 'Unassigned'} - {item.level or 'No level'}"
        groups.setdefault(key, []).append(item)
    return dict(sorted(groups.items(), key=lambda pair: pair[0]))


def evidence_badge(label: str, count: int, klass: str) -> str:
    return f'<span class="ev {klass}">{escape(label)} {count}</span>'


def image_html(value: str | None, alt: str) -> str:
    if not value:
        return ""
    if value.startswith("http") or value.startswith("data:image/"):
        return f'<img src="{escape(value)}" alt="{escape(alt)}" />'
    return ""


def photo_cell(value: str | None, caption: str | None = None, by: str | None = None, *, alt: str = "Evidence photo") -> str:
    if not value and not caption:
        return ""
    label = caption or "Photo attached"
    seed_class = ""
    if value and value.startswith("seed://"):
        label = caption or value.replace("seed://", "").replace("/", " - ")
        seed_class = " seed"
    by_html = f'<div class="by">{escape(by)}</div>' if by else ""
    img = image_html(value, alt)
    return f'<div class="photo{seed_class}">{img}<div class="cap">{escape(label)}</div>{by_html}</div>'


def empty_evidence(label: str) -> str:
    return f'<div class="none">No {escape(label)} uploaded</div>'


def item_card(item: Item) -> str:
    status_class = str(item.status).replace("_", "-")
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    original = "".join(photo_cell(p, alt=f"{item.code} original evidence") for p in item.original_photos) or empty_evidence("original evidence")
    rectification = "".join(
        photo_cell(e.photo, e.comment, e.by, alt=f"{item.code} rectification evidence")
        for e in item.rectification_evidence
    ) or empty_evidence("rectification evidence")
    closeout_html = "".join(
        photo_cell(e.photo, e.note, f"{e.by} ({e.role})", alt=f"{item.code} closeout evidence")
        for e in item.closeout_evidence
    ) or empty_evidence("closeout evidence")
    signoff = f'<div class="signoff">Signed off by {escape(closeout.by)} - {escape(closeout.role)}</div>' if closeout else ""
    overdue_class = " overdue" if is_overdue(item) else ""
    return f"""
    <article class="item status-{escape(status_class)}">
      <div class="item-head">
        <div><div class="code">{escape(item.code)}</div><div class="type">{escape(TYPE_LABEL[item.type])}</div></div>
        <span class="status-badge status-{escape(status_class)}">{escape(STATUS_LABEL[item.status])}</span>
      </div>
      <div class="register-line">
        <span>{escape(location(item))}</span><span>{escape(item.subcontractor or 'Unassigned subcontractor')}</span><span>{escape(item.trade or 'No trade')}</span>
      </div>
      <div class="desc">{escape(item.description)}</div>
      <div class="evidence-cols">
        <div class="col original"><div class="col-title">Original photo / issue evidence</div>{original}</div>
        <div class="col rectification"><div class="col-title">Rectification photo / trade evidence</div>{rectification}</div>
        <div class="col closeout"><div class="col-title">Closeout / signed-off evidence</div>{closeout_html}</div>
      </div>
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
    closed = [i for i in filtered if i.status in CLOSED_STATUSES]
    outstanding = [i for i in filtered if i.status not in CLOSED_STATUSES]
    main_html = build_section("Closed / Complete Evidence", closed) if report_type == "handover" else build_section(title, filtered)
    outstanding_html = build_section("Outstanding / Rejected", outstanding) if report_type == "handover" and outstanding else ""
    generated = date.today().isoformat()
    overdue = len([i for i in filtered if is_overdue(i)])
    client_count = len([i for i in filtered if i.type == "client"])
    return f"""<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>{escape(title)}</title><style>
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}@page{{size:A4;margin:12mm}}body{{font-family:Inter,Arial,sans-serif;color:#161A1D;margin:0;background:#F4F6F8;font-size:12px;line-height:1.35}}.report-shell{{max-width:1040px;margin:0 auto;background:#fff;border:1px solid #DDE3E8;padding:18px}}.header{{display:grid;grid-template-columns:1fr auto;gap:20px;border-bottom:3px solid #26C66A;padding-bottom:12px;margin-bottom:14px}}.logo{{display:flex;align-items:center;gap:10px}}.mark{{width:34px;height:34px;border-radius:10px;background:#283238;display:flex;align-items:center;justify-content:center}}.mark i{{display:block;width:12px;height:12px;border-top:4px solid #69747D;border-right:4px solid #69747D;transform:rotate(45deg);margin-left:-4px}}.mark i:last-child{{border-color:#26C66A}}.word,h1,h2,h3,.code,.num{{font-family:Archivo,Arial,sans-serif}}.word{{font-size:25px;font-weight:800}}.word b{{color:#26C66A}}.tag,.meta,.subtitle{{color:#69747D}}.tag{{font-size:11px;font-weight:700;margin-top:3px}}.meta{{text-align:right;font-size:11px;line-height:1.45}}h1{{margin:0;font-size:25px;line-height:1.05}}.subtitle{{font-size:12px;margin:5px 0 14px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0 16px}}.stat{{background:#F4F6F8;border:1px solid #DDE3E8;border-left:3px solid #161A1D;padding:9px;border-radius:8px}}.stat:nth-child(2){{border-left-color:#26C66A}}.stat:nth-child(3){{border-left-color:#C73535}}.stat:nth-child(4){{border-left-color:#2D6CDF}}.num{{font-size:22px;font-weight:800}}.lbl{{font-size:9px;color:#69747D;text-transform:uppercase;letter-spacing:.4px;font-weight:800}}.report-section{{margin-top:15px}}.report-section>h2{{background:#161A1D;color:#fff;padding:8px 10px;font-size:15px;margin:0 0 8px;border-left:4px solid #26C66A}}.group h3{{color:#283238;border-bottom:1px solid #DDE3E8;padding-bottom:4px;margin:12px 0 7px;font-size:13px}}.item{{border:1px solid #DDE3E8;border-left:5px solid #B8C0C8;border-radius:9px;padding:10px;margin-top:8px;break-inside:avoid;page-break-inside:avoid}}.item.status-closed,.item.status-complete{{border-left-color:#26C66A}}.item.status-rejected{{border-left-color:#C73535}}.item.status-ready-for-review,.item.status-under-inspection{{border-left-color:#2D6CDF}}.item.status-issued,.item.status-in-progress{{border-left-color:#B66A14}}.item-head{{display:flex;justify-content:space-between;gap:10px;align-items:start}}.code{{font-size:16px;font-weight:800;line-height:1}}.type{{color:#69747D;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.45px;margin-top:2px}}.status-badge{{font-size:9px;font-weight:900;padding:4px 7px;border:1px solid #DDE3E8;background:#F4F6F8;text-transform:uppercase;border-radius:999px}}.status-badge.status-closed,.status-badge.status-complete{{background:#EAFBF1;color:#0B6E36}}.status-badge.status-rejected{{background:#FDECEC;color:#8B1E1E}}.register-line{{display:grid;grid-template-columns:1.25fr 1fr .75fr;gap:6px;color:#69747D;font-size:10px;margin-top:7px}}.register-line span{{background:#F4F6F8;border:1px solid #DDE3E8;padding:5px 6px;border-radius:6px}}.desc{{font-size:12px;margin:8px 0}}.evidence-cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:7px}}.col{{background:#F4F6F8;border:1px solid #DDE3E8;padding:7px;min-height:92px;border-radius:8px}}.col.original{{border-top:3px solid #161A1D}}.col.rectification{{border-top:3px solid #B66A14}}.col.closeout{{border-top:3px solid #26C66A}}.col-title{{color:#69747D;font-size:8px;font-weight:900;text-transform:uppercase;letter-spacing:.45px;margin-bottom:5px}}.photo{{background:#fff;border:1px solid #DDE3E8;padding:5px;margin-bottom:5px;font-size:9px;border-radius:6px}}.photo img{{display:block;width:100%;height:78px;object-fit:cover;border-radius:5px;margin-bottom:5px}}.photo.seed{{background:#fff}}.by{{color:#69747D;font-size:8px;margin-top:2px}}.none{{color:#69747D;font-size:10px;border:1px dashed #B8C0C8;background:#fff;padding:8px;border-radius:6px}}.none.block{{padding:10px;background:#F4F6F8;border-radius:8px}}.signoff{{color:#0B6E36;font-weight:800;font-size:11px;margin-top:7px}}.meta-line{{display:flex;gap:5px;align-items:center;margin-top:7px;flex-wrap:wrap}}.ev{{font-size:8px;font-weight:900;padding:3px 6px;border:1px solid #DDE3E8;background:#fff;text-transform:uppercase;border-radius:999px}}.ev.closeout{{background:#EAFBF1}}.ev.rectification{{background:#FFF4DF}}.due{{margin-left:auto;font-size:9px;color:#69747D;font-weight:800}}.due.overdue{{color:#C73535}}.footer{{margin-top:18px;padding-top:10px;border-top:1px solid #DDE3E8;text-align:center;color:#69747D;font-size:9px;letter-spacing:.4px;font-weight:800}}@media print{{body{{background:#fff}}.report-shell{{border:0;padding:0;max-width:none}}.item{{margin-top:6px}}}}
</style></head><body><div class="report-shell"><div class="header"><div><div class="logo">{brand_mark()}</div><div class="tag">Site QA Control - Evidence Register</div></div><div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(settings.active_project)}<br />Generated {escape(generated)}</div></div><h1>{escape(title)}</h1><div class="subtitle">Original issue, subcontractor rectification and supervisor closeout evidence in one printable register.</div><div class="summary"><div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Items</div></div><div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed / Complete</div></div><div class="stat"><div class="num">{overdue}</div><div class="lbl">Overdue</div></div><div class="stat"><div class="num">{client_count}</div><div class="lbl">Client Defects</div></div></div>{main_html}{outstanding_html}<div class="footer">CleanRun IQ - Capture the item. Assign the trade. Close it with proof.</div></div></body></html>"""
