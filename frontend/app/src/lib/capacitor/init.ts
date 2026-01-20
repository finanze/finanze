import { Capacitor } from "@capacitor/core"
import { CapacitorSQLite, SQLiteConnection } from "@capacitor-community/sqlite"
import { PlatformInfo, PlatformType } from "@/types"
import "./plugins"

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
