import React from "react"
import { ScrollView, StyleSheet, Text } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { useLayoutMenuScroll, useTheme } from "@/presentation/context"
import { getThemeColors, spacing } from "@/presentation/theme"
import { useFloatingTabBarContentInset } from "@/presentation/components/navigation/useFloatingTabBarInset"

export default function TransactionsScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { onScroll } = useLayoutMenuScroll()
  const bottomInset = useFloatingTabBarContentInset()

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={["top"]}
    >
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: bottomInset }]}
        showsVerticalScrollIndicator={false}
        scrollIndicatorInsets={{ bottom: bottomInset }}
        onScroll={onScroll}
        scrollEventThrottle={16}
      >
        <Text style={[styles.title, { color: colors.text }]}>Transactions</Text>
        <Text style={[styles.subtitle, { color: colors.textMuted }]}>
          Empty for now — this is a placeholder screen.
        </Text>
      </ScrollView>
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
