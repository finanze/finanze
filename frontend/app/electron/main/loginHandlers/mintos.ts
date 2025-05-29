import { BrowserWindow, ipcMain, session } from "electron"
import {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "."

export const MINTOS_ID = "e0000000-0000-0000-0000-000000000007"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const mintosPartition = `persist:mintos`
  let mintosWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    webPreferences: {
      partition: mintosPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const mintosSession = session.fromPartition(mintosPartition)

  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
  }

  mintosSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: [] },
    details => {
      if (details.url.includes("/api/auth/login")) {
        mintosWindow?.webContents
          .executeJavaScript(
            `document.querySelector('#login-username').value + ' ' + document.querySelector('#login-password').value`,
          )
          .then(r => {
            const [user, password] = r.split(" ")
            result.credentials = { user, password }
          })
      } else if (details.url.includes("/webapp-api/user")) {
        const cookieHeader = details.requestHeaders["Cookie"]
        if (cookieHeader) {
          result.success = true
          result.credentials.cookie = cookieHeader
          if (!result.credentials.user) {
            mintosSession.clearStorageData()
            mintosWindow?.reload()
            return
          }
        }

        sendCompletion(result)
        mintosWindow?.close()
      }
    },
  )

  await mintosWindow.loadURL("https://www.mintos.com/en/login")

  if (request.credentials)
    await mintosWindow?.webContents.executeJavaScript(`
            function typeAndTab(e,t){const n=document.getElementById(e);n&&(n.focus(),n.value=t,n.dispatchEvent(new Event('input',{bubbles:!0})),n.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',code:'Tab',keyCode:9,which:9,bubbles:!0,cancelable:!0})))}function pressEnter(){const e=document.activeElement||document.body;e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:!0,cancelable:!0}))}
            typeAndTab('login-username', '${request.credentials?.user}')
            typeAndTab('login-password', '${request.credentials?.password}')
        `)

  mintosWindow.on("closed", () => {
    mintosWindow?.removeAllListeners()
    mintosSession.removeAllListeners()
    if (
      !result.credentials ||
      !result.credentials.cookie ||
      !result.credentials.user ||
      !result.credentials.password
    ) {
      sendCompletion(result)
    }
    mintosWindow = null
  })

  return { success: true }
}

function sendCompletion(result: LoginHandlerResult) {
  console.debug("Sending completion for Mintos:", MINTOS_ID)

  ipcMain.emit("completed-external-login", null, MINTOS_ID, result)
}
