import { ParsedFields, parseTranscript } from "@/lib/voiceParser";

/**
 * Voice-to-Note service layer. Transcription is delegated to ElevenLabs Scribe
 * through the Rork toolkit proxy; field extraction uses the deterministic local
 * parser so it works the same online or offline. The interface is intentionally
 * abstract so a server-side LLM extractor can be slotted in later without
 * touching the Capture UI.
 */

const TOOLKIT_URL = process.env.EXPO_PUBLIC_TOOLKIT_URL ?? "";
const TOOLKIT_KEY = process.env.EXPO_PUBLIC_RORK_TOOLKIT_SECRET_KEY ?? "";

export interface VoiceResult {
  transcript: string;
  fields: ParsedFields;
  /** True when the cloud transcription succeeded. */
  online: boolean;
}

export interface TranscribeOptions {
  subcontractors: string[];
}

function guessName(uri: string): string {
  const lower = uri.toLowerCase();
  if (lower.endsWith(".m4a")) return "note.m4a";
  if (lower.endsWith(".mp4")) return "note.mp4";
  if (lower.endsWith(".wav")) return "note.wav";
  if (lower.endsWith(".caf")) return "note.caf";
  return "note.m4a";
}

function guessType(uri: string): string {
  const lower = uri.toLowerCase();
  if (lower.endsWith(".m4a")) return "audio/m4a";
  if (lower.endsWith(".mp4")) return "audio/mp4";
  if (lower.endsWith(".wav")) return "audio/wav";
  if (lower.endsWith(".caf")) return "audio/x-caf";
  return "audio/m4a";
}

/**
 * Transcribe a recorded audio file via ElevenLabs Scribe (scribe_v2) and parse
 * structured fields. Throws on network/transcription failure so the caller can
 * fall back to manual entry — capture must never be blocked.
 */
export async function transcribeAndExtract(
  audioUri: string,
  options: TranscribeOptions,
): Promise<VoiceResult> {
  if (!TOOLKIT_URL || !TOOLKIT_KEY) {
    throw new Error("Voice AI is not configured on this device.");
  }

  const form = new FormData();
  form.append("model_id", "scribe_v2");
  form.append("file", {
    uri: audioUri,
    name: guessName(audioUri),
    type: guessType(audioUri),
  } as unknown as Blob);

  const res = await fetch(`${TOOLKIT_URL}/v2/elevenlabs/v1/speech-to-text`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOOLKIT_KEY}` },
    body: form,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Transcription failed (${res.status}). ${detail.slice(0, 120)}`);
  }

  const json = (await res.json()) as { text?: string };
  const transcript = (json.text ?? "").trim();
  const fields = parseTranscript(transcript, { subcontractors: options.subcontractors });
  return { transcript, fields, online: true };
}

/** Parse an already-captured transcript locally (used for retry / offline). */
export function extractFromTranscript(
  transcript: string,
  options: TranscribeOptions,
): VoiceResult {
  const fields = parseTranscript(transcript, { subcontractors: options.subcontractors });
  return { transcript: transcript.trim(), fields, online: false };
}
