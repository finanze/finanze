import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { router } from "expo-router"
import { useAuth } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { Button, Card } from "@/presentation/components/ui"
import { getThemeColors, spacing } from "@/presentation/theme"
import { CloudOff } from "lucide-react-native"

export default function NoBackupScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()
  const { signOut } = useAuth()

  const handleSignOut = async () => {
    // Sign out and return to login
    await signOut()
    router.replace("/(auth)/login")
  }

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <View style={styles.content}>
        <View style={styles.iconContainer}>
          <View style={[styles.iconBox, { borderColor: colors.border }]}>
            <CloudOff color={colors.textMuted} size={28} strokeWidth={1.5} />
          </View>
        </View>

        <Text style={[styles.title, { color: colors.text }]}>
          {t.onboarding.noBackupTitle}
        </Text>

        <Text style={[styles.message, { color: colors.textMuted }]}>
          {t.onboarding.noBackupMessage}
        </Text>

        <Card style={styles.instructionsCard}>
          <Text style={[styles.instructions, { color: colors.textSecondary }]}>
            {t.onboarding.noBackupInstructions}
          </Text>
        </Card>

        <View style={styles.buttonContainer}>
          <Button
            title={t.auth.signOut}
            onPress={handleSignOut}
            variant="ghost"
          />
        </View>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.lg,
  },
  iconContainer: {
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  iconBox: {
    width: 64,
    height: 64,
    borderRadius: 16,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  title: {
    fontSize: 24,
    fontWeight: "200",
    textAlign: "center",
    letterSpacing: 0.5,
  },
  message: {
    fontSize: 14,
    fontWeight: "300",
    textAlign: "center",
    lineHeight: 22,
    letterSpacing: 0.3,
  },
  instructionsCard: {
    marginTop: spacing.md,
  },
  instructions: {
    fontSize: 12,
    fontWeight: "300",
    textAlign: "center",
    lineHeight: 18,
    letterSpacing: 0.3,
  },
  buttonContainer: {
    marginTop: spacing.xl,
  },
})
