import { useAudioRecorder, AudioModule, RecordingPresets, setAudioModeAsync } from "expo-audio";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  Camera,
  Check,
  ChevronRight,
  ImagePlus,
  Loader,
  Mic,
  Sparkles,
  Square,
  Trash2,
  X,
} from "lucide-react-native";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { EvidencePhoto } from "@/components/EvidencePhoto";
import { SectionCard } from "@/components/SectionCard";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { addDays, formatDate } from "@/lib/format";
import { ParsedFields } from "@/lib/voiceParser";
import { extractFromTranscript, transcribeAndExtract } from "@/lib/voiceService";
import { useActiveProjectConfig, useAppStore } from "@/providers/AppStore";
import { ItemType, Priority, RAISED_BY_OPTIONS, TRADES } from "@/types/models";

type VoiceState = "idle" | "recording" | "processing" | "ready";

const TYPE_OPTIONS: { type: ItemType; label: string; hint: string }[] = [
  { type: "defect", label: "Defect", hint: "Damaged / non-compliant" },
  { type: "incomplete", label: "Incomplete", hint: "Not finished yet" },
  { type: "client", label: "Client Defect", hint: "Raised by client side" },
];

export default function CaptureScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ walk?: string }>();
  const { settings, defaultDueDate, create, issue } = useAppStore();
  const cfg = useActiveProjectConfig();

  const [walkMode, setWalkMode] = useState<boolean>(params.walk === "1");
  const [walkCount, setWalkCount] = useState<number>(0);

  const [type, setType] = useState<ItemType>("defect");
  const [building, setBuilding] = useState<string>("");
  const [level, setLevel] = useState<string>("");
  const [unit, setUnit] = useState<string>("");
  const [room, setRoom] = useState<string>("");
  const [trade, setTrade] = useState<string>("");
  const [subcontractor, setSubcontractor] = useState<string>("");
  const [priority, setPriority] = useState<Priority>("high");
  const [dueDate, setDueDate] = useState<string>(defaultDueDate);
  const [description, setDescription] = useState<string>("");
  const [raisedBy, setRaisedBy] = useState<string>("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [voiceTranscript, setVoiceTranscript] = useState<string>("");
  const [parsedVoiceFields, setParsedVoiceFields] = useState<ParsedFields | null>(null);

  // Voice-to-note state
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState<string>("");
  const [voiceNote, setVoiceNote] = useState<string>("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [seconds, setSeconds] = useState<number>(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const resetForm = useCallback(
    (keepLocation: boolean) => {
      if (!keepLocation) {
        setBuilding("");
        setLevel("");
        setUnit("");
        setRoom("");
        setTrade("");
        setSubcontractor("");
      } else {
        // Walk capture: retain project/building/level/unit, clear room/description/photos.
        setRoom("");
      }
      setDescription("");
      setPhotos([]);
      setRaisedBy("");
      setVoiceTranscript("");
      setParsedVoiceFields(null);
      setTranscript("");
      setVoiceNote("");
      setVoiceState("idle");
      setPriority("high");
      setDueDate(defaultDueDate);
    },
    [defaultDueDate],
  );

  const applyFields = useCallback(
    (fields: ParsedFields) => {
      if (fields.type) setType(fields.type);
      if (fields.building) setBuilding(fields.building);
      if (fields.level) setLevel(fields.level);
      if (fields.unit) setUnit(fields.unit);
      if (fields.room) setRoom(fields.room);
      if (fields.trade) setTrade(fields.trade);
      if (fields.subcontractor) setSubcontractor(fields.subcontractor);
      if (fields.priority) setPriority(fields.priority);
      if (fields.dueDate) setDueDate(fields.dueDate);
      if (fields.raisedBy) setRaisedBy(fields.raisedBy);
      if (fields.description) setDescription(fields.description);
    },
    [],
  );

  const startRecording = useCallback(async () => {
    try {
      const granted = await AudioModule.requestRecordingPermissionsAsync();
      if (!granted.granted) {
        Alert.alert("Microphone needed", "Allow microphone access to use Voice-to-Note, or enter the item manually.");
        return;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      if (Platform.OS !== "web") Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      setSeconds(0);
      setVoiceState("recording");
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      console.warn("[CleanRun] recording failed", e);
      Alert.alert("Could not start recording", "You can still capture this item manually.");
      setVoiceState("idle");
    }
  }, [recorder]);

  const stopAndProcess = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setVoiceState("processing");
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("No recording captured");
      const result = await transcribeAndExtract(uri, { subcontractors: settings.subcontractors });
      setTranscript(result.transcript);
      setVoiceTranscript(result.transcript);
      setParsedVoiceFields(result.fields);
      applyFields(result.fields);
      setVoiceState("ready");
      if (Platform.OS !== "web") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e) {
      console.warn("[CleanRun] transcription failed", e);
      setVoiceState("idle");
      Alert.alert(
        "Voice AI unavailable",
        "We couldn't transcribe that note (offline or service unavailable). You can type the note below and we'll structure it locally, or enter the item manually.",
      );
    }
  }, [recorder, settings.subcontractors, applyFields]);

  const applyTypedNote = useCallback(() => {
    const text = voiceNote.trim();
    if (!text) return;
    const result = extractFromTranscript(text, { subcontractors: settings.subcontractors });
    setTranscript(text);
    setVoiceTranscript(text);
    setParsedVoiceFields(result.fields);
    applyFields(result.fields);
    setVoiceState("ready");
  }, [voiceNote, settings.subcontractors, applyFields]);

  const pickPhoto = useCallback(async (mode: "camera" | "library") => {
    try {
      if (mode === "camera") {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) {
          Alert.alert("Camera needed", "Allow camera access to capture a photo, or pick from your library.");
          return;
        }
        const res = await ImagePicker.launchCameraAsync({ quality: 0.6, allowsEditing: false });
        if (!res.canceled && res.assets[0]) setPhotos((p) => [...p, res.assets[0].uri]);
      } else {
        const res = await ImagePicker.launchImageLibraryAsync({
          quality: 0.6,
          allowsMultipleSelection: true,
          mediaTypes: ["images"],
        });
        if (!res.canceled) setPhotos((p) => [...p, ...res.assets.map((a) => a.uri)]);
      }
    } catch (e) {
      console.warn("[CleanRun] photo capture failed", e);
    }
  }, []);

  const removePhoto = useCallback((uri: string) => {
    setPhotos((p) => p.filter((x) => x !== uri));
  }, []);

  const validate = useCallback(
    (forIssue: boolean): string | null => {
      if (!building) return "Select a building.";
      if (type === "defect" && photos.length === 0) return "A Defect requires at least one original photo.";
      if (type === "client" && photos.length === 0) return "A Client Defect requires at least one original photo.";
      if (type === "client" && !raisedBy) return "A Client Defect requires a Raised By / source.";
      if (!description.trim()) return "Add a short description.";
      if (forIssue && (!trade || !subcontractor)) return "Issue Now requires a trade and subcontractor.";
      return null;
    },
    [building, type, photos.length, raisedBy, description, trade, subcontractor],
  );

  const buildPayload = useCallback(
    () => ({
      type,
      status: "open" as const,
      project: settings.activeProject,
      building,
      level,
      unit,
      room,
      trade,
      subcontractor,
      priority,
      dueDate,
      description: description.trim(),
      raisedBy: type === "client" ? raisedBy : undefined,
      voiceTranscript: voiceTranscript || undefined,
      voiceNote: voiceTranscript
        ? {
            transcript: voiceTranscript,
            parsedFields: parsedVoiceFields ? { ...parsedVoiceFields } : undefined,
            createdAt: new Date().toISOString(),
            status: parsedVoiceFields ? "parsed" as const : "transcribed" as const,
          }
        : undefined,
      originalPhotos: photos,
      createdBy: settings.preparedBy,
    }),
    [type, settings, building, level, unit, room, trade, subcontractor, priority, dueDate, description, raisedBy, voiceTranscript, parsedVoiceFields, photos],
  );

  const doSave = useCallback(
    (next: "view" | "list" | "walk", forIssue: boolean) => {
      const error = validate(forIssue);
      if (error) {
        Alert.alert("Hold on", error);
        return;
      }
      const proceed = () => {
        const item = create(buildPayload());
        if (forIssue && trade && subcontractor) {
          issue(item.id, { to: subcontractor, by: settings.preparedBy });
        }
        if (Platform.OS !== "web") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        if (next === "view") {
          router.push(`/item/${item.id}`);
        } else if (next === "walk") {
          setWalkCount((c) => c + 1);
          resetForm(true);
        } else {
          router.push("/items");
        }
      };

      if (type === "incomplete" && photos.length === 0) {
        Alert.alert(
          "No photo attached",
          "Incomplete Work can be saved without a photo, but a photo is recommended. Save anyway?",
          [
            { text: "Cancel", style: "cancel" },
            { text: "Save anyway", onPress: proceed },
          ],
        );
        return;
      }
      proceed();
    },
    [validate, create, buildPayload, trade, subcontractor, issue, settings.preparedBy, router, type, photos.length, resetForm],
  );

  const photoRequired = type === "defect" || type === "client";

  return (
    <View style={styles.flex}>
      <SafeAreaView edges={["top"]} style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.headerTitle}>Capture Item</Text>
          <Pressable
            style={[styles.walkToggle, walkMode && styles.walkToggleActive]}
            onPress={() => {
              setWalkMode((w) => !w);
              if (!walkMode) setWalkCount(0);
            }}
          >
            <Text style={[styles.walkToggleText, walkMode && { color: palette.white }]}>
              {walkMode ? `Walk · ${walkCount}` : "Walk Capture"}
            </Text>
          </Pressable>
        </View>
        <Text style={styles.headerSub}>{settings.activeProject}</Text>
      </SafeAreaView>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        {/* Photo evidence — this is intentionally first. CleanRun IQ is photo-first. */}
        <SectionCard
          title="Photo Evidence"
          subtitle={photoRequired ? "Required for this item type" : "Recommended"}
        >
          <Text style={styles.photoHelper}>Start with evidence. Defects and client defects require at least one photo.</Text>
          <View style={styles.photoGrid}>
            {photos.map((uri) => (
              <View key={uri} style={styles.photoThumb}>
                <EvidencePhoto uri={uri} size={92} />
                <Pressable style={styles.photoRemove} onPress={() => removePhoto(uri)}>
                  <X size={13} color={palette.white} />
                </Pressable>
              </View>
            ))}
            <Pressable style={[styles.addPhoto, styles.addPhotoPrimary]} onPress={() => pickPhoto("camera")}>
              <Camera size={24} color={palette.white} />
              <Text style={[styles.addPhotoText, styles.addPhotoPrimaryText]}>Take Photo</Text>
            </Pressable>
            <Pressable style={styles.addPhoto} onPress={() => pickPhoto("library")}>
              <ImagePlus size={22} color={palette.navy} />
              <Text style={styles.addPhotoText}>Upload Photo</Text>
            </Pressable>
          </View>
        </SectionCard>

        {/* Voice-to-Note */}
        <VoiceBlock
          state={voiceState}
          seconds={seconds}
          transcript={transcript}
          voiceNote={voiceNote}
          setVoiceNote={setVoiceNote}
          onStart={startRecording}
          onStop={stopAndProcess}
          onApplyTyped={applyTypedNote}
          onClear={() => {
            setVoiceState("idle");
            setTranscript("");
            setVoiceNote("");
            setVoiceTranscript("");
            setParsedVoiceFields(null);
          }}
        />

        {/* Item type */}
        <SectionCard title="Item type">
          <View style={styles.typeRow}>
            {TYPE_OPTIONS.map((opt) => {
              const active = type === opt.type;
              return (
                <Pressable
                  key={opt.type}
                  style={[styles.typeCard, active && styles.typeCardActive]}
                  onPress={() => setType(opt.type)}
                >
                  <Text style={[styles.typeLabel, active && { color: palette.navy }]}>{opt.label}</Text>
                  <Text style={[styles.typeHint, active && { color: palette.navy }]}>{opt.hint}</Text>
                </Pressable>
              );
            })}
          </View>
        </SectionCard>

        {/* Location */}
        <SectionCard title="Location">
          <ChipField label="Building" value={building} options={cfg.buildings} onChange={setBuilding} />
          <ChipField label="Level" value={level} options={cfg.levels} onChange={setLevel} />
          <ChipField label="Unit / Area" value={unit} options={cfg.units} onChange={setUnit} allowCustom />
          <ChipField label="Room / Location" value={room} options={cfg.rooms} onChange={setRoom} allowCustom last />
        </SectionCard>

        {/* Client defect source */}
        {type === "client" ? (
          <SectionCard title="Raised by" subtitle="Required for Client Defects">
            <View style={styles.chipsWrap}>
              {RAISED_BY_OPTIONS.map((o) => (
                <Chip key={o} label={o} active={raisedBy === o} onPress={() => setRaisedBy(o)} />
              ))}
            </View>
          </SectionCard>
        ) : null}

        {/* Assignment */}
        <SectionCard title="Assignment">
          <ChipField label="Trade" value={trade} options={TRADES} onChange={setTrade} />
          <ChipField
            label="Subcontractor"
            value={subcontractor}
            options={settings.subcontractors}
            onChange={setSubcontractor}
            last
          />
        </SectionCard>

        {/* Priority + due */}
        <SectionCard title="Priority & due date">
          <View style={styles.chipsWrap}>
            <Chip label="High" active={priority === "high"} onPress={() => setPriority("high")} />
            <Chip label="Urgent" active={priority === "urgent"} onPress={() => setPriority("urgent")} tone="red" />
          </View>
          <View style={styles.dueRow}>
            {[0, 1, 3, 7].map((d) => {
              const date = addDays(d);
              return (
                <Chip
                  key={d}
                  label={d === 0 ? "Today" : d === 1 ? "Tomorrow" : `+${d}d`}
                  active={dueDate === date}
                  onPress={() => setDueDate(date)}
                />
              );
            })}
          </View>
          <Text style={styles.dueHint}>Due {formatDate(dueDate)}</Text>
        </SectionCard>

        {/* Description */}
        <SectionCard title="Description">
          <TextInput
            style={styles.textArea}
            placeholder="Describe the item, location detail and rectification needed…"
            placeholderTextColor={palette.textFaint}
            value={description}
            onChangeText={setDescription}
            multiline
          />
        </SectionCard>

        <View style={{ height: 8 }} />
      </ScrollView>

      {/* Action bar */}
      <SafeAreaView edges={["bottom"]} style={styles.actionBar}>
        {walkMode ? (
          <>
            <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => doSave("walk", false)}>
              <Check size={18} color={palette.navy} />
              <Text style={styles.btnGhostText}>Save + Next</Text>
            </Pressable>
            <Pressable style={[styles.btn, styles.btnPrimary]} onPress={() => doSave("walk", true)}>
              <ChevronRight size={18} color={palette.white} />
              <Text style={styles.btnPrimaryText}>Save + Issue + Next</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Pressable style={[styles.btn, styles.btnGhost]} onPress={() => doSave("view", false)}>
              <Check size={18} color={palette.navy} />
              <Text style={styles.btnGhostText}>Save</Text>
            </Pressable>
            <Pressable style={[styles.btn, styles.btnPrimary]} onPress={() => doSave("list", true)}>
              <ChevronRight size={18} color={palette.white} />
              <Text style={styles.btnPrimaryText}>Issue Now</Text>
            </Pressable>
          </>
        )}
      </SafeAreaView>
    </View>
  );
}

function VoiceBlock({
  state,
  seconds,
  transcript,
  voiceNote,
  setVoiceNote,
  onStart,
  onStop,
  onApplyTyped,
  onClear,
}: {
  state: VoiceState;
  seconds: number;
  transcript: string;
  voiceNote: string;
  setVoiceNote: (v: string) => void;
  onStart: () => void;
  onStop: () => void;
  onApplyTyped: () => void;
  onClear: () => void;
}) {
  return (
    <View style={styles.voiceCard}>
      <View style={styles.voiceHeader}>
        <Sparkles size={18} color={palette.greenBright} />
        <Text style={styles.voiceTitle}>Voice-to-Note AI</Text>
      </View>
      <Text style={styles.voiceSub}>
        After adding evidence, describe the item and CleanRun IQ will draft the fields.
      </Text>

      {state === "idle" ? (
        <Pressable style={styles.micBtn} onPress={onStart}>
          <Mic size={26} color={palette.white} />
          <Text style={styles.micBtnText}>Speak Item</Text>
        </Pressable>
      ) : state === "recording" ? (
        <Pressable style={[styles.micBtn, styles.micBtnRecording]} onPress={onStop}>
          <Square size={20} color={palette.white} fill={palette.white} />
          <Text style={styles.micBtnText}>Tap to stop · {seconds}s</Text>
        </Pressable>
      ) : state === "processing" ? (
        <View style={[styles.micBtn, styles.micBtnProcessing]}>
          <ActivityIndicator color={palette.white} />
          <Text style={styles.micBtnText}>Transcribing & drafting…</Text>
        </View>
      ) : (
        <View style={styles.transcriptReady}>
          <View style={styles.transcriptHeader}>
            <Check size={16} color={palette.green} />
            <Text style={styles.transcriptReadyText}>Draft ready — review fields below</Text>
            <Pressable onPress={onClear} hitSlop={8}>
              <Text style={styles.transcriptRedo}>Redo</Text>
            </Pressable>
          </View>
          <Text style={styles.transcriptText}>“{transcript}”</Text>
        </View>
      )}

      {state === "idle" ? (
        <View style={styles.typedNote}>
          <Text style={styles.typedLabel}>No mic? Type the note and we&apos;ll structure it</Text>
          <TextInput
            style={styles.typedInput}
            placeholder="e.g. Block B level 2 unit B-204 bathroom, damaged tile, Sterling Tiling, urgent, due Friday"
            placeholderTextColor={palette.textFaint}
            value={voiceNote}
            onChangeText={setVoiceNote}
            multiline
          />
          {voiceNote.trim().length > 0 ? (
            <Pressable style={styles.applyTyped} onPress={onApplyTyped}>
              <Sparkles size={15} color={palette.navy} />
              <Text style={styles.applyTypedText}>Draft form from note</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  tone,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  tone?: "red";
}) {
  return (
    <Pressable
      style={[
        styles.chip,
        active && (tone === "red" ? styles.chipActiveRed : styles.chipActive),
      ]}
      onPress={onPress}
    >
      <Text style={[styles.chipText, active && { color: palette.white }]}>{label}</Text>
    </Pressable>
  );
}

function ChipField({
  label,
  value,
  options,
  onChange,
  allowCustom,
  last,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  allowCustom?: boolean;
  last?: boolean;
}) {
  const [custom, setCustom] = useState<string>("");
  return (
    <View style={[styles.field, !last && styles.fieldBorder]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.chipsWrap}>
        {options.map((o) => (
          <Chip key={o} label={o} active={value === o} onPress={() => onChange(value === o ? "" : o)} />
        ))}
        {value && !options.includes(value) ? (
          <Chip label={value} active onPress={() => onChange("")} />
        ) : null}
      </View>
      {allowCustom ? (
        <TextInput
          style={styles.customInput}
          placeholder={`Add ${label.toLowerCase()}…`}
          placeholderTextColor={palette.textFaint}
          value={custom}
          onChangeText={setCustom}
          onSubmitEditing={() => {
            if (custom.trim()) {
              onChange(custom.trim());
              setCustom("");
            }
          }}
          returnKeyType="done"
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  header: { backgroundColor: palette.navy, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  headerTitle: { fontSize: font.size.xxl, fontWeight: font.weight.heavy, color: palette.white },
  headerSub: { fontSize: font.size.sm, color: "rgba(255,255,255,0.7)", marginTop: 2 },
  walkToggle: { backgroundColor: "rgba(255,255,255,0.14)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill },
  walkToggleActive: { backgroundColor: palette.green },
  walkToggleText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: "rgba(255,255,255,0.9)" },

  scroll: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xxl },

  voiceCard: {
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.card,
  },
  voiceHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  voiceTitle: { fontSize: font.size.md, fontWeight: font.weight.heavy, color: palette.navy },
  voiceSub: { fontSize: font.size.sm, color: palette.textMuted, lineHeight: 19 },
  micBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    backgroundColor: palette.navy,
    borderRadius: radius.md,
    paddingVertical: 14,
  },
  micBtnRecording: { backgroundColor: palette.red },
  micBtnProcessing: { backgroundColor: palette.navySoft },
  micBtnText: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.white },
  transcriptReady: { backgroundColor: palette.surfaceAlt, borderRadius: radius.md, padding: spacing.md, gap: 8 },
  transcriptHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  transcriptReadyText: { flex: 1, fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.navy },
  transcriptRedo: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.greenBright },
  transcriptText: { fontSize: font.size.sm, color: palette.text, fontStyle: "italic", lineHeight: 20 },
  typedNote: { gap: 8 },
  typedLabel: { fontSize: font.size.xs, color: palette.textMuted, fontWeight: font.weight.semibold },
  typedInput: {
    backgroundColor: palette.surfaceAlt,
    borderRadius: radius.md,
    padding: spacing.md,
    color: palette.text,
    fontSize: font.size.sm,
    minHeight: 60,
    textAlignVertical: "top",
  },
  applyTyped: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: palette.surfaceAlt,
    borderRadius: radius.md,
    paddingVertical: 12,
  },
  applyTypedText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.navy },

  typeRow: { flexDirection: "row", gap: spacing.sm },
  typeCard: {
    flex: 1,
    borderWidth: 1.5,
    borderColor: palette.border,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: 2,
  },
  typeCardActive: { borderColor: palette.navy, backgroundColor: "#EEF2F9" },
  typeLabel: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.textMuted },
  typeHint: { fontSize: 10, color: palette.textFaint },

  photoHelper: { fontSize: font.size.sm, color: palette.textMuted, lineHeight: 19, marginBottom: spacing.sm },
  photoGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  photoThumb: { position: "relative" },
  photoRemove: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: palette.red,
    alignItems: "center",
    justifyContent: "center",
  },
  addPhoto: {
    width: 108,
    height: 92,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: palette.borderStrong,
    borderStyle: "dashed",
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  addPhotoPrimary: { backgroundColor: palette.navy, borderColor: palette.navy, borderStyle: "solid" },
  addPhotoText: { fontSize: font.size.xs, fontWeight: font.weight.semibold, color: palette.navy, textAlign: "center" },
  addPhotoPrimaryText: { color: palette.white },

  field: { paddingVertical: spacing.md },
  fieldBorder: { borderBottomWidth: 1, borderBottomColor: palette.border },
  fieldLabel: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted, marginBottom: spacing.sm },
  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: palette.surfaceAlt,
    borderWidth: 1,
    borderColor: palette.border,
  },
  chipActive: { backgroundColor: palette.navy, borderColor: palette.navy },
  chipActiveRed: { backgroundColor: palette.red, borderColor: palette.red },
  chipText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.text },
  customInput: {
    marginTop: spacing.sm,
    backgroundColor: palette.surfaceAlt,
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: font.size.sm,
    color: palette.text,
  },
  dueRow: { flexDirection: "row", gap: 8, marginTop: spacing.sm },
  dueHint: { fontSize: font.size.sm, color: palette.textMuted, marginTop: spacing.sm, fontWeight: font.weight.medium },

  textArea: {
    minHeight: 90,
    fontSize: font.size.md,
    color: palette.text,
    textAlignVertical: "top",
    lineHeight: 21,
  },

  actionBar: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    backgroundColor: palette.surface,
    borderTopWidth: 1,
    borderTopColor: palette.border,
  },
  btn: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, paddingVertical: 15, borderRadius: radius.md },
  btnGhost: { backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.borderStrong },
  btnGhostText: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.navy },
  btnPrimary: { backgroundColor: palette.navy },
  btnPrimaryText: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.white },
});
