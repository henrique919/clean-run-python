import React, { ReactNode } from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { font, palette, radius, shadow, spacing } from "@/constants/theme";

export function SectionCard({
  title,
  subtitle,
  right,
  children,
  style,
  accent,
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  style?: ViewStyle;
  accent?: string;
}) {
  return (
    <View style={[styles.card, style]}>
      {accent ? <View style={[styles.accent, { backgroundColor: accent }]} /> : null}
      {title ? (
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{title}</Text>
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
          {right}
        </View>
      ) : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: palette.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: palette.border,
    padding: spacing.lg,
    overflow: "hidden",
    ...shadow.card,
  },
  accent: { position: "absolute", left: 0, top: 0, bottom: 0, width: 4 },
  header: { flexDirection: "row", alignItems: "center", marginBottom: spacing.md, gap: spacing.sm },
  title: { fontSize: font.size.md, fontWeight: font.weight.bold, color: palette.text },
  subtitle: { fontSize: font.size.sm, color: palette.textMuted, marginTop: 2 },
});
