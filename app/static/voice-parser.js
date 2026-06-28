/**
 * voice-parser.js — Deterministic voice-to-fields parser for CleanRun IQ.
 * No AI required. Works offline. Import before app.js.
 *
 * Exported (global): window.VoiceParser = { parseVoiceNote }
 */
(function (global) {
  'use strict';

  const NUMBER_WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5,
    six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, ground: 0, oh: 0,
  };

  const ROOM_KEYWORDS = [
    'ensuite', 'bathroom', 'kitchen', 'living', 'laundry', 'balcony',
    'hallway', 'garage', 'lobby', 'lounge', 'dining', 'toilet',
    'wc', 'pantry', 'stairwell', 'corridor', 'entry', 'external',
    'bedroom', 'master bedroom', 'master bathroom',
  ];

  // Order matters: longer/more specific first to avoid partial matches
  const TRADE_HINTS = [
    { matches: ['cabinet maker', 'cabinet-maker', 'cabinetry'], trade: 'Joinery' },
    { matches: ['joinery'], trade: 'Joinery' },
    { matches: ['waterproofer', 'waterproofing', 'waterproof'], trade: 'Waterproofing' },
    { matches: ['plasterer', 'plasterboard', 'plastering'], trade: 'Plastering' },
    { matches: ['renderer', 'rendering', 'render'], trade: 'Render' },
    { matches: ['painter', 'painting'], trade: 'Painting' },
    { matches: ['tiler', 'tiling', 'grout', 'regrout'], trade: 'Tiling' },
    { matches: ['tile'], trade: 'Tiling' },
    { matches: ['paint'], trade: 'Painting' },
    { matches: ['plaster'], trade: 'Plastering' },
    { matches: ['door', 'hardware', 'hinge', 'lock'], trade: 'Doors / Hardware' },
    { matches: ['window', 'glaz', 'glass', 'aluminium', 'aluminum'], trade: 'Windows / Aluminium' },
    { matches: ['carpet', 'timber floor', 'vinyl', 'flooring'], trade: 'Flooring' },
    { matches: ['gutter', 'roofing'], trade: 'Roofing' },
    { matches: ['facade', 'cladding'], trade: 'Cladding' },
    { matches: ['power point', 'gpo', 'electrical', 'electrician'], trade: 'Electrical' },
    { matches: ['hydraulic', 'plumbing', 'plumber', 'tap', 'basin', 'drain', 'pipe'], trade: 'Hydraulic' },
    { matches: ['mechanical', 'hvac', 'air con', 'aircon', 'duct'], trade: 'Mechanical' },
    { matches: ['fire services', 'sprinkler', 'smoke detector'], trade: 'Fire Services' },
    { matches: ['cleaning', 'overspray'], trade: 'Cleaning' },
    { matches: ['landscap', 'garden', 'turf'], trade: 'Landscaping' },
    { matches: ['concrete', 'slab'], trade: 'Concrete' },
    { matches: ['caulk', 'sealant', 'silicone'], trade: 'Caulking / Sealant' },
    { matches: ['floor'], trade: 'Flooring' },
    { matches: ['roof'], trade: 'Roofing' },
    { matches: ['clad'], trade: 'Cladding' },
    { matches: ['electric', 'light switch'], trade: 'Electrical' },
    { matches: ['plumb'], trade: 'Hydraulic' },
  ];

  const URGENT_WORDS = ['urgent', 'critical', 'immediate', 'immediately', 'safety', 'stop work', 'asap', 'emergency'];
  const DEFECT_WORDS = ['damaged', 'defective', 'cracked', 'crack', 'scratched', 'broken', 'chipped', 'leak', 'stain', 'drummy', 'faulty'];
  const INCOMPLETE_WORDS = ['not finished', 'unfinished', 'incomplete', 'missing', 'not installed', 'outstanding work'];
  const CLIENT_WORDS = ['client raised', 'owner raised', 'superintendent', 'consultant', 'architect'];

  function wordToNum(word) {
    return NUMBER_WORDS[word.toLowerCase()] ?? null;
  }

  /**
   * Convert a word-number sequence like "three oh five" to a digit string "305".
   * Returns null if any word is not a number word.
   */
  function parseNumberWords(str) {
    const words = str.trim().toLowerCase().split(/\s+/);
    const nums = words.map(w => NUMBER_WORDS[w]);
    if (nums.some(n => n === undefined || n === null)) return null;
    return nums.map(n => String(n)).join('');
  }

  function detectBuilding(text) {
    let m;
    // "building 3" / "building three" / "bldg 3"
    m = text.match(/\b(?:building|bldg)\s+([a-z0-9]+)/i);
    if (m) {
      const val = m[1].toLowerCase();
      const n = wordToNum(val);
      const num = n != null ? n : (isNaN(Number(val)) ? val.toUpperCase() : Number(val));
      return { value: `Building ${num}`, normalized: `B${num}` };
    }
    // "B3" or "B 3" (uppercase B followed by digits)
    m = text.match(/\bB\s*([0-9]{1,2})\b/);
    if (m) return { value: `B${m[1]}`, normalized: `B${m[1]}` };
    // "B three" / "B two"
    m = text.match(/\bB\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b/i);
    if (m) {
      const n = wordToNum(m[1]);
      if (n != null) return { value: `B${n}`, normalized: `B${n}` };
    }
    // "block B" / "tower 1"
    m = text.match(/\bblock\s+([a-z0-9]+)/i);
    if (m) return { value: `Block ${m[1].toUpperCase()}`, normalized: `Block ${m[1].toUpperCase()}` };
    m = text.match(/\btower\s+([a-z0-9]+)/i);
    if (m) return { value: `Tower ${m[1].toUpperCase()}`, normalized: `Tower ${m[1].toUpperCase()}` };
    return null;
  }

  function detectLevel(text) {
    let m;
    // "level 1" / "l1" / "floor 1" / "lvl 1"
    m = text.match(/\b(?:level|floor|lvl)\s*([0-9]{1,2})\b/i);
    if (m) return `Level ${parseInt(m[1], 10)}`;
    // "level one" / "floor two"
    m = text.match(/\b(?:level|floor)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/i);
    if (m) {
      const n = wordToNum(m[1]);
      return n != null ? `Level ${n}` : null;
    }
    // "ground floor" / "ground level" / bare "ground"
    if (/\bground\s+(?:floor|level)\b/i.test(text) || /\bon\s+ground\b/i.test(text)) return 'Ground';
    return null;
  }

  var NUM_WORD_ALT = '(?:zero|one|two|three|four|five|six|seven|eight|nine|oh)';
  var NUM_WORD_SEQ_RE = new RegExp(
    '\\b(?:unit|apartment|apt|lot)\\s+(' + NUM_WORD_ALT + '(?:\\s+' + NUM_WORD_ALT + ')*)\\b', 'i'
  );

  function detectUnit(text) {
    var m;
    // "unit 305" — pure digits, word-bounded so we don't eat following words
    m = text.match(/\b(?:unit|apartment|apt|lot)\s+([0-9]+)\b/i);
    if (m) return 'U' + m[1];

    // "unit three oh five" — bounded number-word sequence
    m = text.match(NUM_WORD_SEQ_RE);
    if (m) {
      var pw = parseNumberWords(m[1]);
      if (pw) return 'U' + pw;
    }

    // "unit B-204" — single alphanumeric token
    m = text.match(/\b(?:unit|apartment|apt|lot)\s+([A-Za-z0-9-]+)\b/i);
    if (m) return 'U' + m[1].toUpperCase();
    // Bare "U305"
    m = text.match(/\bU([0-9]{2,4})\b/);
    if (m) return `U${m[1]}`;
    return null;
  }

  function detectRoom(text) {
    const lower = text.toLowerCase();
    for (const kw of ROOM_KEYWORDS) {
      if (lower.includes(kw)) {
        const bedMatch = lower.match(/bedroom\s*([0-9])/);
        if (kw === 'bedroom' && bedMatch) return `Bedroom ${bedMatch[1]}`;
        return kw.charAt(0).toUpperCase() + kw.slice(1);
      }
    }
    return null;
  }

  function detectTrade(text) {
    const lower = text.toLowerCase();
    for (const { matches, trade } of TRADE_HINTS) {
      if (matches.some(m => lower.includes(m))) return trade;
    }
    return null;
  }

  function detectType(text) {
    const lower = text.toLowerCase();
    if (CLIENT_WORDS.some(w => lower.includes(w))) return 'client';
    if (INCOMPLETE_WORDS.some(w => lower.includes(w))) return 'incomplete';
    if (DEFECT_WORDS.some(w => lower.includes(w))) return 'defect';
    return null;
  }

  /**
   * Strip location/assignment phrases from transcript and return a clean description.
   * Preserves action/defect wording. Converts remaining comma-clauses to sentence form.
   */
  function cleanDescription(transcript, parsed) {
    let text = transcript;

    if (parsed.building) {
      text = text.replace(/\b(?:building|bldg)\s+\w+[,\s]*/gi, ' ');
      text = text.replace(/\bB\s*[0-9]{1,2}\b[,\s]*/g, ' ');
      text = text.replace(/\b(?:block|tower)\s+\w+[,\s]*/gi, ' ');
      // "B three" etc.
      text = text.replace(/\bB\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b[,\s]*/gi, ' ');
    }

    if (parsed.unit) {
      // "unit 305" — digits only, word-bounded
      text = text.replace(/\b(?:unit|apartment|apt|lot)\s+[0-9]+\b[,\s]*/gi, ' ');
      // "unit three oh five" — number words only
      text = text.replace(/\b(?:unit|apartment|apt|lot)\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|oh)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|oh))*\b[,\s]*/gi, ' ');
      // Bare "U305"
      text = text.replace(/\bU[0-9]{2,4}\b[,\s]*/g, ' ');
    }

    if (parsed.level) {
      text = text.replace(/\b(?:on\s+)?(?:level|floor|lvl)\s+\w+[,\s]*/gi, ' ');
      text = text.replace(/\bground\s+(?:floor|level)?[,\s]*/gi, ' ');
      text = text.replace(/\bL[0-9]{1,2}\b[,\s]*/g, ' ');
    }

    if (parsed.room) {
      const roomEsc = parsed.room.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(new RegExp(`\\b${roomEsc}\\b[,\\s]*`, 'gi'), ' ');
    }

    // Remove project names if supplied
    for (const name of (parsed._projectNames || [])) {
      const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(new RegExp(`\\b${esc}\\b[,\\s]*`, 'gi'), ' ');
    }

    // Clean up leading commas/spaces
    text = text.replace(/\s{2,}/g, ' ').trim();
    text = text.replace(/^[\s,;]+/, '').trim();

    // Convert remaining commas between clauses into sentence breaks
    text = text.replace(/,\s*(?=[A-Za-z])/g, (m, offset, str) => {
      // Only replace if what follows looks like a new clause (not a list item)
      return '. ';
    });

    // Capitalise after each sentence boundary
    text = text.replace(/([.!?])\s+([a-z])/g, (_, p, c) => `${p} ${c.toUpperCase()}`);

    // Remove any double periods
    text = text.replace(/\.{2,}/g, '.').replace(/\.\s+\./g, '.').trim();

    // Sentence-case the first character
    if (text) text = text.charAt(0).toUpperCase() + text.slice(1);

    // Ensure ends with a period
    if (text && !/[.!?]$/.test(text)) text += '.';

    // Fallback: if cleaned text is too short, return the last meaningful clause
    if (!text || text.length < 4) {
      const clauses = transcript.split(/[,]+/).map(s => s.trim()).filter(Boolean);
      const last = clauses[clauses.length - 1] || transcript;
      text = last.charAt(0).toUpperCase() + last.slice(1);
      if (!/[.!?]$/.test(text)) text += '.';
    }

    return text;
  }

  /**
   * Primary export. Parse a spoken or typed defect note into structured fields.
   *
   * @param {string} transcript
   * @param {object} [config]  optional project config { buildings, levels, units, rooms, projectNames }
   * @returns {{ building?, level?, unit?, room?, trade?, type?, priority, description, raw_transcript, confidence, warnings[] }}
   */
  function parseVoiceNote(transcript, config) {
    config = config || {};
    const original = (transcript || '').trim();
    if (!original) return { raw_transcript: '', description: '', confidence: 0, warnings: ['Empty transcript'] };

    const parsed = {
      raw_transcript: original,
      confidence: 0,
      warnings: [],
      _projectNames: config.projectNames || [],
    };

    const building = detectBuilding(original);
    if (building) {
      const cfgBuildings = config.buildings || [];
      const match = cfgBuildings.find(b =>
        b === building.value ||
        b === building.normalized ||
        b.toLowerCase() === building.value.toLowerCase() ||
        b.toLowerCase() === building.normalized.toLowerCase()
      );
      parsed.building = match || building.normalized || building.value;
    }

    const level = detectLevel(original);
    if (level) {
      const cfgLevels = config.levels || [];
      const match = cfgLevels.find(l => l.toLowerCase() === level.toLowerCase());
      parsed.level = match || level;
    }

    const unit = detectUnit(original);
    if (unit) {
      const cfgUnits = config.units || [];
      // Normalise to digits-only for comparison ("U203" → "203", "Unit 203" → "203")
      const norm = unit.replace(/^U(?:nit\s*)?/i, '').trim();
      const match = cfgUnits.find(function (u) {
        if (u === unit) return true;
        const uNorm = u.replace(/^U(?:nit\s*)?/i, '').trim();
        return uNorm === norm;
      });
      parsed.unit = match || unit;
    }

    const room = detectRoom(original);
    if (room) {
      const cfgRooms = config.rooms || [];
      const match = cfgRooms.find(r => r.toLowerCase() === room.toLowerCase());
      parsed.room = match || room;
    }

    const trade = detectTrade(original);
    if (trade) parsed.trade = trade;

    const type = detectType(original);
    if (type) parsed.type = type;

    parsed.priority = URGENT_WORDS.some(w => original.toLowerCase().includes(w)) ? 'urgent' : 'high';

    parsed.description = cleanDescription(original, parsed);

    const fieldCount = ['building', 'level', 'unit', 'room', 'trade'].filter(k => parsed[k]).length;
    parsed.confidence = Math.min(fieldCount / 3, 1.0);

    // Remove internal helper key before returning
    delete parsed._projectNames;

    return parsed;
  }

  // Expose as global and CommonJS module
  var exports = { parseVoiceNote: parseVoiceNote, cleanDescription: cleanDescription };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exports;
  } else {
    global.VoiceParser = exports;
  }

}(typeof globalThis !== 'undefined' ? globalThis : this));
