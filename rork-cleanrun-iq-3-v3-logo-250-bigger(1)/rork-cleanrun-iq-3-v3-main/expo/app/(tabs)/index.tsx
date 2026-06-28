import { useRouter } from "expo-router";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CloudOff,
  Plus,
  RefreshCw,
  Search,
  TriangleAlert,
} from "lucide-react-native";
import React, { useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BrandBanner, BrandMark } from "@/components/Brand";
import { ItemCard } from "@/components/ItemCard";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { derivedFlags, isOverdue, todayISO } from "@/lib/format";
import { useAppStore } from "@/providers/AppStore";
import { Item } from "@/types/models";

export default function HomeScreen() {
  const router = useRouter();
  const { items, settings, online, pendingSyncCount, setActiveProject } = useAppStore();
  const [projectPickerOpen, setProjectPickerOpen] = useState<boolean>(false);

  const projectItems = useMemo(
    () => items.filter((i) => i.project === settings.activeProject),
    [items, settings.activeProject],
  );

  const stats = useMemo(() => {
    const open = projectItems.filter((i) => i.status === "open").length;
    const overdue = projectItems.filter((i) => isOverdue(i)).length;
    const ready = projectItems.filter((i) => i.status === "ready_for_review").length;
    const closedToday = projectItems.filter(
      (i) => (i.status === "closed" || i.status === "complete") && i.closedAt?.slice(0, 10) === todayISO(),
    ).length;
    return { open, overdue, ready, closedToday };
  }, [projectItems]);

  const needsAttention = useMemo(
    () =>
      projectItems
        .filter((i) => isOverdue(i) || i.status === "rejected")
        .sort((a, b) => a.dueDate.localeCompare(b.dueDate)),
    [projectItems],
  );

  const readyToInspect = useMemo(
    () => projectItems.filter((i) => i.status === "ready_for_review"),
    [projectItems],
  );

  const nextItems = useMemo(() => {
    const active = projectItems.filter((i) => i.status !== "closed" && i.status !== "complete");
    const score = (i: Item) => {
      if (isOverdue(i)) return 0;
      if (i.status === "rejected") return 1;
      if (i.status === "ready_for_review") return 2;
      if (i.status === "open") return 3;
      return 4;
    };
    return active.sort((a, b) => score(a) - score(b) || a.dueDate.localeCompare(b.dueDate)).slice(0, 4);
  }, [projectItems]);

  return (
    <View style={styles.flex}>
      <SafeAreaView edges={["top"]} style={styles.headerWrap}>
        <View style={styles.headerTop}>
          <View style={styles.bannerBox}>
            <BrandBanner width={150} />
          </View>
          <Pressable style={styles.iconBtn} onPress={() => router.push("/items")}>
            <Search size={20} color={palette.white} />
          </Pressable>
        </View>

        <Pressable style={styles.projectSelector} onPress={() => setProjectPickerOpen(true)}>
          <View>
            <Text style={styles.projectLabel}>Active project</Text>
            <Text style={styles.projectName}>{settings.activeProject}</Text>
          </View>
          <ChevronDown size={20} color={palette.white} />
        </Pressable>

        <View style={styles.syncRow}>
          {online ? (
            <>
              <View style={[styles.syncDot, { backgroundColor: palette.greenBright }]} />
              <Text style={styles.syncText}>
                {pendingSyncCount > 0 ? `${pendingSyncCount} change${pendingSyncCount > 1 ? "s" : ""} syncing…` : "All changes synced"}
              </Text>
              {pendingSyncCount > 0 ? <RefreshCw size={13} color="rgba(255,255,255,0.7)" /> : null}
            </>
          ) : (
            <>
              <CloudOff size={14} color={palette.amber} />
              <Text style={styles.syncText}>Offline — saving locally</Text>
            </>
          )}
        </View>
      </SafeAreaView>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Pressable
          style={({ pressed }) => [styles.captureCta, pressed && { opacity: 0.92 }]}
          onPress={() => router.push("/capture")}
        >
          <View style={styles.captureIcon}>
            <Plus size={26} color={palette.navy} strokeWidth={2.6} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.captureTitle}>Capture Item</Text>
            <Text style={styles.captureSub}>Photo, voice-to-note or walk capture</Text>
          </View>
          <ChevronRight size={22} color="rgba(255,255,255,0.8)" />
        </Pressable>

        <View style={styles.statsGrid}>
          <StatCard label="Open" value={stats.open} tone={palette.navy} onPress={() => router.push("/items?filter=Open")} />
          <StatCard label="Overdue" value={stats.overdue} tone={palette.red} onPress={() => router.push("/items?filter=Overdue")} />
          <StatCard label="Ready for Review" value={stats.ready} tone={palette.violet} onPress={() => router.push("/items?filter=Ready for Review")} />
          <StatCard label="Closed Today" value={stats.closedToday} tone={palette.green} onPress={() => router.push("/items?filter=Closed")} />
        </View>

        {needsAttention.length > 0 ? (
          <Banner
            icon={<TriangleAlert size={18} color="#B91C1C" />}
            tone={palette.redSoft}
            fg="#B91C1C"
            title={`${needsAttention.length} need your attention`}
            sub="Overdue or rejected items"
            onPress={() => router.push("/items?filter=Overdue")}
          />
        ) : null}

        {readyToInspect.length > 0 ? (
          <Banner
            icon={<CheckCircle2 size={18} color="#6D28D9" />}
            tone={palette.violetSoft}
            fg="#6D28D9"
            title={`${readyToInspect.length} ready to inspect`}
            sub="Subcontractor marked ready for review"
            onPress={() => router.push("/items?filter=Ready for Review")}
          />
        ) : null}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Next to deal with</Text>
          <Pressable onPress={() => router.push("/items")} hitSlop={8}>
            <Text style={styles.sectionLink}>View all</Text>
          </Pressable>
        </View>

        {nextItems.length === 0 ? (
          <View style={styles.empty}>
            <CheckCircle2 size={32} color={palette.green} />
            <Text style={styles.emptyTitle}>All clear on {settings.activeProject}</Text>
            <Text style={styles.emptySub}>Nothing open right now. Capture a new item to get started.</Text>
          </View>
        ) : (
          <View style={{ gap: spacing.md }}>
            {nextItems.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </View>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>

      <Modal visible={projectPickerOpen} transparent animationType="fade" onRequestClose={() => setProjectPickerOpen(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setProjectPickerOpen(false)}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Switch project</Text>
            {settings.projects.map((p) => {
              const active = p === settings.activeProject;
              return (
                <Pressable
                  key={p}
                  style={[styles.projectOption, active && styles.projectOptionActive]}
                  onPress={() => {
                    setActiveProject(p);
                    setProjectPickerOpen(false);
                  }}
                >
                  <BrandMark size={32} radius={9} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.projectOptionName}>{p}</Text>
                    <Text style={styles.projectOptionMeta}>
                      {items.filter((i) => i.project === p).length} items
                    </Text>
                  </View>
                  {active ? <CheckCircle2 size={20} color={palette.green} /> : null}
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

function StatCard({
  label,
  value,
  tone,
  onPress,
}: {
  label: string;
  value: number;
  tone: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={({ pressed }) => [styles.statCard, pressed && { opacity: 0.85 }]} onPress={onPress}>
      <View style={[styles.statBar, { backgroundColor: tone }]} />
      <Text style={[styles.statValue, { color: tone }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </Pressable>
  );
}

function Banner({
  icon,
  tone,
  fg,
  title,
  sub,
  onPress,
}: {
  icon: React.ReactNode;
  tone: string;
  fg: string;
  title: string;
  sub: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={[styles.attentionBanner, { backgroundColor: tone }]} onPress={onPress}>
      {icon}
      <View style={{ flex: 1 }}>
        <Text style={[styles.bannerTitle, { color: fg }]}>{title}</Text>
        <Text style={[styles.bannerSub, { color: fg }]}>{sub}</Text>
      </View>
      <ChevronRight size={18} color={fg} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  headerWrap: {
    backgroundColor: palette.navy,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    borderBottomLeftRadius: 26,
    borderBottomRightRadius: 26,
  },
  headerTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  bannerBox: {
    backgroundColor: palette.white,
    borderRadius: radius.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  iconBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(255,255,255,0.12)",
    alignItems: "center",
    justifyContent: "center",
  },
  projectSelector: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "rgba(255,255,255,0.1)",
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    marginTop: spacing.lg,
  },
  projectLabel: { fontSize: font.size.xs, color: "rgba(255,255,255,0.6)", fontWeight: font.weight.semibold, textTransform: "uppercase", letterSpacing: 0.6 },
  projectName: { fontSize: font.size.xl, color: palette.white, fontWeight: font.weight.bold, marginTop: 2 },
  syncRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md },
  syncDot: { width: 8, height: 8, borderRadius: 4 },
  syncText: { fontSize: font.size.sm, color: "rgba(255,255,255,0.8)", fontWeight: font.weight.medium },

  scroll: { padding: spacing.lg, gap: spacing.lg },
  captureCta: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: palette.green,
    borderRadius: radius.lg,
    padding: spacing.lg,
    ...shadow.floating,
  },
  captureIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: palette.white,
    alignItems: "center",
    justifyContent: "center",
  },
  captureTitle: { fontSize: font.size.lg, fontWeight: font.weight.heavy, color: palette.white },
  captureSub: { fontSize: font.size.sm, color: "rgba(255,255,255,0.85)", marginTop: 2 },

  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  statCard: {
    width: "47.5%",
    flexGrow: 1,
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    padding: spacing.lg,
    overflow: "hidden",
    ...shadow.card,
  },
  statBar: { position: "absolute", left: 0, top: 0, bottom: 0, width: 4 },
  statValue: { fontSize: font.size.huge, fontWeight: font.weight.heavy },
  statLabel: { fontSize: font.size.sm, color: palette.textMuted, fontWeight: font.weight.semibold, marginTop: 2 },

  attentionBanner: { flexDirection: "row", alignItems: "center", gap: spacing.md, borderRadius: radius.lg, padding: spacing.lg },
  bannerTitle: { fontSize: font.size.md, fontWeight: font.weight.bold },
  bannerSub: { fontSize: font.size.sm, opacity: 0.8, marginTop: 1 },

  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text },
  sectionLink: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.navy },

  empty: { alignItems: "center", gap: 6, padding: spacing.xl, backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border },
  emptyTitle: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text, marginTop: 4 },
  emptySub: { fontSize: font.size.sm, color: palette.textMuted, textAlign: "center" },

  modalBackdrop: { flex: 1, backgroundColor: "rgba(10,24,48,0.5)", justifyContent: "flex-end" },
  modalSheet: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, gap: spacing.sm, paddingBottom: spacing.xxl },
  modalTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text, marginBottom: spacing.sm },
  projectOption: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  projectOptionActive: { borderColor: palette.green, backgroundColor: palette.greenSoft },
  projectOptionName: { fontSize: font.size.md, fontWeight: font.weight.semibold, color: palette.text },
  projectOptionMeta: { fontSize: font.size.sm, color: palette.textMuted },
});
