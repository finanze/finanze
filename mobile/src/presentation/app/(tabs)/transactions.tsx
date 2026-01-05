import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { useTheme } from "@/presentation/context"
import { getThemeColors, spacing } from "@/presentation/theme"

export default function TransactionsScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={["top"]}
    >
      <View style={styles.content}>
        <Text style={[styles.title, { color: colors.text }]}>Transactions</Text>
        <Text style={[styles.subtitle, { color: colors.textMuted }]}>
          Empty for now — this is a placeholder screen.
        </Text>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.sm,
  },
  title: {
    fontSize: 18,
    fontWeight: "300",
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 14,
    fontWeight: "300",
    letterSpacing: 0.3,
    lineHeight: 20,
  },
})
