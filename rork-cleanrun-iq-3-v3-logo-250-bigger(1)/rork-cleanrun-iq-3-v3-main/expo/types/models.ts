/**
 * CleanRun IQ domain model — ported from the clean-run-3/update-1 web product.
 * Items represent Defects, Incomplete Works and Client Defects with a disciplined
 * workflow and three separate evidence chains.
 */

export type ItemType = "defect" | "incomplete" | "client";

export type ItemStatus =
  | "open"
  | "issued"
  | "in_progress"
  | "ready_for_review"
  | "under_inspection"
  | "rejected"
  | "closed"
  | "complete";

export type Priority = "high" | "urgent";

export const ESCALATION_DAYS = 10;

export const RAISED_BY_OPTIONS = [
  "Client PM",
  "Superintendent",
  "Consultant",
  "Architect",
  "Buyer",
  "Other",
] as const;

/** Subcontractor-supplied evidence of rectification. */
export interface RectificationEvidence {
  id: string;
  photo?: string;
  comment?: string;
  by: string;
  at: string;
}

/** Site-team closeout evidence. Multiple entries supported. */
export interface CloseoutEvidence {
  id: string;
  photo?: string;
  by: string;
  role: string;
  note?: string;
  confirmation?: string;
  at: string;
}

export interface Comment {
  id: string;
  text: string;
  by: string;
  at: string;
}

export interface IssueEvent {
  at: string;
  by?: string;
  to: string;
  note?: string;
  reissue?: boolean;
}

export interface InspectionEvent {
  at: string;
  by: string;
  action: "started" | "accepted" | "rejected";
  reason?: string;
}

export interface AuditEvent {
  at: string;
  action: string;
  by?: string;
  note?: string;
}

/** Local-first sync state for offline field use. */
export type SyncState = "synced" | "pending" | "offline" | "failed";

export interface Item {
  id: string;
  code: string;
  type: ItemType;
  project: string;
  building: string;
  level: string;
  unit: string;
  room: string;
  trade: string;
  subcontractor: string;
  priority: Priority;
  dueDate: string;
  description: string;
  status: ItemStatus;
  createdAt: string;
  updatedAt: string;
  createdBy?: string;

  /** Photos taken by the site team when first raising the item. */
  originalPhotos: string[];
  /** Photos/notes uploaded by the subcontractor as evidence of rectification. */
  rectificationEvidence: RectificationEvidence[];
  /** Photos & sign-off entered by site team when closing. */
  closeoutEvidence: CloseoutEvidence[];
  comments: Comment[];
  issueHistory: IssueEvent[];
  inspectionHistory: InspectionEvent[];
  auditEvents: AuditEvent[];

  /** Client Defects: who raised the issue. */
  raisedBy?: string;
  /** Raw voice transcript when the item was captured via Voice-to-Note. */
  voiceTranscript?: string;

  /** Structured voice note record (preferred over raw voiceTranscript). */
  voiceNote?: VoiceNote;

  issuedAt?: string;
  inProgressAt?: string;
  readyForReviewAt?: string;
  underInspectionAt?: string;
  closedAt?: string;
  rejectionReason?: string;

  /** Local-first sync state. */
  sync: SyncState;
}

/** Per-subcontractor profile stored under Settings. */
export interface SubProfile {
  name: string;
  trade?: string;
  contact?: string;
  email?: string;
  phone?: string;
}

/** Per-project setup defaults. */
export interface ProjectConfig {
  name: string;
  address?: string;
  buildings: string[];
  levels: string[];
  units: string[];
  rooms: string[];
  defaultDueDays: number;
}

export interface Settings {
  projects: string[];
  projectConfigs: Record<string, ProjectConfig>;
  subcontractors: string[];
  subProfiles: Record<string, SubProfile>;
  activeProject: string;
  company: string;
  preparedBy: string;
}

export interface PlanPin {
  id: string;
  /** Normalised 0..1 coordinates relative to the image. */
  x: number;
  y: number;
  itemId?: string;
  label?: string;
}

export interface VoiceNote {
  transcript: string;
  audioUri?: string;
  parsedFields?: Record<string, unknown>;
  createdAt: string;
  status: "recorded" | "transcribed" | "parsed" | "failed";
}

export interface Plan {
  id: string;
  project: string;
  building: string;
  level: string;
  name: string;
  image: string;
  pins: PlanPin[];
  createdAt: string;
}

export const TRADES = [
  "Painting",
  "Plastering",
  "Tiling",
  "Waterproofing",
  "Joinery",
  "Doors / Hardware",
  "Windows / Aluminium",
  "Flooring",
  "Roofing",
  "Cladding",
  "Electrical",
  "Hydraulic",
  "Mechanical",
  "Fire Services",
  "Cleaning",
  "Landscaping",
  "Concrete",
  "Render",
  "Caulking / Sealant",
  "General Damage",
];

export const STATUS_LABEL: Record<ItemStatus, string> = {
  open: "Open",
  issued: "Issued",
  in_progress: "In Progress",
  ready_for_review: "Ready for Review",
  under_inspection: "Under Inspection",
  rejected: "Rejected",
  closed: "Closed",
  complete: "Complete",
};

export const TYPE_LABEL: Record<ItemType, string> = {
  defect: "Defect",
  incomplete: "Incomplete Work",
  client: "Client Defect",
};

export const CODE_PREFIX: Record<ItemType, string> = {
  defect: "DEF",
  incomplete: "INC",
  client: "CLD",
};
