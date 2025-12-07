import type { BrowserWindow } from "electron"
import type { FinanzeConfig } from "../types"

const CONFIG_STORAGE_KEY = "backendConfig"

let mainWindowRef: BrowserWindow | null = null

export function setMainWindow(window: BrowserWindow | null): void {
  mainWindowRef = window
}

export async function readRendererConfig(): Promise<FinanzeConfig> {
  if (!mainWindowRef || mainWindowRef.isDestroyed()) {
    return {}
  }
  try {
    const result = await mainWindowRef.webContents.executeJavaScript(
      `localStorage.getItem('${CONFIG_STORAGE_KEY}')`,
    )
    if (result) {
      return JSON.parse(result)
    }
  } catch (error) {
    console.error("Failed to read config from renderer:", error)
  }
  return {}
}
