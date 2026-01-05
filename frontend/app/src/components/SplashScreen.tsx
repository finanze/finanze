import { useState, useEffect } from "react"
import { useI18n } from "@/i18n"
import { LoginQuickSettings } from "@/components/ui/ThemeSelector"
import { AdvancedSettings } from "@/components/ui/AdvancedSettings"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useTheme } from "@/context/ThemeContext"
import { getApiServerInfo, type ApiServerInfo } from "@/services/api"
import { hasConfig } from "@/services/configStorage"
import { isElectron, isNativeMobile } from "@/lib/platform"

const getServerDisplayName = (url: string): string => {
  return url.replace(/^https?:\/\//, "")
}

export default function SplashScreen() {
  const { t } = useI18n()
  const { theme } = useTheme()
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)
  const [serverInfo, setServerInfo] = useState<ApiServerInfo | null>(null)
  const [hasStoredConfig, setHasStoredConfig] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }

    setHasStoredConfig(hasConfig())
    getApiServerInfo().then(setServerInfo)
  }, [])

  const isLight =
    theme === "light" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      !window.matchMedia("(prefers-color-scheme: dark)").matches)
  const gradientClass = isLight
    ? "from-gray-400 via-gray-700 to-gray-300"
    : "from-gray-800 via-white to-gray-700"
  const isMobile = isNativeMobile()
  const iconSize = 75

  const getStatusMessage = () => {
    if (!serverInfo) {
      return t.common.connectingToServer
    }
    if (serverInfo.isCustomServer && serverInfo.serverDisplay) {
      return `${t.common.connectingToServer} ${getServerDisplayName(serverInfo.serverDisplay)}`
    }
    return t.common.startingServer
  }

  return (
    <div
      className={
        isMobile
          ? `select-none min-h-screen flex flex-col items-center justify-center ${
              isLight ? "bg-white" : "bg-black"
            }`
          : "select-none min-h-screen flex flex-col items-center justify-center bg-gradient-50 dark:bg-black p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gradient-100 to-gradient-300 dark:from-gradient-900 dark:to-black"
      }
    >
      <img
        src="finanze-fg.svg"
        alt="Finanze Logo"
        className={
          isMobile
            ? `animate-breathing select-none pointer-events-none ${
                isLight ? "invert" : ""
              }`
            : "w-64 h-64 animate-breathing drop-shadow invert dark:invert-0 select-none pointer-events-none"
        }
        style={isMobile ? { width: iconSize, height: iconSize } : undefined}
        draggable={false}
      />
      {!isMobile && (
        <div className="absolute bottom-20 flex flex-col items-center gap-3">
          <p
            className={`text-lg font-bold bg-gradient-to-r ${gradientClass} bg-[length:200%_auto] animate-text-shine bg-clip-text text-transparent`}
          >
            {getStatusMessage()}
          </p>
        </div>
      )}
      {isMobile && (
        <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2">
          <LoadingSpinner
            size="md"
            className={isLight ? "text-black" : "text-white"}
          />
        </div>
      )}
      <div className="absolute bottom-6 left-6">
        <LoginQuickSettings
          isDesktop={isElectron()}
          onOpenAdvancedSettings={() => setShowAdvancedSettings(true)}
          advancedSettingsDisabled={!hasStoredConfig}
        />
      </div>
      <AdvancedSettings
        isOpen={showAdvancedSettings}
        onClose={() => setShowAdvancedSettings(false)}
      />
    </div>
  )
}
