import { Capacitor } from "@capacitor/core"
import { SplashScreen } from "@capacitor/splash-screen"
import { PlatformInfo, PlatformType } from "@/types"
import "./plugins"

function setupGlobalErrorHandlers(): void {
  window.addEventListener("error", event => {
    const err: any = (event as any).error
    if (err?.stack) {
      console.error("Global error:", err.stack)
    } else {
      console.error("Global error:", event.message)
    }
  })

  window.addEventListener("unhandledrejection", event => {
    const reason: any = (event as any).reason
    if (reason?.stack) {
      console.error("Unhandled rejection:", reason.stack)
    } else {
      console.error("Unhandled rejection:", reason)
    }
  })
}

export async function initializeCapacitorPlatform(): Promise<void> {
  setupGlobalErrorHandlers()

  if (!Capacitor.isNativePlatform()) {
    return
  }

  const platform = Capacitor.getPlatform()

  let platformType: PlatformType
  switch (platform) {
    case "ios":
      platformType = PlatformType.IOS
      break
    case "android":
      platformType = PlatformType.ANDROID
      break
    default:
      platformType = PlatformType.WEB
  }

  const info: PlatformInfo = {
    type: platformType,
    osVersion: undefined,
  }

  window.platform = info
}

export function isCapacitorNative(): boolean {
  return Capacitor.isNativePlatform()
}

export function hideSplashScreen() {
  if (!isCapacitorNative()) return

  SplashScreen.hide()
}
