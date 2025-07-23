import { useState, useEffect, useCallback, useRef } from "react"
import { checkForUpdates, ReleaseUpdateInfo } from "@/utils/releaseUtils"

export interface ReleaseUpdateState {
  isChecking: boolean
  updateInfo: ReleaseUpdateInfo | null
  error: string | null
  lastChecked: Date | null
}

export interface UseReleaseUpdateOptions {
  checkOnMount?: boolean
  skipVersions?: string[]
  onUpdateAvailable?: (updateInfo: ReleaseUpdateInfo) => void
}

export function useReleaseUpdate(options: UseReleaseUpdateOptions = {}) {
  const { checkOnMount = true, skipVersions = [], onUpdateAvailable } = options

  const [state, setState] = useState<ReleaseUpdateState>({
    isChecking: false,
    updateInfo: null,
    error: null,
    lastChecked: null,
  })

  // Use refs to store the latest values without causing re-renders
  const skipVersionsRef = useRef(skipVersions)
  const onUpdateAvailableRef = useRef(onUpdateAvailable)

  // Update refs when values change
  useEffect(() => {
    skipVersionsRef.current = skipVersions
  }, [skipVersions])

  useEffect(() => {
    onUpdateAvailableRef.current = onUpdateAvailable
  }, [onUpdateAvailable])

  const checkForUpdatesInternal = useCallback(async () => {
    setState(prev => ({ ...prev, isChecking: true, error: null }))

    try {
      const updateInfo = await checkForUpdates()

      setState(prev => ({
        ...prev,
        isChecking: false,
        updateInfo,
        lastChecked: new Date(),
      }))

      // Check if we should notify about the update
      if (
        updateInfo.hasUpdate &&
        updateInfo.release &&
        !skipVersionsRef.current.includes(updateInfo.latestVersion) &&
        onUpdateAvailableRef.current
      ) {
        onUpdateAvailableRef.current(updateInfo)
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error"
      setState(prev => ({
        ...prev,
        isChecking: false,
        error: errorMessage,
        lastChecked: new Date(),
      }))
    }
  }, []) // No dependencies to prevent infinite loop

  useEffect(() => {
    if (checkOnMount) {
      checkForUpdatesInternal()
    }
  }, [checkOnMount, checkForUpdatesInternal])

  return {
    ...state,
    checkForUpdates: checkForUpdatesInternal,
  }
}
