import { BrowserWindow, ipcMain, session } from "electron"
import { ExternalLoginRequestResult, LoginHandlerResult } from "."

export const UNICAJA_ID = "e0000000-0000-0000-0000-000000000002"

export async function promptLogin(): Promise<ExternalLoginRequestResult> {
  const unicajaPartition = `persist:unicaja`
  let unicajaWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    webPreferences: {
      partition: unicajaPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const unicajaSession = session.fromPartition(unicajaPartition)
  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
  }
  unicajaSession.clearStorageData()

  unicajaSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: [] },
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
  unicajaWindow.loadURL("https://univia.unicajabanco.es/login")

  unicajaWindow.on("closed", () => {
    unicajaSession.removeAllListeners()
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
