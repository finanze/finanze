import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import {
  app,
  BrowserWindow,
  dialog,
  globalShortcut,
  ipcMain,
  nativeTheme,
  shell,
} from "electron"
import isDev from "electron-is-dev"
import { createMenu } from "./menu"
import {
  ThemeMode,
  AppConfig,
  OS,
  PlatformInfo,
  BackendStartOptions,
  BackendActionResult,
  BackendErrorInfo,
  FinanzeConfig,
} from "../types"
import { promptLogin } from "./loginHandlers"
import packageJson from "../../package.json" assert { type: "json" }
import { BackendController } from "./backend-controller"
import {
  initializeLogger,
  mapBackendLogLevel,
  updateLoggerConfig,
  type LogLevel,
} from "./logging"
import { setMainWindow, readRendererConfig } from "./renderer-config"
import {
  setupAutoUpdater,
  initializeAutoUpdater,
  registerAutoUpdateHandlers,
  checkForUpdatesOnStartup,
} from "./auto-updater"
import {
  setupAboutWindow,
  createAboutWindow,
  closeAboutWindow,
  getAboutInfo,
} from "./about-window"
import { createTray } from "./tray"

const packageMetadata = packageJson as {
  author?: string | { name?: string }
  repository?: string | { url?: string }
  homepage?: string
}

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export const APP_ROOT = join(__dirname, "../..")
export const MAIN_DIST = join(APP_ROOT, "dist-electron")
export const RENDERER_DIST = join(APP_ROOT, "dist")
export const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL
export const VITE_PUBLIC = VITE_DEV_SERVER_URL
  ? join(APP_ROOT, "public")
  : RENDERER_DIST

const appConfig: AppConfig = {
  os:
    process.platform === "darwin"
      ? OS.MAC
      : process.platform === "win32"
        ? OS.WINDOWS
        : OS.LINUX,
  isDev: isDev,
  ports: {
    backend: 7592,
  },
  urls: {
    backend: "http://localhost",
    vite:
      isDev && VITE_DEV_SERVER_URL
        ? VITE_DEV_SERVER_URL
        : `file://${join(__dirname, "../dist/index.html")}`,
  },
}

setupAutoUpdater(appConfig, OS)

const platformInfo: PlatformInfo = {
  type: appConfig.os,
  arch: process.arch,
  osVersion: process.getSystemVersion(),
  electronVersion: process.versions.electron,
}

const preload = join(__dirname, "../preload/index.mjs")

const backendController = new BackendController({
  appConfig,
  devEntryPoint: join(__dirname, "..", "..", "..", "..", "finanze"),
  defaultArgs: {
    port: appConfig.ports.backend,
    logLevel: appConfig.isDev ? "DEBUG" : "INFO",
    dataDir: appConfig.isDev ? join("..", "..", ".storage") : undefined,
    logDir: appConfig.isDev ? join("..", "..", ".storage", "logs") : undefined,
    logFileLevel: undefined,
    thirdPartyLogLevel: undefined,
  },
})

const BACKEND_STATUS_CHANNEL = "backend:status"

let mainWindow: BrowserWindow | null = null
let rendererConfig: FinanzeConfig = {}

backendController.on("status-changed", status => {
  sendToAllWindows(BACKEND_STATUS_CHANNEL, status)
})

if (appConfig.os === OS.WINDOWS) app.setAppUserModelId(app.getName())

if (!app.requestSingleInstanceLock()) {
  console.warn("Failed to acquire single instance lock")
  if (!appConfig.isDev) {
    app.quit()
    process.exit(0)
  } else {
    console.warn("Continuing despite lock failure (Dev mode)")
  }
}

function getSuitableTitleBarOverlay() {
  if (appConfig.os === OS.MAC) {
    return undefined // No overlay for macOS
  }

  const shouldUseDarkColors = nativeTheme.shouldUseDarkColors

  return {
    color: shouldUseDarkColors ? "rgba(0, 0, 0, 0)" : "rgba(255, 255, 255, 0)",
    symbolColor: shouldUseDarkColors ? "#ffffff" : "#000000",
  }
}

function updateTitleBarOverlay(mainWindow: BrowserWindow | null) {
  if (appConfig.os !== OS.MAC && mainWindow) {
    const overlay = getSuitableTitleBarOverlay()
    if (overlay) {
      mainWindow.setTitleBarOverlay(overlay)
    }
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: appConfig.isDev ? 1900 : 1250,
    height: appConfig.isDev ? 1200 : 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: preload,
    },
    titleBarStyle: "hidden",
    titleBarOverlay: getSuitableTitleBarOverlay(),
  })

  setMainWindow(mainWindow)

  globalShortcut.register("CommandOrControl+Alt+I", () => {
    mainWindow?.webContents.toggleDevTools()
  })

  if (appConfig.isDev) {
    await mainWindow.loadURL(appConfig.urls.vite)
    mainWindow.webContents.openDevTools()
  } else {
    await mainWindow.loadFile(join(RENDERER_DIST, "index.html"))
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https:")) shell.openExternal(url)
    return { action: "deny" }
  })

  mainWindow.on("closed", () => {
    mainWindow = null
    setMainWindow(null)
  })

  createMenu(mainWindow, () => {
    createAboutWindow(mainWindow)
  })
}

async function showOrCreateMainWindow(): Promise<void> {
  if (mainWindow === null) {
    await createWindow()
  } else {
    mainWindow.show()
  }
}

// Helper function to send events to all windows
function sendToAllWindows(channel: string, ...args: any[]) {
  BrowserWindow.getAllWindows().forEach(window => {
    if (!window.isDestroyed() && !window.webContents.isDestroyed()) {
      try {
        console.debug(`Sending ${channel} to window ${window.id}`)
        window.webContents.send(channel, ...args)
      } catch (error) {
        console.error(`Failed to send ${channel} to window ${window.id}`, error)
      }
    }
  })
}

function getLogConfigFromRendererConfig(config: FinanzeConfig): {
  logDir: string | undefined
  minLevel: LogLevel
  minFileLevel: LogLevel | undefined
} {
  const logDir =
    config.backend?.logDir ??
    (appConfig.isDev
      ? join(__dirname, "..", "..", "..", "..", ".storage", "logs")
      : undefined)

  const minLevel = config.backend?.logLevel
    ? mapBackendLogLevel(config.backend.logLevel)
    : appConfig.isDev
      ? "DEBUG"
      : "INFO"

  const minFileLevel = config.backend?.logFileLevel
    ? mapBackendLogLevel(config.backend.logFileLevel)
    : undefined

  return { logDir, minLevel, minFileLevel }
}

async function applyLogConfigFromRenderer(): Promise<void> {
  const config = await readRendererConfig()
  rendererConfig = config
  const logConfig = getLogConfigFromRendererConfig(config)
  updateLoggerConfig(logConfig)
}

async function startBackendProcess(
  options?: BackendStartOptions,
): Promise<BackendActionResult> {
  try {
    const status = await backendController.start(options)
    return { success: true, status }
  } catch (error) {
    return {
      success: false,
      status: backendController.getStatus(),
      error: serializeBackendError(error),
    }
  }
}

async function stopBackendProcess(): Promise<BackendActionResult> {
  try {
    await applyLogConfigFromRenderer()
    const status = await backendController.stop()
    return { success: true, status }
  } catch (error) {
    return {
      success: false,
      status: backendController.getStatus(),
      error: serializeBackendError(error),
    }
  }
}

async function restartBackendProcess(): Promise<BackendActionResult> {
  try {
    await applyLogConfigFromRenderer()
    await backendController.stop()
    const status = await backendController.start(rendererConfig.backend)
    return { success: true, status }
  } catch (error) {
    return {
      success: false,
      status: backendController.getStatus(),
      error: serializeBackendError(error),
    }
  }
}

function serializeBackendError(error: unknown): BackendErrorInfo {
  if (error instanceof Error) {
    const err = error as NodeJS.ErrnoException
    return {
      message: error.message,
      stack: error.stack ?? null,
      code: err.code ?? null,
    }
  }

  return {
    message: typeof error === "string" ? error : "Unknown error",
    stack: null,
    code: null,
  }
}

app.whenReady().then(async () => {
  setupAboutWindow({
    isDev: appConfig.isDev,
    viteDevServerUrl: VITE_DEV_SERVER_URL,
    rendererDist: RENDERER_DIST,
    preload,
    packageMetadata,
    platformInfo,
  })

  ipcMain.handle("api-url", async () => {
    if (!rendererConfig.serverUrl) {
      rendererConfig = await readRendererConfig()
    }
    if (rendererConfig.serverUrl) {
      return { url: rendererConfig.serverUrl, custom: true }
    }
    return {
      url: appConfig.urls.backend + ":" + appConfig.ports.backend,
      custom: false,
    }
  })
  ipcMain.handle("platform", () => platformInfo)
  ipcMain.on("theme-mode-change", (_, mode: ThemeMode) => {
    nativeTheme.themeSource = mode
    updateTitleBarOverlay(mainWindow)
  })
  ipcMain.on("open-about-window", () => {
    createAboutWindow(mainWindow)
  })
  ipcMain.handle("about-info", () => getAboutInfo())
  ipcMain.handle("external-login", async (_, id, request) => {
    return await promptLogin(id, request)
  })

  ipcMain.handle("backend-status", () => backendController.getStatus())
  ipcMain.handle(
    "backend-start",
    async (_, options: BackendStartOptions = {}) =>
      await startBackendProcess(options),
  )
  ipcMain.handle("backend-stop", async () => await stopBackendProcess())
  ipcMain.handle("backend-restart", async () => await restartBackendProcess())

  ipcMain.handle("select-directory", async (_, initialPath?: string) => {
    const result = await dialog.showOpenDialog({
      title: "Select directory",
      properties: ["openDirectory", "createDirectory"],
      defaultPath: initialPath,
    })

    if (result.canceled || result.filePaths.length === 0) {
      return null
    }

    return result.filePaths[0]
  })

  ipcMain.on("completed-external-login", (_, id, result) => {
    sendToAllWindows("completed-external-login", id, result)
  })

  registerAutoUpdateHandlers()

  await createWindow()

  rendererConfig = await readRendererConfig()
  console.debug("Renderer config loaded:", JSON.stringify(rendererConfig))
  const logConfig = getLogConfigFromRendererConfig(rendererConfig)
  initializeLogger(logConfig)

  if (!rendererConfig.serverUrl) {
    const startupBackendResult = await startBackendProcess(
      rendererConfig.backend,
    )
    if (!startupBackendResult.success && startupBackendResult.error) {
      dialog.showErrorBox(
        "Failed to start backend",
        startupBackendResult.error.message,
      )
    }
  } else {
    console.info(
      "Skipping backend start because custom serverUrl is configured:",
      rendererConfig.serverUrl,
    )
  }

  createTray({
    publicPath: VITE_PUBLIC,
    onShowWindow: showOrCreateMainWindow,
    onAbout: () => createAboutWindow(mainWindow),
  })

  initializeAutoUpdater()
  checkForUpdatesOnStartup()

  app.on("activate", async () => {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (mainWindow === null) {
      await createWindow()
    }
  })
})

app.on("second-instance", () => {
  if (mainWindow) {
    // Focus on the main window if the user tried to open another
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

// Quit when all windows are closed, except on macOS
app.on("window-all-closed", () => {
  mainWindow = null
  closeAboutWindow()
  if (appConfig.os !== OS.MAC) {
    app.quit()
  }
})

// Clean up the Python process when the app is quitting
app.on("will-quit", e => {
  e.preventDefault()
  quit()
    .then()
    .catch(error => console.error(error))
})

async function quit() {
  app.removeAllListeners("second-instance")
  app.removeAllListeners("window-all-closed")
  app.removeAllListeners("activate")
  app.removeAllListeners("will-quit")

  try {
    try {
      closeAboutWindow()
      await stopBackendProcess()
      await new Promise(resolve => setTimeout(resolve, 1000))
    } catch (error) {
      console.error("Error terminating backend:", error)
    }

    app.quit()
  } finally {
    try {
      if (appConfig.os !== OS.WINDOWS) app.quit()
    } catch {
      // Ignore errors from retrying
    }
  }
}
