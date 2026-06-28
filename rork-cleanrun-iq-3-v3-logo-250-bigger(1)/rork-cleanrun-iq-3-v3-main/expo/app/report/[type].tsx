import { Asset } from "expo-asset";
import * as FileSystem from "expo-file-system/legacy";
import * as Print from "expo-print";
import { Stack, useLocalSearchParams } from "expo-router";
import * as Sharing from "expo-sharing";
import { Download, FileText } from "lucide-react-native";
import React, { useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BrandBanner } from "@/components/Brand";
import { EvidencePhoto } from "@/components/EvidencePhoto";
import { StatusChip, TypeChip } from "@/components/chips";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { formatDate, formatLocation, isOverdue } from "@/lib/format";
import {
  buildReportHtml,
  filterForReport,
  groupByLocation,
  REPORT_META,
  ReportType,
} from "@/lib/reportBuilder";
import { useAppStore } from "@/providers/AppStore";

export default function ReportPreviewScreen() {
  const { type } = useLocalSearchParams<{ type: ReportType }>();
  const { items, settings } = useAppStore();
  const [exporting, setExporting] = useState<boolean>(false);

  const reportType = (type ?? "handover") as ReportType;
  const meta = REPORT_META[reportType];

  const reportItems = useMemo(() => {
    const projectItems = items.filter((i) => i.project === settings.activeProject);
    return filterForReport(projectItems, reportType);
  }, [items, settings.activeProject, reportType]);

  const groups = useMemo(() => groupByLocation(reportItems), [reportItems]);

  const exportPdf = async () => {
    try {
      setExporting(true);
      // Load the banner as a data URI so it embeds in the PDF.
      const asset = Asset.fromModule(require("@/assets/images/brand/banner.png"));
      await asset.downloadAsync();
      let bannerDataUri = "";
      if (asset.localUri) {
        const b64 = await FileSystem.readAsStringAsync(asset.localUri, { encoding: "base64" });
        bannerDataUri = `data:image/png;base64,${b64}`;
      }
      const html = buildReportHtml(reportItems, reportType, settings, bannerDataUri);
      const { uri } = await Print.printToFileAsync({ html });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: "application/pdf", dialogTitle: `${meta.title} Report` });
      } else {
        Alert.alert("Report ready", "PDF generated successfully.");
      }
    } catch (e) {
      console.warn("[CleanRun] report export failed", e);
      Alert.alert("Export failed", "Could not generate the PDF. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <View style={styles.flex}>
      <Stack.Screen options={{ title: meta.title }} />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.reportHeader}>
          <View style={styles.bannerBox}>
            <BrandBanner width={150} />
          </View>
          <Text style={styles.reportTitle}>{meta.title} Report</Text>
          <Text style={styles.reportMeta}>
            {settings.activeProject} · {settings.company}
          </Text>
          <Text style={styles.reportMeta}>Generated {new Date().toLocaleString()}</Text>
        </View>

        <View style={styles.summaryGrid}>
          <Summary label="Total" value={reportItems.length} />
          <Summary
            label="Closed"
            value={reportItems.filter((i) => i.status === "closed" || i.status === "complete").length}
            tone={palette.green}
          />
          <Summary label="Overdue" value={reportItems.filter((i) => isOverdue(i)).length} tone={palette.red} />
        </View>

        {groups.length === 0 ? (
          <View style={styles.empty}>
            <FileText size={32} color={palette.textFaint} />
            <Text style={styles.emptyText}>No items match this report.</Text>
          </View>
        ) : (
          groups.map((g) => (
            <View key={g.key} style={{ gap: spacing.sm }}>
              <Text style={styles.groupHeader}>{g.key}</Text>
              {g.items.map((item) => {
                const closeout = item.closeoutEvidence[0];
                return (
                  <View key={item.id} style={styles.itemCard}>
                    <View style={styles.itemHead}>
                      <Text style={styles.itemCode}>{item.code}</Text>
                      <View style={styles.itemHeadRight}>
                        <TypeChip type={item.type} />
                        <StatusChip status={item.status} />
                      </View>
                    </View>
                    <Text style={styles.itemLoc}>
                      {formatLocation(item)} · {item.subcontractor || "Unassigned"}
                    </Text>
                    <Text style={styles.itemDesc}>{item.description}</Text>

                    <View style={styles.evidenceCols}>
                      <EvidenceColumn title="Original" photos={item.originalPhotos} tone={palette.navy} />
                      <EvidenceColumn
                        title="Rectification"
                        photos={item.rectificationEvidence.map((e) => e.photo).filter(Boolean) as string[]}
                        tone={palette.amber}
                      />
                      <EvidenceColumn
                        title="Closeout"
                        photos={item.closeoutEvidence.map((e) => e.photo).filter(Boolean) as string[]}
                        tone={palette.green}
                      />
                    </View>

                    {closeout ? (
                      <Text style={styles.signoff}>
                        ✓ Signed off by {closeout.by} ({closeout.role}) · {formatDate(closeout.at)}
                      </Text>
                    ) : null}
                    <Text style={[styles.itemDue, isOverdue(item) && { color: palette.red, fontWeight: "700" }]}>
                      Due {formatDate(item.dueDate)}
                    </Text>
                  </View>
                );
              })}
            </View>
          ))
        )}
        <View style={{ height: 16 }} />
      </ScrollView>

      <SafeAreaView edges={["bottom"]} style={styles.actionBar}>
        <Pressable style={styles.exportBtn} onPress={exportPdf} disabled={exporting}>
          {exporting ? (
            <ActivityIndicator color={palette.white} />
          ) : (
            <>
              <Download size={18} color={palette.white} />
              <Text style={styles.exportText}>Export PDF & Share</Text>
            </>
          )}
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

function EvidenceColumn({ title, photos, tone }: { title: string; photos: string[]; tone: string }) {
  return (
    <View style={styles.evCol}>
      <Text style={[styles.evColTitle, { color: tone }]}>{title}</Text>
      {photos.length === 0 ? (
        <Text style={styles.evNone}>—</Text>
      ) : (
        <View style={{ gap: 4 }}>
          {photos.slice(0, 2).map((p, idx) => (
            <EvidencePhoto key={`${p}-${idx}`} uri={p} size={undefined} style={styles.evPhoto} />
          ))}
        </View>
      )}
    </View>
  );
}

function Summary({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <View style={styles.summaryCard}>
      <Text style={[styles.summaryValue, tone ? { color: tone } : null]}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  scroll: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xxl },
  reportHeader: { backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.lg, alignItems: "center", ...shadow.card },
  bannerBox: { backgroundColor: palette.white, borderRadius: radius.sm, padding: 6, marginBottom: spacing.sm },
  reportTitle: { fontSize: font.size.lg, fontWeight: font.weight.heavy, color: palette.navy, marginTop: spacing.sm },
  reportMeta: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 2 },

  summaryGrid: { flexDirection: "row", gap: spacing.sm },
  summaryCard: { flex: 1, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, padding: spacing.md, alignItems: "center" },
  summaryValue: { fontSize: font.size.xxl, fontWeight: font.weight.heavy, color: palette.navy },
  summaryLabel: { fontSize: font.size.xs, color: palette.textMuted, textTransform: "uppercase", letterSpacing: 0.4 },

  empty: { alignItems: "center", gap: 8, padding: spacing.xxl },
  emptyText: { fontSize: font.size.sm, color: palette.textMuted },

  groupHeader: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.white, backgroundColor: palette.navy, paddingHorizontal: spacing.md, paddingVertical: 8, borderRadius: radius.sm, marginTop: spacing.sm },
  itemCard: { backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, padding: spacing.md },
  itemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  itemHeadRight: { flexDirection: "row", gap: 6 },
  itemCode: { fontSize: font.size.md, fontWeight: font.weight.heavy, color: palette.navy },
  itemLoc: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 4 },
  itemDesc: { fontSize: font.size.sm, color: palette.text, marginTop: 6, lineHeight: 19 },
  evidenceCols: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  evCol: { flex: 1, backgroundColor: palette.surfaceAlt, borderRadius: radius.sm, padding: 8 },
  evColTitle: { fontSize: 10, fontWeight: font.weight.bold, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 },
  evNone: { fontSize: font.size.sm, color: palette.textFaint },
  evPhoto: { width: "100%", aspectRatio: 1.3 },
  signoff: { fontSize: font.size.sm, color: palette.green, fontWeight: font.weight.semibold, marginTop: spacing.sm },
  itemDue: { fontSize: font.size.xs, color: palette.textMuted, marginTop: 4 },

  actionBar: { backgroundColor: palette.surface, borderTopWidth: 1, borderTopColor: palette.border, paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  exportBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, backgroundColor: palette.navy, paddingVertical: 16, borderRadius: radius.md },
  exportText: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.white },
});
