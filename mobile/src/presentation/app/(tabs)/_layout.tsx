import React, { useEffect } from "react"
import { Stack, router } from "expo-router"
import { useTheme } from "@/presentation/context"
import { useAuth } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"
import { LayoutMenuButton } from "@/presentation/components/navigation/LayoutMenuButton"
import { View, StyleSheet } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { spacing } from "@/presentation/theme"

export default function TabsLayout() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { session, isInitialized } = useAuth()
  const insets = useSafeAreaInsets()

  useEffect(() => {
    if (!isInitialized) return
    if (!session) {
      router.replace("/(auth)/login")
    }
  }, [isInitialized, session])

  const anchorTop = insets.top + spacing.md

  return (
    <View style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="transactions" />
        <Stack.Screen
          name="settings"
          options={{
            presentation: "modal",
          }}
        />
      </Stack>

      <View style={[styles.overlay, { top: anchorTop, left: spacing.md }]}>
        <LayoutMenuButton anchorTop={anchorTop} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  overlay: {
    position: "absolute",
    zIndex: 50,
  },
})
