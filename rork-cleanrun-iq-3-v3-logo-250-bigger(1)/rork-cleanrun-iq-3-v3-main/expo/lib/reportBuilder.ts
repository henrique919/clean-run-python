import { formatDate, formatLocation, isOverdue, statusLabel, itemTypeLabel } from "@/lib/format";
import { Item, Settings } from "@/types/models";

export type ReportType =
  | "open"
  | "overdue"
  | "handover"
  | "subcontractor"
  | "client"
  | "incomplete";

export const REPORT_META: Record<ReportType, { title: string; description: string; hero?: boolean }> = {
  handover: {
    title: "Closed / Handover Evidence",
    description: "Full evidence chain: original issue, rectification & closeout sign-off",
    hero: true,
  },
  open: { title: "Open Items", description: "All items not yet closed" },
  overdue: { title: "Overdue Items", description: "Items past their due date" },
  subcontractor: { title: "Subcontractor", description: "Items grouped by responsible trade" },
  client: { title: "Client Defects", description: "Items raised by the client side" },
  incomplete: { title: "Incomplete Works", description: "Work not yet finished" },
};

export function filterForReport(items: Item[], type: ReportType): Item[] {
  switch (type) {
    case "open":
      return items.filter((i) => i.status !== "closed" && i.status !== "complete");
    case "overdue":
      return items.filter((i) => isOverdue(i));
    case "handover":
      // Return all items so the report can show closed/complete evidence
      // alongside rejected/outstanding items in a separate section.
      return [...items].sort((a, b) => {
        const rank = (s: string) => (s === "closed" || s === "complete" ? 0 : 1);
        return rank(a.status) - rank(b.status) || b.updatedAt.localeCompare(a.updatedAt);
      });
    case "subcontractor":
      return [...items].sort((a, b) => a.subcontractor.localeCompare(b.subcontractor));
    case "client":
      return items.filter((i) => i.type === "client");
    case "incomplete":
      return items.filter((i) => i.type === "incomplete");
  }
}

interface Group {
  key: string;
  items: Item[];
}

/** Group items by Building → Level for report rendering. */
export function groupByLocation(items: Item[]): Group[] {
  const map = new Map<string, Item[]>();
  for (const item of items) {
    const key = `${item.building || "Unassigned"} · ${item.level || "—"}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return Array.from(map.entries())
    .map(([key, list]) => ({ key, items: list }))
    .sort((a, b) => a.key.localeCompare(b.key));
}

function esc(s: string): string {
  return (s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function evidenceChip(label: string, count: number, color: string): string {
  return `<span class="ev" style="background:${color}1a;color:${color}">${label}: ${count}</span>`;
}

/**
 * Build a polished, print-ready HTML report. Evidence is kept in three distinct
 * columns — original issue, rectification, closeout — which is the CleanRun IQ
 * differentiator. Photos are referenced by URI; seed photos render as labels.
 */
export function buildReportHtml(
  items: Item[],
  type: ReportType,
  settings: Settings,
  bannerDataUri: string,
): string {
  const meta = REPORT_META[type];
  const groups = groupByLocation(items);
  const now = new Date();
  const closedComplete = items.filter((i) => i.status === "closed" || i.status === "complete");
  const outstanding = items.filter((i) => i.status !== "closed" && i.status !== "complete");

  const summary = `
    <div class="summary">
      <div class="stat"><div class="num">${items.length}</div><div class="lbl">Total items</div></div>
      <div class="stat"><div class="num">${items.filter((i) => i.status === "closed" || i.status === "complete").length}</div><div class="lbl">Closed</div></div>
      <div class="stat"><div class="num">${items.filter((i) => isOverdue(i)).length}</div><div class="lbl">Overdue</div></div>
      <div class="stat"><div class="num">${items.filter((i) => i.type === "client").length}</div><div class="lbl">Client defects</div></div>
    </div>`;

  const closedGroups = groupByLocation(closedComplete);
  const groupHtml = closedGroups
    .map((g) => {
      const rows = g.items
        .map((item) => {
          const closeout = item.closeoutEvidence[0];
          return `
          <div class="item">
            <div class="item-head">
              <div>
                <span class="code">${esc(item.code)}</span>
                <span class="type">${esc(itemTypeLabel(item.type))}</span>
              </div>
              <span class="status status-${item.status}">${esc(statusLabel(item.status))}</span>
            </div>
            <div class="loc">${esc(formatLocation(item))} · ${esc(item.trade || "—")} · ${esc(item.subcontractor || "Unassigned")}</div>
            <div class="desc">${esc(item.description)}</div>
            <div class="evidence-cols">
              <div class="col">
                <div class="col-title">Original issue</div>
                ${item.originalPhotos.map((p) => photoCell(p)).join("") || '<div class="none">No photos</div>'}
              </div>
              <div class="col">
                <div class="col-title">Rectification</div>
                ${item.rectificationEvidence.map((e) => photoCell(e.photo, e.comment, e.by)).join("") || '<div class="none">—</div>'}
              </div>
              <div class="col">
                <div class="col-title">Closeout</div>
                ${item.closeoutEvidence.map((e) => photoCell(e.photo, e.note, `${e.by} (${e.role})`)).join("") || '<div class="none">—</div>'}
              </div>
            </div>
            ${closeout ? `<div class="signoff">✓ Signed off by ${esc(closeout.by)} (${esc(closeout.role)}) · ${esc(formatDate(closeout.at))}</div>` : ""}
            <div class="meta-line">${evidenceChip("Original", item.originalPhotos.length, "#0E1F3A")} ${evidenceChip("Rectification", item.rectificationEvidence.length, "#F59E0B")} ${evidenceChip("Closeout", item.closeoutEvidence.length, "#16A34A")} <span class="due ${isOverdue(item) ? "overdue" : ""}">Due ${esc(formatDate(item.dueDate))}</span></div>
          </div>`;
        })
        .join("");
      return `<div class="group"><h2>${esc(g.key)}</h2>${rows}</div>`;
    })
    .join("");

  const outstandingHtml =
    type === "handover" && outstanding.length > 0
      ? `<div class="outstanding"><h2>Outstanding / Rejected (${outstanding.length})</h2>${outstanding
          .map(
            (i) =>
              `<div class="out-row"><span class="code">${esc(i.code)}</span> ${esc(formatLocation(i))} — <strong>${esc(statusLabel(i.status))}</strong>${i.rejectionReason ? ` · ${esc(i.rejectionReason)}` : ""}</div>`,
          )
          .join("")}</div>`
      : "";

  return `<!DOCTYPE html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #0E1B2E; margin: 0; padding: 24px; background: #fff; }
    .header { display:flex; align-items:center; justify-content:space-between; border-bottom: 3px solid #0E1F3A; padding-bottom: 16px; margin-bottom: 16px; }
    .header img { height: 46px; }
    .header .meta { text-align: right; font-size: 12px; color: #5A6B82; }
    h1 { font-size: 22px; margin: 4px 0; color: #0E1F3A; }
    .subtitle { color: #5A6B82; font-size: 13px; margin-bottom: 16px; }
    .summary { display:flex; gap: 12px; margin-bottom: 20px; }
    .stat { flex:1; background:#F4F6F9; border-radius: 12px; padding: 14px; text-align:center; }
    .stat .num { font-size: 26px; font-weight: 800; color:#0E1F3A; }
    .stat .lbl { font-size: 11px; color:#5A6B82; text-transform: uppercase; letter-spacing: .4px; }
    .group { margin-bottom: 18px; }
    .group h2 { font-size: 14px; background:#0E1F3A; color:#fff; padding: 8px 12px; border-radius: 8px; }
    .item { border:1px solid #E3E8F0; border-radius: 12px; padding: 14px; margin-top: 10px; page-break-inside: avoid; }
    .item-head { display:flex; justify-content:space-between; align-items:center; }
    .code { font-weight: 800; font-size: 15px; color:#0E1F3A; }
    .type { font-size: 11px; color:#5A6B82; margin-left: 8px; }
    .status { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; background:#EEF1F6; color:#5A6B82; }
    .status-closed, .status-complete { background:#DCFCE7; color:#15803D; }
    .status-rejected { background:#FEE2E2; color:#B91C1C; }
    .status-in_progress { background:#FEF3C7; color:#B45309; }
    .loc { font-size: 12px; color:#5A6B82; margin-top: 4px; }
    .desc { font-size: 13px; margin: 8px 0; }
    .evidence-cols { display:flex; gap: 10px; margin-top: 8px; }
    .col { flex:1; background:#F8FAFC; border-radius: 8px; padding: 8px; }
    .col-title { font-size: 10px; font-weight:700; text-transform: uppercase; letter-spacing:.4px; color:#5A6B82; margin-bottom: 6px; }
    .photo { border-radius: 6px; padding: 10px; margin-bottom: 6px; font-size: 11px; }
    .photo .cap { color:#334155; }
    .photo .by { color:#64748B; font-size: 10px; margin-top: 2px; }
    .none { font-size: 11px; color:#94A3B8; }
    .signoff { margin-top: 8px; font-size: 12px; color:#15803D; font-weight: 600; }
    .meta-line { margin-top: 8px; display:flex; gap: 6px; align-items:center; }
    .ev { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
    .due { margin-left:auto; font-size: 11px; color:#5A6B82; }
    .due.overdue { color:#B91C1C; font-weight: 700; }
    .outstanding { margin-top: 20px; border-top: 2px solid #FEE2E2; padding-top: 12px; }
    .outstanding h2 { color:#B91C1C; font-size: 14px; }
    .out-row { font-size: 12px; padding: 4px 0; border-bottom: 1px solid #F1F5F9; }
    .footer { margin-top: 24px; text-align:center; font-size: 11px; color:#94A3B8; }
  </style></head><body>
    <div class="header">
      <img src="${bannerDataUri}" alt="CleanRun IQ" style="max-width:200px;"/>
      <div class="meta">
        <div><strong>${esc(settings.company)}</strong></div>
        <div>Generated ${now.toLocaleString()}</div>
        <div>Prepared by ${esc(settings.preparedBy)}</div>
      </div>
    </div>
    <h1>${esc(meta.title)} Report</h1>
    <div class="subtitle">${esc(settings.activeProject)} · ${esc(meta.description)}</div>
    ${summary}
    ${groupHtml || '<div class="none">No items match this report.</div>'}
    ${outstandingHtml}
    <div class="footer">Generated with CleanRun IQ · Capture → Assign → Issue → Inspect → Close with Evidence → Report</div>
  </body></html>`;
}

function photoCell(uri?: string, caption?: string, by?: string): string {
  if (!uri && !caption) return "";
  let bg = "#E7ECF5";
  let label = caption ?? "Photo";
  if (uri && uri.startsWith("seed://")) {
    const rest = uri.slice("seed://".length).split("/");
    const tone = rest[0];
    label = caption ?? decodeURIComponent(rest.slice(1).join("/"));
    bg = { amber: "#FEF3C7", red: "#FEE2E2", green: "#DCFCE7", sky: "#E0F2FE", violet: "#EDE9FE", navy: "#E7ECF5" }[tone] ?? "#E7ECF5";
    return `<div class="photo" style="background:${bg}"><div class="cap">📷 ${esc(label)}</div>${by ? `<div class="by">${esc(by)}</div>` : ""}</div>`;
  }
  if (uri) {
    return `<div class="photo" style="background:${bg};padding:0;overflow:hidden"><img src="${uri}" style="width:100%;display:block"/>${caption ? `<div class="cap" style="padding:6px">${esc(caption)}</div>` : ""}${by ? `<div class="by" style="padding:0 6px 6px">${esc(by)}</div>` : ""}</div>`;
  }
  return `<div class="photo" style="background:${bg}"><div class="cap">${esc(label)}</div>${by ? `<div class="by">${esc(by)}</div>` : ""}</div>`;
}
