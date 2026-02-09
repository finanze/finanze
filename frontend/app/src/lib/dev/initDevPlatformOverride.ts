import { PlatformType } from "@/types"

export function initDevPlatformOverride() {
  if (!import.meta.env.DEV) {
    return
  }

  const forcedPlatform = import.meta.env.VITE_FORCE_PLATFORM as
    | string
    | undefined

  if (!forcedPlatform) {
    return
  }

  const normalized = forcedPlatform.toUpperCase()
  const platformType = Object.values(PlatformType).find(
    type => type.toUpperCase() === normalized,
  )

  if (platformType) {
    window.platform = { type: platformType }
    console.log(`[Dev] Forcing platform: ${platformType}`)
  } else {
    console.warn(`[Dev] Unknown VITE_FORCE_PLATFORM value: ${forcedPlatform}`)
  }
}
