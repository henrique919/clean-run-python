from __future__ import annotations

import re
from datetime import date
from html import escape

from app.datetime_format import format_field_date
from app.models import Item, ItemStatus, Settings, STATUS_LABEL, TYPE_LABEL
from app.storage import resolve_photo_url, resolve_share_photo_url

REPORT_TITLES = {
    "handover": "Closed / Handover Evidence",
    "open": "Open Items",
    "overdue": "Overdue Items",
    "subcontractor": "Subcontractor Summary",
    "client": "Client Defects",
    "incomplete": "Incomplete Works",
    "register": "Project Defect Register",
    "exceptions": "Exceptions Report",
}

CLOSED_STATUSES = {ItemStatus.CLOSED, ItemStatus.COMPLETE}

REPORT_SHARE_SLUGS = {
    "register": "Defect-Register",
    "handover": "Handover-Evidence",
    "exceptions": "Exceptions-Report",
    "subcontractor": "Subcontractor-Summary",
    "client": "Client-Defects",
    "incomplete": "Incomplete-Works",
    "open": "Open-Items",
    "overdue": "Overdue-Items",
}

RETURN_REPORTS_SCRIPT = """
function returnToReports(){
  const app=document.body.dataset.appReturn||"/?route=reports";
  const target=app.startsWith("http")?app:(location.origin+(app.startsWith("/")?app:"/"+app));
  try{
    if(window.opener&&!window.opener.closed){
      window.opener.location.href=target;
      window.opener.focus();
      window.close();
      return;
    }
  }catch(e){}
  location.href=target;
}
"""

PHOTO_ORIENTATION_SCRIPT = """
(function(){
  function classify(img){
    if(!img.naturalWidth||!img.naturalHeight)return;
    var cell=img.closest(".photo");
    if(!cell)return;
    cell.classList.remove("portrait","landscape","square");
    var ratio=img.naturalWidth/img.naturalHeight;
    if(ratio<0.92)cell.classList.add("portrait");
    else if(ratio>1.08)cell.classList.add("landscape");
    else cell.classList.add("landscape");
  }
  document.querySelectorAll(".photo img").forEach(function(img){
    if(img.complete)classify(img);
    else img.addEventListener("load",function(){classify(img)},{once:true});
  });
})();
"""

SHARE_REPORT_SCRIPT = """
async function shareReport(){
  const title=document.title||"CleanRun IQ Report";
  const filename=document.body.dataset.shareFile||"CleanRun-IQ-Report.html";
  const imgs=[...document.querySelectorAll(".report-shell img[src]")];
  const restore=[];
  for(const img of imgs){
    const src=img.getAttribute("src");
    if(!src||src.startsWith("data:"))continue;
    restore.push([img,src]);
    const candidates=[img.getAttribute("data-share-src"),src].filter(Boolean);
    for(const candidate of candidates){
      try{
        const res=await fetch(candidate);
        if(!res.ok)continue;
        const blob=await res.blob();
        const dataUrl=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result);r.onerror=no;r.readAsDataURL(blob)});
        img.setAttribute("src",dataUrl);
        break;
      }catch(e){}
    }
  }
  const html="<!doctype html><html>"+document.documentElement.innerHTML+"</html>";
  restore.forEach(([img,src])=>img.setAttribute("src",src));
  const file=new File([html],filename,{type:"text/html;charset=utf-8"});
  try{
    if(navigator.share&&(navigator.canShare?navigator.canShare({files:[file]}):true)){
      await navigator.share({title,text:title,files:[file]});
      return;
    }
  }catch(err){if(err&&err.name==="AbortError")return}
  const url=URL.createObjectURL(file);
  const link=document.createElement("a");
  link.href=url;
  link.download=filename;
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}
"""


def is_overdue(item: Item) -> bool:
    return item.status not in CLOSED_STATUSES and item.due_date < date.today().isoformat()


def missing_original_photo(item: Item) -> bool:
    return item.type in {"defect", "client"} and len(item.original_photos) == 0


def missing_rectification_evidence(item: Item) -> bool:
    return item.status not in CLOSED_STATUSES and len(item.rectification_evidence) == 0


def missing_closeout_evidence(item: Item) -> bool:
    return item.status in CLOSED_STATUSES and len(item.closeout_evidence) == 0


def is_exception_item(item: Item) -> bool:
    return (
        is_overdue(item)
        or item.status == ItemStatus.REJECTED
        or missing_original_photo(item)
        or missing_rectification_evidence(item)
        or missing_closeout_evidence(item)
    )


def filter_items(items: list[Item], report_type: str, *, subcontractor: str | None = None) -> list[Item]:
    if report_type == "open":
        filtered = [i for i in items if i.status not in CLOSED_STATUSES]
    elif report_type == "overdue":
        filtered = [i for i in items if is_overdue(i)]
    elif report_type == "subcontractor":
        filtered = sorted(items, key=lambda i: (i.subcontractor or "", i.trade or ""))
    elif report_type == "client":
        filtered = [i for i in items if i.type == "client"]
    elif report_type == "incomplete":
        filtered = [i for i in items if i.type == "incomplete"]
    elif report_type == "register":
        filtered = sorted(items, key=lambda i: (i.updated_at, i.code), reverse=True)
    elif report_type == "exceptions":
        filtered = [i for i in items if is_exception_item(i)]
    elif report_type == "handover":
        filtered = sorted(items, key=lambda i: (i.status not in CLOSED_STATUSES, i.updated_at))
    else:
        filtered = items
    if subcontractor:
        filtered = [i for i in filtered if (i.subcontractor or "").strip().lower() == subcontractor.strip().lower()]
    return filtered


def location(item: Item) -> str:
    return " / ".join([p for p in [item.building, item.level, item.unit, item.room] if p]) or "Unassigned"


def parse_report_projects(project_param: list[str] | None, active_project: str) -> list[str]:
    if not project_param:
        return [active_project] if active_project else []
    projects: list[str] = []
    for value in project_param:
        for part in value.split(","):
            name = part.strip()
            if name:
                projects.append(name)
    if not projects and active_project:
        return [active_project]
    seen: set[str] = set()
    unique: list[str] = []
    for name in projects:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def group_by_project(items: list[Item]) -> dict[str, list[Item]]:
    groups: dict[str, list[Item]] = {}
    for item in items:
        key = item.project or "Unassigned"
        groups.setdefault(key, []).append(item)
    return dict(sorted(groups.items(), key=lambda pair: pair[0]))


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
    resolved = resolve_photo_url(value)
    if resolved is None:
        return '<div class="none">Evidence photo unavailable</div>'
    if resolved.startswith("http") or resolved.startswith("data:image/"):
        share = resolve_share_photo_url(value)
        src = resolved
        extra_attrs = ""
        if share and share.startswith("http") and share != resolved:
            # Mid-size transform keeps report/print weight down; the original
            # stays available as a runtime fallback if the transform 404s.
            src = share
            extra_attrs = (
                f' data-share-src="{escape(share)}" data-full-src="{escape(resolved)}"'
                ' onerror="if(!this.dataset.fb){this.dataset.fb=1;this.src=this.dataset.fullSrc}"'
            )
        return f'<img src="{escape(src)}" alt="{escape(alt)}"{extra_attrs} />'
    return ""


def photo_stack(*cells: str) -> str:
    present = [cell for cell in cells if cell]
    if not present:
        return ""
    if len(present) == 1:
        return present[0]
    return f'<div class="photo-stack multi">{"".join(present)}</div>'


def photo_cell(value: str | None, caption: str | None = None, by: str | None = None, *, alt: str = "Evidence photo", at: str | None = None, compact: bool = False) -> str:
    if not value and not caption and not by and not at:
        return ""
    label = caption or "Photo attached"
    seed_class = ""
    if value and value.startswith("seed://"):
        label = caption or value.replace("seed://", "").replace("/", " - ")
        seed_class = " seed"
    by_html = f'<div class="by">{escape(by)}</div>' if by else ""
    at_html = f'<div class="time">{escape(format_field_date(at))}</div>' if at else ""
    img = image_html(value, alt)
    return f'<div class="photo{seed_class}">{img}<div class="cap">{escape(label)}</div>{by_html}{at_html}</div>'


def evidence_block(title: str, body: str, *, kind: str) -> str:
    empty_class = " is-empty" if "evidence-empty" in body else ""
    return f'<section class="evidence-block {kind}{empty_class}"><div class="evidence-title">{escape(title)}</div>{body}</section>'


def empty_evidence(label: str) -> str:
    return f'<div class="none evidence-empty">No {escape(label)} uploaded</div>'


def item_card(item: Item) -> str:
    overdue = is_overdue(item)
    status_class = "overdue" if overdue else str(item.status).replace("_", "-")
    status_label = "Overdue" if overdue else STATUS_LABEL[item.status]
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    original = photo_stack(
        *(
            photo_cell(p, alt=f"{item.code} original evidence", at=item.created_at)
            for p in item.original_photos
        )
    ) or empty_evidence("original evidence")
    rectification = photo_stack(
        *(
            photo_cell(e.photo, e.comment, e.by, alt=f"{item.code} rectification evidence", at=e.at)
            for e in item.rectification_evidence
        )
    ) or empty_evidence("rectification evidence")
    closeout_html = photo_stack(
        *(
            photo_cell(e.photo, e.confirmation or e.note, f"{e.by} ({e.role})", alt=f"{item.code} closeout evidence", at=e.at)
            for e in item.closeout_evidence
        )
    ) or empty_evidence("closeout evidence")
    signoff = f'<div class="signoff">Signed off by {escape(closeout.by)} - {escape(closeout.role)}</div>' if closeout else ""
    overdue_class = " overdue" if is_overdue(item) else ""
    return f"""
    <article class="item status-{escape(status_class)}">
      <div class="item-head">
        <div><div class="code">{escape(item.code)}</div><div class="type">{escape(TYPE_LABEL[item.type])}</div></div>
        <span class="status-badge status-{escape(status_class)}">{escape(status_label)}</span>
      </div>
      <div class="register-line">
        <span>{escape(location(item))}</span><span>{escape(item.subcontractor or 'Unassigned subcontractor')}</span><span>{escape(item.trade or 'No trade')}</span>
      </div>
      <div class="desc">{escape(item.description)}</div>
      <div class="evidence-pack">
        {evidence_block("Original photo / issue evidence", original, kind="original")}
        {evidence_block("Rectification photo / trade evidence", rectification, kind="rectification")}
        {evidence_block("Closeout / signed-off evidence", closeout_html, kind="closeout")}
      </div>
      {signoff}
      <div class="meta-line">{evidence_badge('Original', len(item.original_photos), 'original')}{evidence_badge('Rectification', len(item.rectification_evidence), 'rectification')}{evidence_badge('Closeout', len(item.closeout_evidence), 'closeout')}<span class="due{overdue_class}">Due {escape(format_field_date(item.due_date))}</span></div>
    </article>"""


def build_section(title: str, items: list[Item]) -> str:
    groups = group_by_location(items)
    if not groups:
        return '<div class="none block">No items in this section.</div>'
    body = "".join(f'<section class="group"><h3>{escape(key)}</h3>{"".join(item_card(i) for i in group)}</section>' for key, group in groups.items())
    return f'<section class="report-section" aria-label="{escape(title)}">{body}</section>'


def build_handover_sections(items: list[Item]) -> str:
    closed = [i for i in items if i.status in CLOSED_STATUSES]
    outstanding = [i for i in items if i.status not in CLOSED_STATUSES]
    main_html = build_section("Closed / Complete Evidence", closed)
    outstanding_html = build_section("Outstanding / Rejected", outstanding) if outstanding else ""
    return main_html + outstanding_html


def build_project_sections(title: str, items: list[Item], report_type: str) -> str:
    if report_type == "handover":
        return build_handover_sections(items)
    filtered = filter_items(items, report_type)
    return build_section(title, filtered)


def build_scoped_body(title: str, items: list[Item], report_type: str, projects: list[str]) -> str:
    if len(projects) <= 1:
        if report_type == "handover":
            return build_handover_sections(items)
        filtered = filter_items(items, report_type)
        return build_section(title, filtered)
    sections: list[str] = []
    for project_name in projects:
        project_items = [item for item in items if (item.project or "Unassigned") == project_name]
        body = build_project_sections(title, project_items, report_type)
        sections.append(f'<section class="project-block"><h2 class="project-heading">{escape(project_name)}</h2>{body}</section>')
    return "".join(sections) if sections else '<div class="none block">No items in this report.</div>'


def report_scope_heading(projects: list[str], settings: Settings, report_type: str) -> str:
    if len(projects) > 1:
        return f"{len(projects)} projects"
    if len(projects) == 1:
        project_config = settings.project_configs.get(projects[0])
        address = project_config.address if project_config else ""
        if address:
            return f"{projects[0]} - {address}"
        return projects[0]
    if report_type == "subcontractor" and not settings.active_project:
        return "All Active Projects"
    return settings.active_project or "Project"


def report_scope_meta(projects: list[str], settings: Settings) -> str:
    if len(projects) == 1:
        return projects[0]
    if len(projects) > 1:
        return f"{len(projects)} projects"
    return settings.active_project or "Project"


def report_share_filename(settings: Settings, report_type: str, *, projects: list[str] | None = None) -> str:
    scope = projects or ([settings.active_project] if settings.active_project else ["Project"])
    if len(scope) == 1:
        project = re.sub(r"[^A-Za-z0-9]+", "-", (scope[0] or "Project").strip()).strip("-") or "Project"
    elif len(scope) <= 3:
        project = "-".join(
            re.sub(r"[^A-Za-z0-9]+", "-", (name or "Project").strip()).strip("-") or "Project"
            for name in scope[:3]
        )
    else:
        project = f"{len(scope)}-Projects"
    slug = REPORT_SHARE_SLUGS.get(report_type, report_type.replace("_", "-").title())
    day = format_field_date(date.today().isoformat()).replace(" ", "-")
    return f"{project}-{slug}-{day}.html"


def brand_mark() -> str:
    return (
        '<span class="mark" aria-hidden="true">'
        '<svg viewBox="0 0 100 100" width="34" height="34">'
        '<rect width="100" height="100" rx="22" fill="#121619"></rect>'
        '<path d="M30 32 L54 56 L30 80" fill="none" stroke="#8B929C" stroke-width="14" '
        'stroke-linecap="square" stroke-linejoin="miter"></path>'
        '<path d="M56 32 L80 56 L56 80" fill="none" stroke="#20C55E" stroke-width="14" '
        'stroke-linecap="square" stroke-linejoin="miter"></path>'
        '</svg></span><span class="word">CleanRun <b>IQ</b></span>'
    )


def build_report_html(
    items: list[Item],
    settings: Settings,
    report_type: str = "handover",
    *,
    subcontractor: str | None = None,
    projects: list[str] | None = None,
) -> str:
    title = REPORT_TITLES.get(report_type, "CleanRun IQ")
    project_scope = projects or ([settings.active_project] if settings.active_project else [])
    filtered = filter_items(items, report_type, subcontractor=subcontractor)
    closed = [i for i in filtered if i.status in CLOSED_STATUSES]
    generated = format_field_date(date.today().isoformat())
    overdue = len([i for i in filtered if is_overdue(i)])
    client_count = len([i for i in filtered if i.type == "client"])
    heading = report_scope_heading(project_scope, settings, report_type)
    meta_project = report_scope_meta(project_scope, settings)
    scope_note = f" Covering {len(project_scope)} projects." if len(project_scope) > 1 else ""
    body_html = build_scoped_body(title, filtered, report_type, project_scope)
    if subcontractor:
        title = f"{title} - {subcontractor}"
    share_filename = report_share_filename(settings, report_type, projects=project_scope)
    return f"""<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>{escape(title)}</title><style>
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}@page{{size:A4;margin:12mm}}body{{font-family:Inter,Arial,sans-serif;color:#161A1D;margin:0;background:#F4F6F8;font-size:12px;line-height:1.35}}.report-actions{{position:sticky;top:0;z-index:5;display:flex;justify-content:flex-end;gap:8px;max-width:1040px;margin:0 auto;padding:10px 0;background:#F4F6F8}}.report-actions button{{border:1px solid #B8C0C8;background:#fff;color:#161A1D;border-radius:999px;padding:8px 12px;font-weight:800}}.report-actions button.share{{background:#121619;border-color:#121619;color:#fff}}.report-actions button.print{{background:#18A94F;border-color:#18A94F}}.report-shell{{max-width:1040px;margin:0 auto;background:#fff;border:1px solid #DDE3E8;padding:18px}}.header{{display:grid;grid-template-columns:1fr auto;gap:20px;border-bottom:3px solid #20C55E;padding-bottom:12px;margin-bottom:14px}}.logo{{display:flex;align-items:center;gap:10px}}.mark{{width:34px;height:34px}}.word,h1,h2,h3,.code,.num{{font-family:Archivo,Arial,sans-serif}}.word{{font-size:25px;font-weight:800}}.word b{{color:#20C55E}}.tag,.meta,.subtitle{{color:#69747D}}.tag{{font-size:11px;font-weight:700;margin-top:3px}}.meta{{text-align:right;font-size:11px;line-height:1.45}}h1{{margin:0;font-size:25px;line-height:1.05}}.subtitle{{font-size:12px;margin:5px 0 14px}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:14px 0 16px}}.stat{{background:#F4F6F8;border:1px solid #DDE3E8;border-left:3px solid #161A1D;padding:9px;border-radius:8px}}.stat:nth-child(2){{border-left-color:#18A94F}}.stat:nth-child(3){{border-left-color:#B42318}}.stat:nth-child(4){{border-left-color:#1D4ED8}}.num{{font-size:22px;font-weight:800}}.lbl{{font-size:9px;color:#69747D;text-transform:uppercase;letter-spacing:.4px;font-weight:800}}.report-section{{margin-top:15px}}.group h3{{color:#161A1D;border-bottom:1px solid #DDE3E8;padding-bottom:4px;margin:12px 0 7px;font-size:13px}}.item{{border:1px solid #DDE3E8;border-left:5px solid #B8C0C8;border-radius:9px;padding:10px;margin-top:8px}}.item.status-closed,.item.status-complete{{border-left-color:#18A94F}}.item.status-rejected{{border-left-color:#B42318}}.item.status-ready-for-review,.item.status-under-inspection{{border-left-color:#1D4ED8}}.item.status-overdue{{border-left-color:#B42318}}.item.status-issued{{border-left-color:#D99A21}}.item.status-in-progress{{border-left-color:#C27803}}
.status-badge.status-open{{background:#F4F6F8;color:#52606D;border-color:#DDE3E8}}.status-badge.status-ready-for-review,.status-badge.status-under-inspection{{background:#E8F0FF;color:#1D4ED8;border-color:#BFD4FF}}.status-badge.status-in-progress{{background:#FFF0E0;color:#9A4A00;border-color:#F0D0A8}}.status-badge.status-overdue{{background:#FDECEC;color:#8B1E1E;border-color:#F5C2C2}}.status-badge.status-closed,.status-badge.status-complete{{background:#EAFBF1;color:#0B6E36;border-color:#BFE8D0}}.status-badge.status-issued{{background:#FFF4DF;color:#8A5A00;border-color:#F0D7A4}}.item-head{{display:flex;justify-content:space-between;gap:10px;align-items:start}}.code{{font-size:16px;font-weight:800;line-height:1}}.type{{color:#69747D;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.45px;margin-top:2px}}.status-badge{{font-size:9px;font-weight:900;padding:4px 7px;border:1px solid #DDE3E8;background:#F4F6F8;text-transform:uppercase;border-radius:999px}}.status-badge.status-closed,.status-badge.status-complete{{background:#EAFBF1;color:#0B6E36}}.status-badge.status-rejected{{background:#FDECEC;color:#8B1E1E}}.register-line{{display:grid;grid-template-columns:1.25fr 1fr .75fr;gap:6px;color:#69747D;font-size:10px;margin-top:7px}}.register-line span{{background:#F4F6F8;border:1px solid #DDE3E8;padding:5px 6px;border-radius:6px}}.item-head,.register-line,.desc{{break-after:avoid;page-break-after:avoid}}.desc{{font-size:12px;margin:8px 0}}.evidence-pack{{display:flex;flex-direction:column;gap:10px;margin-top:8px}}.evidence-block{{break-inside:avoid;page-break-inside:avoid}}.evidence-block.is-empty{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px;padding:2px 0}}.evidence-block.is-empty .evidence-title{{margin:0;padding:0;border:0;display:inline;flex:0 0 auto}}.evidence-block.is-empty .evidence-empty{{padding:0;border:0;background:transparent;font-size:9px;display:inline}}.evidence-title{{color:#69747D;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.45px;margin:0 0 6px;padding-bottom:4px;border-bottom:2px solid #DDE3E8}}.evidence-block.original .evidence-title{{border-bottom-color:#161A1D}}.evidence-block.rectification .evidence-title{{border-bottom-color:#C27803}}.evidence-block.closeout .evidence-title{{border-bottom-color:#18A94F}}.project-block{{margin-top:18px;break-inside:avoid;page-break-inside:avoid}}.project-heading{{font-size:17px;color:#161A1D;border-bottom:2px solid #20C55E;padding-bottom:5px;margin:0 0 10px}}.photo-stack{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start;break-inside:avoid;page-break-inside:avoid}}.photo-stack.multi .photo{{flex:1 1 calc(50% - 5px);max-width:calc(50% - 5px);min-width:min(100%,200px)}}.photo{{background:#fff;border:1px solid #DDE3E8;padding:6px;font-size:9px;border-radius:8px;break-inside:avoid;page-break-inside:avoid;display:block;max-width:100%}}.photo.landscape{{max-width:60%}}.photo.portrait{{max-width:44%}}.photo img{{display:block;width:100%;height:auto;object-fit:contain;object-position:center;background:transparent;border-radius:6px;margin-bottom:4px;break-inside:avoid;page-break-inside:avoid}}.photo.landscape img{{max-height:280px}}.photo.portrait img{{max-height:360px}}.photo-stack.multi .photo.landscape,.photo-stack.multi .photo.portrait{{max-width:calc(50% - 5px)}}.photo-stack.multi .photo.landscape img{{max-height:240px}}.photo-stack.multi .photo.portrait img{{max-height:300px}}.photo.seed{{background:#fff}}.by,.time{{color:#69747D;font-size:8px;margin-top:2px}}.none{{color:#69747D;font-size:10px;border:1px dashed #B8C0C8;background:#fff;padding:8px;border-radius:6px}}.none.evidence-empty{{padding:7px 8px;font-size:9px}}.none.block{{padding:10px;background:#F4F6F8;border-radius:8px}}.signoff{{color:#0B6E36;font-weight:800;font-size:11px;margin-top:7px}}.meta-line{{display:flex;gap:5px;align-items:center;margin-top:7px;flex-wrap:wrap}}.ev{{font-size:8px;font-weight:900;padding:3px 6px;border:1px solid #DDE3E8;background:#fff;text-transform:uppercase;border-radius:999px}}.ev.closeout{{background:#EAFBF1}}.ev.rectification{{background:#FFF4DF}}.due{{margin-left:auto;font-size:9px;color:#69747D;font-weight:800}}.due.overdue{{color:#B42318}}.footer{{margin-top:18px;padding-top:10px;border-top:1px solid #DDE3E8;text-align:center;color:#69747D;font-size:9px;letter-spacing:.4px;font-weight:800}}@media (max-width:520px){{.photo.landscape,.photo.portrait,.photo-stack.multi .photo{{max-width:100%;flex-basis:100%}}}}@media print{{body{{background:#fff}}.report-actions{{display:none}}.report-shell{{border:0;padding:0;max-width:none}}.item-head,.register-line,.desc,.evidence-block,.photo-stack,.photo,.photo img{{break-inside:avoid;page-break-inside:avoid}}.item-head,.register-line,.desc{{break-after:avoid;page-break-after:avoid}}.photo.landscape{{max-width:60%}}.photo.portrait{{max-width:42%}}.photo.landscape img{{max-height:90mm}}.photo.portrait img{{max-height:100mm}}.photo-stack.multi .photo{{max-width:calc(50% - 4mm)}}.photo-stack.multi .photo.landscape img{{max-height:82mm}}.photo-stack.multi .photo.portrait img{{max-height:95mm}}.item{{margin-top:6px}}}}
</style></head><body data-share-file="{escape(share_filename)}" data-app-return="/?route=reports"><div class="report-actions"><button type="button" onclick="returnToReports()">Return to reports</button><button type="button" class="share" onclick="shareReport()">Share Report</button><button type="button" class="print" onclick="window.print()">Print Report</button></div><div class="report-shell"><div class="header"><div><div class="logo">{brand_mark()}</div><div class="tag">Site QA Control - Evidence Register</div></div><div class="meta"><strong>{escape(settings.company)}</strong><br />{escape(meta_project)}<br />Generated {escape(generated)}</div></div><h1>{escape(heading)}</h1><div class="subtitle">{escape(title)}.{scope_note} Original issue, subcontractor rectification and supervisor closeout evidence in one printable register.</div><div class="summary"><div class="stat"><div class="num">{len(filtered)}</div><div class="lbl">Items</div></div><div class="stat"><div class="num">{len(closed)}</div><div class="lbl">Closed / Complete</div></div><div class="stat"><div class="num">{overdue}</div><div class="lbl">Overdue</div></div><div class="stat"><div class="num">{client_count}</div><div class="lbl">Client Defects</div></div></div>{body_html}<div class="footer">CleanRun IQ - Capture the item. Assign the trade. Close it with proof.</div></div><script>{RETURN_REPORTS_SCRIPT}{SHARE_REPORT_SCRIPT}{PHOTO_ORIENTATION_SCRIPT}</script></body></html>"""
