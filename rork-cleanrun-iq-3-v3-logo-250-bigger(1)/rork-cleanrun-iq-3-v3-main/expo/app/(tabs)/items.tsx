import { useLocalSearchParams } from "expo-router";
import { Search, SlidersHorizontal, X } from "lucide-react-native";
import React, { useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ItemCard } from "@/components/ItemCard";
import { font, palette, radius, spacing } from "@/constants/theme";
import { isOverdue } from "@/lib/format";
import { useAppStore } from "@/providers/AppStore";
import { Item, ItemType } from "@/types/models";

const STATUS_FILTERS = ["All", "Open", "Overdue", "Ready for Review", "Rejected", "Closed"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

const TYPE_FILTERS: { key: "all" | ItemType; label: string }[] = [
  { key: "all", label: "All types" },
  { key: "defect", label: "Defects" },
  { key: "incomplete", label: "Incomplete" },
  { key: "client", label: "Client Defects" },
];

export default function ItemsScreen() {
  const params = useLocalSearchParams<{ filter?: string }>();
  const { items, settings } = useAppStore();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    (STATUS_FILTERS.includes(params.filter as StatusFilter) ? params.filter : "All") as StatusFilter,
  );
  const [typeFilter, setTypeFilter] = useState<"all" | ItemType>("all");
  const [query, setQuery] = useState<string>("");
  const [allProjects, setAllProjects] = useState<boolean>(false);

  const filtered = useMemo(() => {
    const base = items.filter((i) => (allProjects ? true : i.project === settings.activeProject));
    const byType = typeFilter === "all" ? base : base.filter((i) => i.type === typeFilter);
    const byStatus = byType.filter((i) => matchStatus(i, statusFilter));
    const q = query.trim().toLowerCase();
    const bySearch = q
      ? byStatus.filter(
          (i) =>
            i.code.toLowerCase().includes(q) ||
            i.description.toLowerCase().includes(q) ||
            i.subcontractor.toLowerCase().includes(q) ||
            i.trade.toLowerCase().includes(q) ||
            `${i.building} ${i.level} ${i.unit} ${i.room}`.toLowerCase().includes(q),
        )
      : byStatus;
    return bySearch.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }, [items, settings.activeProject, allProjects, typeFilter, statusFilter, query]);

  return (
    <View style={styles.flex}>
      <SafeAreaView edges={["top"]} style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.headerTitle}>Items</Text>
          <Pressable
            style={[styles.projectChip, allProjects && styles.projectChipActive]}
            onPress={() => setAllProjects((v) => !v)}
          >
            <SlidersHorizontal size={14} color={allProjects ? palette.white : palette.navy} />
            <Text style={[styles.projectChipText, allProjects && { color: palette.white }]}>
              {allProjects ? "All projects" : settings.activeProject}
            </Text>
          </Pressable>
        </View>

        <View style={styles.searchBox}>
          <Search size={18} color={palette.textFaint} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search code, location, trade…"
            placeholderTextColor={palette.textFaint}
            value={query}
            onChangeText={setQuery}
          />
          {query.length > 0 ? (
            <Pressable onPress={() => setQuery("")} hitSlop={8}>
              <X size={16} color={palette.textFaint} />
            </Pressable>
          ) : null}
        </View>
      </SafeAreaView>

      <View style={styles.filterBar}>
        <FlatList
          horizontal
          data={TYPE_FILTERS}
          keyExtractor={(t) => t.key}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
          renderItem={({ item: t }) => (
            <Pressable
              style={[styles.typeTab, typeFilter === t.key && styles.typeTabActive]}
              onPress={() => setTypeFilter(t.key)}
            >
              <Text style={[styles.typeTabText, typeFilter === t.key && { color: palette.white }]}>
                {t.label}
              </Text>
            </Pressable>
          )}
        />
        <FlatList
          horizontal
          data={STATUS_FILTERS as readonly string[]}
          keyExtractor={(s) => s}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
          renderItem={({ item: s }) => (
            <Pressable
              style={[styles.statusTab, statusFilter === s && styles.statusTabActive]}
              onPress={() => setStatusFilter(s as StatusFilter)}
            >
              <Text style={[styles.statusTabText, statusFilter === s && { color: palette.navy }]}>{s}</Text>
            </Pressable>
          )}
        />
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(i) => i.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => <ItemCard item={item} />}
        ListHeaderComponent={
          <Text style={styles.count}>
            {filtered.length} item{filtered.length === 1 ? "" : "s"}
          </Text>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No items match</Text>
            <Text style={styles.emptySub}>Try a different filter or capture a new item.</Text>
          </View>
        }
      />
    </View>
  );
}

function matchStatus(item: Item, filter: StatusFilter): boolean {
  switch (filter) {
    case "All":
      return true;
    case "Open":
      return item.status === "open" || item.status === "issued" || item.status === "in_progress";
    case "Overdue":
      return isOverdue(item);
    case "Ready for Review":
      return item.status === "ready_for_review" || item.status === "under_inspection";
    case "Rejected":
      return item.status === "rejected";
    case "Closed":
      return item.status === "closed" || item.status === "complete";
  }
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  header: { backgroundColor: palette.navy, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  headerTitle: { fontSize: font.size.xxl, fontWeight: font.weight.heavy, color: palette.white },
  projectChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: palette.white,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.pill,
  },
  projectChipActive: { backgroundColor: palette.green },
  projectChipText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.navy },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: palette.white,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    marginTop: spacing.md,
  },
  searchInput: { flex: 1, fontSize: font.size.md, color: palette.text },

  filterBar: { backgroundColor: palette.surface, borderBottomWidth: 1, borderBottomColor: palette.border, paddingVertical: spacing.sm, gap: spacing.sm },
  filterRow: { paddingHorizontal: spacing.lg, gap: 8 },
  typeTab: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: radius.pill, backgroundColor: palette.surfaceAlt },
  typeTabActive: { backgroundColor: palette.navy },
  typeTabText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted },
  statusTab: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1, borderColor: palette.border },
  statusTabActive: { borderColor: palette.navy, backgroundColor: "#EEF2F9" },
  statusTabText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted },

  list: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xxl },
  count: { fontSize: font.size.sm, color: palette.textMuted, fontWeight: font.weight.semibold, marginBottom: spacing.xs },
  empty: { alignItems: "center", gap: 6, padding: spacing.xxl },
  emptyTitle: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  emptySub: { fontSize: font.size.sm, color: palette.textMuted },
});
