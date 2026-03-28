import { BrowserWindow, ipcMain, session } from "electron"
import {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "."

export const IBKR_ID = "e0000000-0000-0000-0000-000000000013"

const IBKR_URL = "https://www.interactivebrokers.ie"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const ibkrPartition = `persist:ibkr`
  const ibkrSession = session.fromPartition(ibkrPartition)

  ibkrSession.webRequest.onHeadersReceived(null)

  let ibkrWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    show: false,
    webPreferences: {
      partition: ibkrPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  function closeWindow() {
    setTimeout(() => {
      ibkrWindow?.close()
    }, 1000)
  }

  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
    flow: request.flow,
  }

  ibkrSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: ["<all_urls>"] },
    details => {
      if (details.url.includes("/sso/Authenticator")) {
        ibkrWindow?.webContents
          .executeJavaScript(
            `(() => {
              const u = document.getElementById('xyz-field-username');
              const p = document.getElementById('xyz-field-password');
              return JSON.stringify({
                user: u ? u.value : '',
                password: p ? p.value : ''
              });
            })()`,
          )
          .then(r => {
            const creds = JSON.parse(r)
            if (creds.user) result.credentials.user = creds.user
            if (creds.password) result.credentials.password = creds.password
            console.debug(
              "Captured IBKR credentials:",
              creds ? { user: creds.user, password: "****" } : {},
            )
          })
          .catch(() => {})
      }
    },
  )

  ibkrSession.webRequest.onHeadersReceived(
    { types: ["xhr"], urls: ["<all_urls>"] },
    (details, callback) => {
      if (
        details.url.includes("/AccountManagement/OneBarAuthentication") &&
        details.statusCode === 200
      ) {
        // Wait briefly for Electron to commit Set-Cookie headers from
        // this response into the cookie jar before reading
        setTimeout(() => {
          ibkrSession.cookies
            .get({})
            .then(cookies => {
              const ibkrCookies = cookies.filter(
                c =>
                  c.domain?.includes("interactivebrokers") ||
                  c.domain?.includes(".ie"),
              )
              const cookieStr = ibkrCookies
                .map(c => `${c.name}=${c.value}`)
                .join("; ")
              if (cookieStr) {
                result.success = true
                result.credentials.cookie = cookieStr
                sendCompletion(result)
                closeWindow()
              }
            })
            .catch(err => {
              console.error("Failed to read IBKR cookies:", err)
            })
        }, 500)
      }
      callback({})
    },
  )

  ibkrWindow.once("ready-to-show", () => {
    ibkrWindow?.show()
  })

  try {
    await ibkrWindow.loadURL(`${IBKR_URL}/portal/`)
  } catch (error) {
    const isAborted =
      error instanceof Error && error.message.includes("ERR_ABORTED")
    if (!isAborted) {
      console.error("Failed to load IBKR login page:", error)
      ibkrWindow?.close()
      return { success: false }
    }
  }

  if (request.credentials?.user && request.credentials?.password) {
    ibkrWindow.webContents.once("did-finish-load", () => {
      setTimeout(() => {
        ibkrWindow?.webContents
          .executeJavaScript(
            `(() => {
            const u = document.getElementById('xyz-field-username');
            const p = document.getElementById('xyz-field-password');
            if (u) { u.focus(); u.value = ${JSON.stringify(request.credentials!.user)}; u.dispatchEvent(new Event('input', {bubbles: true})); }
            if (p) { p.focus(); p.value = ${JSON.stringify(request.credentials!.password)}; p.dispatchEvent(new Event('input', {bubbles: true})); }
          })()`,
          )
          .catch(() => {})
      }, 500)
    })
  }

  ibkrWindow.on("closed", () => {
    ibkrSession.webRequest.onSendHeaders(null)
    ibkrSession.webRequest.onHeadersReceived(null)
    ibkrWindow?.removeAllListeners()
    if (!result.credentials || !result.credentials.cookie) {
      sendCompletion(result)
    }
    ibkrWindow = null
  })

  return { success: true }
}

function sendCompletion(result: LoginHandlerResult) {
  console.debug("Sending completion for IBKR:", IBKR_ID)

  ipcMain.emit("completed-external-login", null, IBKR_ID, result)
}
