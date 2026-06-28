import { useRouter } from "expo-router";
import { ChevronRight, FileText, Star } from "lucide-react-native";
import React, { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { BrandBanner } from "@/components/Brand";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { filterForReport, REPORT_META, ReportType } from "@/lib/reportBuilder";
import { useAppStore } from "@/providers/AppStore";

const ORDER: ReportType[] = ["handover", "open", "overdue", "subcontractor", "client", "incomplete"];

export default function ReportsScreen() {
  const router = useRouter();
  const { items, settings } = useAppStore();

  const projectItems = useMemo(
    () => items.filter((i) => i.project === settings.activeProject),
    [items, settings.activeProject],
  );

  return (
    <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
      <View style={styles.banner}>
        <BrandBanner width={160} />
        <Text style={styles.bannerSub}>
          {settings.activeProject} · prepared by {settings.preparedBy}
        </Text>
      </View>

      {ORDER.map((type) => {
        const meta = REPORT_META[type];
        const count = filterForReport(projectItems, type).length;
        return (
          <Pressable
            key={type}
            style={[styles.card, meta.hero && styles.heroCard]}
            onPress={() => router.push(`/report/${type}`)}
          >
            <View style={[styles.icon, meta.hero && styles.heroIcon]}>
              {meta.hero ? (
                <Star size={22} color={palette.white} fill={palette.white} />
              ) : (
                <FileText size={20} color={palette.navy} />
              )}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.title, meta.hero && { color: palette.white }]}>{meta.title}</Text>
              <Text style={[styles.desc, meta.hero && { color: "rgba(255,255,255,0.8)" }]}>
                {meta.description}
              </Text>
              <Text style={[styles.count, meta.hero && { color: palette.greenBright }]}>
                {count} item{count === 1 ? "" : "s"}
              </Text>
            </View>
            <ChevronRight size={20} color={meta.hero ? "rgba(255,255,255,0.7)" : palette.textFaint} />
          </Pressable>
        );
      })}

      <Text style={styles.note}>
        Reports separate original issue, subcontractor rectification and supervisor closeout evidence.
        Open a report to preview and export as PDF.
      </Text>
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.lg, gap: spacing.md },
  banner: { backgroundColor: palette.white, borderRadius: radius.lg, padding: spacing.lg, alignItems: "center", borderWidth: 1, borderColor: palette.border, ...shadow.card },
  bannerSub: { fontSize: font.size.sm, color: palette.textMuted, marginTop: spacing.sm },
  card: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, ...shadow.card },
  heroCard: { backgroundColor: palette.navy, borderColor: palette.navy },
  icon: { width: 46, height: 46, borderRadius: 14, backgroundColor: palette.surfaceAlt, alignItems: "center", justifyContent: "center" },
  heroIcon: { backgroundColor: palette.green },
  title: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  desc: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 2 },
  count: { fontSize: font.size.xs, color: palette.navy, fontWeight: font.weight.bold, marginTop: 6 },
  note: { fontSize: font.size.xs, color: palette.textFaint, textAlign: "center", lineHeight: 17, marginTop: spacing.sm },
});
