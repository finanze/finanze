import { useEffect, useState } from "react"
import {
  getFeatureFlags,
  subscribeFeatureFlags,
} from "@/context/featureFlagsStore"
import {
  isDeviceInRestrictedRegion,
  isRegionCheckEnabled,
} from "@/lib/regionRestriction"

// null while the device check is still resolving.
export function useRegionRestriction(): boolean | null {
  const [flags, setFlags] = useState(getFeatureFlags)
  const [restricted, setRestricted] = useState<boolean | null>(null)
  const enabled = isRegionCheckEnabled(flags)

  useEffect(() => subscribeFeatureFlags(setFlags), [])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    setRestricted(null)
    isDeviceInRestrictedRegion(getFeatureFlags()).then(result => {
      if (!cancelled) setRestricted(result)
    })
    return () => {
      cancelled = true
    }
  }, [enabled])

  return enabled ? restricted : false
}
