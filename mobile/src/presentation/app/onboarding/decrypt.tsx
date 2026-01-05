import React, { useEffect, useState } from "react"
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  TouchableOpacity,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { router, type Href } from "expo-router"
import { useAuth } from "@/presentation/context"
import { useFinancial } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { Button, TextInput } from "@/presentation/components/ui"
import { getThemeColors, spacing } from "@/presentation/theme"
import { BackupFileType } from "@/domain"
import { useApplicationContainer } from "@/presentation/context"
import { Lock } from "lucide-react-native"

export default function DecryptScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()
  const { session, signOut } = useAuth()
  const { loadData, isLoading: isDataLoading } = useFinancial()
  const container = useApplicationContainer()

  const [password, setPassword] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [firstImport, setFirstImport] = useState(false)

  useEffect(() => {
    const checkNeedsImport = async () => {
      if (!session?.accessToken) {
        return
      }

      try {
        const hasDatabase = await container.checkDatasourceExists.execute()
        setFirstImport(!hasDatabase)
      } catch {
        // Best-effort; the action button still works.
      }
    }

    checkNeedsImport()
  }, [session?.accessToken])

  const handleSignOut = () => {
    Alert.alert(t.auth.signOutConfirmTitle, t.auth.signOutConfirmMessage, [
      { text: t.common.cancel, style: "cancel" },
      {
        text: t.auth.signOut,
        style: "destructive",
        onPress: async () => {
          try {
            await signOut()
            router.replace("/(auth)/login")
          } catch (err) {
            console.error("Sign out error:", err)
          }
        },
      },
    ])
  }

  const handleContinue = async () => {
    if (!password.trim()) {
      setError(t.onboarding.dataPasswordRequired)
      return
    }

    if (!session?.accessToken) {
      setError(t.errors.unexpectedError)
      return
    }

    try {
      setIsProcessing(true)
      setError(null)

      await container.initializeDatasource.execute(password)

      await container.importBackup.execute({
        types: [BackupFileType.DATA, BackupFileType.CONFIG],
        password: null,
        force: true,
      })

      // Load financial data after decrypt/import.
      await loadData()

      router.replace("/(tabs)/dashboard" as Href)
    } catch (err: any) {
      console.error("Import error:", err)

      if (err?.name === "PermissionDenied") {
        setError(t.errors.serverError)
        return
      }

      if (
        err.message?.includes("password") ||
        err.message?.includes("decrypt")
      ) {
        setError(t.onboarding.wrongPassword)
      } else {
        setError(t.onboarding.importError)
      }
    } finally {
      setIsProcessing(false)
    }
  }

  const isLoading = isProcessing || isDataLoading

  if (isLoading) {
    return (
      <SafeAreaView
        style={[styles.container, { backgroundColor: colors.background }]}
      >
        <View style={styles.loadingContent}>
          <ActivityIndicator size="small" color={colors.textMuted} />
          <Text style={[styles.loadingText, { color: colors.text }]}>
            {firstImport
              ? t.onboarding.importingBackup
              : t.onboarding.decryptingData}
          </Text>
          <Text
            style={[styles.loadingDescription, { color: colors.textMuted }]}
          >
            {firstImport
              ? t.onboarding.importingDescription
              : t.onboarding.decryptingDescription}
          </Text>
        </View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.iconContainer}>
            <View style={[styles.iconBox, { borderColor: colors.border }]}>
              <Lock color={colors.textMuted} size={28} strokeWidth={1.5} />
            </View>
          </View>

          <Text style={[styles.title, { color: colors.text }]}>
            {firstImport ? t.onboarding.importData : t.onboarding.decryptData}
          </Text>

          <Text style={[styles.message, { color: colors.textMuted }]}>
            {firstImport
              ? t.onboarding.importMessage
              : t.onboarding.decryptMessage}
          </Text>

          <View style={styles.form}>
            <TextInput
              label={t.onboarding.dataPassword}
              placeholder={t.onboarding.dataPasswordPlaceholder}
              value={password}
              onChangeText={text => {
                setPassword(text)
                setError(null)
              }}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              editable={!isLoading}
            />

            {error && (
              <View style={styles.errorContainer}>
                <Text style={[styles.errorText, { color: colors.danger[500] }]}>
                  {error}
                </Text>
              </View>
            )}

            <Button
              title={t.common.continue}
              onPress={handleContinue}
              loading={isLoading}
              disabled={isLoading}
            />

            <TouchableOpacity
              onPress={handleSignOut}
              style={styles.signOutLink}
            >
              <Text style={[styles.signOutText, { color: colors.textMuted }]}>
                {t.auth.signOut}
              </Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
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
  form: {
    marginTop: spacing.xl,
    gap: spacing.lg,
  },
  errorContainer: {
    paddingVertical: spacing.sm,
  },
  errorText: {
    fontSize: 14,
    fontWeight: "400",
    textAlign: "center",
  },
  loadingContent: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.xl,
  },
  loadingText: {
    fontSize: 18,
    fontWeight: "300",
    marginTop: spacing.md,
    letterSpacing: 0.3,
  },
  loadingDescription: {
    fontSize: 14,
    fontWeight: "300",
    textAlign: "center",
    letterSpacing: 0.3,
  },
  signOutLink: {
    alignItems: "center",
    paddingVertical: spacing.md,
  },
  signOutText: {
    fontSize: 14,
    fontWeight: "400",
    letterSpacing: 0.3,
  },
})
