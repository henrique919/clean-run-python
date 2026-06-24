import * as ImagePicker from "expo-image-picker";
import { ChevronDown, HardHat, Send, Upload, X } from "lucide-react-native";
import React, { useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { EvidencePhoto } from "@/components/EvidencePhoto";
import { StatusChip } from "@/components/chips";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { formatDate, formatLocation, isOverdue } from "@/lib/format";
import { useAppStore } from "@/providers/AppStore";
import { Item } from "@/types/models";

export default function SubcontractorScreen() {
  const { items, settings, addRectification } = useAppStore();
  const [sub, setSub] = useState<string>(settings.subcontractors[0] ?? "");
  const [pickerOpen, setPickerOpen] = useState<boolean>(false);
  const [activeItem, setActiveItem] = useState<Item | null>(null);

  // Subcontractors only see their own assigned, still-active items.
  const assigned = useMemo(
    () =>
      items.filter(
        (i) =>
          i.subcontractor === sub &&
          i.status !== "closed" &&
          i.status !== "complete",
      ),
    [items, sub],
  );

  return (
    <View style={styles.flex}>
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <HardHat size={20} color={palette.amber} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerLabel}>Subcontractor view</Text>
          <Pressable style={styles.subSelect} onPress={() => setPickerOpen(true)}>
            <Text style={styles.subName}>{sub || "Select subcontractor"}</Text>
            <ChevronDown size={18} color={palette.navy} />
          </Pressable>
        </View>
      </View>

      <View style={styles.notice}>
        <Text style={styles.noticeText}>
          You only see items assigned to you. Upload rectification evidence and mark ready for review.
        </Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {assigned.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No open items</Text>
            <Text style={styles.emptySub}>Nothing is currently assigned to {sub || "this subcontractor"}.</Text>
          </View>
        ) : (
          assigned.map((item) => (
            <View key={item.id} style={styles.card}>
              <View style={styles.cardHead}>
                <Text style={styles.code}>{item.code}</Text>
                <StatusChip status={item.status} />
              </View>
              <Text style={styles.loc}>{formatLocation(item)}</Text>
              <Text style={styles.desc}>{item.description}</Text>

              {item.originalPhotos.length > 0 ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.photos}>
                  {item.originalPhotos.map((p, idx) => (
                    <EvidencePhoto key={`${p}-${idx}`} uri={p} size={88} />
                  ))}
                </ScrollView>
              ) : null}

              {item.rejectionReason ? (
                <View style={styles.reject}>
                  <Text style={styles.rejectTitle}>Rejected — re-work needed</Text>
                  <Text style={styles.rejectText}>{item.rejectionReason}</Text>
                </View>
              ) : null}

              {item.rectificationEvidence.length > 0 ? (
                <Text style={styles.uploaded}>
                  {item.rectificationEvidence.length} rectification upload
                  {item.rectificationEvidence.length > 1 ? "s" : ""} submitted
                </Text>
              ) : null}

              <View style={styles.cardFooter}>
                <Text style={[styles.due, isOverdue(item) && { color: palette.red, fontWeight: "700" }]}>
                  Due {formatDate(item.dueDate)}
                </Text>
                <Pressable style={styles.uploadBtn} onPress={() => setActiveItem(item)}>
                  <Upload size={15} color={palette.white} />
                  <Text style={styles.uploadBtnText}>Upload evidence</Text>
                </Pressable>
              </View>
            </View>
          ))
        )}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Subcontractor picker */}
      <Modal visible={pickerOpen} transparent animationType="fade" onRequestClose={() => setPickerOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setPickerOpen(false)}>
          <View style={styles.pickerSheet}>
            <Text style={styles.pickerTitle}>Select subcontractor</Text>
            <ScrollView style={{ maxHeight: 380 }}>
              {settings.subcontractors.map((s) => (
                <Pressable
                  key={s}
                  style={[styles.pickerRow, s === sub && styles.pickerRowActive]}
                  onPress={() => {
                    setSub(s);
                    setPickerOpen(false);
                  }}
                >
                  <Text style={styles.pickerRowText}>{s}</Text>
                  <Text style={styles.pickerRowMeta}>
                    {items.filter((i) => i.subcontractor === s && i.status !== "closed" && i.status !== "complete").length} open
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>

      {/* Upload rectification */}
      <UploadDialog
        item={activeItem}
        sub={sub}
        onClose={() => setActiveItem(null)}
        onSubmit={(photo, comment, advance) => {
          if (!activeItem) return;
          addRectification(activeItem.id, { photo, comment, by: sub, advanceToReady: advance });
          setActiveItem(null);
        }}
      />
    </View>
  );
}

function UploadDialog({
  item,
  sub,
  onClose,
  onSubmit,
}: {
  item: Item | null;
  sub: string;
  onClose: () => void;
  onSubmit: (photo: string | undefined, comment: string | undefined, advance: boolean) => void;
}) {
  const [photo, setPhoto] = useState<string | undefined>(undefined);
  const [comment, setComment] = useState<string>("");

  const pick = async () => {
    const res = await ImagePicker.launchCameraAsync({ quality: 0.6 }).catch(() => null);
    if (res && !res.canceled && res.assets[0]) {
      setPhoto(res.assets[0].uri);
      return;
    }
    const lib = await ImagePicker.launchImageLibraryAsync({ quality: 0.6, mediaTypes: ["images"] }).catch(() => null);
    if (lib && !lib.canceled && lib.assets[0]) setPhoto(lib.assets[0].uri);
  };

  const reset = () => {
    setPhoto(undefined);
    setComment("");
  };

  const submit = (advance: boolean) => {
    if (!photo && !comment.trim()) {
      Alert.alert("Add evidence", "Attach a photo or add a comment before submitting.");
      return;
    }
    onSubmit(photo, comment.trim() || undefined, advance);
    reset();
  };

  return (
    <Modal visible={!!item} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.dialog} onPress={(e) => e.stopPropagation()}>
          <View style={styles.dialogHeader}>
            <Text style={styles.dialogTitle}>{item?.code} · Rectification</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <X size={22} color={palette.textMuted} />
            </Pressable>
          </View>

          {photo ? (
            <View style={styles.photoPreview}>
              <EvidencePhoto uri={photo} size={110} />
              <Pressable style={styles.photoRemove} onPress={() => setPhoto(undefined)}>
                <X size={13} color={palette.white} />
              </Pressable>
            </View>
          ) : (
            <Pressable style={styles.addPhoto} onPress={pick}>
              <Upload size={20} color={palette.navy} />
              <Text style={styles.addPhotoText}>Add rectification photo</Text>
            </Pressable>
          )}

          <TextInput
            style={styles.commentInput}
            placeholder="Comment on the work completed…"
            placeholderTextColor={palette.textFaint}
            value={comment}
            onChangeText={setComment}
            multiline
          />

          <View style={styles.dialogActions}>
            <Pressable style={[styles.dialogBtn, styles.ghostBtn]} onPress={() => submit(false)}>
              <Text style={styles.ghostBtnText}>Save progress</Text>
            </Pressable>
            <Pressable style={[styles.dialogBtn, styles.primaryBtn]} onPress={() => submit(true)}>
              <Send size={15} color={palette.white} />
              <Text style={styles.primaryBtnText}>Mark ready</Text>
            </Pressable>
          </View>
          <Text style={styles.dialogNote}>Submitted as {sub}</Text>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border },
  headerIcon: { width: 44, height: 44, borderRadius: 14, backgroundColor: palette.amberSoft, alignItems: "center", justifyContent: "center" },
  headerLabel: { fontSize: font.size.xs, color: palette.textMuted, fontWeight: font.weight.semibold, textTransform: "uppercase", letterSpacing: 0.5 },
  subSelect: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  subName: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.navy },

  notice: { backgroundColor: palette.skySoft, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  noticeText: { fontSize: font.size.sm, color: "#0369A1", lineHeight: 18 },

  scroll: { padding: spacing.lg, gap: spacing.md },
  empty: { alignItems: "center", gap: 6, padding: spacing.xxl },
  emptyTitle: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  emptySub: { fontSize: font.size.sm, color: palette.textMuted, textAlign: "center" },

  card: { backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, gap: spacing.sm, ...shadow.card },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  code: { fontSize: font.size.md, fontWeight: font.weight.heavy, color: palette.navy },
  loc: { fontSize: font.size.sm, color: palette.textMuted },
  desc: { fontSize: font.size.sm, color: palette.text, lineHeight: 19 },
  photos: { gap: spacing.sm, paddingVertical: 4 },
  reject: { backgroundColor: palette.redSoft, borderRadius: radius.md, padding: spacing.md },
  rejectTitle: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: "#B91C1C" },
  rejectText: { fontSize: font.size.sm, color: "#B91C1C", marginTop: 2 },
  uploaded: { fontSize: font.size.xs, color: palette.green, fontWeight: font.weight.semibold },
  cardFooter: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderTopWidth: 1, borderTopColor: palette.border, paddingTop: spacing.sm },
  due: { fontSize: font.size.sm, color: palette.textMuted },
  uploadBtn: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: palette.amber, paddingHorizontal: 14, paddingVertical: 9, borderRadius: radius.pill },
  uploadBtnText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.white },

  backdrop: { flex: 1, backgroundColor: "rgba(10,24,48,0.55)", justifyContent: "flex-end" },
  pickerSheet: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, paddingBottom: spacing.xxl },
  pickerTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text, marginBottom: spacing.md },
  pickerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: spacing.md, paddingHorizontal: spacing.md, borderRadius: radius.md },
  pickerRowActive: { backgroundColor: palette.surfaceAlt },
  pickerRowText: { fontSize: font.size.md, fontWeight: font.weight.semibold, color: palette.text },
  pickerRowMeta: { fontSize: font.size.sm, color: palette.textMuted },

  dialog: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
  dialogHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  dialogTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text },
  photoPreview: { alignSelf: "flex-start", position: "relative" },
  photoRemove: { position: "absolute", top: -6, right: -6, width: 22, height: 22, borderRadius: 11, backgroundColor: palette.red, alignItems: "center", justifyContent: "center" },
  addPhoto: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, borderWidth: 1.5, borderStyle: "dashed", borderColor: palette.borderStrong, borderRadius: radius.md, paddingVertical: 18 },
  addPhotoText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.navy },
  commentInput: { backgroundColor: palette.surfaceAlt, borderRadius: radius.md, padding: spacing.md, fontSize: font.size.sm, color: palette.text, minHeight: 70, textAlignVertical: "top" },
  dialogActions: { flexDirection: "row", gap: spacing.sm },
  dialogBtn: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 14, borderRadius: radius.md },
  ghostBtn: { backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.borderStrong },
  ghostBtnText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.navy },
  primaryBtn: { backgroundColor: palette.green },
  primaryBtnText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.white },
  dialogNote: { fontSize: font.size.xs, color: palette.textFaint, textAlign: "center" },
});
