import { contextBridge, ipcRenderer } from "electron"
import type { ProgressInfo, UpdateInfo } from "electron-updater"
import { getRendererPlatformInfo } from "../shared/platform"
import type {
  ThemeMode,
  AboutAppInfo,
  BackendStartOptions,
  BackendStatus,
  BackendActionResult,
} from "../types"
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

const platformInfo = getRendererPlatformInfo()

contextBridge.exposeInMainWorld("platform", platformInfo)

contextBridge.exposeInMainWorld("ipcAPI", {
  apiUrl: () =>
    ipcRenderer.invoke("api-url") as Promise<{ url: string; custom: boolean }>,

  changeThemeMode: (mode: ThemeMode) =>
    ipcRenderer.send("theme-mode-change", mode),

  showAbout: () => ipcRenderer.send("open-about-window"),

  getAboutInfo: () => ipcRenderer.invoke("about-info") as Promise<AboutAppInfo>,

  requestExternalLogin: async (
    id: string,
    request: ExternalLoginRequest = {},
  ) => ipcRenderer.invoke("external-login", id, request),

  startBackend: (options?: BackendStartOptions) =>
    ipcRenderer.invoke(
      "backend-start",
      options,
    ) as Promise<BackendActionResult>,

  stopBackend: () =>
    ipcRenderer.invoke("backend-stop") as Promise<BackendActionResult>,

  restartBackend: () =>
    ipcRenderer.invoke("backend-restart") as Promise<BackendActionResult>,

  getBackendStatus: () =>
    ipcRenderer.invoke("backend-status") as Promise<BackendStatus>,

  selectDirectory: (initialPath?: string) =>
    ipcRenderer.invoke("select-directory", initialPath) as Promise<
      string | null
    >,

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

  onBackendStatusChange: createIpcListener<BackendStatus>("backend:status"),

  onCompletedExternalLogin: (
    callback: (id: string, result: LoginHandlerResult) => void,
  ) => {
    ipcRenderer.removeAllListeners("completed-external-login")

    ipcRenderer.on("completed-external-login", (_, id, result) => {
      callback(id, result)
    })

    return () => ipcRenderer.removeAllListeners("completed-external-login")
  },

  onOAuthCallback: (
    callback: (tokens: {
      access_token: string
      refresh_token: string
      type?: string
    }) => void,
  ) => {
    ipcRenderer.removeAllListeners("oauth-callback")

    ipcRenderer.on("oauth-callback", (_, tokens) => {
      callback(tokens)
    })

    return () => ipcRenderer.removeAllListeners("oauth-callback")
  },

  onOAuthCallbackError: (
    callback: (payload: {
      error: string
      error_description: string | null
      error_code: string | null
    }) => void,
  ) => {
    ipcRenderer.removeAllListeners("oauth-callback-error")

    ipcRenderer.on("oauth-callback-error", (_, payload) => {
      callback(payload)
    })

    return () => ipcRenderer.removeAllListeners("oauth-callback-error")
  },

  onOAuthCallbackCode: (callback: (payload: { code: string }) => void) => {
    ipcRenderer.removeAllListeners("oauth-callback-code")

    ipcRenderer.on("oauth-callback-code", (_, payload) => {
      callback(payload)
    })

    return () => ipcRenderer.removeAllListeners("oauth-callback-code")
  },

  onOAuthCallbackUrl: (callback: (payload: { url: string }) => void) => {
    ipcRenderer.removeAllListeners("oauth-callback-url")

    ipcRenderer.on("oauth-callback-url", (_, payload) => {
      callback(payload)
    })

    return () => ipcRenderer.removeAllListeners("oauth-callback-url")
  },
} as const)
