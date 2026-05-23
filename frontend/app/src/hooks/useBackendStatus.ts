import { useState, useEffect, useCallback } from "react"
import type { BackendStatus } from "@/types"
import { isElectron } from "@/lib/platform"
import { getConfig } from "@/services/configStorage"

export function useBackendStatus() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus | null>(null)

  useEffect(() => {
    if (!isElectron()) return

    window.ipcAPI?.getBackendStatus().then(setBackendStatus)

    const unsubscribe = window.ipcAPI?.onBackendStatusChange(setBackendStatus)
    return () => unsubscribe?.()
  }, [])

  const retryBackend = useCallback(async () => {
    if (!isElectron() || !window.ipcAPI) return
    const config = getConfig()
    await window.ipcAPI.startBackend(config.backend)
  }, [])

  return { backendStatus, retryBackend }
}
