import { useState, useEffect, useCallback, useMemo } from "react"
import {
  RotateCcw,
  FolderOpen,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
} from "lucide-react"
import { Button } from "@/components/ui/Button"
import { Label } from "@/components/ui/Label"
import { Input } from "@/components/ui/Input"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { useI18n } from "@/i18n"
import { checkStatus, refreshApiBaseUrl } from "@/services/api"
import {
  getConfig,
  saveConfig,
  resetConfig,
  hasConfig,
} from "@/services/configStorage"
import type {
  FinanzeConfig,
  BackendLogLevel,
  BackendStartOptions,
} from "@/types"

export interface AdvancedSettingsFormProps {
  onSaveComplete?: () => void
  onError?: (error: Error) => void
  idPrefix?: string
}

const LOG_LEVELS: BackendLogLevel[] = [
  "NONE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
]

const LOG_FILE_LEVEL_INHERIT = "__inherit__"

const SERVER_URL_PATTERN = /^https?:\/\/.+/i

const isServerUrlFormatValid = (value: string): boolean => {
  const trimmed = value.trim()
  if (!trimmed) {
    return true
  }
  return SERVER_URL_PATTERN.test(trimmed)
}

const normalizeConfig = (config: FinanzeConfig): FinanzeConfig => {
  return {
    serverUrl: config.serverUrl?.trim() || undefined,
    backend: config.backend
      ? {
          dataDir: config.backend.dataDir || undefined,
          logDir: config.backend.logDir || undefined,
          logLevel: config.backend.logLevel,
          logFileLevel: config.backend.logFileLevel,
          thirdPartyLogLevel: config.backend.thirdPartyLogLevel,
          port: config.backend.port,
        }
      : undefined,
  }
}

const areConfigsEqual = (a: FinanzeConfig, b: FinanzeConfig): boolean => {
  const normA = normalizeConfig(a)
  const normB = normalizeConfig(b)
  return JSON.stringify(normA) === JSON.stringify(normB)
}

export function AdvancedSettingsForm({
  onSaveComplete,
  onError,
  idPrefix = "",
}: AdvancedSettingsFormProps) {
  const { t } = useI18n()
  const [config, setConfig] = useState<FinanzeConfig>({})
  const [initialConfig, setInitialConfig] = useState<FinanzeConfig>({})
  const [hasStoredConfig, setHasStoredConfig] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [showOther, setShowOther] = useState(false)
  const [isProbing, setIsProbing] = useState(false)
  const [probeState, setProbeState] = useState<
    "idle" | "success" | "warning" | "error"
  >("idle")
  const [probeMessage, setProbeMessage] = useState<string | null>(null)
  const [serverUrlInvalid, setServerUrlInvalid] = useState(false)
  const isElectron = Boolean(window.ipcAPI)

  const loadConfig = useCallback(async () => {
    try {
      setIsLoading(true)

      const currentConfig = getConfig()
      setHasStoredConfig(hasConfig())

      let status = null
      try {
        const statusPromise = checkStatus()
        const timeoutPromise = new Promise<null>((_, reject) =>
          setTimeout(() => reject(new Error("Timeout")), 2500),
        )
        status = await Promise.race([statusPromise, timeoutPromise])
      } catch (error) {
        console.error("Failed to fetch backend status:", error)
      }

      const backendOptions: BackendStartOptions | undefined =
        status?.server?.options
      const userBackend = currentConfig.backend

      const mergedBackend =
        backendOptions || userBackend
          ? {
              dataDir: userBackend?.dataDir || backendOptions?.dataDir,
              logDir: userBackend?.logDir || backendOptions?.logDir,
              logLevel: userBackend?.logLevel ?? backendOptions?.logLevel,
              logFileLevel:
                userBackend?.logFileLevel ?? backendOptions?.logFileLevel,
              thirdPartyLogLevel:
                userBackend?.thirdPartyLogLevel ??
                backendOptions?.thirdPartyLogLevel,
              port: userBackend?.port ?? backendOptions?.port,
            }
          : undefined

      const loadedConfig = {
        ...currentConfig,
        backend: mergedBackend,
      }

      setConfig(loadedConfig)
      setInitialConfig(loadedConfig)
    } catch (error) {
      console.error("Failed to load config:", error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  useEffect(() => {
    setProbeState("idle")
    setProbeMessage(null)
    setServerUrlInvalid(!isServerUrlFormatValid(config.serverUrl || ""))
  }, [config.serverUrl])

  const hasChanges = useMemo(() => {
    return !areConfigsEqual(config, initialConfig)
  }, [config, initialConfig])

  const handleSave = async () => {
    try {
      setIsSaving(true)
      if (!isServerUrlFormatValid(config.serverUrl || "")) {
        setServerUrlInvalid(true)
        return
      }

      const configToSave: FinanzeConfig = {}

      const trimmedServerUrl = config.serverUrl?.trim()
      if (trimmedServerUrl) {
        configToSave.serverUrl = trimmedServerUrl
      }

      if (config.backend) {
        const backendConfig: BackendStartOptions = {}
        if (config.backend.dataDir)
          backendConfig.dataDir = config.backend.dataDir
        if (config.backend.logDir) backendConfig.logDir = config.backend.logDir
        if (config.backend.logLevel && config.backend.logLevel !== "INFO") {
          backendConfig.logLevel = config.backend.logLevel
        }
        if (config.backend.logFileLevel) {
          backendConfig.logFileLevel = config.backend.logFileLevel
        }
        if (
          config.backend.thirdPartyLogLevel &&
          config.backend.thirdPartyLogLevel !== "WARNING"
        ) {
          backendConfig.thirdPartyLogLevel = config.backend.thirdPartyLogLevel
        }
        if (config.backend.port) backendConfig.port = config.backend.port

        if (Object.keys(backendConfig).length > 0) {
          configToSave.backend = backendConfig
        }
      }

      saveConfig(configToSave)

      if (isElectron) {
        if (configToSave.serverUrl) {
          await window.ipcAPI!.stopBackend()
        } else {
          await window.ipcAPI!.restartBackend()
        }
      }

      await refreshApiBaseUrl()
      onSaveComplete?.()
      if (typeof window !== "undefined") {
        window.location.reload()
      }
    } catch (error) {
      console.error("Failed to save config:", error)
      onError?.(error as Error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = async () => {
    try {
      setIsResetting(true)
      resetConfig()
      if (isElectron) {
        await window.ipcAPI!.restartBackend()
      }
      await refreshApiBaseUrl()
      onSaveComplete?.()
      if (typeof window !== "undefined") {
        window.location.reload()
      }
    } catch (error) {
      console.error("Failed to reset config:", error)
      onError?.(error as Error)
    } finally {
      setIsResetting(false)
      setShowResetConfirm(false)
    }
  }

  const updateBackendConfig = (key: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      backend: {
        ...(prev.backend ?? {}),
        [key]: value,
      },
    }))
  }

  const handlePickDirectory = async (key: "dataDir" | "logDir") => {
    if (window.ipcAPI?.selectDirectory) {
      const selected = await window.ipcAPI.selectDirectory(
        config.backend?.[key] || "",
      )
      if (selected) updateBackendConfig(key, selected)
    }
  }

  const handleProbeServer = async () => {
    const url = (config.serverUrl ?? "").trim()
    if (!url) {
      setProbeState("error")
      setProbeMessage(t.advancedSettings.probeMissingUrl)
      return
    }

    if (!isServerUrlFormatValid(url)) {
      setServerUrlInvalid(true)
      return
    }

    setIsProbing(true)
    setProbeState("idle")
    setProbeMessage(null)

    try {
      const statusResponse = await checkStatus({ baseUrlOverride: url })
      const remoteVersion = statusResponse.server?.version
      const localVersion = __APP_VERSION__

      if (remoteVersion && remoteVersion !== localVersion) {
        setProbeState("warning")
        setProbeMessage(
          `${t.advancedSettings.probeSuccessVersionMismatch} (${t.advancedSettings.localVersion}: ${localVersion}, ${t.advancedSettings.remoteVersion}: ${remoteVersion})`,
        )
      } else {
        setProbeState("success")
        setProbeMessage(t.advancedSettings.probeSuccess)
      }
    } catch (error) {
      console.error("Failed to probe server:", error)
      setProbeState("error")
      setProbeMessage(t.advancedSettings.probeError)
    } finally {
      setIsProbing(false)
    }
  }

  const usingRemoteServer = Boolean(config.serverUrl?.trim())
  const logFileLevelValue =
    config.backend?.logFileLevel ?? LOG_FILE_LEVEL_INHERIT

  const id = (suffix: string) => (idPrefix ? `${idPrefix}-${suffix}` : suffix)

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Server URL Section */}
      <div className="space-y-2">
        <Label htmlFor={id("serverUrl")} className="font-semibold">
          {t.advancedSettings.serverUrl}
        </Label>
        <div className="flex gap-2">
          <Input
            id={id("serverUrl")}
            value={config.serverUrl || ""}
            onChange={e => {
              const newValue = e.target.value
              setConfig(prev => ({
                ...prev,
                serverUrl: newValue,
              }))
              setServerUrlInvalid(!isServerUrlFormatValid(newValue))
            }}
            placeholder={t.advancedSettings.serverUrlPlaceholder}
          />
          <Button
            type="button"
            variant="outline"
            onClick={handleProbeServer}
            disabled={isProbing}
            aria-label={t.advancedSettings.probeButton}
          >
            {isProbing && <RotateCcw className="mr-2 h-4 w-4 animate-spin" />}
            {t.advancedSettings.probeButton}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {t.advancedSettings.serverUrlDesc}
        </p>
        {serverUrlInvalid && (
          <p className="text-xs text-red-500 dark:text-red-400">
            {t.advancedSettings.serverUrlInvalid}
          </p>
        )}
        {probeMessage && (
          <div
            className={`flex items-center gap-2 text-xs ${
              probeState === "success"
                ? "text-emerald-500 dark:text-emerald-400"
                : probeState === "warning"
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-red-500 dark:text-red-400"
            }`}
          >
            {probeState === "success" && (
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
            )}
            {probeState === "warning" && (
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            )}
            {probeState === "error" && (
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
            )}
            <p>{probeMessage}</p>
          </div>
        )}
      </div>

      {/* Backend Section */}
      <div className="space-y-4 pt-2">
        {usingRemoteServer && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            {t.advancedSettings.remoteServerNotice}
          </p>
        )}

        {/* Data Directory */}
        <div className="space-y-2">
          <Label htmlFor={id("dataDir")} className="font-semibold">
            {t.advancedSettings.dataDir}
          </Label>
          <div
            className={`flex gap-2 ${usingRemoteServer ? "opacity-50 pointer-events-none" : ""}`}
          >
            <button
              type="button"
              onClick={() => handlePickDirectory("dataDir")}
              disabled={usingRemoteServer}
              className="flex h-10 w-full items-center rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-accent hover:text-accent-foreground cursor-pointer text-left"
            >
              <FolderOpen className="mr-2 h-4 w-4 flex-shrink-0 text-muted-foreground" />
              <span
                className={
                  config.backend?.dataDir
                    ? "truncate"
                    : "text-muted-foreground truncate"
                }
              >
                {config.backend?.dataDir ||
                  t.advancedSettings.dataDirPlaceholder}
              </span>
            </button>
          </div>
        </div>

        {/* Log Directory */}
        <div className="space-y-2">
          <Label htmlFor={id("logDir")} className="font-semibold">
            {t.advancedSettings.logDir}
          </Label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handlePickDirectory("logDir")}
              className="flex h-10 w-full items-center rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-accent hover:text-accent-foreground cursor-pointer text-left"
            >
              <FolderOpen className="mr-2 h-4 w-4 flex-shrink-0 text-muted-foreground" />
              <span
                className={
                  config.backend?.logDir
                    ? "truncate"
                    : "text-muted-foreground truncate"
                }
              >
                {config.backend?.logDir || t.advancedSettings.logDirPlaceholder}
              </span>
            </button>
          </div>
        </div>

        {/* Log Levels */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor={id("logLevel")} className="font-semibold">
              {t.advancedSettings.logLevel}
            </Label>
            <select
              id={id("logLevel")}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={config.backend?.logLevel || "INFO"}
              onChange={e => updateBackendConfig("logLevel", e.target.value)}
            >
              {LOG_LEVELS.map(level => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={id("logFileLevel")} className="font-semibold">
              {t.advancedSettings.logFileLevel}
            </Label>
            <select
              id={id("logFileLevel")}
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={logFileLevelValue}
              onChange={e => {
                const value = e.target.value
                updateBackendConfig(
                  "logFileLevel",
                  value === LOG_FILE_LEVEL_INHERIT ? undefined : value,
                )
              }}
            >
              <option value={LOG_FILE_LEVEL_INHERIT}>
                {t.advancedSettings.inheritLogLevel}
              </option>
              {LOG_LEVELS.map(level => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Collapsible Other Section */}
        <div className="border-t pt-2 mt-2">
          <button
            type="button"
            className="flex items-center gap-2 text-sm font-semibold text-muted-foreground focus:outline-none"
            onClick={() => setShowOther(v => !v)}
            aria-expanded={showOther}
          >
            {t.advancedSettings.otherSection}
            {showOther ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          {showOther && (
            <div className="space-y-2 pt-2">
              <Label
                htmlFor={id("thirdPartyLogLevel")}
                className="font-semibold"
              >
                {t.advancedSettings.thirdPartyLogLevel}
              </Label>
              <select
                id={id("thirdPartyLogLevel")}
                className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={config.backend?.thirdPartyLogLevel}
                onChange={e =>
                  updateBackendConfig("thirdPartyLogLevel", e.target.value)
                }
                disabled={usingRemoteServer}
              >
                {LOG_LEVELS.map(level => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex justify-between pt-2">
        <Button
          variant="outline"
          onClick={() => setShowResetConfirm(true)}
          disabled={isSaving || isLoading || isResetting || !hasStoredConfig}
        >
          {t.advancedSettings.resetToDefaults}
        </Button>
        <Button
          onClick={handleSave}
          disabled={isSaving || isLoading || serverUrlInvalid || !hasChanges}
        >
          {isSaving && <RotateCcw className="mr-2 h-4 w-4 animate-spin" />}
          {t.common.save}
        </Button>
      </div>

      <ConfirmationDialog
        isOpen={showResetConfirm}
        title={t.advancedSettings.resetConfirmTitle}
        message={t.advancedSettings.resetConfirmMessage}
        warning={t.advancedSettings.resetConfirmWarning}
        confirmText={t.advancedSettings.resetToDefaults}
        cancelText={t.common.cancel}
        onConfirm={handleReset}
        onCancel={() => setShowResetConfirm(false)}
        isLoading={isResetting}
      />
    </div>
  )
}
