import { useEffect, useState } from "react"
import {
  getFeatureFlags,
  subscribeFeatureFlags,
} from "@/context/featureFlagsStore"
import {
  isDeviceInRestrictedRegion,
  isRegionCheckEnabled,
} from "@/lib/regionRestriction"

export function useRegionRestriction(): boolean | null {
  const [flags, setFlags] = useState(getFeatureFlags)
  const enabled = isRegionCheckEnabled(flags)
  const [restricted, setRestricted] = useState<boolean | null>(
    enabled ? null : false,
  )

  useEffect(() => subscribeFeatureFlags(setFlags), [])

  useEffect(() => {
    if (!enabled) {
      setRestricted(false)
      return
    }
    let cancelled = false
    isDeviceInRestrictedRegion(getFeatureFlags()).then(result => {
      if (!cancelled) setRestricted(result)
    })
    return () => {
      cancelled = true
    }
  }, [enabled])

  return enabled ? restricted : false
}
