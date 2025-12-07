import { useCallback, useEffect, useState } from "react"
import type {
  AutoUpdateActionResult,
  AutoUpdateCheckResult,
  AutoUpdateErrorInfo,
  AutoUpdateInfo,
  AutoUpdateProgressInfo,
} from "@/types/release"

export interface AutoUpdaterState {
  isSupported: boolean
  isChecking: boolean
  isDownloading: boolean
  isDownloaded: boolean
  progress: number | null
  bytesPerSecond: number | null
  downloadedBytes: number | null
  totalBytes: number | null
  updateInfo: AutoUpdateInfo | null
  error: AutoUpdateErrorInfo | null
}

export interface UseAutoUpdaterOptions {
  checkOnMount?: boolean
}

const initialState: AutoUpdaterState = {
  isSupported: false,
  isChecking: false,
  isDownloading: false,
  isDownloaded: false,
  progress: null,
  bytesPerSecond: null,
  downloadedBytes: null,
  totalBytes: null,
  updateInfo: null,
  error: null,
}

function pickError(info?: AutoUpdateErrorInfo | null) {
  return info ?? null
}

function detectSupport() {
  return (
    typeof window !== "undefined" && Boolean(window.ipcAPI?.checkForUpdates)
  )
}

export function useAutoUpdater(options: UseAutoUpdaterOptions = {}): {
  state: AutoUpdaterState
  checkForUpdates: () => Promise<AutoUpdateCheckResult | { supported: false }>
  downloadUpdate: () => Promise<AutoUpdateActionResult | { supported: false }>
  quitAndInstall: () => Promise<AutoUpdateActionResult | { supported: false }>
} {
  const { checkOnMount = false } = options

  const [state, setState] = useState<AutoUpdaterState>(() => ({
    ...initialState,
    isSupported: detectSupport(),
  }))

  const isSupported = state.isSupported

  useEffect(() => {
    const nextSupport = detectSupport()
    setState(prev =>
      prev.isSupported === nextSupport
        ? prev
        : { ...prev, isSupported: nextSupport },
    )
  }, [])

  useEffect(() => {
    if (!isSupported) {
      return
    }

    const ipcAPI = typeof window === "undefined" ? undefined : window.ipcAPI

    if (!ipcAPI) {
      return
    }

    const listeners: Array<() => void> = []

    if (ipcAPI.onCheckingForUpdate) {
      listeners.push(
        ipcAPI.onCheckingForUpdate(() => {
          setState(prev => ({
            ...prev,
            isChecking: true,
            error: null,
          }))
        }),
      )
    }

    if (ipcAPI.onUpdateAvailable) {
      listeners.push(
        ipcAPI.onUpdateAvailable((info: AutoUpdateInfo) => {
          setState(prev => ({
            ...prev,
            isChecking: false,
            updateInfo: info,
            isDownloaded: false,
          }))
        }),
      )
    }

    if (ipcAPI.onUpdateNotAvailable) {
      listeners.push(
        ipcAPI.onUpdateNotAvailable(() => {
          setState(prev => ({
            ...prev,
            isChecking: false,
            updateInfo: null,
          }))
        }),
      )
    }

    if (ipcAPI.onDownloadProgress) {
      listeners.push(
        ipcAPI.onDownloadProgress((progress: AutoUpdateProgressInfo) => {
          setState(prev => ({
            ...prev,
            isDownloading: true,
            progress: progress.percent,
            bytesPerSecond: progress.bytesPerSecond,
            downloadedBytes: progress.transferred,
            totalBytes: progress.total,
          }))
        }),
      )
    }

    if (ipcAPI.onUpdateDownloaded) {
      listeners.push(
        ipcAPI.onUpdateDownloaded((info: AutoUpdateInfo) => {
          setState(prev => ({
            ...prev,
            isDownloading: false,
            isChecking: false,
            isDownloaded: true,
            progress: 100,
            updateInfo: info,
          }))
        }),
      )
    }

    if (ipcAPI.onUpdateError) {
      listeners.push(
        ipcAPI.onUpdateError((error: AutoUpdateErrorInfo) => {
          setState(prev => ({
            ...prev,
            isChecking: false,
            isDownloading: false,
            error: pickError(error),
          }))
        }),
      )
    }

    return () => {
      listeners.forEach(dispose => {
        try {
          dispose?.()
        } catch (error) {
          console.error("Failed to dispose auto-update listener", error)
        }
      })
    }
  }, [isSupported])

  const checkForUpdates = useCallback(async () => {
    const ipcAPI = typeof window === "undefined" ? undefined : window.ipcAPI

    if (!isSupported || !ipcAPI?.checkForUpdates) {
      return { supported: false as const }
    }

    setState(prev => ({
      ...prev,
      isChecking: true,
      error: null,
    }))

    try {
      const result = await ipcAPI.checkForUpdates()
      const hasUpdateInfo = Object.prototype.hasOwnProperty.call(
        result,
        "updateInfo",
      )

      setState(prev => ({
        ...prev,
        isChecking: false,
        isSupported: result.supported,
        updateInfo: hasUpdateInfo
          ? (result.updateInfo ?? null)
          : prev.updateInfo,
        error: pickError(result.error),
      }))

      return result
    } catch (error) {
      const fallbackError: AutoUpdateErrorInfo = {
        message: error instanceof Error ? error.message : "Unknown error",
        stack: error instanceof Error ? (error.stack ?? null) : null,
        name: error instanceof Error ? error.name : "Error",
      }

      setState(prev => ({
        ...prev,
        isChecking: false,
        error: fallbackError,
      }))

      return { supported: true as const, error: fallbackError }
    }
  }, [isSupported])

  const downloadUpdate = useCallback(async () => {
    const ipcAPI = typeof window === "undefined" ? undefined : window.ipcAPI

    if (!isSupported || !ipcAPI?.downloadUpdate) {
      return { supported: false as const }
    }

    setState(prev => ({
      ...prev,
      isDownloading: true,
      error: null,
    }))

    try {
      const result = await ipcAPI.downloadUpdate()

      if (result.error) {
        setState(prev => ({
          ...prev,
          isDownloading: false,
          error: pickError(result.error),
        }))
      }

      return result
    } catch (error) {
      const fallbackError: AutoUpdateErrorInfo = {
        message: error instanceof Error ? error.message : "Unknown error",
        stack: error instanceof Error ? (error.stack ?? null) : null,
        name: error instanceof Error ? error.name : "Error",
      }

      setState(prev => ({
        ...prev,
        isDownloading: false,
        error: fallbackError,
      }))

      return { supported: true as const, error: fallbackError }
    }
  }, [isSupported])

  const quitAndInstall = useCallback(async () => {
    const ipcAPI = typeof window === "undefined" ? undefined : window.ipcAPI

    if (!isSupported || !ipcAPI?.quitAndInstall) {
      return { supported: false as const }
    }

    try {
      return await ipcAPI.quitAndInstall()
    } catch (error) {
      const fallbackError: AutoUpdateErrorInfo = {
        message: error instanceof Error ? error.message : "Unknown error",
        stack: error instanceof Error ? (error.stack ?? null) : null,
        name: error instanceof Error ? error.name : "Error",
      }

      setState(prev => ({
        ...prev,
        error: fallbackError,
      }))

      return { supported: true as const, error: fallbackError }
    }
  }, [isSupported])

  useEffect(() => {
    if (checkOnMount && isSupported) {
      void checkForUpdates()
    }
  }, [checkOnMount, isSupported, checkForUpdates])

  return {
    state,
    checkForUpdates,
    downloadUpdate,
    quitAndInstall,
  }
}
