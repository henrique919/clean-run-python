import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { font, palette, radius } from "@/constants/theme";
import { ItemStatus, ItemType, Priority } from "@/types/models";

type Visual = { label: string; fg: string; bg: string; dot: string };

const STATUS_VISUAL: Record<ItemStatus, Visual> = {
  open: { label: "Open", fg: palette.textMuted, bg: palette.surfaceAlt, dot: palette.textFaint },
  issued: { label: "Issued", fg: "#0369A1", bg: palette.skySoft, dot: palette.sky },
  in_progress: { label: "In Progress", fg: "#B45309", bg: palette.amberSoft, dot: palette.amber },
  ready_for_review: { label: "Ready for Review", fg: "#6D28D9", bg: palette.violetSoft, dot: palette.violet },
  under_inspection: { label: "Under Inspection", fg: "#6D28D9", bg: palette.violetSoft, dot: palette.violet },
  rejected: { label: "Rejected", fg: "#B91C1C", bg: palette.redSoft, dot: palette.red },
  closed: { label: "Closed", fg: "#15803D", bg: palette.greenSoft, dot: palette.green },
  complete: { label: "Complete", fg: "#15803D", bg: palette.greenSoft, dot: palette.green },
};

const TYPE_VISUAL: Record<ItemType, { label: string; fg: string; bg: string }> = {
  defect: { label: "Defect", fg: palette.navy, bg: "#E7ECF5" },
  incomplete: { label: "Incomplete", fg: "#0369A1", bg: palette.skySoft },
  client: { label: "Client Defect", fg: "#6D28D9", bg: palette.violetSoft },
};

export function StatusChip({ status, style }: { status: ItemStatus; style?: ViewStyle }) {
  const v = STATUS_VISUAL[status];
  return (
    <View style={[styles.chip, { backgroundColor: v.bg }, style]}>
      <View style={[styles.dot, { backgroundColor: v.dot }]} />
      <Text style={[styles.chipText, { color: v.fg }]} numberOfLines={1}>
        {v.label}
      </Text>
    </View>
  );
}

export function TypeChip({ type, style }: { type: ItemType; style?: ViewStyle }) {
  const v = TYPE_VISUAL[type];
  return (
    <View style={[styles.chip, { backgroundColor: v.bg }, style]}>
      <Text style={[styles.chipText, { color: v.fg }]}>{v.label}</Text>
    </View>
  );
}

export function PriorityChip({ priority }: { priority: Priority }) {
  const urgent = priority === "urgent";
  return (
    <View style={[styles.chip, { backgroundColor: urgent ? palette.redSoft : palette.surfaceAlt }]}>
      <Text style={[styles.chipText, { color: urgent ? "#B91C1C" : palette.textMuted }]}>
        {urgent ? "Urgent" : "High"}
      </Text>
    </View>
  );
}

export function FlagChip({ label }: { label: string }) {
  const tone =
    label === "Overdue"
      ? { fg: "#B91C1C", bg: palette.redSoft }
      : label === "Due Soon"
        ? { fg: "#B45309", bg: palette.amberSoft }
        : label === "Ready for Inspection"
          ? { fg: "#6D28D9", bg: palette.violetSoft }
          : label === "Needs Evidence"
            ? { fg: "#B45309", bg: palette.amberSoft }
            : { fg: palette.textMuted, bg: palette.surfaceAlt };
  return (
    <View style={[styles.flag, { backgroundColor: tone.bg }]}>
      <Text style={[styles.flagText, { color: tone.fg }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.pill,
    alignSelf: "flex-start",
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chipText: { fontSize: font.size.xs, fontWeight: font.weight.semibold },
  flag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.sm, alignSelf: "flex-start" },
  flagText: { fontSize: 10, fontWeight: font.weight.bold, letterSpacing: 0.3, textTransform: "uppercase" },
});
