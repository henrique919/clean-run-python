from __future__ import annotations

import re
from datetime import date
from html import escape

from app.datetime_format import format_field_date
from app.models import Item, ItemStatus, Priority, Settings, STATUS_LABEL, TYPE_LABEL
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
    compact_class = " compact" if compact else ""
    return f'<div class="photo{seed_class}{compact_class}">{img}<div class="cap">{escape(label)}</div>{by_html}{at_html}</div>'


def evidence_block(title: str, body: str, *, kind: str) -> str:
    empty_class = " is-empty" if "evidence-empty" in body else ""
    return f'<section class="evidence-block {kind}{empty_class}"><div class="evidence-title">{escape(title)}</div>{body}</section>'


def empty_evidence(label: str) -> str:
    return f'<div class="none evidence-empty">No {escape(label)} uploaded</div>'


def priority_badge(item: Item) -> str:
    label = "Urgent" if item.priority == Priority.URGENT else "High"
    klass = "urgent" if item.priority == Priority.URGENT else "high"
    return f'<span class="priority-badge priority-{klass}">{escape(label)}</span>'


def signature_block(item: Item) -> str:
    closeout = item.closeout_evidence[0] if item.closeout_evidence else None
    if not closeout:
        return (
            '<div class="sig-block unsigned">'
            '<div class="sig-label">Sign-off</div>'
            '<div class="sig-empty">Awaiting supervisor sign-off</div>'
            "</div>"
        )
    signed_at = format_field_date(closeout.at)
    note = closeout.confirmation or closeout.note
    note_html = f'<div class="sig-note">{escape(note)}</div>' if note else ""
    sig_img = ""
    if closeout.photo:
        img = image_html(closeout.photo, f"{item.code} signature")
        if img:
            sig_img = f'<div class="sig-image">{img}</div>'
    return (
        f'<div class="sig-block signed">'
        f'<div class="sig-label">Sign-off</div>'
        f'<div class="sig-body">{sig_img}'
        f'<div class="sig-detail"><div class="sig-name">{escape(closeout.by)}</div>'
        f'<div class="sig-role">{escape(closeout.role)}</div>'
        f'<div class="sig-date">{escape(signed_at)}</div></div></div>'
        f"{note_html}</div>"
    )


def audit_line(item: Item) -> str:
    updated = format_field_date(item.updated_at)
    detail = f"Last updated {escape(updated)}"
    if item.audit_events:
        latest = item.audit_events[-1]
        action = latest.action.replace("_", " ").title()
        by = latest.by or latest.email or "System"
        detail = f"{escape(action)} by {escape(by)} · {escape(format_field_date(latest.at))}"
    return f'<div class="audit-line">{detail}</div>'


def report_summary_counts(items: list[Item]) -> dict[str, int]:
    closed = {ItemStatus.CLOSED, ItemStatus.COMPLETE}
    issued = {ItemStatus.OPEN, ItemStatus.ISSUED, ItemStatus.IN_PROGRESS}
    ready = {ItemStatus.READY_FOR_REVIEW, ItemStatus.UNDER_INSPECTION}
    return {
        "total": len(items),
        "closed": len([i for i in items if i.status in closed]),
        "issued": len([i for i in items if i.status in issued]),
        "ready": len([i for i in items if i.status in ready]),
        "overdue": len([i for i in items if is_overdue(i) or i.status == ItemStatus.REJECTED]),
        "client": len([i for i in items if i.type == "client"]),
    }


def summary_strip_html(counts: dict[str, int]) -> str:
    cells = (
        ("total", "Total"),
        ("closed", "Closed"),
        ("issued", "Issued / In Progress"),
        ("ready", "Ready / Review"),
        ("overdue", "Overdue / Rejected"),
        ("client", "Client Defects"),
    )
    return "".join(
        f'<div class="stat stat-{key}"><div class="num">{counts[key]}</div><div class="lbl">{label}</div></div>'
        for key, label in cells
    )


def report_styles(*, footer_left: str) -> str:
    footer_text = footer_left.replace("\\", "\\\\").replace('"', '\\"')
    return f"""
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@page{{size:A4 portrait;margin:11mm 11mm 14mm}}
@page{{@bottom-left{{content:"{footer_text}";font:800 8px/1.2 Inter,Arial,sans-serif;color:#69747D;letter-spacing:.2px}}@bottom-right{{content:"Page " counter(page);font:800 8px/1.2 Inter,Arial,sans-serif;color:#69747D}}}}
@page:first{{margin-bottom:11mm;@bottom-left{{content:none}}@bottom-right{{content:none}}}}
body{{font-family:Inter,Arial,sans-serif;color:#161A1D;margin:0;background:#ECEFF2;font-size:11px;line-height:1.4}}
.report-actions{{position:sticky;top:0;z-index:5;display:flex;justify-content:flex-end;gap:8px;max-width:210mm;margin:0 auto;padding:10px 12px;background:#ECEFF2}}
.report-actions button{{border:1px solid #B8C0C8;background:#fff;color:#161A1D;border-radius:999px;padding:8px 12px;font-weight:800;font-size:11px;cursor:pointer}}
.report-actions button.share{{background:#1A2332;border-color:#1A2332;color:#fff}}
.report-actions button.print{{background:#18A94F;border-color:#18A94F;color:#fff}}
.report-shell{{max-width:210mm;margin:0 auto;background:#fff;border:1px solid #D5DCE3;padding:10mm 11mm 8mm}}
.title-block{{border-bottom:2px solid #20C55E;padding-bottom:8px;margin-bottom:10px;max-height:42mm;overflow:hidden}}
.title-row{{display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:start}}
.brand-col{{min-width:0}}
.logo{{display:flex;align-items:center;gap:8px}}
.mark{{width:30px;height:30px;flex:0 0 auto}}
.mark svg{{width:30px;height:30px;display:block}}
.word,h1,h2,h3,.code,.num{{font-family:Archivo,Arial,sans-serif}}
.word{{font-size:18px;font-weight:800;line-height:1;white-space:nowrap}}
.word b{{color:#20C55E}}
.tag{{color:#69747D;font-size:8px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-top:4px;line-height:1.2}}
.title-col{{min-width:0;padding-top:2px}}
h1{{margin:0;font-size:22px;line-height:1.05;color:#1A2332;font-weight:800}}
.report-type{{color:#52606D;font-size:10px;font-weight:700;margin-top:3px;line-height:1.25}}
.meta-col{{text-align:right;font-size:9px;line-height:1.35;color:#52606D;min-width:120px}}
.meta-col strong{{display:block;color:#161A1D;font-size:10px;margin-bottom:2px}}
.meta-kv{{margin-top:1px}}
.meta-kv .k{{color:#8B929C;font-weight:700;text-transform:uppercase;font-size:7px;letter-spacing:.35px}}
.meta-kv .v{{color:#161A1D;font-weight:700}}
.summary-strip{{display:grid;grid-template-columns:repeat(6,1fr);gap:5px;margin-top:8px}}
.stat{{background:#F7F9FA;border:1px solid #DDE3E8;border-left:3px solid #52606D;padding:5px 6px;border-radius:4px;min-width:0}}
.stat-total{{border-left-color:#1A2332}}
.stat-closed{{border-left-color:#18A94F}}
.stat-issued{{border-left-color:#C27803}}
.stat-ready{{border-left-color:#1D4ED8}}
.stat-overdue{{border-left-color:#B42318}}
.num{{font-size:18px;font-weight:800;line-height:1;color:#161A1D}}
.lbl{{font-size:7px;color:#69747D;text-transform:uppercase;letter-spacing:.35px;font-weight:800;margin-top:2px;line-height:1.15}}
.doc-note{{color:#69747D;font-size:9px;margin:0 0 10px;line-height:1.35}}
.report-section{{margin-top:12px}}
.group h3{{color:#1A2332;font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.45px;border-bottom:1px solid #C8D0D8;padding-bottom:3px;margin:10px 0 6px}}
.item{{border:1px solid #D5DCE3;border-left:4px solid #B8C0C8;border-radius:4px;padding:8px 9px;margin-top:6px;background:#fff;break-inside:avoid;page-break-inside:avoid}}
.item.status-closed,.item.status-complete{{border-left-color:#18A94F}}
.item.status-rejected{{border-left-color:#B42318}}
.item.status-ready-for-review,.item.status-under-inspection{{border-left-color:#1D4ED8}}
.item.status-overdue{{border-left-color:#B42318}}
.item.status-issued{{border-left-color:#D99A21}}
.item.status-in-progress{{border-left-color:#C27803}}
.item.status-open{{border-left-color:#8B929C}}
.item-head{{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;break-after:avoid;page-break-after:avoid}}
.item-head-main{{display:flex;align-items:flex-start;gap:8px;min-width:0;flex:1}}
.code{{font-size:14px;font-weight:800;line-height:1;color:#1A2332}}
.type{{color:#69747D;font-size:8px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;margin-top:2px}}
.status-badge{{font-size:8px;font-weight:900;padding:3px 6px;border:1px solid #DDE3E8;background:#F4F6F8;text-transform:uppercase;border-radius:999px;white-space:nowrap;flex:0 0 auto}}
.status-badge.status-open{{background:#F4F6F8;color:#52606D;border-color:#DDE3E8}}
.status-badge.status-ready-for-review,.status-badge.status-under-inspection{{background:#E8F0FF;color:#1D4ED8;border-color:#BFD4FF}}
.status-badge.status-in-progress{{background:#FFF0E0;color:#9A4A00;border-color:#F0D0A8}}
.status-badge.status-overdue{{background:#FDECEC;color:#8B1E1E;border-color:#F5C2C2}}
.status-badge.status-closed,.status-badge.status-complete{{background:#EAFBF1;color:#0B6E36;border-color:#BFE8D0}}
.status-badge.status-issued{{background:#FFF4DF;color:#8A5A00;border-color:#F0D7A4}}
.status-badge.status-rejected{{background:#FDECEC;color:#8B1E1E;border-color:#F5C2C2}}
.priority-badge{{font-size:7px;font-weight:900;padding:2px 5px;border:1px solid #DDE3E8;text-transform:uppercase;border-radius:999px;white-space:nowrap;flex:0 0 auto;align-self:flex-start}}
.priority-badge.priority-high{{background:#F4F6F8;color:#52606D;border-color:#DDE3E8}}
.priority-badge.priority-urgent{{background:#FDECEC;color:#8B1E1E;border-color:#F5C2C2}}
.register-line{{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;color:#52606D;font-size:9px;margin-top:6px;break-after:avoid;page-break-after:avoid}}
.register-line span{{background:#F7F9FA;border:1px solid #E4E9ED;padding:4px 5px;border-radius:3px;line-height:1.25}}
.meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:5px;break-after:avoid;page-break-after:avoid}}
.meta-cell{{background:#F7F9FA;border:1px solid #E4E9ED;border-radius:3px;padding:4px 5px;min-width:0}}
.meta-label{{display:block;font-size:7px;font-weight:800;text-transform:uppercase;letter-spacing:.35px;color:#8B929C;line-height:1.1}}
.meta-value{{display:block;font-size:10px;font-weight:700;color:#161A1D;line-height:1.25;margin-top:1px}}
.desc{{font-size:11px;margin:6px 0;line-height:1.45;color:#161A1D;break-after:avoid;page-break-after:avoid}}
.evidence-matrix{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px;break-inside:avoid;page-break-inside:avoid}}
.evidence-col{{min-width:0;border:1px solid #E4E9ED;border-radius:4px;padding:5px;background:#FAFBFC;break-inside:avoid;page-break-inside:avoid}}
.evidence-col-head{{font-size:8px;font-weight:900;text-transform:uppercase;letter-spacing:.4px;color:#52606D;margin:0 0 4px;padding-bottom:3px;border-bottom:1px solid #DDE3E8}}
.evidence-col.original-col .evidence-col-head{{border-bottom-color:#1A2332;color:#1A2332}}
.evidence-col.closeout-col .evidence-col-head{{border-bottom-color:#18A94F;color:#0B6E36}}
.rect-stage-note{{font-size:8px;color:#69747D;margin-top:5px;padding-top:4px;border-top:1px dashed #DDE3E8;line-height:1.3}}
.evidence-pack{{display:flex;flex-direction:column;gap:7px;margin-top:6px}}
.evidence-block{{break-inside:avoid;page-break-inside:avoid}}
.evidence-block.is-empty{{display:flex;flex-wrap:wrap;align-items:baseline;gap:5px;padding:1px 0}}
.evidence-block.is-empty .evidence-title{{margin:0;padding:0;border:0;display:inline;flex:0 0 auto}}
.evidence-block.is-empty .evidence-empty{{padding:0;border:0;background:transparent;font-size:8px;display:inline;color:#8B929C}}
.evidence-title{{color:#69747D;font-size:8px;font-weight:900;text-transform:uppercase;letter-spacing:.4px;margin:0 0 4px;padding-bottom:3px;border-bottom:1px solid #DDE3E8}}
.evidence-block.original .evidence-title{{border-bottom-color:#1A2332}}
.evidence-block.rectification .evidence-title{{border-bottom-color:#C27803}}
.evidence-block.closeout .evidence-title{{border-bottom-color:#18A94F}}
.project-block{{margin-top:14px;break-inside:avoid;page-break-inside:avoid}}
.project-heading{{font-size:15px;color:#1A2332;border-bottom:2px solid #20C55E;padding-bottom:4px;margin:0 0 8px;font-weight:800}}
.photo-stack{{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start;break-inside:avoid;page-break-inside:avoid}}
.photo-stack.multi .photo{{flex:1 1 calc(50% - 4px);max-width:calc(50% - 4px);min-width:min(100%,160px)}}
.photo{{background:#fff;border:1px solid #DDE3E8;padding:4px;font-size:8px;border-radius:4px;break-inside:avoid;page-break-inside:avoid;display:block;max-width:100%}}
.photo.landscape{{max-width:52%}}
.photo.portrait{{max-width:38%}}
.photo img{{display:block;width:100%;height:auto;max-height:235px;object-fit:contain;object-position:center;background:transparent;border-radius:3px;margin-bottom:3px;break-inside:avoid;page-break-inside:avoid}}
.photo-stack.multi .photo.landscape,.photo-stack.multi .photo.portrait{{max-width:calc(50% - 4px)}}
.photo-stack.multi .photo img{{max-height:210px}}
.photo.compact{{flex:0 0 auto;max-width:72px;padding:3px}}
.photo.compact img{{max-height:52px;margin-bottom:2px}}
.photo-thumb-row{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}
.photo.seed{{background:#fff}}
.by,.time{{color:#69747D;font-size:7px;margin-top:1px;line-height:1.2}}
.cap{{font-weight:700;color:#52606D;line-height:1.2}}
.none{{color:#69747D;font-size:9px;border:1px dashed #C8D0D8;background:#FAFBFC;padding:6px;border-radius:3px}}
.none.evidence-empty{{padding:0;border:0;background:transparent;font-size:8px;color:#8B929C}}
.none.block{{padding:8px;background:#F7F9FA;border-radius:4px;border:1px solid #E4E9ED}}
.sig-block{{border:1px solid #DDE3E8;border-radius:4px;padding:6px 8px;margin-top:7px;min-height:22mm;max-height:32mm;break-inside:avoid;page-break-inside:avoid;display:flex;flex-direction:column;justify-content:center}}
.sig-block.signed{{border-color:#BFE8D0;background:#F8FDFA;border-left:3px solid #18A94F}}
.sig-block.unsigned{{background:#FAFBFC}}
.sig-label{{font-size:7px;font-weight:900;text-transform:uppercase;letter-spacing:.4px;color:#69747D;margin-bottom:4px}}
.sig-body{{display:flex;align-items:center;gap:8px}}
.sig-image{{flex:0 0 auto}}
.sig-image img{{display:block;max-height:16mm;max-width:42mm;width:auto;height:auto;object-fit:contain}}
.sig-detail{{min-width:0}}
.sig-name{{font-size:10px;font-weight:800;color:#0B6E36;line-height:1.2}}
.sig-role{{font-size:8px;color:#52606D;margin-top:1px}}
.sig-date{{font-size:7px;color:#69747D;margin-top:2px}}
.sig-note{{font-size:8px;color:#52606D;margin-top:4px;line-height:1.25}}
.sig-empty{{font-size:9px;color:#8B929C;font-style:italic}}
.meta-line{{display:flex;gap:4px;align-items:center;margin-top:6px;flex-wrap:wrap;border-top:1px solid #EEF1F4;padding-top:5px}}
.audit-line{{font-size:7px;color:#8B929C;margin-top:4px;line-height:1.25}}
.ev{{font-size:7px;font-weight:900;padding:2px 5px;border:1px solid #DDE3E8;background:#fff;text-transform:uppercase;border-radius:999px}}
.ev.closeout{{background:#EAFBF1;border-color:#BFE8D0}}
.ev.rectification{{background:#FFF4DF;border-color:#F0D7A4}}
.ev.original{{background:#F4F6F8}}
.due{{margin-left:auto;font-size:8px;color:#69747D;font-weight:800}}
.due.overdue{{color:#B42318}}
.footer{{margin-top:14px;padding-top:8px;border-top:1px solid #DDE3E8;text-align:center;color:#69747D;font-size:8px;letter-spacing:.35px;font-weight:800}}
@media (max-width:520px){{
.title-row{{grid-template-columns:1fr;gap:8px}}
.meta-col{{text-align:left}}
.summary-strip{{grid-template-columns:repeat(3,1fr)}}
.evidence-matrix{{grid-template-columns:1fr}}
.photo.landscape,.photo.portrait,.photo-stack.multi .photo{{max-width:100%;flex-basis:100%}}
}}
@media print{{
body{{background:#fff}}
.report-actions{{display:none}}
.report-shell{{border:0;padding:0;max-width:none}}
.title-block{{max-height:none;overflow:visible}}
.item,.evidence-matrix,.evidence-col,.evidence-block,.photo-stack,.photo,.photo img,.sig-block{{break-inside:avoid;page-break-inside:avoid}}
.item-head,.register-line,.desc{{break-after:avoid;page-break-after:avoid}}
.photo img{{max-height:62mm}}
.photo-stack.multi .photo img{{max-height:58mm}}
.photo.landscape{{max-width:50%}}
.photo.portrait{{max-width:40%}}
.photo-stack.multi .photo{{max-width:calc(50% - 3mm)}}
.item{{margin-top:5px}}
.footer{{display:none}}
}}
""".strip()


def meta_cell(label: str, value: str) -> str:
    return f'<div class="meta-cell"><span class="meta-label">{escape(label)}</span><span class="meta-value">{escape(value)}</span></div>'


def item_metadata_grid(item: Item) -> str:
    closed_date = ""
    if item.status in CLOSED_STATUSES:
        if item.closeout_evidence and item.closeout_evidence[0].at:
            closed_date = format_field_date(item.closeout_evidence[0].at)
        elif item.updated_at:
            closed_date = format_field_date(item.updated_at)
    cells = [
        meta_cell("Location", location(item)),
        meta_cell("Trade", item.trade or "—"),
        meta_cell("Subcontractor", item.subcontractor or "Unassigned"),
        meta_cell("Due", format_field_date(item.due_date)),
        meta_cell("Captured", format_field_date(item.created_at)),
    ]
    if closed_date:
        cells.append(meta_cell("Closed", closed_date))
    return f'<div class="meta-grid">{"".join(cells)}</div>'


def original_evidence_column(item: Item) -> str:
    photos = item.original_photos
    if not photos:
        return empty_evidence("original evidence")
    primary = photo_cell(photos[0], alt=f"{item.code} original evidence", at=item.created_at)
    extras = photos[1:]
    thumbs = ""
    if extras:
        thumb_cells = "".join(
            photo_cell(p, alt=f"{item.code} original evidence", at=item.created_at, compact=True) for p in extras
        )
        thumbs = f'<div class="photo-thumb-row">{thumb_cells}</div>'
    return primary + thumbs


def closeout_rectification_column(item: Item) -> tuple[str, str]:
    closeout_cells = [
        photo_cell(e.photo, e.confirmation or e.note, f"{e.by} ({e.role})", alt=f"{item.code} closeout evidence", at=e.at)
        for e in item.closeout_evidence
        if e.photo or e.note or e.confirmation
    ]
    rect_cells = [
        photo_cell(e.photo, e.comment, e.by, alt=f"{item.code} rectification evidence", at=e.at)
        for e in item.rectification_evidence
        if e.photo or e.comment
    ]
    rect_note = ""
    if closeout_cells:
        body = photo_stack(*closeout_cells)
        if rect_cells:
            rect_note = (
                f'<div class="rect-stage-note">Rectification evidence on file '
                f"({len(item.rectification_evidence)} record{'s' if len(item.rectification_evidence) != 1 else ''})</div>"
            )
        return body, rect_note
    if rect_cells:
        return photo_stack(*rect_cells), ""
    return empty_evidence("closeout evidence"), ""


def evidence_matrix_html(item: Item) -> str:
    original = original_evidence_column(item)
    closeout_body, rect_note = closeout_rectification_column(item)
    return (
        f'<div class="evidence-matrix">'
        f'<div class="evidence-col original-col"><div class="evidence-col-head">Initial / Original Photo</div>{original}</div>'
        f'<div class="evidence-col closeout-col"><div class="evidence-col-head">Closeout / Rectification Photo</div>{closeout_body}{rect_note}</div>'
        f"</div>"
    )


def title_block_html(
    *,
    heading: str,
    report_title: str,
    settings: Settings,
    meta_project: str,
    generated: str,
    counts: dict[str, int],
    scope_note: str,
) -> str:
    return f"""
    <section class="title-block">
      <div class="title-row">
        <div class="brand-col"><div class="logo">{brand_mark()}</div><div class="tag">Construction closeout evidence register</div></div>
        <div class="title-col">
          <h1>{escape(heading)}</h1>
          <div class="report-type">Defect Rectification / Closeout Register · {escape(report_title)}{escape(scope_note)}</div>
        </div>
        <div class="meta-col">
          <strong>{escape(settings.company)}</strong>
          <div class="meta-kv"><span class="k">Project</span> <span class="v">{escape(meta_project)}</span></div>
          <div class="meta-kv"><span class="k">Generated</span> <span class="v">{escape(generated)}</span></div>
          <div class="meta-kv"><span class="k">Prepared by</span> <span class="v">{escape(settings.prepared_by)}</span></div>
        </div>
      </div>
      <div class="summary-strip">{summary_strip_html(counts)}</div>
    </section>
    <p class="doc-note">Formal defect rectification evidence pack — original issue, trade rectification, and supervisor sign-off in sequence.</p>"""


def item_card(item: Item) -> str:
    overdue = is_overdue(item)
    status_class = "overdue" if overdue else str(item.status).replace("_", "-")
    status_label = "Overdue" if overdue else STATUS_LABEL[item.status]
    overdue_class = " overdue" if is_overdue(item) else ""
    return f"""
    <article class="item status-{escape(status_class)}">
      <div class="item-head">
        <div class="item-head-main">
          <div><div class="code">{escape(item.code)}</div><div class="type">{escape(TYPE_LABEL[item.type])}</div></div>
          {priority_badge(item)}
        </div>
        <span class="status-badge status-{escape(status_class)}">{escape(status_label)}</span>
      </div>
      {item_metadata_grid(item)}
      <div class="desc">{escape(item.description)}</div>
      {evidence_matrix_html(item)}
      {signature_block(item)}
      <div class="meta-line">{evidence_badge('Original', len(item.original_photos), 'original')}{evidence_badge('Rectification', len(item.rectification_evidence), 'rectification')}{evidence_badge('Closeout', len(item.closeout_evidence), 'closeout')}<span class="due{overdue_class}">Due {escape(format_field_date(item.due_date))}</span></div>
      {audit_line(item)}
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
        '<svg viewBox="0 0 100 100" width="30" height="30">'
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
    counts = report_summary_counts(filtered)
    generated = format_field_date(date.today().isoformat())
    heading = report_scope_heading(project_scope, settings, report_type)
    meta_project = report_scope_meta(project_scope, settings)
    scope_note = f" · {len(project_scope)} projects" if len(project_scope) > 1 else ""
    body_html = build_scoped_body(title, filtered, report_type, project_scope)
    display_title = title
    if subcontractor:
        display_title = f"{title} - {subcontractor}"
    share_filename = report_share_filename(settings, report_type, projects=project_scope)
    footer_left = f"CleanRun IQ · {meta_project} · {display_title}"
    styles = report_styles(footer_left=footer_left)
    cover = title_block_html(
        heading=heading,
        report_title=display_title,
        settings=settings,
        meta_project=meta_project,
        generated=generated,
        counts=counts,
        scope_note=scope_note,
    )
    return f"""<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>{escape(display_title)}</title><style>
{styles}
</style></head><body data-share-file="{escape(share_filename)}" data-app-return="/?route=reports"><div class="report-actions"><button type="button" onclick="returnToReports()">Return to reports</button><button type="button" class="share" onclick="shareReport()">Share Report</button><button type="button" class="print" onclick="window.print()">Print Report</button></div><div class="report-shell">{cover}{body_html}<div class="footer">CleanRun IQ · {escape(meta_project)} · {escape(display_title)} · Generated {escape(generated)}</div></div><script>{RETURN_REPORTS_SCRIPT}{SHARE_REPORT_SCRIPT}{PHOTO_ORIENTATION_SCRIPT}</script></body></html>"""
