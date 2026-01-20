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

  switch (normalized) {
    case "ANDROID":
      window.platform = { type: PlatformType.ANDROID }
      console.log("[Dev] Forcing platform: ANDROID")
      break
    case "IOS":
      window.platform = { type: PlatformType.IOS }
      console.log("[Dev] Forcing platform: IOS")
      break
    default:
      console.warn(`[Dev] Unknown VITE_FORCE_PLATFORM value: ${forcedPlatform}`)
  }
}
