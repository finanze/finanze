import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { FileText } from "lucide-react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"

export function TransactionEmptyState() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()

  return (
    <View style={styles.container}>
      <View style={[styles.iconContainer, { borderColor: colors.border }]}>
        <FileText size={28} color={colors.textMuted} strokeWidth={1} />
      </View>
      <Text style={[styles.title, { color: colors.text }]}>
        {t.transactions.noTransactions}
      </Text>
      <Text style={[styles.hint, { color: colors.textMuted }]}>
        {t.transactions.noTransactionsHint}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 80,
    gap: spacing.md,
  },
  iconContainer: {
    width: 64,
    height: 64,
    borderRadius: 16,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: 18,
    fontWeight: "300",
    letterSpacing: 0.5,
  },
  hint: {
    fontSize: 14,
    fontWeight: "300",
    letterSpacing: 0.3,
    textAlign: "center",
    paddingHorizontal: spacing.xxl,
  },
})
