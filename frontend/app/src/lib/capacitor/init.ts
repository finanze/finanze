import { Capacitor } from "@capacitor/core"
import { CapacitorSQLite, SQLiteConnection } from "@capacitor-community/sqlite"
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

async function initSqliteWebDev(platform: PlatformType): Promise<void> {
  if (!import.meta.env.DEV) return
  if (platform !== PlatformType.WEB) return

  const { defineCustomElements: defineJeepSqliteCustomElements } =
    await import("jeep-sqlite/loader")

  defineJeepSqliteCustomElements(window)

  if (!document.querySelector("jeep-sqlite")) {
    const jeepEl = document.createElement("jeep-sqlite")
    document.body.appendChild(jeepEl)
  }

  const sqlite = new SQLiteConnection(CapacitorSQLite)
  await sqlite.initWebStore()
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

  await initSqliteWebDev(platformType)
}

export function isCapacitorNative(): boolean {
  return Capacitor.isNativePlatform()
}
