import { useState, useEffect, useRef } from "react"
import { useI18n } from "@/i18n"
import { LoginQuickSettings } from "@/components/ui/ThemeSelector"
import { AdvancedSettings } from "@/components/ui/AdvancedSettings"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useTheme } from "@/context/ThemeContext"
import { getApiServerInfo, type ApiServerInfo } from "@/services/api"
import { hasConfig } from "@/services/configStorage"
import { isElectron, isNativeMobile } from "@/lib/platform"
import { StatusBar, Style } from "@capacitor/status-bar"
import { useBackendStatus } from "@/hooks/useBackendStatus"
import { Copy, Check } from "lucide-react"
import { copyToClipboard } from "@/lib/clipboard"

const getServerDisplayName = (url: string): string => {
  return url.replace(/^https?:\/\//, "")
}

export default function SplashScreen() {
  const { t } = useI18n()
  const { theme } = useTheme()
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)
  const [serverInfo, setServerInfo] = useState<ApiServerInfo | null>(null)
  const [hasStoredConfig, setHasStoredConfig] = useState(false)
  const { backendStatus } = useBackendStatus()
  const [showDetails, setShowDetails] = useState(false)
  const [copied, setCopied] = useState(false)
  const detailsRef = useRef<HTMLDivElement>(null)

  const backendFailed =
    isElectron() &&
    backendStatus?.state === "error" &&
    !serverInfo?.isCustomServer

  useEffect(() => {
    if (!showDetails) return
    const handleClickOutside = (e: MouseEvent) => {
      if (
        detailsRef.current &&
        !detailsRef.current.contains(e.target as Node)
      ) {
        setShowDetails(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [showDetails])

  const handleCopyOutput = async () => {
    const text = backendStatus?.output || backendStatus?.error?.message || ""
    const ok = await copyToClipboard(text)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

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

  useEffect(() => {
    if (!isNativeMobile()) return
    StatusBar.setStyle({ style: isLight ? Style.Light : Style.Dark })
  }, [isLight])
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
            : `w-64 h-64 ${backendFailed ? "" : "animate-breathing"} drop-shadow invert dark:invert-0 select-none pointer-events-none`
        }
        style={isMobile ? { width: iconSize, height: iconSize } : undefined}
        draggable={false}
      />
      {!isMobile && !backendFailed && (
        <div className="absolute bottom-20 flex flex-col items-center gap-3">
          <p
            className={`text-lg font-bold bg-gradient-to-r ${gradientClass} bg-[length:200%_auto] animate-text-shine bg-clip-text text-transparent`}
          >
            {getStatusMessage()}
          </p>
        </div>
      )}
      {!isMobile && backendFailed && (
        <div className="absolute bottom-16 flex flex-col items-center gap-4 max-w-lg px-4">
          <p className="text-lg font-semibold text-red-400">
            {t.common.backendFailedToStart}
          </p>
          <button
            onClick={() => {
              setCopied(false)
              setShowDetails(v => !v)
            }}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm text-gray-400 hover:text-gray-200 border border-white/10 hover:border-white/20 bg-white/5 hover:bg-white/10 backdrop-blur-sm transition-all"
          >
            {t.common.details}
          </button>
          {showDetails && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-8"
              onMouseDown={e => {
                if (e.target === e.currentTarget) setShowDetails(false)
              }}
            >
              <div
                ref={detailsRef}
                className="w-full max-w-2xl max-h-[70vh] flex flex-col rounded-xl bg-gray-900 border border-white/10 shadow-2xl overflow-hidden"
              >
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                  <span className="text-sm font-medium text-gray-300">
                    {t.common.details}
                  </span>
                  <button
                    onClick={handleCopyOutput}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-gray-400 hover:text-gray-200 hover:bg-white/10 transition-colors"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-green-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="flex-1 overflow-auto p-4 text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                  {backendStatus?.output || backendStatus?.error?.message || ""}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
      {isMobile && !window.platform?.unsupportedWebView && (
        <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2">
          <LoadingSpinner
            size="md"
            className={isLight ? "text-black" : "text-white"}
          />
        </div>
      )}
      {isMobile && window.platform?.unsupportedWebView && (
        <div className="absolute bottom-1/4 left-1/2 -translate-x-1/2 flex flex-col items-center gap-4 w-72 text-center">
          <p className={`text-sm ${isLight ? "text-black" : "text-white"}`}>
            {t.common.unsupportedWebView}
          </p>
          <button
            onClick={() =>
              window.open(
                "market://details?id=com.google.android.webview",
                "_system",
              )
            }
            className={`px-4 py-2 rounded-lg text-sm font-medium ${
              isLight ? "bg-black text-white" : "bg-white text-black"
            }`}
          >
            {t.common.updateWebView}
          </button>
        </div>
      )}
      <div
        className="absolute left-6"
        style={{
          bottom:
            "calc(24px + max(calc(var(--safe-area-inset-bottom, 0px) - 24px), 0px))",
        }}
      >
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
