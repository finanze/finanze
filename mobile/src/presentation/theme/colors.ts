// Color palette for Finanze Mobile
// True dark theme (deep black) and clean light theme
// Minimal, sophisticated, professional financial app aesthetic

export const colors = {
  // Primary brand colors - subtle blue accent
  primary: {
    50: "#eff6ff",
    100: "#dbeafe",
    200: "#bfdbfe",
    300: "#93c5fd",
    400: "#60a5fa",
    500: "#3b82f6",
    600: "#2563eb",
    700: "#1d4ed8",
    800: "#1e40af",
    900: "#1e3a8a",
  },

  // Success colors - muted green
  success: {
    50: "#f0fdf4",
    100: "#dcfce7",
    200: "#bbf7d0",
    300: "#86efac",
    400: "#4ade80",
    500: "#22c55e",
    600: "#16a34a",
    700: "#15803d",
  },

  // Warning colors
  warning: {
    50: "#fffbeb",
    100: "#fef3c7",
    200: "#fde68a",
    300: "#fcd34d",
    400: "#fbbf24",
    500: "#f59e0b",
    600: "#d97706",
  },

  // Danger colors
  danger: {
    50: "#fef2f2",
    100: "#fee2e2",
    200: "#fecaca",
    300: "#fca5a5",
    400: "#f87171",
    500: "#ef4444",
    600: "#dc2626",
  },

  // Light mode - clean white
  light: {
    background: "#ffffff",
    surface: "#f9fafb",
    surfaceElevated: "#ffffff",
    border: "#e5e7eb",
    text: "#050505",
    textSecondary: "#4b5563",
    textMuted: "#9ca3af",
  },

  // Dark mode - true deep black
  dark: {
    background: "#000000",
    surface: "#0a0a0a",
    surfaceElevated: "#141414",
    border: "#1f1f1f",
    text: "#fafafa",
    textSecondary: "#a1a1aa",
    textMuted: "#71717a",
  },

  // Chart colors for asset distribution
  chart: {
    cash: "#22c55e",
    fund: "#3b82f6",
    stockEtf: "#8b5cf6",
    deposit: "#06b6d4",
    crypto: "#f59e0b",
    realEstate: "#ec4899",
    commodity: "#eab308",
    crowdlending: "#14b8a6",
    factoring: "#f97316",
    realEstateCf: "#a855f7",
    loan: "#ef4444",
    card: "#6366f1",
    bond: "#84cc16",
    derivative: "#f43f5e",
    fundPortfolio: "#0ea5e9",
  },
}

export type ColorScheme = "light" | "dark"

export const getThemeColors = (scheme: ColorScheme) => {
  const mode = scheme === "dark" ? colors.dark : colors.light

  return {
    ...mode,
    // Flat primary color for convenience (uses 500 shade)
    primary: colors.primary[500],
    // Full color palettes with shades
    primaryShades: colors.primary,
    success: colors.success,
    warning: colors.warning,
    danger: colors.danger,
    chart: colors.chart,
  }
}
