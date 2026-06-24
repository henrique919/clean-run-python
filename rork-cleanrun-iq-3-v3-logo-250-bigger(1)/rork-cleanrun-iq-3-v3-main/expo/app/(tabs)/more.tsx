import { useRouter } from "expo-router";
import {
  ChevronRight,
  CloudOff,
  FileText,
  HardHat,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Users,
} from "lucide-react-native";
import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BrandBanner } from "@/components/Brand";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { useAppStore } from "@/providers/AppStore";

export default function MoreScreen() {
  const router = useRouter();
  const { settings, online, pendingSyncCount, items } = useAppStore();

  const groups: {
    title: string;
    rows: { icon: React.ReactNode; label: string; sub: string; onPress: () => void }[];
  }[] = [
    {
      title: "Reporting",
      rows: [
        {
          icon: <FileText size={20} color={palette.navy} />,
          label: "Reports & Handover",
          sub: "Evidence-chain & closeout reports",
          onPress: () => router.push("/reports"),
        },
      ],
    },
    {
      title: "Field roles",
      rows: [
        {
          icon: <HardHat size={20} color={palette.amber} />,
          label: "Subcontractor Mode",
          sub: "Assigned items & rectification upload",
          onPress: () => router.push("/subcontractor"),
        },
      ],
    },
    {
      title: "Admin",
      rows: [
        {
          icon: <SlidersHorizontal size={20} color={palette.violet} />,
          label: "Project Setup",
          sub: "Buildings, levels, units & rooms",
          onPress: () => router.push("/setup"),
        },
        {
          icon: <Settings size={20} color={palette.textMuted} />,
          label: "Settings & Admin",
          sub: "Company, subcontractors, demo data",
          onPress: () => router.push("/settings"),
        },
      ],
    },
  ];

  return (
    <View style={styles.flex}>
      <SafeAreaView edges={["top"]} style={styles.header}>
        <View style={styles.bannerBox}>
          <BrandBanner width={160} />
        </View>
        <Text style={styles.tagline}>Field capture, review & closeout companion</Text>
      </SafeAreaView>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.syncCard}>
          {online ? (
            <RefreshCw size={20} color={palette.green} />
          ) : (
            <CloudOff size={20} color={palette.amber} />
          )}
          <View style={{ flex: 1 }}>
            <Text style={styles.syncTitle}>{online ? "Online" : "Offline"}</Text>
            <Text style={styles.syncSub}>
              {online
                ? pendingSyncCount > 0
                  ? `${pendingSyncCount} change${pendingSyncCount > 1 ? "s" : ""} syncing`
                  : "All field data synced"
                : "Field actions are saved locally and will sync"}
            </Text>
          </View>
          <View style={styles.statBubble}>
            <Text style={styles.statBubbleNum}>{items.length}</Text>
            <Text style={styles.statBubbleLabel}>items</Text>
          </View>
        </View>

        {groups.map((g) => (
          <View key={g.title} style={{ gap: spacing.sm }}>
            <Text style={styles.groupTitle}>{g.title}</Text>
            <View style={styles.group}>
              {g.rows.map((row, idx) => (
                <Pressable
                  key={row.label}
                  style={[styles.row, idx < g.rows.length - 1 && styles.rowBorder]}
                  onPress={row.onPress}
                >
                  <View style={styles.rowIcon}>{row.icon}</View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowLabel}>{row.label}</Text>
                    <Text style={styles.rowSub}>{row.sub}</Text>
                  </View>
                  <ChevronRight size={18} color={palette.textFaint} />
                </Pressable>
              ))}
            </View>
          </View>
        ))}

        <Text style={styles.footer}>
          CleanRun IQ Field App · {settings.company}
        </Text>
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  header: { backgroundColor: palette.navy, paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, alignItems: "center" },
  bannerBox: { backgroundColor: palette.white, borderRadius: radius.md, paddingHorizontal: 14, padding: 12, marginTop: spacing.sm },
  tagline: { fontSize: font.size.sm, color: "rgba(255,255,255,0.7)", marginTop: spacing.md },

  scroll: { padding: spacing.lg, gap: spacing.lg },
  syncCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, ...shadow.card },
  syncTitle: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  syncSub: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 1 },
  statBubble: { alignItems: "center", backgroundColor: palette.surfaceAlt, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 8 },
  statBubbleNum: { fontSize: font.size.lg, fontWeight: font.weight.heavy, color: palette.navy },
  statBubbleLabel: { fontSize: 10, color: palette.textMuted },

  groupTitle: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.6, marginLeft: spacing.xs },
  group: { backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, overflow: "hidden", ...shadow.card },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg },
  rowBorder: { borderBottomWidth: 1, borderBottomColor: palette.border },
  rowIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: palette.surfaceAlt, alignItems: "center", justifyContent: "center" },
  rowLabel: { fontSize: font.size.md, fontWeight: font.weight.semibold, color: palette.text },
  rowSub: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 1 },

  footer: { textAlign: "center", fontSize: font.size.xs, color: palette.textFaint, marginTop: spacing.sm },
});
