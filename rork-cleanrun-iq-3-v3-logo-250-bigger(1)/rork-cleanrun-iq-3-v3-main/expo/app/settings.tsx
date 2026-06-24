import { Building2, Plus, RotateCcw, Trash2, UserPlus } from "lucide-react-native";
import React, { useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { BrandBanner } from "@/components/Brand";
import { SectionCard } from "@/components/SectionCard";
import { font, palette, radius, spacing } from "@/constants/theme";
import { useAppStore } from "@/providers/AppStore";
import { TRADES } from "@/types/models";

export default function SettingsScreen() {
  const { settings, updateCompany, addSubcontractor, addProject, resetDemo } = useAppStore();
  const [company, setCompany] = useState<string>(settings.company);
  const [preparedBy, setPreparedBy] = useState<string>(settings.preparedBy);
  const [newSub, setNewSub] = useState<string>("");
  const [newSubTrade, setNewSubTrade] = useState<string>("");
  const [newProject, setNewProject] = useState<string>("");

  return (
    <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      <View style={styles.bannerBox}>
        <BrandBanner width={160} />
      </View>

      <SectionCard title="Company & branding">
        <Text style={styles.label}>Company name</Text>
        <TextInput
          style={styles.input}
          value={company}
          onChangeText={setCompany}
          onBlur={() => updateCompany({ company: company.trim() || settings.company })}
          placeholder="Company name"
          placeholderTextColor={palette.textFaint}
        />
        <Text style={styles.label}>Prepared by</Text>
        <TextInput
          style={styles.input}
          value={preparedBy}
          onChangeText={setPreparedBy}
          onBlur={() => updateCompany({ preparedBy: preparedBy.trim() || settings.preparedBy })}
          placeholder="Your name / role"
          placeholderTextColor={palette.textFaint}
        />
        <Text style={styles.hint}>Used on report headers and audit events.</Text>
      </SectionCard>

      <SectionCard title="Projects" right={<Building2 size={18} color={palette.navy} />}>
        {settings.projects.map((p) => (
          <View key={p} style={styles.listRow}>
            <Text style={styles.listText}>{p}</Text>
            {p === settings.activeProject ? <Text style={styles.activeBadge}>Active</Text> : null}
          </View>
        ))}
        <View style={styles.addRow}>
          <TextInput
            style={[styles.input, { flex: 1, marginTop: 0 }]}
            value={newProject}
            onChangeText={setNewProject}
            placeholder="Add a project…"
            placeholderTextColor={palette.textFaint}
          />
          <Pressable
            style={styles.addBtn}
            onPress={() => {
              if (newProject.trim()) {
                addProject(newProject.trim());
                setNewProject("");
              }
            }}
          >
            <Plus size={18} color={palette.white} />
          </Pressable>
        </View>
      </SectionCard>

      <SectionCard title={`Subcontractors (${settings.subcontractors.length})`} right={<UserPlus size={18} color={palette.navy} />}>
        {settings.subcontractors.map((s) => {
          const profile = settings.subProfiles[s];
          return (
            <View key={s} style={styles.listRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.listText}>{s}</Text>
                {profile?.trade ? <Text style={styles.listSub}>{profile.trade}</Text> : null}
              </View>
            </View>
          );
        })}
        <Text style={styles.label}>Add subcontractor</Text>
        <TextInput
          style={styles.input}
          value={newSub}
          onChangeText={setNewSub}
          placeholder="Company name"
          placeholderTextColor={palette.textFaint}
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tradeRow}>
          {TRADES.map((t) => (
            <Pressable
              key={t}
              style={[styles.tradeChip, newSubTrade === t && styles.tradeChipActive]}
              onPress={() => setNewSubTrade(newSubTrade === t ? "" : t)}
            >
              <Text style={[styles.tradeChipText, newSubTrade === t && { color: palette.white }]}>{t}</Text>
            </Pressable>
          ))}
        </ScrollView>
        <Pressable
          style={styles.fullBtn}
          onPress={() => {
            if (newSub.trim()) {
              addSubcontractor({ name: newSub.trim(), trade: newSubTrade || undefined });
              setNewSub("");
              setNewSubTrade("");
            }
          }}
        >
          <Text style={styles.fullBtnText}>Add subcontractor</Text>
        </Pressable>
      </SectionCard>

      <SectionCard title="Demo data">
        <Pressable
          style={styles.resetBtn}
          onPress={() =>
            Alert.alert("Reset demo data", "Restore the original sample items, projects and subcontractors? Your captured items will be replaced.", [
              { text: "Cancel", style: "cancel" },
              { text: "Reset", style: "destructive", onPress: resetDemo },
            ])
          }
        >
          <RotateCcw size={16} color={palette.red} />
          <Text style={styles.resetText}>Reset to demo data</Text>
        </Pressable>
      </SectionCard>

      <Text style={styles.footer}>CleanRun IQ Field App</Text>
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.lg, gap: spacing.md },
  bannerBox: { backgroundColor: palette.white, borderRadius: radius.lg, padding: spacing.lg, alignItems: "center", borderWidth: 1, borderColor: palette.border },
  label: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted, marginTop: spacing.md, marginBottom: 6 },
  input: { backgroundColor: palette.surfaceAlt, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 12, fontSize: font.size.md, color: palette.text },
  hint: { fontSize: font.size.xs, color: palette.textFaint, marginTop: 8 },
  listRow: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: palette.border },
  listText: { fontSize: font.size.md, color: palette.text, fontWeight: font.weight.medium },
  listSub: { fontSize: font.size.xs, color: palette.textMuted, marginTop: 1 },
  activeBadge: { fontSize: font.size.xs, fontWeight: font.weight.bold, color: palette.green, backgroundColor: palette.greenSoft, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  addRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  addBtn: { width: 46, borderRadius: radius.md, backgroundColor: palette.navy, alignItems: "center", justifyContent: "center" },
  tradeRow: { gap: 8, paddingVertical: spacing.sm },
  tradeChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.pill, backgroundColor: palette.surfaceAlt, borderWidth: 1, borderColor: palette.border },
  tradeChipActive: { backgroundColor: palette.navy, borderColor: palette.navy },
  tradeChipText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted },
  fullBtn: { backgroundColor: palette.navy, paddingVertical: 14, borderRadius: radius.md, alignItems: "center", marginTop: spacing.sm },
  fullBtnText: { color: palette.white, fontWeight: font.weight.bold, fontSize: font.size.md },
  resetBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, paddingVertical: 14, borderRadius: radius.md, backgroundColor: palette.redSoft },
  resetText: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.red },
  footer: { textAlign: "center", fontSize: font.size.xs, color: palette.textFaint, marginTop: spacing.sm },
});
