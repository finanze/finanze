import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import os from 'node:os'
import { app, BrowserWindow, ipcMain, Menu, shell, Tray } from 'electron'
import isDev from 'electron-is-dev'
import { type ChildProcess, spawn } from 'child_process'
import { createMenu } from './menu'
import { type AppConfig, OS } from './app-config'
import { promptLogin } from './loginHandlers'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export const APP_ROOT = join(__dirname, '../..')
export const MAIN_DIST = join(APP_ROOT, 'dist-electron')
export const RENDERER_DIST = join(APP_ROOT, 'dist')
export const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL
export const VITE_PUBLIC = VITE_DEV_SERVER_URL
    ? join(APP_ROOT, 'public')
    : RENDERER_DIST

const appConfig: AppConfig = {
    os:
        process.platform === 'darwin'
            ? OS.MAC
            : process.platform === 'win32'
                ? OS.WINDOWS
                : OS.LINUX,
    isDev: isDev,
    ports: {
        backend: 8080,
    },
    urls: {
        backend: 'http://localhost',
        vite:
            isDev && VITE_DEV_SERVER_URL
                ? VITE_DEV_SERVER_URL
                : `file://${join(__dirname, '../dist/index.html')}`,
    },
}

const preload = join(__dirname, '../preload/index.mjs')

const apiUrl = appConfig.urls.backend + ':' + appConfig.ports.backend

let mainWindow: BrowserWindow | null = null
let tray = null
let pythonProcess: ChildProcess | null = null

if (os.release().startsWith('6.1')) app.disableHardwareAcceleration()

if (appConfig.os === OS.WINDOWS) app.setAppUserModelId(app.getName())

if (!app.requestSingleInstanceLock()) {
    app.quit()
    process.exit(0)
}

function startPythonBackend() {
    const executablePath = appConfig.isDev
        ? 'python'
        : join(process.resourcesPath, 'bin', 'server')

    const args = [
        '--port',
        appConfig.ports.backend.toString(),
    ]
    if (appConfig.isDev) {
        let backendPyPath = join(__dirname, '..', '..', '..', '..', 'finanze')

        console.log(`Starting dev Python backend: ${executablePath} ${backendPyPath}`)
        const devArgs = [
            backendPyPath,
            '--data-dir',
            '../../../.storage',
            '--log-level',
            'DEBUG',]

        pythonProcess = spawn(executablePath, [...devArgs, ...args])
    } else {
        console.log(`Starting Python backend: ${executablePath}`)

        pythonProcess = spawn(executablePath, args)
    }

    pythonProcess?.stdout?.on('data', (data) => {
        console.log(`>> ${data}`)
    })

    pythonProcess?.stderr?.on('data', (data) => {
        console.error(`>> ${data}`)
    })

    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`)
        pythonProcess = null
    })
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
        titleBarStyle: 'hidden',
        ...(appConfig.os !== OS.MAC ? { titleBarOverlay: true } : {}),
    })

    if (appConfig.isDev) {
        await mainWindow.loadURL(appConfig.urls.vite)
        mainWindow.webContents.openDevTools()
    } else {
        await mainWindow.loadFile(join(RENDERER_DIST, 'index.html'))
    }

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('https:')) shell.openExternal(url)
        return { action: 'deny' }
    })

    mainWindow.on('closed', () => {
        mainWindow = null
    })

    createMenu(mainWindow)
}

function createTray() {
    tray = new Tray(join(VITE_PUBLIC, 'tray.png'))
    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Finanze',
            click: async () => {
                if (mainWindow === null) {
                    await createWindow()
                } else {
                    mainWindow.show()
                }
            },
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                app.quit()
            },
        },
    ])
    tray.setToolTip('Finanze')
    tray.setContextMenu(contextMenu)

    tray.on('click', async () => {
        if (mainWindow === null) {
            await createWindow()
        } else {
            mainWindow.show()
        }
    })
}

// Helper function to send events to all windows
function sendToAllWindows(channel: string, ...args: any[]) {
    BrowserWindow.getAllWindows().forEach((window) => {
        if (!window.isDestroyed()) {
            console.log(`Sending ${channel} to window ${window.id}`)
            window.webContents.send(channel, ...args)
        }
    })
}

app.whenReady().then(async () => {
    ipcMain.handle('api-url', () => apiUrl)
    ipcMain.handle('show-about', () => { })
    ipcMain.handle('external-login', async (_, id, request) => {
        return await promptLogin(id, request)
    })

    ipcMain.on('completed-external-login', (_, id, result) => {
        sendToAllWindows('completed-external-login', id, result)
    })

    startPythonBackend()

    await createWindow()
    createTray()

    app.on('activate', async () => {
        // On macOS it's common to re-create a window in the app when the
        // dock icon is clicked and there are no other windows open.
        if (mainWindow === null) {
            await createWindow()
        }
    })
})

app.on('second-instance', () => {
    if (mainWindow) {
        // Focus on the main window if the user tried to open another
        if (mainWindow.isMinimized()) mainWindow.restore()
        mainWindow.focus()
    }
})

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', () => {
    mainWindow = null
    if (appConfig.os !== OS.MAC) {
        app.quit()
    }
})

// Clean up the Python process when the app is quitting
app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill()
        pythonProcess = null
    }
})
