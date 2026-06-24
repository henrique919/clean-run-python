import {
  CODE_PREFIX,
  ESCALATION_DAYS,
  Item,
  ItemStatus,
  ItemType,
  STATUS_LABEL,
  TYPE_LABEL,
} from "@/types/models";

export function makeId(): string {
  return (
    (globalThis as { crypto?: { randomUUID?: () => string } }).crypto?.randomUUID?.() ??
    `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  );
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function addDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function nextCode(items: Item[], type: ItemType): string {
  const prefix = CODE_PREFIX[type];
  const max = items
    .filter((i) => i.code?.startsWith(`${prefix}-`))
    .map((i) => parseInt(i.code.slice(prefix.length + 1), 10))
    .filter((n) => Number.isFinite(n))
    .reduce((a, b) => Math.max(a, b), 0);
  return `${prefix}-${String(max + 1).padStart(3, "0")}`;
}

export function itemTypeLabel(type: ItemType): string {
  return TYPE_LABEL[type] ?? "Item";
}

export function statusLabel(status: ItemStatus): string {
  return STATUS_LABEL[status] ?? status;
}

export function formatLocation(
  item: Pick<Item, "building" | "level" | "unit" | "room">,
): string {
  return (
    [item.building, item.level, item.unit, item.room].filter(Boolean).join(" · ") ||
    "Location not set"
  );
}

export function isOverdue(item: Item): boolean {
  if (item.status === "closed" || item.status === "complete") return false;
  return item.dueDate < todayISO();
}

export function isDueSoon(item: Item): boolean {
  if (item.status === "closed" || item.status === "complete") return false;
  if (isOverdue(item)) return false;
  const due = new Date(item.dueDate).getTime();
  const days = (due - Date.now()) / 86400000;
  return days >= 0 && days <= 2;
}

export function daysInProgress(item: Item): number {
  if (!item.inProgressAt) return 0;
  if (item.status === "closed" || item.status === "complete") return 0;
  const ms = Date.now() - new Date(item.inProgressAt).getTime();
  return Math.floor(ms / 86400000);
}

export function isEscalated(item: Item): boolean {
  return item.status === "in_progress" && daysInProgress(item) > ESCALATION_DAYS;
}

export function requiresCloseoutEvidence(type: ItemType): boolean {
  return type === "defect" || type === "client";
}

/** Derived field flags surfaced across cards, lists and the dashboard. */
export function derivedFlags(item: Item): string[] {
  const flags: string[] = [];
  if (isOverdue(item)) flags.push("Overdue");
  else if (isDueSoon(item)) flags.push("Due Soon");
  if (item.status === "issued" || item.status === "in_progress")
    flags.push("Waiting on Subcontractor");
  if (item.status === "ready_for_review") flags.push("Ready for Inspection");
  if (
    requiresCloseoutEvidence(item.type) &&
    item.status === "under_inspection" &&
    item.closeoutEvidence.length === 0
  )
    flags.push("Needs Evidence");
  return flags;
}

export function nextActionLabel(status: ItemStatus): string {
  switch (status) {
    case "open":
      return "Issue to subcontractor";
    case "issued":
      return "Mark in progress";
    case "in_progress":
      return "Mark ready for review";
    case "ready_for_review":
      return "Start inspection";
    case "under_inspection":
      return "Close with evidence";
    case "rejected":
      return "Re-issue";
    case "closed":
    case "complete":
      return "Closed";
  }
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
