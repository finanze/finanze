import React, { useEffect, useState } from "react"
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  TouchableOpacity,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { router, type Href } from "expo-router"
import { useAuth } from "@/presentation/context"
import { useFinancial } from "@/presentation/context"
import { usePrivacy } from "@/presentation/context"
import { useLayoutMenuScroll } from "@/presentation/context"
import { useTheme, type ThemeMode } from "@/presentation/context/ThemeContext"
import { useI18n } from "@/presentation/i18n"
import { Button, ToggleSwitch } from "@/presentation/components/ui"
import { getThemeColors, spacing } from "@/presentation/theme"
import { formatDateTime } from "@/presentation/utils/financialDataUtils"
import { Sun, Moon, Smartphone } from "lucide-react-native"
import { useApplicationContainer } from "@/presentation/context"
import Constants from "expo-constants"
import { useFloatingTabBarContentInset } from "@/presentation/components/navigation/useFloatingTabBarInset"

const THEME_OPTIONS: {
  value: ThemeMode
  Icon: React.ComponentType<{ size?: number; color?: string }>
}[] = [
  { value: "light", Icon: Sun },
  { value: "dark", Icon: Moon },
  { value: "system", Icon: Smartphone },
]

export default function SettingsScreen() {
  const { resolvedTheme, themeMode, setThemeMode } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t, language, setLanguage, locale } = useI18n()
  const { hideAmounts, setHideAmounts } = usePrivacy()
  const { user, signOut, isLoading } = useAuth()
  const { targetCurrency, clearData } = useFinancial()
  const { onScroll } = useLayoutMenuScroll()
  const bottomInset = useFloatingTabBarContentInset()

  const appVersion =
    typeof Constants.expoConfig?.version === "string" &&
    Constants.expoConfig.version.length > 0
      ? Constants.expoConfig.version
      : "—"

  const container = useApplicationContainer()
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  useEffect(() => {
    let isActive = true

    const load = async () => {
      try {
        const d = await container.getLocalLastUpdate.execute()
        if (isActive) setLastUpdate(d)
      } catch {
        // Best-effort: keep showing "—".
      }
    }

    void load()

    return () => {
      isActive = false
    }
  }, [container])

  const hasData = lastUpdate !== null

  const navigateToImport = () => {
    router.replace("/onboarding/decrypt" as Href)
  }

  const handleSignOut = async () => {
    Alert.alert(t.auth.signOutConfirmTitle, t.auth.signOutConfirmMessage, [
      { text: t.common.cancel, style: "cancel" },
      {
        text: t.auth.signOut,
        style: "destructive",
        onPress: async () => {
          try {
            await signOut()
            router.replace("/(auth)/login" as Href)
          } catch (err) {
            console.error("Sign out error:", err)
            Alert.alert(t.common.error, t.auth.signOutError)
          }
        },
      },
    ])
  }

  const handleLanguageToggle = async () => {
    await setLanguage(language === "en" ? "es" : "en")
  }

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={["top", "bottom"]}
    >
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: bottomInset }]}
        showsVerticalScrollIndicator={false}
        scrollIndicatorInsets={{ bottom: bottomInset }}
        onScroll={onScroll}
        scrollEventThrottle={16}
      >
        {/* Account */}
        <View style={styles.section}>
          <View style={styles.accountHeader}>
            <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
              {t.settings.account}
            </Text>
            <Button
              title={t.auth.signOut}
              onPress={handleSignOut}
              variant="outline"
              size="sm"
              loading={isLoading}
            />
          </View>
          <Text style={[styles.email, { color: colors.text }]}>
            {user?.email || "—"}
          </Text>
        </View>

        {/* General */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            {t.settings.general}
          </Text>
          <View style={styles.settingRow}>
            <Text style={[styles.settingLabel, { color: colors.textMuted }]}>
              {t.settings.defaultCurrency}
            </Text>
            <Text style={[styles.settingValue, { color: colors.text }]}>
              {targetCurrency || "—"}
            </Text>
          </View>
        </View>

        {/* Appearance */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            {t.settings.appearance}
          </Text>
          <View style={styles.themeOptions}>
            {THEME_OPTIONS.map(option => (
              <TouchableOpacity
                key={option.value}
                style={[
                  styles.themeOption,
                  {
                    backgroundColor:
                      themeMode === option.value
                        ? colors.surface
                        : "transparent",
                  },
                ]}
                onPress={() => setThemeMode(option.value)}
              >
                <option.Icon
                  size={18}
                  color={
                    themeMode === option.value ? colors.text : colors.textMuted
                  }
                />
                <Text
                  style={[
                    styles.themeLabel,
                    {
                      color:
                        themeMode === option.value
                          ? colors.text
                          : colors.textMuted,
                    },
                  ]}
                >
                  {option.value === "light"
                    ? t.settings.themeLight
                    : option.value === "dark"
                      ? t.settings.themeDark
                      : t.settings.themeSystem}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Language */}
        <View style={styles.section}>
          <View style={styles.settingRow}>
            <Text style={[styles.settingLabel, { color: colors.textMuted }]}>
              {t.settings.language}
            </Text>
            <TouchableOpacity onPress={handleLanguageToggle}>
              <Text style={[styles.settingValue, { color: colors.text }]}>
                {language === "en"
                  ? t.settings.languageEnglish
                  : t.settings.languageSpanish}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Privacy */}
        <View style={styles.section}>
          <View style={styles.settingRow}>
            <Text style={[styles.settingLabel, { color: colors.textMuted }]}>
              {t.settings.hideAmounts}
            </Text>
            <ToggleSwitch
              value={hideAmounts}
              onValueChange={val => {
                void setHideAmounts(val)
              }}
            />
          </View>
        </View>

        {/* Data */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
            {t.settings.data}
          </Text>
          {!hasData ? (
            <View style={styles.fetchDataContainer}>
              <Text style={[styles.noDataText, { color: colors.textMuted }]}>
                {t.settings.noDataLoaded}
              </Text>
              <Button
                title={t.settings.importBackup}
                onPress={navigateToImport}
                size="sm"
              />
            </View>
          ) : (
            <>
              <View style={styles.settingRow}>
                <Text
                  style={[styles.settingLabel, { color: colors.textMuted }]}
                >
                  {t.settings.lastSync}
                </Text>
                <Text style={[styles.settingValue, { color: colors.text }]}>
                  {lastUpdate
                    ? formatDateTime(lastUpdate.toISOString(), locale)
                    : "—"}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.dangerAction}
                onPress={() => {
                  Alert.alert(
                    t.settings.deleteDataTitle,
                    t.settings.deleteDataMessage,
                    [
                      { text: t.common.cancel, style: "cancel" },
                      {
                        text: t.common.delete,
                        style: "destructive",
                        onPress: async () => {
                          try {
                            clearData()
                            await container.clearLocalData.execute()
                            setLastUpdate(null)
                          } catch (e) {
                            Alert.alert(
                              t.common.error,
                              t.settings.deleteDataError,
                            )
                          }
                        },
                      },
                    ],
                  )
                }}
              >
                <Text
                  style={[styles.dangerText, { color: colors.danger[500] }]}
                >
                  {t.settings.deleteLocalData}
                </Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* App Info */}
        <View style={styles.appInfo}>
          <Text style={[styles.version, { color: colors.textMuted }]}>
            {t.settings.appVersion.replace("{version}", appVersion)}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  modalHandleContainer: {
    alignItems: "center",
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  modalHandle: {
    width: 56,
    height: 6,
    borderRadius: 3,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.xl,
  },
  section: {
    gap: spacing.md,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.5,
  },
  accountHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  email: {
    fontSize: 16,
    fontWeight: "300",
    letterSpacing: 0.3,
  },
  themeOptions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  themeOption: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderRadius: 12,
    gap: 6,
  },
  themeLabel: {
    fontSize: 12,
    fontWeight: "400",
    letterSpacing: 0.3,
  },
  settingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  settingLabel: {
    fontSize: 14,
    fontWeight: "300",
  },
  settingValue: {
    fontSize: 14,
    fontWeight: "500",
  },
  dangerAction: {
    paddingVertical: spacing.sm,
  },
  dangerText: {
    fontSize: 14,
    fontWeight: "400",
  },
  fetchDataContainer: {
    gap: spacing.md,
  },
  noDataText: {
    fontSize: 14,
    fontWeight: "300",
    letterSpacing: 0.3,
  },
  appInfo: {
    alignItems: "center",
    marginTop: spacing.lg,
  },
  version: {
    fontSize: 12,
    fontWeight: "300",
    letterSpacing: 0.5,
  },
})
