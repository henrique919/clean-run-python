/**
 * voice-capture.js — reliable browser audio recorder for CleanRun IQ.
 * Records a short audio blob with MediaRecorder and sends it to /api/voice/parse.
 * If AI transcription is unavailable, the typed note parser remains the fallback.
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

  var currentState = STATES.IDLE;
  var recorder = null;
  var stream = null;
  var chunks = [];

  function el(id) { return document.getElementById(id); }

  function setState(state, message) {
    currentState = state;
    renderState(message);
  }

  function setStatus(message) {
    var statusEl = el('voiceStatus');
    if (statusEl) statusEl.textContent = message || '';
  }

  function setFallback(visible, message) {
    var fallbackEl = el('voiceFallback');
    if (!fallbackEl) return;
    fallbackEl.classList.toggle('hidden', !visible);
    if (message) {
      var helper = fallbackEl.querySelector('.helper');
      if (helper) helper.textContent = message;
    }
  }

  function renderState(message) {
    var btn = el('voiceRecordBtn');
    if (!btn) return;

    btn.disabled = false;
    btn.classList.remove('voice-btn--recording', 'voice-btn--processing');

    switch (currentState) {
      case STATES.IDLE:
        btn.textContent = '🎤 Record Note';
        setStatus(message || '');
        break;
      case STATES.REQUESTING:
        btn.textContent = 'Requesting microphone…';
        btn.disabled = true;
        setStatus(message || 'Waiting for microphone permission.');
        break;
      case STATES.RECORDING:
        btn.textContent = '⏹ Stop Recording';
        btn.classList.add('voice-btn--recording');
        setStatus(message || 'Listening… speak the item clearly, then tap Stop.');
        break;
      case STATES.PROCESSING:
        btn.textContent = 'Processing…';
        btn.disabled = true;
        btn.classList.add('voice-btn--processing');
        setStatus(message || 'Processing voice note…');
        break;
      case STATES.PARSED:
        btn.textContent = '🎤 Record Again';
        setStatus(message || 'Fields drafted. Review and edit before saving.');
        break;
      case STATES.FAILED:
        btn.textContent = '🎤 Retry';
        setStatus(message || 'Voice capture failed. Retry or type a note below.');
        setFallback(true, 'Voice unavailable — type your note below and tap Draft form from note.');
        break;
    }
  }

  function supportedMimeType() {
    if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return '';
    var candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/mpeg'];
    for (var i = 0; i < candidates.length; i += 1) {
      if (MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];
    }
    return '';
  }

  function stopTracks() {
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
    }
  }

  function projectValue() {
    return el('project')?.value || '';
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      setState(STATES.FAILED, 'This browser cannot record voice notes. Type the note and use Draft form from note.');
      return;
    }

    chunks = [];
    setFallback(false);
    setState(STATES.REQUESTING);

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      var mimeType = supportedMimeType();
      var options = mimeType ? { mimeType: mimeType } : undefined;
      recorder = new MediaRecorder(stream, options);

      recorder.ondataavailable = function (event) {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      };

      recorder.onerror = function () {
        stopTracks();
        setState(STATES.FAILED, 'Recording failed. Retry or type the note below.');
      };

      recorder.onstop = function () {
        stopTracks();
        uploadRecording().catch(function (error) {
          setState(STATES.FAILED, error.message || 'Voice parsing failed. Type the note below.');
        });
      };

      recorder.start();
      setState(STATES.RECORDING);
    } catch (error) {
      stopTracks();
      if (error && (error.name === 'NotAllowedError' || error.name === 'SecurityError')) {
        setState(STATES.FAILED, 'Microphone permission denied. Type the note and use Draft form from note.');
      } else {
        setState(STATES.FAILED, 'Could not access the microphone. Retry or type the note below.');
      }
    }
  }

  function stopRecording() {
    if (!recorder || currentState !== STATES.RECORDING) return;
    setState(STATES.PROCESSING, 'Uploading and transcribing voice note…');
    try {
      recorder.stop();
    } catch (error) {
      stopTracks();
      setState(STATES.FAILED, 'Could not stop recording. Retry or type the note below.');
    }
  }

  async function uploadRecording() {
    if (!chunks.length) {
      setState(STATES.FAILED, 'No audio was recorded. Retry or type the note below.');
      return;
    }

    var type = chunks[0].type || supportedMimeType() || 'audio/webm';
    var audioBlob = new Blob(chunks, { type: type });
    if (!audioBlob.size) {
      setState(STATES.FAILED, 'The recording was empty. Retry or type the note below.');
      return;
    }

    var formData = new FormData();
    formData.append('audio', audioBlob, 'cleanrun-voice-note.webm');
    formData.append('project', projectValue());

    var fetcher = window.cleanrunApiFetch || window.fetch.bind(window);
    var res = await fetcher('/api/voice/parse', { method: 'POST', body: formData });
    if (!res.ok) {
      var err = await res.json().catch(function () { return {}; });
      throw new Error(err.detail || 'AI voice parsing is unavailable. Type the note below.');
    }

    var result = await res.json();
    var transcript = (result.transcript || result.parsed?.raw_transcript || '').trim();
    if (!transcript) {
      setState(STATES.FAILED, 'No speech was detected. Retry or type the note below.');
      return;
    }

    var noteEl = el('voiceNote');
    if (noteEl) noteEl.value = transcript;

    if (typeof window.cleanrunApplyVoiceResult === 'function') {
      window.cleanrunApplyVoiceResult(result.parsed || {}, transcript, result.source || 'ai');
    } else if (typeof window.draftFromVoice === 'function') {
      window.draftFromVoice(transcript);
    }

    setState(STATES.PARSED, 'AI drafted the fields. Review before saving.');
  }

  function toggle() {
    if (currentState === STATES.RECORDING) stopRecording();
    else if (currentState !== STATES.REQUESTING && currentState !== STATES.PROCESSING) startRecording();
  }

  window.voiceCapture = { toggle: toggle, states: STATES };

  document.addEventListener('DOMContentLoaded', function () {
    var btn = el('voiceRecordBtn');
    if (!btn) return;
    btn.addEventListener('click', toggle);
    if (!window.MediaRecorder) {
      setFallback(true, 'Voice recording is not supported here — type your note below and tap Draft form from note.');
      setStatus('Voice recording is not supported in this browser.');
    }
  });
}());
