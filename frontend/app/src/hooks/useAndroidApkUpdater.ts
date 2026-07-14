import { useCallback, useRef, useState } from "react"
import type { PluginListenerHandle } from "@capacitor/core"
import {
  apkAddProgressListener,
  apkCanInstall,
  apkDownload,
  apkInstall,
  apkOpenInstallSettings,
} from "@/lib/capacitor/apkUpdater"
import { isAndroid } from "@/lib/platform"

export interface AndroidApkUpdaterState {
  isSupported: boolean
  isDownloading: boolean
  isDownloaded: boolean
  needsPermission: boolean
  progress: number | null
  downloadedBytes: number | null
  totalBytes: number | null
  error: string | null
}

const initialState: AndroidApkUpdaterState = {
  isSupported: false,
  isDownloading: false,
  isDownloaded: false,
  needsPermission: false,
  progress: null,
  downloadedBytes: null,
  totalBytes: null,
  error: null,
}

function detectSupport(): boolean {
  return isAndroid() && __CONNECTIONS__
}

export function useAndroidApkUpdater(): {
  state: AndroidApkUpdaterState
  download: (
    url: string,
    fileName: string,
    expectedSize?: number,
  ) => Promise<void>
  install: () => Promise<void>
} {
  const [state, setState] = useState<AndroidApkUpdaterState>(() => ({
    ...initialState,
    isSupported: detectSupport(),
  }))

  const downloadedPathRef = useRef<string | null>(null)

  const download = useCallback(
    async (url: string, fileName: string, expectedSize?: number) => {
      if (!detectSupport()) return

      setState(prev => ({
        ...prev,
        isDownloading: true,
        isDownloaded: false,
        needsPermission: false,
        progress: 0,
        downloadedBytes: 0,
        totalBytes: null,
        error: null,
      }))

      let listener: PluginListenerHandle | null = null

      try {
        listener = await apkAddProgressListener(progress => {
          const percent =
            progress.total > 0
              ? Math.min(100, (progress.downloaded / progress.total) * 100)
              : 0
          setState(prev => ({
            ...prev,
            progress: percent,
            downloadedBytes: progress.downloaded,
            totalBytes: progress.total > 0 ? progress.total : null,
          }))
        })

        const result = await apkDownload(url, fileName, expectedSize)
        if (!result) {
          throw new Error("Download failed")
        }
        downloadedPathRef.current = result.path

        setState(prev => ({
          ...prev,
          isDownloading: false,
          isDownloaded: true,
          progress: 100,
        }))
      } catch (error) {
        setState(prev => ({
          ...prev,
          isDownloading: false,
          isDownloaded: false,
          error: error instanceof Error ? error.message : "Download failed",
        }))
      } finally {
        await listener?.remove()
      }
    },
    [],
  )

  const install = useCallback(async () => {
    if (!detectSupport()) return

    const path = downloadedPathRef.current
    if (!path) return

    try {
      const granted = await apkCanInstall()
      if (!granted) {
        setState(prev => ({ ...prev, needsPermission: true }))
        await apkOpenInstallSettings()
        return
      }

      setState(prev => ({ ...prev, needsPermission: false }))
      await apkInstall(path)
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : "Install failed",
      }))
    }
  }, [])

  return { state, download, install }
}
