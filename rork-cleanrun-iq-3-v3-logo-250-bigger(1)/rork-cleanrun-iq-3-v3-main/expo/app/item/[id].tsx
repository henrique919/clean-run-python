import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import {
  CheckCircle2,
  ClipboardCheck,
  History,
  MapPin,
  MessageSquare,
  Mic,
  RotateCcw,
  Send,
  ShieldCheck,
  Truck,
  Wrench,
  X,
} from "lucide-react-native";
import React, { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { EvidencePhoto } from "@/components/EvidencePhoto";
import { SectionCard } from "@/components/SectionCard";
import { FlagChip, PriorityChip, StatusChip, TypeChip } from "@/components/chips";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import {
  derivedFlags,
  formatDate,
  formatDateTime,
  formatLocation,
  isOverdue,
  itemTypeLabel,
  relativeTime,
  requiresCloseoutEvidence,
} from "@/lib/format";
import { useAppStore } from "@/providers/AppStore";
import { Item } from "@/types/models";

export default function ItemDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const store = useAppStore();
  const item = store.getItem(id);

  const [commentText, setCommentText] = useState<string>("");
  const [rejectOpen, setRejectOpen] = useState<boolean>(false);
  const [closeoutOpen, setCloseoutOpen] = useState<boolean>(false);
  const [reopenOpen, setReopenOpen] = useState<boolean>(false);

  if (!item) {
    return (
      <View style={styles.missing}>
        <Text style={styles.missingText}>Item not found</Text>
      </View>
    );
  }

  const flags = derivedFlags(item);
  const overdue = isOverdue(item);

  return (
    <View style={styles.flex}>
      <Stack.Screen options={{ title: item.code }} />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* A. Summary */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryTop}>
            <View style={{ flex: 1 }}>
              <Text style={styles.code}>{item.code}</Text>
              <Text style={styles.location}>{formatLocation(item)}</Text>
            </View>
            <TypeChip type={item.type} />
          </View>
          <View style={styles.summaryChips}>
            <StatusChip status={item.status} />
            <PriorityChip priority={item.priority} />
            {flags.map((f) => (
              <FlagChip key={f} label={f} />
            ))}
          </View>
          <View style={styles.summaryMeta}>
            <Meta label="Project" value={item.project} />
            <Meta label="Trade" value={item.trade || "—"} />
            <Meta label="Subcontractor" value={item.subcontractor || "Unassigned"} />
            <Meta label="Due" value={formatDate(item.dueDate)} tone={overdue ? palette.red : undefined} />
            {item.raisedBy ? <Meta label="Raised by" value={item.raisedBy} /> : null}
          </View>
        </View>

        {/* B. Original Issue */}
        <SectionCard title="Original Issue" accent={palette.navy}>
          <Text style={styles.description}>{item.description || "No description"}</Text>
          {(item.voiceNote || item.voiceTranscript) ? (
            <View style={styles.voiceQuote}>
              <Mic size={14} color={palette.green} />
              <View style={{ flex: 1 }}>
                <Text style={styles.voiceQuoteLabel}>Created from voice note</Text>
                <Text style={styles.voiceQuoteText} numberOfLines={4}>
                  “{item.voiceNote?.transcript ?? item.voiceTranscript}”
                </Text>
              </View>
            </View>
          ) : null}
          <PhotoRow photos={item.originalPhotos} emptyLabel="No original photos" />
          <Text style={styles.captureMeta}>
            Captured by {item.createdBy ?? "Site team"} · {formatDateTime(item.createdAt)}
          </Text>
        </SectionCard>

        {/* C. Assignment / Issue History */}
        <SectionCard
          title="Assignment & Issue History"
          accent={palette.sky}
          right={<Truck size={18} color={palette.sky} />}
        >
          {item.issueHistory.length === 0 ? (
            <Text style={styles.muted}>Not yet issued to a subcontractor.</Text>
          ) : (
            <View style={{ gap: spacing.sm }}>
              {item.issueHistory.map((ev, idx) => (
                <View key={`${ev.at}-${idx}`} style={styles.timelineRow}>
                  <View style={[styles.timelineDot, { backgroundColor: palette.sky }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.timelineTitle}>
                      {ev.reissue ? "Re-issued to" : "Issued to"} {ev.to}
                    </Text>
                    <Text style={styles.timelineMeta}>
                      {ev.by ? `${ev.by} · ` : ""}
                      {formatDateTime(ev.at)}
                    </Text>
                    {ev.note ? <Text style={styles.timelineNote}>{ev.note}</Text> : null}
                  </View>
                </View>
              ))}
            </View>
          )}
        </SectionCard>

        {/* D. Subcontractor Response */}
        <SectionCard
          title="Subcontractor Rectification"
          subtitle="Evidence uploaded by the trade"
          accent={palette.amber}
          right={<Wrench size={18} color={palette.amber} />}
        >
          {item.rectificationEvidence.length === 0 ? (
            <Text style={styles.muted}>No rectification evidence yet.</Text>
          ) : (
            <View style={{ gap: spacing.md }}>
              {item.rectificationEvidence.map((ev) => (
                <View key={ev.id} style={styles.evidenceRow}>
                  {ev.photo ? <EvidencePhoto uri={ev.photo} size={72} /> : null}
                  <View style={{ flex: 1 }}>
                    {ev.comment ? <Text style={styles.evidenceComment}>{ev.comment}</Text> : null}
                    <Text style={styles.evidenceMeta}>
                      {ev.by} · {relativeTime(ev.at)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </SectionCard>

        {/* E. Inspection */}
        {item.inspectionHistory.length > 0 || item.status === "under_inspection" ? (
          <SectionCard
            title="Inspection"
            accent={palette.violet}
            right={<ClipboardCheck size={18} color={palette.violet} />}
          >
            {item.inspectionHistory.length === 0 ? (
              <Text style={styles.muted}>Inspection in progress.</Text>
            ) : (
              <View style={{ gap: spacing.sm }}>
                {item.inspectionHistory.map((ev, idx) => (
                  <View key={`${ev.at}-${idx}`} style={styles.timelineRow}>
                    <View
                      style={[
                        styles.timelineDot,
                        { backgroundColor: ev.action === "rejected" ? palette.red : palette.violet },
                      ]}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.timelineTitle}>
                        Inspection {ev.action}
                      </Text>
                      <Text style={styles.timelineMeta}>
                        {ev.by} · {formatDateTime(ev.at)}
                      </Text>
                      {ev.reason ? <Text style={styles.rejectReason}>{ev.reason}</Text> : null}
                    </View>
                  </View>
                ))}
              </View>
            )}
          </SectionCard>
        ) : null}

        {/* F. Closeout Evidence */}
        <SectionCard
          title="Closeout Evidence"
          subtitle="Supervisor sign-off proof"
          accent={palette.green}
          right={<ShieldCheck size={18} color={palette.green} />}
        >
          {item.closeoutEvidence.length === 0 ? (
            <Text style={styles.muted}>
              {requiresCloseoutEvidence(item.type)
                ? "Closeout evidence required before this item can be closed."
                : "No closeout evidence recorded."}
            </Text>
          ) : (
            <View style={{ gap: spacing.md }}>
              {item.closeoutEvidence.map((ev) => (
                <View key={ev.id} style={styles.closeoutRow}>
                  {ev.photo ? <EvidencePhoto uri={ev.photo} size={72} /> : null}
                  <View style={{ flex: 1 }}>
                    {ev.note ? <Text style={styles.evidenceComment}>{ev.note}</Text> : null}
                    {ev.confirmation ? (
                      <View style={styles.confirmRow}>
                        <CheckCircle2 size={13} color={palette.green} />
                        <Text style={styles.confirmText}>{ev.confirmation}</Text>
                      </View>
                    ) : null}
                    <Text style={styles.evidenceMeta}>
                      {ev.by} ({ev.role}) · {formatDateTime(ev.at)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </SectionCard>

        {/* Comments */}
        <SectionCard title="Comments" right={<MessageSquare size={18} color={palette.textMuted} />}>
          {item.comments.length === 0 ? (
            <Text style={styles.muted}>No comments.</Text>
          ) : (
            <View style={{ gap: spacing.sm, marginBottom: spacing.sm }}>
              {item.comments.map((c) => (
                <View key={c.id} style={styles.comment}>
                  <Text style={styles.commentText}>{c.text}</Text>
                  <Text style={styles.commentMeta}>
                    {c.by} · {relativeTime(c.at)}
                  </Text>
                </View>
              ))}
            </View>
          )}
          <View style={styles.commentInputRow}>
            <TextInput
              style={styles.commentInput}
              placeholder="Add a comment…"
              placeholderTextColor={palette.textFaint}
              value={commentText}
              onChangeText={setCommentText}
            />
            <Pressable
              style={styles.commentSend}
              onPress={() => {
                if (!commentText.trim()) return;
                store.addComment(item.id, { text: commentText.trim(), by: store.settings.preparedBy });
                setCommentText("");
              }}
            >
              <Send size={16} color={palette.white} />
            </Pressable>
          </View>
        </SectionCard>

        {/* G. Audit Trail */}
        <SectionCard title="Audit Trail" right={<History size={18} color={palette.textMuted} />}>
          <View style={{ gap: spacing.sm }}>
            {[...item.auditEvents].reverse().map((ev, idx) => (
              <View key={`${ev.at}-${idx}`} style={styles.auditRow}>
                <View style={styles.auditDot} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.auditAction}>{ev.action}</Text>
                  <Text style={styles.auditMeta}>
                    {ev.by ? `${ev.by} · ` : ""}
                    {formatDateTime(ev.at)}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        </SectionCard>

        <View style={{ height: 12 }} />
      </ScrollView>

      <ActionBar
        item={item}
        onReject={() => setRejectOpen(true)}
        onCloseout={() => setCloseoutOpen(true)}
        onReopen={() => setReopenOpen(true)}
      />

      <RejectDialog
        visible={rejectOpen}
        onClose={() => setRejectOpen(false)}
        onSubmit={(reason) => {
          store.reject(item.id, store.settings.preparedBy, reason);
          setRejectOpen(false);
        }}
      />
      <CloseoutDialog
        visible={closeoutOpen}
        item={item}
        preparedBy={store.settings.preparedBy}
        onClose={() => setCloseoutOpen(false)}
        onSubmit={(payload) => {
          store.closeWithEvidence(item.id, [payload]);
          setCloseoutOpen(false);
          router.back();
        }}
      />
      <ReopenDialog
        visible={reopenOpen}
        onClose={() => setReopenOpen(false)}
        onSubmit={(reason) => {
          store.reopen(item.id, store.settings.preparedBy, reason);
          setReopenOpen(false);
        }}
      />
    </View>
  );
}

function ActionBar({
  item,
  onReject,
  onCloseout,
  onReopen,
}: {
  item: Item;
  onReject: () => void;
  onCloseout: () => void;
  onReopen: () => void;
}) {
  const store = useAppStore();
  const by = store.settings.preparedBy;

  const haptic = () => {
    if (Platform.OS !== "web") Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  const buttons = useMemo(() => {
    const list: { label: string; onPress: () => void; variant: "primary" | "ghost" | "danger" }[] = [];
    switch (item.status) {
      case "open":
        list.push({ label: "Issue to subcontractor", variant: "primary", onPress: () => issue() });
        break;
      case "issued":
        list.push({ label: "Mark In Progress", variant: "primary", onPress: () => store.markInProgress(item.id, item.subcontractor) });
        list.push({ label: "Re-issue", variant: "ghost", onPress: () => issue(true) });
        break;
      case "in_progress":
        list.push({ label: "Mark Ready for Review", variant: "primary", onPress: () => store.markReady(item.id, item.subcontractor) });
        list.push({ label: "Re-issue", variant: "ghost", onPress: () => issue(true) });
        break;
      case "ready_for_review":
        list.push({ label: "Start Inspection", variant: "primary", onPress: () => store.startInspection(item.id, by) });
        list.push({ label: "Reject", variant: "danger", onPress: onReject });
        break;
      case "under_inspection":
        if (item.type === "incomplete") {
          list.push({ label: "Mark Complete", variant: "primary", onPress: onCloseout });
        } else {
          list.push({ label: "Close with Evidence", variant: "primary", onPress: onCloseout });
        }
        list.push({ label: "Reject", variant: "danger", onPress: onReject });
        break;
      case "rejected":
        list.push({ label: "Re-issue", variant: "primary", onPress: () => issue(true) });
        list.push({ label: "Return to In Progress", variant: "ghost", onPress: () => store.markInProgress(item.id, item.subcontractor) });
        break;
      case "closed":
      case "complete":
        list.push({ label: "Reopen (Admin)", variant: "ghost", onPress: onReopen });
        break;
    }
    return list;

    function issue(reissue?: boolean) {
      if (!item.subcontractor || !item.trade) {
        Alert.alert("Assign first", "Issuing requires a trade and subcontractor. Edit the item to assign one.");
        return;
      }
      store.issue(item.id, { to: item.subcontractor, by, reissue });
      haptic();
    }
  }, [item, store, by, onReject, onCloseout, onReopen]);

  const incompleteComplete = item.status === "complete";

  return (
    <SafeAreaView edges={["bottom"]} style={styles.actionBar}>
      {item.status === "closed" || incompleteComplete ? (
        <View style={styles.closedBanner}>
          <CheckCircle2 size={18} color={palette.green} />
          <Text style={styles.closedText}>
            {item.type === "incomplete" ? "Complete" : "Closed with evidence"} · read-only
          </Text>
        </View>
      ) : null}
      <View style={styles.actionRow}>
        {buttons.map((b) => (
          <Pressable
            key={b.label}
            style={[
              styles.actionBtn,
              b.variant === "primary" && styles.actionPrimary,
              b.variant === "ghost" && styles.actionGhost,
              b.variant === "danger" && styles.actionDanger,
            ]}
            onPress={b.onPress}
          >
            <Text
              style={[
                styles.actionLabel,
                b.variant === "primary" && { color: palette.white },
                b.variant === "danger" && { color: palette.white },
                b.variant === "ghost" && { color: palette.navy },
              ]}
            >
              {b.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

function RejectDialog({
  visible,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState<string>("");
  return (
    <DialogShell visible={visible} title="Reject on inspection" onClose={onClose}>
      <Text style={styles.dialogLabel}>Why is this being rejected?</Text>
      <TextInput
        style={styles.dialogInput}
        placeholder="Describe what still needs rectifying…"
        placeholderTextColor={palette.textFaint}
        value={reason}
        onChangeText={setReason}
        multiline
      />
      <Pressable
        style={[styles.dialogBtn, styles.actionDanger, !reason.trim() && styles.dialogBtnDisabled]}
        disabled={!reason.trim()}
        onPress={() => {
          onSubmit(reason.trim());
          setReason("");
        }}
      >
        <Text style={[styles.actionLabel, { color: palette.white }]}>Reject & return</Text>
      </Pressable>
    </DialogShell>
  );
}

function CloseoutDialog({
  visible,
  item,
  preparedBy,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  item: Item;
  preparedBy: string;
  onClose: () => void;
  onSubmit: (payload: { photo?: string; by: string; role: string; note?: string; confirmation: string }) => void;
}) {
  const [photo, setPhoto] = useState<string | undefined>(undefined);
  const [note, setNote] = useState<string>("");
  const [role, setRole] = useState<string>("Site Manager");
  const [confirmed, setConfirmed] = useState<boolean>(false);
  const requiresPhoto = requiresCloseoutEvidence(item.type);

  const reset = () => {
    setPhoto(undefined);
    setNote("");
    setConfirmed(false);
  };

  const pick = async () => {
    const res = await ImagePicker.launchCameraAsync({ quality: 0.6 }).catch(() => null);
    if (res && !res.canceled && res.assets[0]) {
      setPhoto(res.assets[0].uri);
      return;
    }
    const lib = await ImagePicker.launchImageLibraryAsync({ quality: 0.6, mediaTypes: ["images"] }).catch(() => null);
    if (lib && !lib.canceled && lib.assets[0]) setPhoto(lib.assets[0].uri);
  };

  const canSubmit = confirmed && (!requiresPhoto || !!photo);

  return (
    <DialogShell visible={visible} title={item.type === "incomplete" ? "Mark complete" : "Close with evidence"} onClose={onClose}>
      <Text style={styles.dialogLabel}>
        Closeout photo {requiresPhoto ? "(required)" : "(optional)"}
      </Text>
      {photo ? (
        <View style={styles.closeoutPhoto}>
          <EvidencePhoto uri={photo} size={96} />
          <Pressable style={styles.photoRemove} onPress={() => setPhoto(undefined)}>
            <X size={13} color={palette.white} />
          </Pressable>
        </View>
      ) : (
        <Pressable style={styles.addCloseoutPhoto} onPress={pick}>
          <ShieldCheck size={20} color={palette.navy} />
          <Text style={styles.addPhotoText}>Add closeout photo</Text>
        </Pressable>
      )}

      <Text style={styles.dialogLabel}>Signed off by role</Text>
      <View style={styles.roleRow}>
        {["Site Manager", "Supervisor", "Foreman", "PM"].map((r) => (
          <Pressable
            key={r}
            style={[styles.roleChip, role === r && styles.roleChipActive]}
            onPress={() => setRole(r)}
          >
            <Text style={[styles.roleChipText, role === r && { color: palette.white }]}>{r}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.dialogLabel}>Note (optional)</Text>
      <TextInput
        style={styles.dialogInput}
        placeholder="Confirm what was verified at closeout…"
        placeholderTextColor={palette.textFaint}
        value={note}
        onChangeText={setNote}
        multiline
      />

      <Pressable style={styles.confirmCheck} onPress={() => setConfirmed((c) => !c)}>
        <View style={[styles.checkbox, confirmed && styles.checkboxOn]}>
          {confirmed ? <CheckCircle2 size={16} color={palette.white} /> : null}
        </View>
        <Text style={styles.confirmCheckText}>
          I confirm this item is rectified and accepted by {preparedBy}.
        </Text>
      </Pressable>

      <Pressable
        style={[styles.dialogBtn, styles.actionPrimary, !canSubmit && styles.dialogBtnDisabled]}
        disabled={!canSubmit}
        onPress={() => {
          onSubmit({ photo, by: preparedBy, role, note: note.trim() || undefined, confirmation: "Confirmed rectified" });
          reset();
        }}
      >
        <Text style={[styles.actionLabel, { color: palette.white }]}>
          {item.type === "incomplete" ? "Mark complete" : "Close item"}
        </Text>
      </Pressable>
    </DialogShell>
  );
}

function ReopenDialog({
  visible,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState<string>("");
  return (
    <DialogShell visible={visible} title="Reopen item" onClose={onClose}>
      <View style={styles.reopenWarn}>
        <RotateCcw size={16} color="#B45309" />
        <Text style={styles.reopenWarnText}>Reopening returns the item to In Progress and logs the reason.</Text>
      </View>
      <Text style={styles.dialogLabel}>Reason for reopening</Text>
      <TextInput
        style={styles.dialogInput}
        placeholder="Why is this being reopened?"
        placeholderTextColor={palette.textFaint}
        value={reason}
        onChangeText={setReason}
        multiline
      />
      <Pressable
        style={[styles.dialogBtn, styles.actionPrimary, !reason.trim() && styles.dialogBtnDisabled]}
        disabled={!reason.trim()}
        onPress={() => {
          onSubmit(reason.trim());
          setReason("");
        }}
      >
        <Text style={[styles.actionLabel, { color: palette.white }]}>Reopen item</Text>
      </Pressable>
    </DialogShell>
  );
}

function DialogShell({
  visible,
  title,
  onClose,
  children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.dialogBackdrop} onPress={onClose}>
        <Pressable style={styles.dialogSheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.dialogHeader}>
            <Text style={styles.dialogTitle}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <X size={22} color={palette.textMuted} />
            </Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: spacing.sm }}>
            {children}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function PhotoRow({ photos, emptyLabel }: { photos: string[]; emptyLabel: string }) {
  if (photos.length === 0) return <Text style={styles.muted}>{emptyLabel}</Text>;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.photoRow}>
      {photos.map((p, idx) => (
        <EvidencePhoto key={`${p}-${idx}`} uri={p} size={120} />
      ))}
    </ScrollView>
  );
}

function Meta({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={[styles.metaValue, tone ? { color: tone } : null]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xxl },
  missing: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: palette.background },
  missingText: { fontSize: font.size.md, color: palette.textMuted },

  summaryCard: { backgroundColor: palette.navy, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md, ...shadow.card },
  summaryTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  code: { fontSize: font.size.xxl, fontWeight: font.weight.heavy, color: palette.white, letterSpacing: 0.4 },
  location: { fontSize: font.size.sm, color: "rgba(255,255,255,0.7)", marginTop: 2 },
  summaryChips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  summaryMeta: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.12)", paddingTop: spacing.md },
  metaItem: { minWidth: "28%" },
  metaLabel: { fontSize: 10, color: "rgba(255,255,255,0.5)", fontWeight: font.weight.semibold, textTransform: "uppercase", letterSpacing: 0.5 },
  metaValue: { fontSize: font.size.sm, color: palette.white, fontWeight: font.weight.semibold, marginTop: 2 },

  description: { fontSize: font.size.md, color: palette.text, lineHeight: 22, marginBottom: spacing.md },
  voiceQuote: { flexDirection: "row", gap: 8, backgroundColor: palette.greenSoft, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.md },
  voiceQuoteLabel: { fontSize: font.size.xs, fontWeight: font.weight.bold, color: "#15803D", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.4 },
  voiceQuoteText: { fontSize: font.size.sm, color: "#15803D", fontStyle: "italic", lineHeight: 19 },
  captureMeta: { fontSize: font.size.xs, color: palette.textFaint, marginTop: spacing.sm },
  photoRow: { gap: spacing.sm, paddingVertical: 4 },

  muted: { fontSize: font.size.sm, color: palette.textFaint },
  timelineRow: { flexDirection: "row", gap: spacing.md },
  timelineDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  timelineTitle: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.text },
  timelineMeta: { fontSize: font.size.xs, color: palette.textMuted, marginTop: 1 },
  timelineNote: { fontSize: font.size.sm, color: palette.text, marginTop: 4, fontStyle: "italic" },
  rejectReason: { fontSize: font.size.sm, color: palette.red, marginTop: 4, fontWeight: font.weight.medium },

  evidenceRow: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  evidenceComment: { fontSize: font.size.sm, color: palette.text, lineHeight: 19 },
  evidenceMeta: { fontSize: font.size.xs, color: palette.textFaint, marginTop: 4 },
  closeoutRow: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  confirmRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  confirmText: { fontSize: font.size.xs, color: palette.green, fontWeight: font.weight.bold },

  comment: { backgroundColor: palette.surfaceAlt, borderRadius: radius.md, padding: spacing.md },
  commentText: { fontSize: font.size.sm, color: palette.text, lineHeight: 19 },
  commentMeta: { fontSize: font.size.xs, color: palette.textFaint, marginTop: 4 },
  commentInputRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  commentInput: { flex: 1, backgroundColor: palette.surfaceAlt, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 10, fontSize: font.size.sm, color: palette.text },
  commentSend: { width: 40, height: 40, borderRadius: 20, backgroundColor: palette.navy, alignItems: "center", justifyContent: "center" },

  auditRow: { flexDirection: "row", gap: spacing.md },
  auditDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: palette.borderStrong, marginTop: 5 },
  auditAction: { fontSize: font.size.sm, fontWeight: font.weight.medium, color: palette.text },
  auditMeta: { fontSize: font.size.xs, color: palette.textFaint, marginTop: 1 },

  actionBar: { backgroundColor: palette.surface, borderTopWidth: 1, borderTopColor: palette.border, paddingHorizontal: spacing.lg, paddingTop: spacing.md, gap: spacing.sm },
  closedBanner: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: palette.greenSoft, borderRadius: radius.md, padding: spacing.sm },
  closedText: { fontSize: font.size.sm, color: "#15803D", fontWeight: font.weight.semibold },
  actionRow: { flexDirection: "row", gap: spacing.sm },
  actionBtn: { flex: 1, paddingVertical: 14, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  actionPrimary: { backgroundColor: palette.navy },
  actionGhost: { backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.borderStrong },
  actionDanger: { backgroundColor: palette.red },
  actionLabel: { fontSize: font.size.sm, fontWeight: font.weight.bold },

  dialogBackdrop: { flex: 1, backgroundColor: "rgba(10,24,48,0.55)", justifyContent: "flex-end" },
  dialogSheet: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, maxHeight: "88%" },
  dialogHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  dialogTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text },
  dialogLabel: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted, marginTop: spacing.sm },
  dialogInput: { backgroundColor: palette.surfaceAlt, borderRadius: radius.md, padding: spacing.md, fontSize: font.size.sm, color: palette.text, minHeight: 70, textAlignVertical: "top" },
  dialogBtn: { paddingVertical: 15, borderRadius: radius.md, alignItems: "center", marginTop: spacing.md },
  dialogBtnDisabled: { opacity: 0.4 },

  closeoutPhoto: { alignSelf: "flex-start", position: "relative" },
  addCloseoutPhoto: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, borderWidth: 1.5, borderStyle: "dashed", borderColor: palette.borderStrong, borderRadius: radius.md, paddingVertical: 18 },
  addPhotoText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.navy },
  photoRemove: { position: "absolute", top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: palette.red, alignItems: "center", justifyContent: "center" },
  roleRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  roleChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.border },
  roleChipActive: { backgroundColor: palette.navy, borderColor: palette.navy },
  roleChipText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.text },
  confirmCheck: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md },
  checkbox: { width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: palette.borderStrong, alignItems: "center", justifyContent: "center" },
  checkboxOn: { backgroundColor: palette.green, borderColor: palette.green },
  confirmCheckText: { flex: 1, fontSize: font.size.sm, color: palette.text, lineHeight: 19 },
  reopenWarn: { flexDirection: "row", gap: 8, backgroundColor: palette.amberSoft, borderRadius: radius.md, padding: spacing.md },
  reopenWarnText: { flex: 1, fontSize: font.size.sm, color: "#B45309", lineHeight: 18 },
});
