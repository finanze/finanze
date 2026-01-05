import { Stack } from "expo-router"
import { StatusBar } from "expo-status-bar"
import {
  ApplicationContainerProvider,
  AuthProvider,
  FinancialProvider,
  PrivacyProvider,
  ThemeProvider,
  useTheme,
} from "@/presentation/context"
import { I18nProvider } from "@/presentation/i18n"
import { getThemeColors } from "@/presentation/theme"

function RootStack() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  return (
    <>
      <StatusBar style={resolvedTheme === "dark" ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen name="(auth)" options={{ animation: "fade" }} />
        <Stack.Screen name="onboarding" options={{ animation: "fade" }} />
      </Stack>
    </>
  )
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <PrivacyProvider>
          <ApplicationContainerProvider>
            <AuthProvider>
              <FinancialProvider>
                <RootStack />
              </FinancialProvider>
            </AuthProvider>
          </ApplicationContainerProvider>
        </PrivacyProvider>
      </I18nProvider>
    </ThemeProvider>
  )
}
