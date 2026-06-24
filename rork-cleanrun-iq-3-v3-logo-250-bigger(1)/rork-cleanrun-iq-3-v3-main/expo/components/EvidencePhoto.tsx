import { Image } from "expo-image";
import { Camera } from "lucide-react-native";
import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { font, palette, radius } from "@/constants/theme";

const TONE_MAP: Record<string, { bg: string; fg: string }> = {
  amber: { bg: "#FEF3C7", fg: "#B45309" },
  red: { bg: "#FEE2E2", fg: "#B91C1C" },
  green: { bg: "#DCFCE7", fg: "#15803D" },
  sky: { bg: "#E0F2FE", fg: "#0369A1" },
  violet: { bg: "#EDE9FE", fg: "#6D28D9" },
  navy: { bg: "#E7ECF5", fg: palette.navy },
};

function parseSeed(uri: string): { tone: string; label: string } | null {
  if (!uri.startsWith("seed://")) return null;
  const rest = uri.slice("seed://".length);
  const [tone, ...labelParts] = rest.split("/");
  return { tone, label: decodeURIComponent(labelParts.join("/")) };
}

/**
 * Renders a captured photo. Real device captures are file/asset URIs; demo seed
 * photos use the `seed://tone/label` scheme drawn as a labelled colour block so
 * the app works fully offline.
 */
export function EvidencePhoto({
  uri,
  size,
  style,
}: {
  uri: string;
  size?: number;
  style?: ViewStyle;
}) {
  const dim = size ? { width: size, height: size } : { flex: 1, aspectRatio: 1 };
  const seed = parseSeed(uri);

  if (seed) {
    const tone = TONE_MAP[seed.tone] ?? TONE_MAP.navy;
    return (
      <View style={[styles.box, dim, { backgroundColor: tone.bg }, style]}>
        <Camera size={18} color={tone.fg} />
        <Text style={[styles.label, { color: tone.fg }]} numberOfLines={2}>
          {seed.label}
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.box, dim, style]}>
      <Image source={{ uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    borderRadius: radius.md,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    padding: 8,
    backgroundColor: palette.surfaceAlt,
  },
  label: { fontSize: font.size.xs, fontWeight: font.weight.semibold, textAlign: "center" },
});
