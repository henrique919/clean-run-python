/**
 * voice-app-bridge.js — isolates voice parsing/application from app.js.
 * Keeps manual capture untouched while preserving raw transcript + parsed fields.
 */
(function () {
  'use strict';

  var lastVoiceParsed = null;

  function el(id) { return document.getElementById(id); }

  function value(id) { return (el(id)?.value || '').trim(); }

  function setStatus(message) {
    var statusEl = el('voiceStatus');
    if (statusEl) statusEl.textContent = message || '';
  }

  function toast(message) {
    if (typeof window.toast === 'function') window.toast(message);
    else setStatus(message);
  }

  function optionsFromSelect(id) {
    var select = el(id);
    return select ? Array.prototype.map.call(select.options || [], function (opt) { return opt.value; }).filter(Boolean) : [];
  }

  function optionsFromDatalist(id) {
    var list = el(id);
    return list ? Array.prototype.map.call(list.options || [], function (opt) { return opt.value; }).filter(Boolean) : [];
  }

  function currentParserConfig() {
    return {
      projectNames: optionsFromSelect('project'),
      buildings: optionsFromDatalist('buildingOptions'),
      levels: optionsFromDatalist('levelOptions'),
      units: optionsFromDatalist('unitOptions'),
      rooms: optionsFromDatalist('roomOptions'),
      trades: optionsFromSelect('trade'),
      subcontractors: optionsFromDatalist('subOptions'),
    };
  }

  function optionMatch(options, wanted) {
    if (!wanted) return null;
    var lower = String(wanted).toLowerCase();
    var wantedDigits = String(wanted).replace(/[^0-9]/g, '');
    return options.find(function (opt) {
      var optDigits = String(opt).replace(/[^0-9]/g, '');
      return opt === wanted || String(opt).toLowerCase() === lower || (wantedDigits && optDigits === wantedDigits);
    }) || null;
  }

  function applyTextField(id, parsedValue, label, warnings, options) {
    if (!parsedValue) return;
    var field = el(id);
    if (!field) return;
    var finalValue = options?.length ? (optionMatch(options, parsedValue) || parsedValue) : parsedValue;
    if (!field.value.trim()) field.value = finalValue;
    else if (field.value.trim() !== finalValue) warnings.push(label + ' already selected. Voice result not applied.');
  }

  function applySelectField(id, parsedValue, label, warnings) {
    if (!parsedValue) return;
    var field = el(id);
    if (!field) return;
    var match = optionMatch(optionsFromSelect(id), parsedValue);
    if (!match) {
      warnings.push(label + ' voice result was not an available option.');
      return;
    }
    if (!field.value) field.value = match;
    else if (field.value !== match) warnings.push(label + ' already selected. Voice result not applied.');
  }

  function applyDescription(parsed, transcript, warnings) {
    if (!parsed.description) return;
    var field = el('description');
    if (!field) return;
    var current = field.value.trim();
    var raw = (transcript || parsed.raw_transcript || '').trim();
    if (!current || current.toLowerCase() === raw.toLowerCase()) field.value = parsed.description;
    else if (current !== parsed.description) warnings.push('Description already entered. Voice description not applied.');
  }

  function applyProject(parsed, warnings) {
    if (!parsed.project) return;
    var field = el('project');
    if (!field) return;
    var match = optionMatch(optionsFromSelect('project'), parsed.project);
    if (!match) return;
    if (!field.value) field.value = match;
    else if (field.value !== match) warnings.push('Project mentioned in voice note, but the active project was not changed.');
  }

  function normalisedParsed(parsed, transcript) {
    var result = Object.assign({}, parsed || {});
    result.raw_transcript = transcript || result.raw_transcript || value('voiceNote');
    result.description = result.description || '';
    result.warnings = Array.isArray(result.warnings) ? result.warnings : [];
    return result;
  }

  function applyVoiceResult(parsed, transcript, source) {
    var warnings = [];
    var result = normalisedParsed(parsed, transcript);
    lastVoiceParsed = result;
    window.cleanrunLastVoiceParsed = result;

    if (el('voiceNote')) el('voiceNote').value = result.raw_transcript || transcript || '';

    applyProject(result, warnings);
    applyTextField('building', result.building, 'Building', warnings, optionsFromDatalist('buildingOptions'));
    applyTextField('level', result.level, 'Level', warnings, optionsFromDatalist('levelOptions'));
    applyTextField('unit', result.unit, 'Unit / area', warnings, optionsFromDatalist('unitOptions'));
    applyTextField('room', result.room, 'Room / location', warnings, optionsFromDatalist('roomOptions'));
    applySelectField('trade', result.trade, 'Trade', warnings);
    applyTextField('subcontractor', result.subcontractor, 'Subcontractor', warnings, optionsFromDatalist('subOptions'));
    applySelectField('type', result.type, 'Item type', warnings);
    applySelectField('priority', result.priority, 'Priority', warnings);
    if (result.due_date && el('dueDate') && !el('dueDate').value) el('dueDate').value = result.due_date;
    applyDescription(result, result.raw_transcript, warnings);

    if (typeof window.refreshSubcontractors === 'function') window.refreshSubcontractors();
    var parserWarnings = (result.warnings || []).filter(Boolean);
    var message = source === 'ai' ? 'AI drafted fields. Review before saving.' : 'Typed note drafted fields. Review before saving.';
    var combined = warnings.concat(parserWarnings);
    toast(combined.length ? message + ' ' + combined.join(' ') : message);
    setStatus(message);
  }

  function parseTypedNote() {
    var note = value('voiceNote');
    if (!note) {
      toast('Type or speak a note first.');
      return null;
    }
    if (!window.VoiceParser || typeof window.VoiceParser.parseVoiceNote !== 'function') {
      toast('Parser not loaded — refresh the page.');
      return null;
    }
    var parsed = window.VoiceParser.parseVoiceNote(note, currentParserConfig());
    applyVoiceResult(parsed, note, 'typed');
    return parsed;
  }

  function patchPayloadViaFetch() {
    if (window.__cleanrunVoiceFetchPatched) return;
    var originalFetch = window.fetch;
    if (typeof originalFetch !== 'function') return;

    window.fetch = function (input, init) {
      try {
        var url = typeof input === 'string' ? input : input?.url;
        var method = String(init?.method || 'GET').toUpperCase();
        var headers = init?.headers || {};
        var contentType = typeof headers.get === 'function' ? headers.get('Content-Type') : (headers['Content-Type'] || headers['content-type'] || '');
        if (url && url.indexOf('/api/items') === 0 && method === 'POST' && init?.body && String(contentType).includes('application/json')) {
          var body = JSON.parse(init.body);
          var transcript = value('voiceNote') || body.voice_transcript || body.voice_note?.transcript;
          var parsedFields = lastVoiceParsed || window.cleanrunLastVoiceParsed || body.voice_note?.parsed_fields || {};
          if (transcript) {
            body.voice_transcript = transcript;
            body.voice_note = {
              transcript: transcript,
              parsed_fields: parsedFields,
              status: parsedFields && Object.keys(parsedFields).length ? 'parsed' : 'transcribed',
            };
            init = Object.assign({}, init, { body: JSON.stringify(body) });
          }
        }
      } catch (error) {
        // Never block a save because voice metadata patching failed.
      }
      return originalFetch.call(this, input, init);
    };

    window.__cleanrunVoiceFetchPatched = true;
  }

  function bindTypedParser() {
    var btn = el('draftFromNote');
    if (btn) btn.onclick = parseTypedNote;
    window.draftFromVoice = function (transcript) {
      if (el('voiceNote') && transcript) el('voiceNote').value = transcript;
      return parseTypedNote();
    };
  }

  window.cleanrunApplyVoiceResult = applyVoiceResult;
  window.cleanrunParseTypedNote = parseTypedNote;

  document.addEventListener('DOMContentLoaded', function () {
    bindTypedParser();
    patchPayloadViaFetch();
  });
}());
