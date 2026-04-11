import { useState, useEffect, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n, type Locale } from "@/i18n"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Label } from "@/components/ui/Label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs"
import { motion } from "framer-motion"
import {
  ChevronDown,
  ChevronUp,
  Unlink,
  AlertTriangle,
  Cloud,
  Sun,
  Moon,
  SunMoon,
} from "lucide-react"
import { useAppContext } from "@/context/AppContext"
import { useTheme } from "@/context/ThemeContext"
import { useBackupAlert } from "@/context/BackupAlertContext"
import { useCloud } from "@/context/CloudContext"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { CloudRole, FFStatus } from "@/types"
import { AdvancedSettingsForm } from "@/components/ui/AdvancedSettingsForm"
import { IntegrationsTab } from "@/components/settings/IntegrationsTab"
import { GeneralTab } from "@/components/settings/GeneralTab"
import { CloudTab } from "@/components/settings/CloudTab"
import { isNativeMobile } from "@/lib/platform"
import {
  checkBiometricAvailability,
  deleteCredentials,
  hasStoredCredentials as checkHasStoredBiometricCredentials,
} from "@/lib/mobile/biometric"
import type { BiometricAvailability } from "@/lib/mobile/biometric"
import { cn } from "@/lib/utils"

const APPLICATION_LOCALES: Locale[] = ["en-US", "es-ES"]

export default function SettingsPage() {
  const { t, locale, changeLocale } = useI18n()
  const [searchParams] = useSearchParams()
  const {
    showToast,
    fetchSettings,
    isLoadingSettings,
    fetchExternalIntegrations,
    featureFlags,
  } = useAppContext()
  const { role } = useCloud()
  const { theme, setThemeMode } = useTheme()
  const { alertColor } = useBackupAlert()
  const [activeTab, setActiveTab] = useState(
    searchParams.get("tab") || "general",
  )
  const [biometricAvailability, setBiometricAvailability] =
    useState<BiometricAvailability | null>(null)
  const [hasStoredBiometricCredentials, setHasStoredBiometricCredentials] =
    useState(false)
  const [isClearingBiometricCredentials, setIsClearingBiometricCredentials] =
    useState(false)

  const isCloudEnabled = featureFlags.CLOUD === FFStatus.ON

  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    advancedSettings: false,
  })

  const isDesktopApp = typeof window !== "undefined" && !!window.ipcAPI

  const applicationLanguageOptions = APPLICATION_LOCALES.map(code => ({
    code,
    label: t.settings.applicationLanguageOptions[code],
  }))

  useEffect(() => {
    fetchSettings()
    fetchExternalIntegrations()
  }, [])

  const refreshBiometricStatus = useCallback(async () => {
    if (!__MOBILE__ || !isNativeMobile()) return

    const availability = await checkBiometricAvailability()
    setBiometricAvailability(availability)

    if (availability.isAvailable) {
      const saved = await checkHasStoredBiometricCredentials()
      setHasStoredBiometricCredentials(saved)
    } else {
      setHasStoredBiometricCredentials(false)
    }
  }, [])

  useEffect(() => {
    refreshBiometricStatus()
  }, [refreshBiometricStatus])

  const handleClearBiometricCredentials = useCallback(async () => {
    if (!__MOBILE__ || !isNativeMobile()) return
    if (!biometricAvailability?.isAvailable) return
    if (!hasStoredBiometricCredentials) return

    try {
      setIsClearingBiometricCredentials(true)
      await deleteCredentials()
      setHasStoredBiometricCredentials(false)
      showToast(t.settings.biometricCredentialsCleared, "success")
    } catch {
      showToast(t.settings.biometricCredentialsClearError, "error")
    } finally {
      setIsClearingBiometricCredentials(false)
    }
  }, [
    biometricAvailability?.isAvailable,
    hasStoredBiometricCredentials,
    showToast,
    t.settings.biometricCredentialsClearError,
    t.settings.biometricCredentialsCleared,
  ])

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  if (isLoadingSettings) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.settings.title}</h1>
      </div>

      <Tabs
        defaultValue="general"
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full"
      >
        <div className="flex justify-center w-full">
          <TabsList
            className={`grid w-full max-w-[800px] h-auto min-h-[3rem] ${isCloudEnabled ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2 sm:grid-cols-3"}`}
          >
            <TabsTrigger
              value="general"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.general}
            </TabsTrigger>
            {isCloudEnabled && (
              <TabsTrigger
                value="cloud"
                className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center gap-1"
              >
                <Cloud
                  className={cn(
                    "h-4 w-4",
                    role === CloudRole.PLUS ? "text-amber-400" : undefined,
                  )}
                />
                {t.settings.cloud.tabTitle}
                {alertColor && (
                  <span
                    className={`ml-1 inline-block h-1.5 w-1.5 rounded-full ${
                      alertColor === "dark-red"
                        ? "bg-red-700"
                        : alertColor === "red"
                          ? "bg-red-500"
                          : "bg-amber-500"
                    }`}
                  />
                )}
              </TabsTrigger>
            )}
            <TabsTrigger
              value="application"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.application}
            </TabsTrigger>
            <TabsTrigger
              value="integrations"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.integrations}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="general" className="space-y-4 mt-4">
          <GeneralTab />
        </TabsContent>

        <TabsContent value="application" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {t.settings.applicationDisclaimerDescription}
              </p>
              <Card>
                <CardHeader>
                  <CardTitle>{t.settings.applicationLanguageTitle}</CardTitle>
                  <CardDescription>
                    {t.settings.applicationLanguageDescription}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Label htmlFor="application-language">
                      {t.settings.applicationLanguageTitle}
                    </Label>
                    <select
                      id="application-language"
                      value={locale}
                      aria-label={t.settings.applicationLanguageTitle}
                      onChange={event => {
                        const nextLocale = event.target.value as Locale
                        if (nextLocale !== locale) {
                          changeLocale(nextLocale)
                        }
                      }}
                      className="flex h-10 w-full max-w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {applicationLanguageOptions.map(option => (
                        <option key={option.code} value={option.code}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t.settings.themeTitle}</CardTitle>
                  <CardDescription>
                    {t.settings.themeDescription}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-1 rounded-lg bg-muted p-1 w-fit">
                    <button
                      onClick={() => setThemeMode("light")}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        theme === "light"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Sun className="h-4 w-4" />
                      {t.common.light}
                    </button>
                    <button
                      onClick={() => setThemeMode("dark")}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        theme === "dark"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Moon className="h-4 w-4" />
                      {t.common.dark}
                    </button>
                    <button
                      onClick={() => setThemeMode("system")}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        theme === "system"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <SunMoon className="h-4 w-4" />
                      {t.common.system}
                    </button>
                  </div>
                </CardContent>
              </Card>

              {isNativeMobile() && (
                <Card>
                  <CardHeader>
                    <CardTitle>
                      {t.settings.biometricCredentialsTitle}
                    </CardTitle>
                    <CardDescription>
                      {t.settings.biometricCredentialsDescription}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">
                          {hasStoredBiometricCredentials
                            ? t.settings.biometricCredentialsActionTitle
                            : t.settings.biometricCredentialsNotEnabledTitle}
                        </p>
                        {!hasStoredBiometricCredentials && (
                          <p className="text-xs text-muted-foreground">
                            {t.settings.biometricCredentialsNotEnabledHint}
                          </p>
                        )}
                      </div>
                      {hasStoredBiometricCredentials && (
                        <Button
                          type="button"
                          variant="outline"
                          className="w-auto px-3"
                          onClick={handleClearBiometricCredentials}
                          disabled={
                            isClearingBiometricCredentials ||
                            !biometricAvailability?.isAvailable
                          }
                        >
                          {isClearingBiometricCredentials ? (
                            <>
                              <LoadingSpinner size="sm" className="mr-2" />
                              {t.common.loading}
                            </>
                          ) : (
                            <>
                              <Unlink className="mr-2 h-4 w-4" />
                              {t.settings.biometricCredentialsAction}
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Advanced Settings Section (Desktop only) */}
              {isDesktopApp && (
                <Card>
                  <CardHeader
                    className="cursor-pointer select-none"
                    onClick={() => toggleSection("advancedSettings")}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{t.advancedSettings.title}</CardTitle>
                        <CardDescription>
                          {t.advancedSettings.subtitle}
                        </CardDescription>
                      </div>
                      {expandedSections.advancedSettings ? (
                        <ChevronUp className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </CardHeader>
                  {expandedSections.advancedSettings && (
                    <CardContent>
                      <div className="space-y-3">
                        <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                          {t.advancedSettings.restartWarning}
                        </p>
                        <AdvancedSettingsForm
                          idPrefix="settings"
                          onError={() =>
                            showToast(t.settings.saveError, "error")
                          }
                        />
                      </div>
                    </CardContent>
                  )}
                </Card>
              )}
            </div>
          </motion.div>
        </TabsContent>

        {isCloudEnabled && (
          <TabsContent value="cloud" className="space-y-4 mt-4">
            <CloudTab />
          </TabsContent>
        )}

        <TabsContent value="integrations" className="space-y-4 mt-4">
          <IntegrationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
