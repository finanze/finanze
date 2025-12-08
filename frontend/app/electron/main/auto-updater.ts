import { BrowserWindow, ipcMain } from "electron"
import ElectronUpdater, {
  type ProgressInfo,
  type UpdateInfo,
} from "electron-updater"
import { AppConfig, OS } from "../types"

const { autoUpdater } = ElectronUpdater

const AUTO_UPDATE_CHANNELS = {
  checking: "auto-update:checking",
  available: "auto-update:available",
  notAvailable: "auto-update:not-available",
  progress: "auto-update:download-progress",
  downloaded: "auto-update:downloaded",
  error: "auto-update:error",
} as const

let supportsNativeAutoUpdate = false
let autoUpdateChannel: string | undefined

function serializeError(error: unknown) {
  if (error instanceof Error) {
    return {
      message: error.message,
      stack: error.stack ?? null,
      name: error.name,
    }
  }

  return {
    message: typeof error === "string" ? error : "Unknown error",
    stack: null,
    name: "Error",
  }
}

function sendToAllWindows(channel: string, ...args: unknown[]) {
  BrowserWindow.getAllWindows().forEach(window => {
    if (!window.isDestroyed() && !window.webContents.isDestroyed()) {
      try {
        window.webContents.send(channel, ...args)
      } catch (error) {
        console.error(`Failed to send ${channel} to window ${window.id}`, error)
      }
    }
  })
}

export function setupAutoUpdater(appConfig: AppConfig): void {
  supportsNativeAutoUpdate = !appConfig.isDev && appConfig.os !== OS.MAC

  let defaultChannel = "latest"
  if (appConfig.os === OS.MAC && appConfig.arch !== "arm64") {
    defaultChannel = `latest-${process.arch}`
  }

  autoUpdateChannel = process.env.AUTO_UPDATE_CHANNEL || defaultChannel
  autoUpdater.channel = autoUpdateChannel

  const customFeedUrl = process.env.AUTO_UPDATE_FEED_URL
  if (customFeedUrl && supportsNativeAutoUpdate) {
    ElectronUpdater.autoUpdater.setFeedURL({
      provider: "generic",
      url: customFeedUrl,
    })
  }
}

export function initializeAutoUpdater(): void {
  if (!supportsNativeAutoUpdate) {
    return
  }

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false

  autoUpdater.on("checking-for-update", () => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.checking)
  })

  autoUpdater.on("update-available", (info: UpdateInfo) => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.available, info)
  })

  autoUpdater.on("update-not-available", (info: UpdateInfo) => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.notAvailable, info)
  })

  autoUpdater.on("download-progress", (progress: ProgressInfo) => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.progress, progress)
  })

  autoUpdater.on("update-downloaded", (info: UpdateInfo) => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.downloaded, info)
  })

  autoUpdater.on("error", (error: unknown) => {
    sendToAllWindows(AUTO_UPDATE_CHANNELS.error, serializeError(error))
  })
}

export function registerAutoUpdateHandlers(): void {
  ipcMain.handle("auto-update-check", async () => {
    if (!supportsNativeAutoUpdate) {
      return { supported: false }
    }

    try {
      const result = await autoUpdater.checkForUpdates()

      return {
        supported: true,
        updateInfo: result?.updateInfo ?? null,
      }
    } catch (error) {
      return {
        supported: true,
        error: serializeError(error),
      }
    }
  })

  ipcMain.handle("auto-update-download", async () => {
    if (!supportsNativeAutoUpdate) {
      return { supported: false }
    }

    try {
      await autoUpdater.downloadUpdate()
      return { supported: true }
    } catch (error) {
      return {
        supported: true,
        error: serializeError(error),
      }
    }
  })

  ipcMain.handle("auto-update-install", () => {
    if (!supportsNativeAutoUpdate) {
      return { supported: false }
    }

    setImmediate(() => {
      autoUpdater.quitAndInstall()
    })

    return { supported: true }
  })
}

export function checkForUpdatesOnStartup(): void {
  if (supportsNativeAutoUpdate) {
    autoUpdater
      .checkForUpdates()
      .catch((error: unknown) =>
        console.error("Auto update check failed", error),
      )
  }
}

export function isAutoUpdateSupported(): boolean {
  return supportsNativeAutoUpdate
}
