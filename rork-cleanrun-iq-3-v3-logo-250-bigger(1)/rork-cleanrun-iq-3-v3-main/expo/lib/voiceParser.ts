import { ItemType, Priority, TRADES } from "@/types/models";
import { addDays, todayISO } from "@/lib/format";

/**
 * Structured fields extracted from a spoken site note. Anything the parser is
 * not confident about is left undefined so the user fills it in manually.
 */
export interface ParsedFields {
  type?: ItemType;
  building?: string;
  level?: string;
  unit?: string;
  room?: string;
  title?: string;
  description?: string;
  trade?: string;
  subcontractor?: string;
  priority?: Priority;
  dueDate?: string;
  raisedBy?: string;
}

const NUMBER_WORDS: Record<string, number> = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  ground: 0,
};

const ROOM_KEYWORDS = [
  "bathroom",
  "ensuite",
  "kitchen",
  "living",
  "laundry",
  "balcony",
  "hallway",
  "garage",
  "bedroom",
  "lobby",
  "lounge",
  "dining",
  "toilet",
  "wc",
  "pantry",
  "stairwell",
  "corridor",
];

const TRADE_HINTS: { match: string[]; trade: string }[] = [
  { match: ["paint"], trade: "Painting" },
  { match: ["plaster", "render"], trade: "Plastering" },
  { match: ["tile", "tiler", "tiling", "grout"], trade: "Tiling" },
  { match: ["waterproof", "membrane", "leak", "seal"], trade: "Waterproofing" },
  { match: ["joinery", "cabinet", "cabinetry", "bench"], trade: "Joinery" },
  { match: ["door", "hardware", "hinge", "lock"], trade: "Doors / Hardware" },
  { match: ["window", "glaz", "glass", "aluminium", "aluminum"], trade: "Windows / Aluminium" },
  { match: ["floor", "carpet", "timber floor", "vinyl"], trade: "Flooring" },
  { match: ["roof", "gutter"], trade: "Roofing" },
  { match: ["clad", "facade"], trade: "Cladding" },
  { match: ["electric", "power point", "gpo", "light", "switch"], trade: "Electrical" },
  { match: ["plumb", "hydraulic", "tap", "basin", "drain", "pipe"], trade: "Hydraulic" },
  { match: ["mechanical", "hvac", "air con", "aircon", "duct"], trade: "Mechanical" },
  { match: ["fire", "sprinkler", "smoke"], trade: "Fire Services" },
  { match: ["clean", "overspray"], trade: "Cleaning" },
  { match: ["landscap", "garden", "turf"], trade: "Landscaping" },
  { match: ["concrete", "slab"], trade: "Concrete" },
  { match: ["caulk", "sealant", "silicone"], trade: "Caulking / Sealant" },
];

const URGENT_WORDS = ["urgent", "critical", "immediate", "immediately", "safety", "stop work", "stop-work", "asap", "emergency"];

const CLIENT_WORDS = ["client", "superintendent", "consultant", "architect", "buyer", "owner raised", "client raised", "client-side"];
const INCOMPLETE_WORDS = ["not finished", "unfinished", "incomplete", "missing", "not installed", "pending", "not yet", "outstanding work", "not complete", "yet to"];
const DEFECT_WORDS = ["damaged", "defective", "cracked", "crack", "scratched", "scratch", "broken", "chipped", "leak", "stain", "drummy", "lippage", "faulty"];

const WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

function findRaisedBy(text: string): string | undefined {
  if (text.includes("superintendent")) return "Superintendent";
  if (text.includes("consultant")) return "Consultant";
  if (text.includes("architect")) return "Architect";
  if (text.includes("buyer")) return "Buyer";
  if (text.includes("client pm") || text.includes("client p m")) return "Client PM";
  if (text.includes("client")) return "Client PM";
  return undefined;
}

function detectType(text: string): ItemType | undefined {
  if (CLIENT_WORDS.some((w) => text.includes(w))) return "client";
  if (INCOMPLETE_WORDS.some((w) => text.includes(w))) return "incomplete";
  if (DEFECT_WORDS.some((w) => text.includes(w))) return "defect";
  return undefined;
}

function detectBuilding(text: string): string | undefined {
  // "block b", "building 3", "tower 1"
  const block = text.match(/\bblock\s+([a-z0-9]+)/);
  if (block) return `Block ${block[1].toUpperCase()}`;
  const tower = text.match(/\btower\s+([a-z0-9]+)/);
  if (tower) return `Tower ${tower[1].toUpperCase()}`;
  const building = text.match(/\bbuilding\s+([a-z0-9]+)/);
  if (building) {
    const v = building[1];
    const n = NUMBER_WORDS[v];
    return `Building ${n !== undefined ? n : v.toUpperCase()}`;
  }
  return undefined;
}

function detectLevel(text: string): string | undefined {
  const m = text.match(/\b(?:level|floor|l)\s*([0-9]{1,2})/);
  if (m) return `L${m[1].padStart(2, "0")}`;
  const word = text.match(/\b(?:level|floor)\s+(ground|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)/);
  if (word) {
    const n = NUMBER_WORDS[word[1]];
    if (n !== undefined) return `L${String(n).padStart(2, "0")}`;
  }
  return undefined;
}

function detectUnit(text: string, original: string): string | undefined {
  // unit B-204, unit 301, apartment 12
  const dashed = original.match(/\b([A-Za-z]{1,3}-?\d{2,4})\b/);
  const unitKw = text.match(/\b(?:unit|apartment|apt|lot)\s+([a-z0-9-]+)/);
  if (unitKw) {
    const raw = unitKw[1];
    // try to recover original casing
    const orig = original.match(new RegExp(`(?:unit|apartment|apt|lot)\\s+([A-Za-z0-9-]+)`, "i"));
    return (orig ? orig[1] : raw).toUpperCase();
  }
  if (dashed && /[a-zA-Z]/.test(dashed[1]) && dashed[1].includes("-")) return dashed[1].toUpperCase();
  return undefined;
}

function detectRoom(text: string, original: string): string | undefined {
  for (const kw of ROOM_KEYWORDS) {
    if (text.includes(kw)) {
      const bedroom = text.match(/bedroom\s*([0-9])/);
      if (kw === "bedroom" && bedroom) return `Bedroom ${bedroom[1]}`;
      // capture a leading word e.g. "master ensuite"
      const phrase = original.match(new RegExp(`(master\\s+)?${kw}`, "i"));
      return titleCase((phrase ? phrase[0] : kw).toLowerCase());
    }
  }
  return undefined;
}

function detectTrade(text: string): string | undefined {
  for (const hint of TRADE_HINTS) {
    if (hint.match.some((m) => text.includes(m))) return hint.trade;
  }
  return undefined;
}

function detectDueDate(text: string): string | undefined {
  if (text.includes("today")) return todayISO();
  if (text.includes("tomorrow")) return addDays(1);
  if (text.includes("end of week") || text.includes("eow")) {
    const now = new Date();
    const day = now.getDay();
    const toFriday = (5 - day + 7) % 7 || 5;
    return addDays(toFriday);
  }
  const inDays = text.match(/\bin\s+([0-9]{1,2})\s+days?/);
  if (inDays) return addDays(parseInt(inDays[1], 10));
  for (let i = 0; i < WEEKDAYS.length; i++) {
    if (text.includes(`by ${WEEKDAYS[i]}`) || text.includes(`due ${WEEKDAYS[i]}`) || text.includes(WEEKDAYS[i])) {
      const now = new Date();
      const day = now.getDay();
      const diff = (i - day + 7) % 7 || 7;
      return addDays(diff);
    }
  }
  return undefined;
}

function matchFromList(text: string, original: string, list: string[]): string | undefined {
  // exact / contains match against known subcontractors or trades
  const lower = list.map((l) => ({ raw: l, low: l.toLowerCase() }));
  const direct = lower.find((l) => text.includes(l.low));
  if (direct) return direct.raw;
  // token overlap
  for (const l of lower) {
    const tokens = l.low.split(/\s+/).filter((t) => t.length > 3);
    if (tokens.some((t) => text.includes(t))) return l.raw;
  }
  return undefined;
}

function firstSentence(original: string): string {
  const trimmed = original.trim();
  const m = trimmed.match(/[^.!?]+/);
  const candidate = (m ? m[0] : trimmed).trim();
  return candidate.length > 60 ? candidate.slice(0, 57).trim() + "…" : candidate;
}

/**
 * Deterministic, offline-capable rule-based parser. Used directly as the AI
 * fallback and to enrich any cloud transcription.
 */
export function parseTranscript(
  transcript: string,
  options: { subcontractors: string[] },
): ParsedFields {
  const original = transcript.trim();
  if (!original) return {};
  const text = original.toLowerCase();

  const fields: ParsedFields = {};

  const type = detectType(text);
  if (type) fields.type = type;

  const building = detectBuilding(text);
  if (building) fields.building = building;

  const level = detectLevel(text);
  if (level) fields.level = level;

  const unit = detectUnit(text, original);
  if (unit) fields.unit = unit;

  const room = detectRoom(text, original);
  if (room) fields.room = room;

  const trade = detectTrade(text);
  if (trade && TRADES.includes(trade)) fields.trade = trade;

  const sub = matchFromList(text, original, options.subcontractors);
  if (sub) fields.subcontractor = sub;

  if (URGENT_WORDS.some((w) => text.includes(w))) fields.priority = "urgent";
  else fields.priority = "high";

  const due = detectDueDate(text);
  if (due) fields.dueDate = due;

  if (fields.type === "client") {
    const raisedBy = findRaisedBy(text);
    if (raisedBy) fields.raisedBy = raisedBy;
  }

  fields.title = firstSentence(original);
  fields.description = original;

  return fields;
}
