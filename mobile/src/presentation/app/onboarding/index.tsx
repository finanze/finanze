import React, { useState, useEffect } from "react"
import { View, Text, StyleSheet, ActivityIndicator, Image } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { router, type Href } from "expo-router"
import { useAuth } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, typography, spacing } from "@/presentation/theme"
import { BackupFileType, CloudPermission } from "@/domain"
import type { ApplicationContainer } from "@/domain"
import { useApplicationContainer } from "@/presentation/context"

import splashIconDark from "../../../../assets/splash-icon.png"
import splashIconLight from "../../../../assets/splash-icon-light.png"

export default function BackupCheckScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()
  const { session, isInitialized } = useAuth()
  const container = useApplicationContainer()
  const splashIcon = resolvedTheme === "dark" ? splashIconDark : splashIconLight

  const [isChecking, setIsChecking] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lockupRowHeight, setLockupRowHeight] = useState(56)

  useEffect(() => {
    if (!isInitialized) return

    if (!session) {
      router.replace("/(auth)/login" as Href)
      return
    }

    checkData()
  }, [isInitialized, session])

  const checkRemote = async (container: ApplicationContainer) => {
    const backupInfo = await container.getBackups.execute({ onlyLocal: false })
    const dataPiece = backupInfo.pieces[BackupFileType.DATA]
    return dataPiece?.remote ?? null
  }

  const checkData = async () => {
    try {
      setIsChecking(true)
      setError(null)

      if (!session) {
        setError(t.errors.unexpectedError)
        return
      }

      if (!session.user.permissions.includes(CloudPermission.BACKUP_INFO)) {
        router.replace("/onboarding/not-allowed" as Href)
        return
      }

      const hasDatabase = await container.checkDatasourceExists.execute()

      if (hasDatabase) {
        router.replace("/onboarding/decrypt" as Href)
      } else {
        const hasDataBackup = await checkRemote(container)
        if (hasDataBackup) {
          router.replace("/onboarding/decrypt" as Href)
        } else {
          router.replace("/onboarding/no-backup" as Href)
        }
      }
    } catch (err: any) {
      console.error("Error checking backup:", err)

      if (err.message?.includes("Too many requests")) {
        setError(t.errors.tooManyRequests)
      } else if (
        err.message?.includes("Network") ||
        err.message?.includes("fetch")
      ) {
        setError(t.errors.networkError)
      } else {
        setError(t.errors.serverError)
      }
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <SafeAreaView
      edges={["left", "right"]}
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <View
        pointerEvents="none"
        style={[
          styles.absoluteSuccess,
          { transform: [{ translateY: -lockupRowHeight / 2 }] },
        ]}
      >
        <View
          style={styles.headerLockup}
          onLayout={event => {
            const nextHeight = event.nativeEvent.layout.height
            if (!nextHeight) return
            setLockupRowHeight(nextHeight)
          }}
        >
          <Image source={splashIcon} style={styles.headerLogoImage} />
          <Text style={[styles.logo, { color: colors.text }]}>Finanze</Text>
        </View>

        {isChecking ? (
          <ActivityIndicator size="small" color={colors.textMuted} />
        ) : null}
      </View>

      {!isChecking && error ? (
        <View style={styles.errorContainer}>
          <Text style={[styles.errorText, { color: colors.danger[500] }]}>
            {error}
          </Text>
          <Text
            style={[styles.retryLink, { color: colors.text }]}
            onPress={checkData}
          >
            {t.common.retry}
          </Text>
        </View>
      ) : null}
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  absoluteSuccess: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    gap: spacing.lg,
  },
  headerLockup: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  headerLogoImage: {
    width: 56,
    height: 56,
    marginRight: 12,
  },
  logo: {
    fontSize: 42,
    fontWeight: "700",
    letterSpacing: -1,
  },
  errorContainer: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    transform: [{ translateY: 140 }],
    paddingHorizontal: spacing.xl,
  },
  errorText: {
    ...typography.body,
    textAlign: "center",
  },
  retryLink: {
    ...typography.label,
    marginTop: spacing.sm,
  },
})
