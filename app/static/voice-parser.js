/**
 * voice-parser.js — Deterministic voice-to-fields parser for CleanRun IQ.
 * No AI required. Works offline. Import before app.js.
 *
 * Exported (global): window.VoiceParser = { parseVoiceNote, cleanDescription }
 */
(function (global) {
  'use strict';

  var NUMBER_WORDS = {
    zero: 0, oh: 0, o: 0,
    one: 1, two: 2, three: 3, four: 4, five: 5,
    six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15,
    sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20,
  };

  var ROOM_KEYWORDS = [
    'master bathroom', 'master bedroom', 'rear balcony', 'front balcony',
    'ground floor', 'roof', 'external', 'entry', 'ensuite', 'bathroom',
    'kitchen', 'living', 'laundry', 'balcony', 'hallway', 'garage', 'lobby',
    'lounge', 'dining', 'toilet', 'wc', 'pantry', 'stairwell', 'corridor',
    'bedroom'
  ];

  var TRADE_HINTS = [
    { matches: ['cabinet maker', 'cabinet-maker', 'cabinetry', 'joinery'], trade: 'Joinery' },
    { matches: ['waterproofer', 'waterproofing', 'waterproof'], trade: 'Waterproofing' },
    { matches: ['plasterer', 'plasterboard', 'plastering', 'plaster'], trade: 'Plastering' },
    { matches: ['renderer', 'rendering', 'render'], trade: 'Render' },
    { matches: ['painter', 'painting', 'paint'], trade: 'Painting' },
    { matches: ['tiler', 'tiling', 'regrout', 'grout', 'tile'], trade: 'Tiling' },
    { matches: ['door', 'hardware', 'hinge', 'lock'], trade: 'Doors / Hardware' },
    { matches: ['window', 'glaz', 'glass', 'aluminium', 'aluminum'], trade: 'Windows / Aluminium' },
    { matches: ['carpet', 'timber floor', 'vinyl', 'flooring'], trade: 'Flooring' },
    { matches: ['gutter', 'roofing', 'roof'], trade: 'Roofing' },
    { matches: ['facade', 'cladding', 'clad'], trade: 'Cladding' },
    { matches: ['power point', 'gpo', 'electrical', 'electrician', 'electric', 'light switch'], trade: 'Electrical' },
    { matches: ['hydraulic', 'plumbing', 'plumber', 'tap', 'basin', 'drain', 'pipe'], trade: 'Hydraulic' },
    { matches: ['mechanical', 'hvac', 'air con', 'aircon', 'duct'], trade: 'Mechanical' },
    { matches: ['fire services', 'sprinkler', 'smoke detector'], trade: 'Fire Services' },
    { matches: ['cleaning', 'overspray'], trade: 'Cleaning' },
    { matches: ['landscap', 'garden', 'turf'], trade: 'Landscaping' },
    { matches: ['concrete', 'slab'], trade: 'Concrete' },
    { matches: ['caulk', 'sealant', 'silicone'], trade: 'Caulking / Sealant' },
  ];

  var URGENT_WORDS = ['urgent', 'critical', 'immediate', 'immediately', 'safety', 'stop work', 'asap', 'emergency'];
  var DEFECT_WORDS = ['damaged', 'defective', 'cracked', 'crack', 'scratched', 'broken', 'chipped', 'leak', 'stain', 'drummy', 'faulty', 'defect'];
  var INCOMPLETE_WORDS = ['not finished', 'unfinished', 'incomplete', 'missing', 'not installed', 'outstanding work'];
  var CLIENT_WORDS = ['client raised', 'owner raised', 'superintendent', 'consultant', 'architect'];

  function escapeRegex(value) {
    return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function cleanSpaces(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function wordToNum(word) {
    return NUMBER_WORDS[String(word || '').toLowerCase()] ?? null;
  }

  function parseNumberWords(str) {
    var words = String(str || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return null;
    var nums = words.map(function (word) { return NUMBER_WORDS[word]; });
    if (nums.some(function (num) { return num === undefined || num === null || num > 9; })) return null;
    return nums.map(function (num) { return String(num); }).join('');
  }

  function optionValues(values) {
    return Array.isArray(values) ? values.filter(Boolean).map(String) : [];
  }

  function digitsOnly(value) {
    return String(value || '').replace(/[^0-9]/g, '');
  }

  function findBuildingOption(raw, config) {
    var cfg = optionValues(config.buildings);
    var rawDigits = digitsOnly(raw);
    if (!cfg.length) return null;
    return cfg.find(function (candidate) {
      var c = candidate.toLowerCase();
      return candidate === raw || c === raw.toLowerCase() || digitsOnly(candidate) === rawDigits || c === ('b' + rawDigits);
    }) || null;
  }

  function findUnitOption(raw, config) {
    var cfg = optionValues(config.units);
    var rawDigits = digitsOnly(raw);
    if (!cfg.length) return null;
    return cfg.find(function (candidate) {
      return candidate === raw || candidate.toLowerCase() === raw.toLowerCase() || digitsOnly(candidate) === rawDigits;
    }) || null;
  }

  function findSimpleOption(value, values) {
    var lower = String(value || '').toLowerCase();
    return optionValues(values).find(function (candidate) { return candidate.toLowerCase() === lower; }) || null;
  }

  function detectProject(text, config) {
    var lower = text.toLowerCase();
    var names = optionValues(config.projectNames || config.projects);
    return names.find(function (name) { return lower.includes(name.toLowerCase()); }) || null;
  }

  function detectBuilding(text, config) {
    var m = text.match(/\b(?:building|bldg)\s+([a-z0-9]+)\b/i);
    if (m) {
      var token = m[1].toLowerCase();
      var n = wordToNum(token);
      var num = n != null ? String(n) : token.replace(/[^0-9a-z]/gi, '').toUpperCase();
      var normalized = /^\d+$/.test(num) ? ('B' + num) : ('Building ' + num);
      return findBuildingOption(normalized, config) || normalized;
    }

    m = text.match(/\bB\s*([0-9]{1,2})\b/);
    if (m) return findBuildingOption('B' + m[1], config) || ('B' + m[1]);

    m = text.match(/\bB\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b/i);
    if (m) {
      var wordNum = wordToNum(m[1]);
      if (wordNum != null) return findBuildingOption('B' + wordNum, config) || ('B' + wordNum);
    }

    m = text.match(/\bblock\s+([a-z0-9]+)\b/i);
    if (m) return 'Block ' + m[1].toUpperCase();

    m = text.match(/\btower\s+([a-z0-9]+)\b/i);
    if (m) return 'Tower ' + m[1].toUpperCase();

    return null;
  }

  function detectLevel(text, config) {
    var m = text.match(/\b(?:level|floor|lvl)\s*([0-9]{1,2})\b/i);
    if (m) return findSimpleOption('Level ' + parseInt(m[1], 10), config.levels) || ('Level ' + parseInt(m[1], 10));

    m = text.match(/\b(?:level|floor|lvl)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/i);
    if (m) {
      var n = wordToNum(m[1]);
      if (n != null) return findSimpleOption('Level ' + n, config.levels) || ('Level ' + n);
    }

    if (/\bground\s+(?:floor|level)\b/i.test(text) || /\bon\s+ground\b/i.test(text) || /\bground\b/i.test(text)) {
      return findSimpleOption('Ground', config.levels) || 'Ground';
    }

    return null;
  }

  var NUM_WORD_ALT = '(?:zero|one|two|three|four|five|six|seven|eight|nine|oh|o)';
  var NUM_WORD_SEQ_RE = new RegExp('\\b(?:unit|apartment|apt|lot)\\s+(' + NUM_WORD_ALT + '(?:\\s+' + NUM_WORD_ALT + ')*)\\b', 'i');

  function detectUnit(text, config) {
    var m = text.match(/\b(?:unit|apartment|apt|lot)\s+([0-9]+)\b/i);
    if (m) return findUnitOption('U' + m[1], config) || ('U' + m[1]);

    m = text.match(NUM_WORD_SEQ_RE);
    if (m) {
      var numberWords = parseNumberWords(m[1]);
      if (numberWords) return findUnitOption('U' + numberWords, config) || ('U' + numberWords);
    }

    m = text.match(/\b(?:unit|apartment|apt|lot)\s+([A-Za-z0-9-]+)\b/i);
    if (m) return findUnitOption('U' + m[1].toUpperCase(), config) || ('U' + m[1].toUpperCase());

    m = text.match(/\bU\s*([0-9]{2,4})\b/i);
    if (m) return findUnitOption('U' + m[1], config) || ('U' + m[1]);

    return null;
  }

  function detectRoom(text, config) {
    var lower = text.toLowerCase();
    var cfgRooms = optionValues(config.rooms);

    var configured = cfgRooms
      .slice()
      .sort(function (a, b) { return b.length - a.length; })
      .find(function (room) { return lower.includes(room.toLowerCase()); });
    if (configured) return configured;

    for (var i = 0; i < ROOM_KEYWORDS.length; i += 1) {
      var kw = ROOM_KEYWORDS[i];
      if (lower.includes(kw)) {
        if (kw === 'bedroom') {
          var bedMatch = lower.match(/bedroom\s*([0-9])/);
          if (bedMatch) return 'Bedroom ' + bedMatch[1];
        }
        if (kw === 'roof') return findSimpleOption('Roof', cfgRooms) || 'Roof';
        if (kw === 'ground floor') continue;
        return kw.replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      }
    }
    return null;
  }

  function detectTrade(text, config) {
    var lower = text.toLowerCase();
    var cfgTrades = optionValues(config.trades);
    for (var i = 0; i < TRADE_HINTS.length; i += 1) {
      var hint = TRADE_HINTS[i];
      if (hint.matches.some(function (needle) { return lower.includes(needle); })) {
        return findSimpleOption(hint.trade, cfgTrades) || hint.trade;
      }
    }
    return null;
  }

  function detectSubcontractor(text, config) {
    var lower = text.toLowerCase();
    return optionValues(config.subcontractors)
      .slice()
      .sort(function (a, b) { return b.length - a.length; })
      .find(function (name) { return lower.includes(name.toLowerCase()); }) || null;
  }

  function detectType(text) {
    var lower = text.toLowerCase();
    if (CLIENT_WORDS.some(function (w) { return lower.includes(w); })) return 'client';
    if (INCOMPLETE_WORDS.some(function (w) { return lower.includes(w); })) return 'incomplete';
    if (DEFECT_WORDS.some(function (w) { return lower.includes(w); })) return 'defect';
    return 'defect';
  }

  function removeRegex(value, regex) {
    return value.replace(regex, ' ');
  }

  function removeKnownPhrase(value, phrase) {
    if (!phrase) return value;
    return removeRegex(value, new RegExp('\\b' + escapeRegex(phrase) + '\\b[,;:\\s]*', 'gi'));
  }

  function normaliseDescription(value) {
    var text = cleanSpaces(value)
      .replace(/^[,.;:\-\s]+/, '')
      .replace(/[,;:\-\s]+$/, '')
      .replace(/\s+,/g, ',')
      .replace(/\bto patch sand and paint\b/gi, 'to patch, sand and paint')
      .replace(/\b(penetration|vanity|entry|wall|door|tile|crack|damage)\s+(waterproofer|tiler|painter|plasterer|renderer|cabinet maker)\s+to\b/gi, '$1. $2 to')
      .replace(/,\s*(?=(?:and\s+)?(?:tiler|painter|plasterer|renderer|waterproofer|cabinet maker|subcontractor|trade)\b)/gi, '. ')
      .replace(/,\s*(?=[A-Z])/g, '. ')
      .replace(/\s*\.\s*/g, '. ')
      .replace(/\.{2,}/g, '.')
      .trim();

    if (text) text = text.charAt(0).toUpperCase() + text.slice(1);
    text = text.replace(/([.!?])\s+([a-z])/g, function (_, p, c) { return p + ' ' + c.toUpperCase(); });
    if (text && !/[.!?]$/.test(text)) text += '.';
    return text;
  }

  function actionFallback(transcript) {
    var clauses = String(transcript || '').split(/[,;]+/).map(cleanSpaces).filter(Boolean);
    var actionWords = /(repair|repaired|replace|regrout|patch|repaint|review|make good|scratched|cracked|damage|defect|incomplete|missing|silicone|leak|broken|chipped)/i;
    var chosen = clauses.find(function (clause) { return actionWords.test(clause); }) || clauses[clauses.length - 1] || transcript;
    return normaliseDescription(chosen);
  }

  function cleanDescription(transcript, parsed) {
    var text = String(transcript || '');

    if (parsed.project) text = removeKnownPhrase(text, parsed.project);

    if (parsed.building) {
      text = removeRegex(text, /\b(?:building|bldg)\s+(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b[,;:\s]*/gi);
      text = removeRegex(text, /\bB\s*(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b[,;:\s]*/gi);
      text = removeRegex(text, /\b(?:block|tower)\s+\w+\b[,;:\s]*/gi);
      text = removeKnownPhrase(text, parsed.building);
    }

    if (parsed.unit) {
      text = removeRegex(text, /\b(?:unit|apartment|apt|lot)\s+[0-9A-Za-z-]+\b[,;:\s]*/gi);
      text = removeRegex(text, new RegExp('\\b(?:unit|apartment|apt|lot)\\s+' + NUM_WORD_ALT + '(?:\\s+' + NUM_WORD_ALT + ')*\\b[,;:\\s]*', 'gi'));
      text = removeRegex(text, /\bU\s*[0-9]{2,4}\b[,;:\s]*/gi);
      text = removeKnownPhrase(text, parsed.unit);
    }

    if (parsed.level) {
      text = removeRegex(text, /\b(?:on\s+)?(?:level|floor|lvl)\s*(?:[0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b[,;:\s]*/gi);
      text = removeRegex(text, /\b(?:on\s+)?ground\s+(?:floor|level)\b[,;:\s]*/gi);
      if (parsed.level === 'Ground') text = removeRegex(text, /\bground\b[,;:\s]*/gi);
      text = removeRegex(text, /\bL\s*[0-9]{1,2}\b[,;:\s]*/gi);
      text = removeKnownPhrase(text, parsed.level);
    }

    if (parsed.room) {
      text = removeKnownPhrase(text, parsed.room);
    }

    text = text
      .replace(/\b(?:urgent|high priority|critical priority)\b[,;:\s]*/gi, ' ')
      .replace(/\b(?:defect|incomplete work|client defect)\b[,;:\s]*(?=(?:building|bldg|b\s*\d|unit|level|floor|lvl)\b)/gi, ' ')
      .replace(/\b(on|at|in)\s*(?=[,.;]|$)/gi, ' ');

    var cleaned = normaliseDescription(text);
    if (!cleaned || cleaned.length < 4) cleaned = actionFallback(transcript);
    return cleaned;
  }

  function parseVoiceNote(transcript, config) {
    config = config || {};
    var original = cleanSpaces(transcript);
    if (!original) return { raw_transcript: '', description: '', confidence: 0, warnings: ['Empty transcript'] };

    var parsed = {
      raw_transcript: original,
      project: detectProject(original, config),
      building: null,
      level: null,
      unit: null,
      room: null,
      trade: null,
      subcontractor: null,
      priority: URGENT_WORDS.some(function (w) { return original.toLowerCase().includes(w); }) ? 'urgent' : 'high',
      type: detectType(original),
      due_date: null,
      description: '',
      confidence: 0,
      warnings: [],
    };

    parsed.building = detectBuilding(original, config);
    parsed.level = detectLevel(original, config);
    parsed.unit = detectUnit(original, config);
    parsed.room = detectRoom(original, config);
    parsed.trade = detectTrade(original, config);
    parsed.subcontractor = detectSubcontractor(original, config);
    parsed.description = cleanDescription(original, parsed);

    var fieldCount = ['building', 'level', 'unit', 'room', 'trade', 'subcontractor'].filter(function (key) { return Boolean(parsed[key]); }).length;
    parsed.confidence = Math.min(fieldCount / 4, 1.0);
    if (!parsed.description || parsed.description === original) parsed.warnings.push('Description may need review.');
    if (!parsed.building) parsed.warnings.push('Building not detected.');
    if (!parsed.unit) parsed.warnings.push('Unit / area not detected.');

    return parsed;
  }

  var exports = { parseVoiceNote: parseVoiceNote, cleanDescription: cleanDescription };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exports;
  } else {
    global.VoiceParser = exports;
  }
}(typeof window !== 'undefined' ? window : globalThis));
