import { app, BrowserWindow, shell } from "electron"
import { join } from "node:path"
import { pathToFileURL } from "node:url"
import type { AboutAppInfo, PlatformInfo } from "../types"

interface AboutWindowConfig {
  isDev: boolean
  viteDevServerUrl?: string
  rendererDist: string
  preload: string
  packageMetadata: {
    author?: string | { name?: string }
    repository?: string | { url?: string }
    homepage?: string
  }
  platformInfo: PlatformInfo
}

let aboutWindow: BrowserWindow | null = null
let config: AboutWindowConfig

export function setupAboutWindow(cfg: AboutWindowConfig): void {
  config = cfg
}

export function getAboutInfo(): AboutAppInfo {
  const authorField = config.packageMetadata.author
  const author =
    typeof authorField === "string" ? authorField : (authorField?.name ?? null)

  const repositoryField = config.packageMetadata.repository
  const repository =
    typeof repositoryField === "string"
      ? repositoryField
      : (repositoryField?.url ?? null)

  return {
    appName: app.getName(),
    version: app.getVersion(),
    author,
    repository,
    homepage: config.packageMetadata.homepage ?? null,
  }
}

function getAboutWindowUrl(): string {
  if (config.isDev && config.viteDevServerUrl) {
    return new URL("about.html", config.viteDevServerUrl).toString()
  }

  return pathToFileURL(join(config.rendererDist, "about.html")).toString()
}

export function createAboutWindow(
  parentWindow: BrowserWindow | null,
): BrowserWindow {
  if (aboutWindow && !aboutWindow.isDestroyed()) {
    aboutWindow.focus()
    return aboutWindow
  }

  aboutWindow = new BrowserWindow({
    width: 440,
    height: 605,
    resizable: false,
    minimizable: false,
    maximizable: false,
    title: app.getName(),
    show: false,
    parent: parentWindow ?? undefined,
    modal: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: config.preload,
    },
  })

  aboutWindow.setMenu(null)

  aboutWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https:")) {
      shell.openExternal(url)
    }
    return { action: "deny" }
  })

  aboutWindow.on("closed", () => {
    aboutWindow = null
  })

  aboutWindow.once("ready-to-show", () => {
    aboutWindow?.show()
  })

  void aboutWindow.loadURL(getAboutWindowUrl())

  return aboutWindow
}

export function closeAboutWindow(): void {
  aboutWindow?.close()
}

export function getAboutWindow(): BrowserWindow | null {
  return aboutWindow
}
