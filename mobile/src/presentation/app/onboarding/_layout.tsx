import { Stack } from "expo-router"
import { useTheme } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"

export default function OnboardingLayout() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.background },
        animation: "fade",
        gestureEnabled: false, // Prevent going back during onboarding
      }}
    />
  )
}
