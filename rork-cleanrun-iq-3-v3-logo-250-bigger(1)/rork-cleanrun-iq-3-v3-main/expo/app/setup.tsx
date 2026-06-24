import { Plus, X } from "lucide-react-native";
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { SectionCard } from "@/components/SectionCard";
import { font, palette, radius, spacing } from "@/constants/theme";
import { useActiveProjectConfig, useAppStore } from "@/providers/AppStore";
import { ProjectConfig } from "@/types/models";

type ListKey = "buildings" | "levels" | "units" | "rooms";

export default function SetupScreen() {
  const { settings, updateProjectConfig, setActiveProject } = useAppStore();
  const cfg = useActiveProjectConfig();

  const update = (key: ListKey, values: string[]) => {
    updateProjectConfig(settings.activeProject, { [key]: values } as Partial<ProjectConfig>);
  };

  return (
    <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      <SectionCard title="Active project">
        <View style={styles.projectRow}>
          {settings.projects.map((p) => (
            <Pressable
              key={p}
              style={[styles.projectChip, p === settings.activeProject && styles.projectChipActive]}
              onPress={() => setActiveProject(p)}
            >
              <Text style={[styles.projectChipText, p === settings.activeProject && { color: palette.white }]}>
                {p}
              </Text>
            </Pressable>
          ))}
        </View>
        {cfg.address ? <Text style={styles.address}>{cfg.address}</Text> : null}
      </SectionCard>

      <ListEditor title="Buildings" values={cfg.buildings} onChange={(v) => update("buildings", v)} />
      <ListEditor title="Levels" values={cfg.levels} onChange={(v) => update("levels", v)} />
      <ListEditor title="Units / Areas" values={cfg.units} onChange={(v) => update("units", v)} />
      <ListEditor title="Rooms / Locations" values={cfg.rooms} onChange={(v) => update("rooms", v)} />

      <Text style={styles.footer}>
        These options appear as quick-select chips when capturing items.
      </Text>
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

function ListEditor({
  title,
  values,
  onChange,
}: {
  title: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState<string>("");
  return (
    <SectionCard title={title}>
      <View style={styles.chips}>
        {values.length === 0 ? <Text style={styles.empty}>None yet</Text> : null}
        {values.map((v) => (
          <View key={v} style={styles.chip}>
            <Text style={styles.chipText}>{v}</Text>
            <Pressable hitSlop={6} onPress={() => onChange(values.filter((x) => x !== v))}>
              <X size={14} color={palette.textMuted} />
            </Pressable>
          </View>
        ))}
      </View>
      <View style={styles.addRow}>
        <TextInput
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder={`Add ${title.toLowerCase()}…`}
          placeholderTextColor={palette.textFaint}
          onSubmitEditing={() => {
            const v = draft.trim();
            if (v && !values.includes(v)) {
              onChange([...values, v]);
              setDraft("");
            }
          }}
          returnKeyType="done"
        />
        <Pressable
          style={styles.addBtn}
          onPress={() => {
            const v = draft.trim();
            if (v && !values.includes(v)) {
              onChange([...values, v]);
              setDraft("");
            }
          }}
        >
          <Plus size={18} color={palette.white} />
        </Pressable>
      </View>
    </SectionCard>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.lg, gap: spacing.md },
  projectRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  projectChip: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: radius.pill, backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.border },
  projectChipActive: { backgroundColor: palette.navy, borderColor: palette.navy },
  projectChipText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.text },
  address: { fontSize: font.size.sm, color: palette.textMuted, marginTop: spacing.md },

  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  empty: { fontSize: font.size.sm, color: palette.textFaint },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: palette.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: palette.border },
  chipText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.text },
  addRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  input: { flex: 1, backgroundColor: palette.surfaceAlt, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 12, fontSize: font.size.md, color: palette.text },
  addBtn: { width: 46, borderRadius: radius.md, backgroundColor: palette.navy, alignItems: "center", justifyContent: "center" },
  footer: { textAlign: "center", fontSize: font.size.xs, color: palette.textFaint, marginTop: spacing.sm },
});
