import { useRouter } from "expo-router";
import { CalendarClock, ChevronRight, ImageIcon, ShieldCheck } from "lucide-react-native";
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { EvidencePhoto } from "@/components/EvidencePhoto";
import { FlagChip, PriorityChip, StatusChip, TypeChip } from "@/components/chips";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { derivedFlags, formatDate, formatLocation, isOverdue, nextActionLabel } from "@/lib/format";
import { Item } from "@/types/models";

export function ItemCard({ item }: { item: Item }) {
  const router = useRouter();
  const overdue = isOverdue(item);
  const flags = derivedFlags(item);
  const thumb = item.originalPhotos[0];
  const evidenceCount =
    item.originalPhotos.length + item.rectificationEvidence.length + item.closeoutEvidence.length;
  const closed = item.status === "closed" || item.status === "complete";

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={() => router.push(`/item/${item.id}`)}
    >
      <View style={styles.row}>
        {thumb ? (
          <EvidencePhoto uri={thumb} size={64} />
        ) : (
          <View style={styles.noThumb}>
            <ImageIcon size={20} color={palette.textFaint} />
          </View>
        )}

        <View style={{ flex: 1 }}>
          <View style={styles.topRow}>
            <Text style={styles.code}>{item.code}</Text>
            <TypeChip type={item.type} />
          </View>
          <Text style={styles.location} numberOfLines={1}>
            {formatLocation(item)}
          </Text>
          <Text style={styles.description} numberOfLines={2}>
            {item.description || "No description"}
          </Text>
        </View>
      </View>

      <View style={styles.metaRow}>
        <StatusChip status={item.status} />
        <PriorityChip priority={item.priority} />
        {flags.slice(0, 1).map((f) => (
          <FlagChip key={f} label={f} />
        ))}
      </View>

      <View style={styles.footer}>
        <View style={styles.footerLeft}>
          <CalendarClock size={14} color={overdue ? palette.red : palette.textMuted} />
          <Text style={[styles.due, overdue && { color: palette.red, fontWeight: font.weight.bold }]}>
            {closed ? "Closed" : `Due ${formatDate(item.dueDate)}`}
          </Text>
          {evidenceCount > 0 ? (
            <View style={styles.evidence}>
              <ShieldCheck size={13} color={palette.green} />
              <Text style={styles.evidenceText}>{evidenceCount}</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.action}>
          <Text style={styles.actionText} numberOfLines={1}>
            {nextActionLabel(item.status)}
          </Text>
          <ChevronRight size={16} color={palette.navy} />
        </View>
      </View>

      <Text style={styles.sub} numberOfLines={1}>
        {item.subcontractor || "Unassigned"} · {item.trade || "No trade"}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadow.card,
  },
  pressed: { opacity: 0.85, transform: [{ scale: 0.992 }] },
  row: { flexDirection: "row", gap: spacing.md },
  noThumb: {
    width: 64,
    height: 64,
    borderRadius: radius.md,
    backgroundColor: palette.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  code: { fontSize: font.size.md, fontWeight: font.weight.heavy, color: palette.text, letterSpacing: 0.3 },
  location: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 3 },
  description: { fontSize: font.size.sm, color: palette.text, marginTop: 4, lineHeight: 19 },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: palette.border,
    paddingTop: spacing.sm,
  },
  footerLeft: { flexDirection: "row", alignItems: "center", gap: 6 },
  due: { fontSize: font.size.sm, color: palette.textMuted },
  evidence: { flexDirection: "row", alignItems: "center", gap: 3, marginLeft: 6 },
  evidenceText: { fontSize: font.size.xs, color: palette.green, fontWeight: font.weight.bold },
  action: { flexDirection: "row", alignItems: "center", gap: 2, maxWidth: "55%" },
  actionText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.navy },
  sub: { fontSize: font.size.xs, color: palette.textFaint, fontWeight: font.weight.medium },
});
