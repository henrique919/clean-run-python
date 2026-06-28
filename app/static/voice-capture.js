/**
 * voice-capture.js — Browser speech recognition state machine for CleanRun IQ.
 * Requires voice-parser.js to be loaded first.
 *
 * States: idle | requesting_permission | recording | processing | parsed | failed
 *
 * Falls back to typed-note parsing when SpeechRecognition is unavailable.
 */
(function () {
  'use strict';

  var STATES = {
    IDLE: 'idle',
    REQUESTING: 'requesting_permission',
    RECORDING: 'recording',
    PROCESSING: 'processing',
    PARSED: 'parsed',
    FAILED: 'failed',
  };

  var recognition = null;
  var currentState = STATES.IDLE;
  var partialTranscript = '';

  var hasSpeechAPI = typeof window !== 'undefined' &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  // ── UI helpers ───────────────────────────────────────────────────────────────

  function el(id) { return document.getElementById(id); }

  function setState(state) {
    currentState = state;
    renderState(state);
  }

  function renderState(state) {
    var btn = el('voiceRecordBtn');
    var statusEl = el('voiceStatus');
    var fallbackEl = el('voiceFallback');
    if (!btn) return;

    btn.disabled = false;
    btn.classList.remove('voice-btn--recording', 'voice-btn--processing');
    if (fallbackEl) fallbackEl.classList.add('hidden');

    switch (state) {
      case STATES.IDLE:
        btn.textContent = '🎤 Record Note';
        if (statusEl) statusEl.textContent = '';
        break;

      case STATES.REQUESTING:
        btn.textContent = 'Requesting microphone…';
        btn.disabled = true;
        if (statusEl) statusEl.textContent = 'Waiting for microphone permission.';
        break;

      case STATES.RECORDING:
        btn.textContent = '⏹ Stop Recording';
        btn.classList.add('voice-btn--recording');
        if (statusEl) statusEl.textContent = 'Recording… Speak clearly then tap Stop.';
        break;

      case STATES.PROCESSING:
        btn.textContent = 'Processing…';
        btn.disabled = true;
        btn.classList.add('voice-btn--processing');
        if (statusEl) statusEl.textContent = 'Processing transcript…';
        break;

      case STATES.PARSED:
        btn.textContent = '🎤 Record Again';
        if (statusEl) statusEl.textContent = 'Fields drafted. Review and edit before saving.';
        break;

      case STATES.FAILED:
        btn.textContent = '🎤 Retry';
        if (statusEl) statusEl.textContent = 'Voice capture failed. Retry or type a note below.';
        if (fallbackEl) fallbackEl.classList.remove('hidden');
        break;
    }
  }

  function setStatus(msg) {
    var statusEl = el('voiceStatus');
    if (statusEl) statusEl.textContent = msg;
  }

  // ── Core recognition ─────────────────────────────────────────────────────────

  function handleTranscript(transcript) {
    transcript = (transcript || '').trim();
    if (!transcript) {
      if (partialTranscript) {
        transcript = partialTranscript;
      } else {
        setStatus('No speech detected. Speak clearly and try again, or type a note below.');
        setState(STATES.FAILED);
        return;
      }
    }

    // Preserve raw transcript in the textarea
    var noteEl = el('voiceNote');
    if (noteEl) noteEl.value = transcript;

    setState(STATES.PARSED);

    // Call app.js integration point
    if (typeof window.draftFromVoice === 'function') {
      window.draftFromVoice(transcript);
    }
  }

  function startRecognition() {
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-AU';
    recognition.maxAlternatives = 1;

    recognition.onstart = function () {
      setState(STATES.RECORDING);
    };

    recognition.onresult = function (event) {
      var interim = '';
      var final = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      partialTranscript = (final || interim).trim();
      if (interim) setStatus('Heard: "' + interim + '"');
    };

    recognition.onerror = function (event) {
      if (event.error === 'not-allowed' || event.error === 'permission-denied') {
        setStatus('Microphone permission denied. Type your note below instead.');
        var fallbackEl = el('voiceFallback');
        if (fallbackEl) fallbackEl.classList.remove('hidden');
        setState(STATES.FAILED);
      } else if (event.error === 'no-speech') {
        if (partialTranscript) {
          setState(STATES.PROCESSING);
          handleTranscript(partialTranscript);
        } else {
          setStatus('No speech detected. Speak more clearly and try again, or type a note below.');
          setState(STATES.FAILED);
        }
      } else if (event.error === 'aborted') {
        if (partialTranscript) {
          setState(STATES.PROCESSING);
          handleTranscript(partialTranscript);
        } else {
          setState(STATES.IDLE);
        }
      } else {
        setStatus('Voice error (' + event.error + '). Try again or type a note below.');
        setState(STATES.FAILED);
      }
    };

    recognition.onend = function () {
      if (currentState === STATES.RECORDING) {
        setState(STATES.PROCESSING);
        setTimeout(function () { handleTranscript(partialTranscript); }, 100);
      }
    };

    try {
      recognition.start();
      setState(STATES.REQUESTING);
    } catch (e) {
      setStatus('Could not start voice capture: ' + e.message);
      setState(STATES.FAILED);
    }
  }

  function stopRecognition() {
    if (recognition) {
      try { recognition.stop(); } catch (e) { /* ignore */ }
    }
  }

  function toggle() {
    if (currentState === STATES.RECORDING) {
      stopRecognition();
    } else if (currentState !== STATES.REQUESTING && currentState !== STATES.PROCESSING) {
      partialTranscript = '';
      if (!hasSpeechAPI) {
        var btn = el('voiceRecordBtn');
        var statusEl = el('voiceStatus');
        var fallbackEl = el('voiceFallback');
        if (btn) { btn.textContent = 'Voice not supported'; btn.disabled = true; }
        if (statusEl) statusEl.textContent = 'Your browser does not support voice capture. Type a note and use "Draft from note" instead.';
        if (fallbackEl) fallbackEl.classList.remove('hidden');
        return;
      }
      startRecognition();
    }
  }

  // Expose to global scope
  window.voiceCapture = { toggle: toggle, states: STATES };

  document.addEventListener('DOMContentLoaded', function () {
    var btn = el('voiceRecordBtn');
    if (!btn) return;

    if (!hasSpeechAPI) {
      btn.textContent = 'Voice not supported in this browser';
      btn.disabled = true;
      var statusEl = el('voiceStatus');
      var fallbackEl = el('voiceFallback');
      if (statusEl) statusEl.textContent = 'Your browser does not support voice capture. Type a note and use "Draft from note" instead.';
      if (fallbackEl) fallbackEl.classList.remove('hidden');
      return;
    }

    btn.addEventListener('click', toggle);
  });

}());
