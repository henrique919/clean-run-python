import { Image } from "expo-image";
import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";

const ICON_MARK = require("@/assets/images/brand/icon-mark.png");
const BANNER = require("@/assets/images/brand/banner.png");

/** Square CleanRun IQ app mark (navy tile). Use as a compact brand mark. */
export function BrandMark({ size = 40, radius = 11, style }: { size?: number; radius?: number; style?: ViewStyle }) {
  return (
    <View style={[{ width: size, height: size, borderRadius: radius, overflow: "hidden" }, style]}>
      <Image source={ICON_MARK} style={{ width: size, height: size }} contentFit="cover" />
    </View>
  );
}

/**
 * Horizontal CleanRun IQ banner logo (white background). Use on headers,
 * report headers and onboarding. Preserves aspect ratio (~3:1).
 */
export function BrandBanner({ width, style }: { width: number; style?: ViewStyle }) {
  // New CleanRun IQ horizontal banner. Render at full requested width.
  // This is 250% larger than the previous reduced 40% treatment.
  const renderWidth = Math.round(width);
  const height = Math.round(renderWidth / 5.15);
  return (
    <View style={[{ width: renderWidth, height, overflow: "hidden" }, style]}>
      <Image source={BANNER} style={{ width: renderWidth, height }} contentFit="contain" />
    </View>
  );
}

const styles = StyleSheet.create({});
