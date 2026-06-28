import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { ImagePlus, MapPin, Plus, Trash2, X } from "lucide-react-native";
import React, { useMemo, useState } from "react";
import {
  Alert,
  LayoutChangeEvent,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { EvidencePhoto } from "@/components/EvidencePhoto";
import { StatusChip } from "@/components/chips";
import { font, palette, radius, shadow, spacing } from "@/constants/theme";
import { formatLocation } from "@/lib/format";
import { useActiveProjectConfig, useAppStore } from "@/providers/AppStore";
import { usePlans } from "@/providers/PlansStore";
import { Item, Plan, PlanPin } from "@/types/models";

export default function PlansScreen() {
  const { plans, addPlan, removePlan, addPin, updatePin, removePin } = usePlans();
  const { items, settings } = useAppStore();
  const cfg = useActiveProjectConfig();

  const projectPlans = useMemo(
    () => plans.filter((p) => p.project === settings.activeProject),
    [plans, settings.activeProject],
  );
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const activePlan = projectPlans.find((p) => p.id === activePlanId) ?? projectPlans[0] ?? null;

  const [imageSize, setImageSize] = useState<{ w: number; h: number }>({ w: 1, h: 1 });
  const [pendingPin, setPendingPin] = useState<{ x: number; y: number } | null>(null);
  const [linkPinId, setLinkPinId] = useState<string | null>(null);

  const projectItems = useMemo(
    () => items.filter((i) => i.project === settings.activeProject),
    [items, settings.activeProject],
  );

  const pinColor = (pin: PlanPin): string => {
    const linked = pin.itemId ? projectItems.find((i) => i.id === pin.itemId) : undefined;
    if (!linked) return palette.amber;
    if (linked.status === "closed" || linked.status === "complete") return palette.green;
    return palette.navy;
  };

  const uploadPlan = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7, mediaTypes: ["images"] }).catch(() => null);
    if (res && !res.canceled && res.assets[0]) {
      const plan = addPlan({
        project: settings.activeProject,
        building: cfg.buildings[0] ?? "",
        level: cfg.levels[0] ?? "",
        name: `${cfg.buildings[0] ?? "Plan"} · ${cfg.levels[0] ?? ""}`.trim(),
        image: res.assets[0].uri,
      });
      setActivePlanId(plan.id);
    }
  };

  const onPlanPress = (e: { locationX: number; locationY: number }) => {
    if (!activePlan) return;
    const x = Math.max(0, Math.min(1, e.locationX / imageSize.w));
    const y = Math.max(0, Math.min(1, e.locationY / imageSize.h));
    setPendingPin({ x, y });
  };

  const router = useRouter();

  return (
    <View style={styles.flex}>
      <SafeAreaView edges={["top"]} style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.headerTitle}>Plans</Text>
          <Pressable style={styles.uploadBtn} onPress={uploadPlan}>
            <ImagePlus size={16} color={palette.navy} />
            <Text style={styles.uploadBtnText}>Add plan</Text>
          </Pressable>
        </View>
        <Text style={styles.headerSub}>{settings.activeProject} · tap a plan to drop pins</Text>
      </SafeAreaView>

      {projectPlans.length === 0 ? (
        <View style={styles.empty}>
          <MapPin size={36} color={palette.textFaint} />
          <Text style={styles.emptyTitle}>No plans yet</Text>
          <Text style={styles.emptySub}>Upload a level drawing to start pinning items to locations.</Text>
          <Pressable style={styles.emptyBtn} onPress={uploadPlan}>
            <Text style={styles.emptyBtnText}>Upload a plan</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          {projectPlans.length > 1 ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.planTabs}>
              {projectPlans.map((p) => (
                <Pressable
                  key={p.id}
                  style={[styles.planTab, activePlan?.id === p.id && styles.planTabActive]}
                  onPress={() => setActivePlanId(p.id)}
                >
                  <Text style={[styles.planTabText, activePlan?.id === p.id && { color: palette.white }]}>
                    {p.name}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          ) : null}

          {activePlan ? (
            <>
              <View style={styles.planCard}>
                <View style={styles.planCardHeader}>
                  <Text style={styles.planName}>{activePlan.name}</Text>
                  <Pressable
                    hitSlop={8}
                    onPress={() =>
                      Alert.alert("Delete plan", "Remove this plan and its pins?", [
                        { text: "Cancel", style: "cancel" },
                        {
                          text: "Delete",
                          style: "destructive",
                          onPress: () => {
                            removePlan(activePlan.id);
                            setActivePlanId(null);
                          },
                        },
                      ])
                    }
                  >
                    <Trash2 size={18} color={palette.textMuted} />
                  </Pressable>
                </View>

                <Pressable
                  style={styles.planImageWrap}
                  onLayout={(e: LayoutChangeEvent) =>
                    setImageSize({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })
                  }
                  onPress={(e) => onPlanPress(e.nativeEvent)}
                >
                  {activePlan.image.startsWith("seed-plan://") ? (
                    <SeedPlan />
                  ) : (
                    <EvidencePhoto uri={activePlan.image} style={StyleSheet.absoluteFill} />
                  )}
                  {activePlan.pins.map((pin) => (
                    <Pressable
                      key={pin.id}
                      style={[
                        styles.pin,
                        {
                          left: pin.x * imageSize.w - 14,
                          top: pin.y * imageSize.h - 28,
                          backgroundColor: pinColor(pin),
                        },
                      ]}
                      onPress={() => {
                        if (pin.itemId) router.push(`/item/${pin.itemId}`);
                        else setLinkPinId(pin.id);
                      }}
                    >
                      <Text style={styles.pinText}>{pin.label ?? "?"}</Text>
                    </Pressable>
                  ))}
                </Pressable>
                <Text style={styles.planHint}>Tap anywhere on the plan to drop a pin</Text>
              </View>

              <View style={styles.legend}>
                <LegendDot color={palette.amber} label="Unlinked" />
                <LegendDot color={palette.navy} label="Open item" />
                <LegendDot color={palette.green} label="Closed" />
              </View>

              <Text style={styles.pinsTitle}>{activePlan.pins.length} pins on this plan</Text>
              {activePlan.pins.map((pin) => {
                const linked = pin.itemId ? projectItems.find((i) => i.id === pin.itemId) : undefined;
                return (
                  <Pressable
                    key={pin.id}
                    style={styles.pinRow}
                    onPress={() => (linked ? router.push(`/item/${linked.id}`) : setLinkPinId(pin.id))}
                  >
                    <View style={[styles.pinBadge, { backgroundColor: pinColor(pin) }]}>
                      <Text style={styles.pinBadgeText}>{pin.label ?? "?"}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      {linked ? (
                        <>
                          <Text style={styles.pinItemCode}>{linked.code} · {linked.trade}</Text>
                          <Text style={styles.pinItemLoc} numberOfLines={1}>{formatLocation(linked)}</Text>
                        </>
                      ) : (
                        <Text style={styles.pinUnlinked}>Tap to link an item</Text>
                      )}
                    </View>
                    {linked ? <StatusChip status={linked.status} /> : null}
                    <Pressable hitSlop={8} onPress={() => removePin(activePlan.id, pin.id)}>
                      <X size={16} color={palette.textFaint} />
                    </Pressable>
                  </Pressable>
                );
              })}
              <View style={{ height: 24 }} />
            </>
          ) : null}
        </ScrollView>
      )}

      {/* Drop new pin -> choose item */}
      <LinkItemModal
        visible={!!pendingPin || !!linkPinId}
        items={projectItems}
        onClose={() => {
          setPendingPin(null);
          setLinkPinId(null);
        }}
        onSelect={(item) => {
          if (!activePlan) return;
          if (pendingPin) {
            addPin(activePlan.id, { x: pendingPin.x, y: pendingPin.y, itemId: item.id, label: item.code });
            setPendingPin(null);
          } else if (linkPinId) {
            updatePin(activePlan.id, linkPinId, { itemId: item.id, label: item.code });
            setLinkPinId(null);
          }
        }}
        onSkip={
          pendingPin
            ? () => {
                if (!activePlan || !pendingPin) return;
                addPin(activePlan.id, { x: pendingPin.x, y: pendingPin.y, label: "•" });
                setPendingPin(null);
              }
            : undefined
        }
      />
    </View>
  );
}

function LinkItemModal({
  visible,
  items,
  onClose,
  onSelect,
  onSkip,
}: {
  visible: boolean;
  items: Item[];
  onClose: () => void;
  onSelect: (item: Item) => void;
  onSkip?: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable style={styles.modalSheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Link pin to item</Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <X size={22} color={palette.textMuted} />
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ gap: spacing.sm }} style={{ maxHeight: 420 }}>
            {items.map((item) => (
              <Pressable key={item.id} style={styles.itemOption} onPress={() => onSelect(item)}>
                <View style={[styles.pinBadge, { backgroundColor: palette.navy }]}>
                  <Text style={styles.pinBadgeText}>{item.code.split("-")[1]}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.itemOptionCode}>{item.code} · {item.trade || "No trade"}</Text>
                  <Text style={styles.itemOptionLoc} numberOfLines={1}>{formatLocation(item)}</Text>
                </View>
                <StatusChip status={item.status} />
              </Pressable>
            ))}
          </ScrollView>
          {onSkip ? (
            <Pressable style={styles.skipBtn} onPress={onSkip}>
              <Plus size={16} color={palette.navy} />
              <Text style={styles.skipBtnText}>Drop unlinked pin</Text>
            </Pressable>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function SeedPlan() {
  return (
    <View style={styles.seedPlan}>
      <View style={styles.seedRoomTL}><Text style={styles.seedRoomText}>A-305 Kitchen</Text></View>
      <View style={styles.seedRoomTR}><Text style={styles.seedRoomText}>A-304 Ensuite</Text></View>
      <View style={styles.seedRoomBL}><Text style={styles.seedRoomText}>Living</Text></View>
      <View style={styles.seedRoomBR}><Text style={styles.seedRoomText}>Bedroom</Text></View>
    </View>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: palette.background },
  header: { backgroundColor: palette.navy, paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  headerTitle: { fontSize: font.size.xxl, fontWeight: font.weight.heavy, color: palette.white },
  headerSub: { fontSize: font.size.sm, color: "rgba(255,255,255,0.7)", marginTop: 2 },
  uploadBtn: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: palette.white, paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.pill },
  uploadBtnText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.navy },

  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8, padding: spacing.xxl },
  emptyTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text },
  emptySub: { fontSize: font.size.sm, color: palette.textMuted, textAlign: "center" },
  emptyBtn: { marginTop: spacing.md, backgroundColor: palette.navy, paddingHorizontal: 20, paddingVertical: 12, borderRadius: radius.md },
  emptyBtnText: { color: palette.white, fontWeight: font.weight.bold, fontSize: font.size.sm },

  scroll: { padding: spacing.lg, gap: spacing.md },
  planTabs: { gap: 8, paddingBottom: spacing.sm },
  planTab: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: palette.surfaceAlt },
  planTabActive: { backgroundColor: palette.navy },
  planTabText: { fontSize: font.size.sm, fontWeight: font.weight.semibold, color: palette.textMuted },

  planCard: { backgroundColor: palette.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: palette.border, padding: spacing.md, ...shadow.card },
  planCardHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm },
  planName: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  planImageWrap: { width: "100%", aspectRatio: 1.5, borderRadius: radius.md, overflow: "hidden", backgroundColor: palette.surfaceAlt },
  pin: { position: "absolute", minWidth: 28, height: 28, paddingHorizontal: 6, borderRadius: 14, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: palette.white, ...shadow.floating },
  pinText: { fontSize: 10, fontWeight: font.weight.heavy, color: palette.white },
  planHint: { fontSize: font.size.xs, color: palette.textFaint, textAlign: "center", marginTop: spacing.sm },

  legend: { flexDirection: "row", gap: spacing.lg, paddingHorizontal: spacing.xs },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendDot: { width: 12, height: 12, borderRadius: 6 },
  legendText: { fontSize: font.size.xs, color: palette.textMuted, fontWeight: font.weight.medium },

  pinsTitle: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.text, marginTop: spacing.sm },
  pinRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: palette.surface, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border, padding: spacing.md },
  pinBadge: { minWidth: 36, height: 36, paddingHorizontal: 6, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  pinBadgeText: { fontSize: font.size.xs, fontWeight: font.weight.heavy, color: palette.white },
  pinItemCode: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.text },
  pinItemLoc: { fontSize: font.size.xs, color: palette.textMuted, marginTop: 1 },
  pinUnlinked: { fontSize: font.size.sm, color: palette.amber, fontWeight: font.weight.semibold },

  modalBackdrop: { flex: 1, backgroundColor: "rgba(10,24,48,0.55)", justifyContent: "flex-end" },
  modalSheet: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, paddingBottom: spacing.xxl },
  modalHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  modalTitle: { fontSize: font.size.lg, fontWeight: font.weight.bold, color: palette.text },
  itemOption: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: palette.border },
  itemOptionCode: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.text },
  itemOptionLoc: { fontSize: font.size.xs, color: palette.textMuted, marginTop: 1 },
  skipBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, marginTop: spacing.md, paddingVertical: 12, borderRadius: radius.md, backgroundColor: palette.surfaceAlt },
  skipBtnText: { fontSize: font.size.sm, fontWeight: font.weight.bold, color: palette.navy },

  seedPlan: { flex: 1, backgroundColor: "#F1F4F9", padding: 14, gap: 8 },
  seedRoomText: { fontSize: font.size.xs, color: palette.textMuted, fontWeight: font.weight.semibold },
  seedRoomTL: { position: "absolute", left: "8%", top: "12%", backgroundColor: "#E2E8F0", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 16 },
  seedRoomTR: { position: "absolute", right: "8%", top: "12%", backgroundColor: "#E2E8F0", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 16 },
  seedRoomBL: { position: "absolute", left: "8%", bottom: "12%", backgroundColor: "#EAEEF4", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 16 },
  seedRoomBR: { position: "absolute", right: "8%", bottom: "12%", backgroundColor: "#EAEEF4", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 16 },
});
