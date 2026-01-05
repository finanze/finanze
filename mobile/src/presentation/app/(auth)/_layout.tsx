import React, { useEffect } from "react"
import { Stack, router } from "expo-router"
import { useTheme } from "@/presentation/context"
import { useAuth } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"

export default function AuthLayout() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { user, isInitialized } = useAuth()

  useEffect(() => {
    if (!isInitialized) return
    if (user) {
      const timeout = setTimeout(() => {
        router.replace("/")
      }, 450)

      return () => clearTimeout(timeout)
    }
  }, [isInitialized, user])

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: "fade",
      }}
    />
  )
}
