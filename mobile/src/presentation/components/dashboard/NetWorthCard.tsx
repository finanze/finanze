import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import { SensitiveText } from "../ui"
import { Dezimal } from "@/domain"

interface NetWorthCardProps {
  totalValue: Dezimal
  currency: string
}

export function NetWorthCard({ totalValue, currency }: NetWorthCardProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)
  const { t } = useI18n()

  return (
    <View style={styles.container}>
      <Text style={[styles.label, { color: colors.textMuted }]}>
        {t.dashboard.netWorth}
      </Text>
      <SensitiveText
        kind="currency"
        value={totalValue}
        currency={currency}
        style={[styles.value, { color: colors.text }]}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    alignItems: "flex-start",
    paddingVertical: spacing.lg,
  },
  label: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.5,
  },
  value: {
    fontSize: 42,
    fontWeight: "200",
    letterSpacing: -1,
    marginTop: spacing.xs,
  },
})
