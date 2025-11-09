import { contextBridge, ipcRenderer } from "electron"
import type { ProgressInfo, UpdateInfo } from "electron-updater"
import type { ThemeMode, AboutAppInfo } from "../types"
import type {
  ExternalLoginRequest,
  LoginHandlerResult,
} from "../main/loginHandlers"

function createIpcListener<T>(channel: string) {
  return (callback: (payload: T) => void) => {
    const listener = (_: Electron.IpcRendererEvent, data: T) => callback(data)
    ipcRenderer.on(channel, listener)
    return () => ipcRenderer.removeListener(channel, listener)
  }
}

contextBridge.exposeInMainWorld("ipcAPI", {
  apiUrl: () => ipcRenderer.invoke("api-url"),

  platform: () => ipcRenderer.invoke("platform"),

  changeThemeMode: (mode: ThemeMode) =>
    ipcRenderer.send("theme-mode-change", mode),

  showAbout: () => ipcRenderer.send("open-about-window"),

  getAboutInfo: () => ipcRenderer.invoke("about-info") as Promise<AboutAppInfo>,

  requestExternalLogin: async (
    id: string,
    request: ExternalLoginRequest = {},
  ) => ipcRenderer.invoke("external-login", id, request),

  checkForUpdates: () => ipcRenderer.invoke("auto-update-check"),

  downloadUpdate: () => ipcRenderer.invoke("auto-update-download"),

  quitAndInstall: () => ipcRenderer.invoke("auto-update-install"),

  onCheckingForUpdate: createIpcListener<void>("auto-update:checking"),

  onUpdateAvailable: createIpcListener<UpdateInfo>("auto-update:available"),

  onUpdateNotAvailable: createIpcListener<UpdateInfo>(
    "auto-update:not-available",
  ),

  onUpdateDownloaded: createIpcListener<UpdateInfo>("auto-update:downloaded"),

  onDownloadProgress: createIpcListener<ProgressInfo>(
    "auto-update:download-progress",
  ),

  onUpdateError: createIpcListener<{
    message: string
    stack: string | null
    name: string
  }>("auto-update:error"),

  onCompletedExternalLogin: (
    callback: (id: string, result: LoginHandlerResult) => void,
  ) => {
    ipcRenderer.removeAllListeners("completed-external-login")

    ipcRenderer.on("completed-external-login", (_, id, result) => {
      callback(id, result)
    })

    return () => ipcRenderer.removeAllListeners("completed-external-login")
  },
} as const)
