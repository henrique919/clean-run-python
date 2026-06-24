/**
 * CleanRun IQ design system — calm, premium, field-ready construction SaaS palette.
 * Navy primary, green accent, amber warnings, red for overdue/rejected.
 */

export const palette = {
  navy: "#0E1F3A",
  navyDeep: "#0A1830",
  navyMid: "#16294A",
  navySoft: "#1E3357",

  green: "#16A34A",
  greenBright: "#22C55E",
  greenSoft: "#DCFCE7",

  amber: "#F59E0B",
  amberSoft: "#FEF3C7",

  sky: "#0EA5E9",
  skySoft: "#E0F2FE",

  violet: "#7C3AED",
  violetSoft: "#EDE9FE",

  red: "#DC2626",
  redSoft: "#FEE2E2",

  white: "#FFFFFF",
  background: "#F4F6F9",
  surface: "#FFFFFF",
  surfaceAlt: "#EEF1F6",
  border: "#E3E8F0",
  borderStrong: "#CDD5E1",

  text: "#0E1B2E",
  textMuted: "#5A6B82",
  textFaint: "#8A98AC",
} as const;

export const Colors = {
  primary: palette.navy,
  primaryDeep: palette.navyDeep,
  accent: palette.green,
  background: palette.background,
  surface: palette.surface,
  border: palette.border,
  text: palette.text,
  textMuted: palette.textMuted,
} as const;

export type StatusVisual = { label: string; color: string; soft: string };

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  pill: 999,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const font = {
  size: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 20,
    xxl: 26,
    huge: 34,
  },
  weight: {
    regular: "400" as const,
    medium: "500" as const,
    semibold: "600" as const,
    bold: "700" as const,
    heavy: "800" as const,
  },
} as const;

export const shadow = {
  card: {
    boxShadow: "0px 6px 14px rgba(14, 27, 46, 0.06)",
    elevation: 2,
  },
  floating: {
    boxShadow: "0px 12px 22px rgba(14, 27, 46, 0.16)",
    elevation: 8,
  },
} as const;
