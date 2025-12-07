import { BrowserWindow, ipcMain, session } from "electron"
import { ExternalLoginRequestResult, LoginHandlerResult } from "."

export const UNICAJA_ID = "e0000000-0000-0000-0000-000000000002"

export async function promptLogin(): Promise<ExternalLoginRequestResult> {
  const unicajaPartition = `persist:unicaja`
  const unicajaSession = session.fromPartition(unicajaPartition)

  unicajaSession.webRequest.onSendHeaders(null)

  let unicajaWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    show: false,
    webPreferences: {
      partition: unicajaPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
  }
  unicajaSession.clearStorageData()

  unicajaSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: ["<all_urls>"] },
    details => {
      if (details.url.includes("/rest/autenticacion")) {
        unicajaWindow?.webContents
          .executeJavaScript(
            `document.querySelector('#username').value + ' ' + document.querySelector('#pwd').value`,
          )
          .then(r => {
            const [user, password] = r.split(" ")
            result.credentials = { user, password }
          })
      } else if (details.url.includes("/rest/perfilusuario")) {
        unicajaSession.cookies
          .get({
            url: "https://univia.unicajabanco.es",
            name: "_abck",
          })
          .then(current_cookies => {
            if (current_cookies.length > 0) {
              result.success = true
              result.credentials.abck = current_cookies[0].value
            }

            sendCompletion(result)
            unicajaWindow?.close()
          })
      }
    },
  )
  unicajaWindow.once("ready-to-show", () => {
    unicajaWindow?.show()
  })

  try {
    await unicajaWindow.loadURL("https://univia.unicajabanco.es/login")
  } catch (error: any) {
    // ERR_ABORTED (-3) happens on redirects, which is expected for login pages
    const isAborted =
      error?.message?.includes("ERR_ABORTED") ||
      error?.toString?.()?.includes("ERR_ABORTED")
    if (!isAborted) {
      console.error("Failed to load Unicaja login page:", error)
      unicajaWindow?.close()
      return { success: false }
    }
  }

  unicajaWindow.on("closed", () => {
    unicajaSession.webRequest.onSendHeaders(null)
    unicajaWindow?.removeAllListeners()
    if (!result.success && !result.credentials.abck) {
      sendCompletion(result)
    }
    unicajaWindow = null
  })

  return { success: true }
}

function sendCompletion(result: LoginHandlerResult) {
  console.debug("Sending completion for Unicaja:", UNICAJA_ID)

  ipcMain.emit("completed-external-login", null, UNICAJA_ID, result)
}
