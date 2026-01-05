import { StyleSheet } from "react-native"

export const typography = StyleSheet.create({
  // Headers
  h1: {
    fontSize: 32,
    fontWeight: "700",
    lineHeight: 40,
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 24,
    fontWeight: "600",
    lineHeight: 32,
    letterSpacing: -0.3,
  },
  h3: {
    fontSize: 20,
    fontWeight: "600",
    lineHeight: 28,
  },
  h4: {
    fontSize: 18,
    fontWeight: "600",
    lineHeight: 24,
  },

  // Body text
  bodyLarge: {
    fontSize: 16,
    fontWeight: "400",
    lineHeight: 24,
  },
  body: {
    fontSize: 14,
    fontWeight: "400",
    lineHeight: 20,
  },
  bodySmall: {
    fontSize: 12,
    fontWeight: "400",
    lineHeight: 16,
  },

  // Labels
  label: {
    fontSize: 14,
    fontWeight: "500",
    lineHeight: 20,
  },
  labelSmall: {
    fontSize: 12,
    fontWeight: "500",
    lineHeight: 16,
  },

  // Numbers/Currency
  currency: {
    fontSize: 28,
    fontWeight: "700",
    lineHeight: 36,
    fontVariant: ["tabular-nums"],
  },
  currencySmall: {
    fontSize: 16,
    fontWeight: "600",
    lineHeight: 24,
    fontVariant: ["tabular-nums"],
  },

  // Percentage
  percentage: {
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 20,
    fontVariant: ["tabular-nums"],
  },
})

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
}

export const borderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
}
