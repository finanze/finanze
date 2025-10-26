import { contextBridge, ipcRenderer } from "electron"
import type { ThemeMode, AboutAppInfo } from "../types"
import type {
  ExternalLoginRequest,
  LoginHandlerResult,
} from "../main/loginHandlers"

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
