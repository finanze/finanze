import { BrowserWindow, ipcMain, session } from "electron"
import { ExternalLoginRequestResult, LoginHandlerResult } from "."

export const ING_ID = "e0000000-0000-0000-0000-000000000010"

export async function promptLogin(): Promise<ExternalLoginRequestResult> {
  const ingPartition = `persist:ing`
  const ingSession = session.fromPartition(ingPartition)

  ingSession.webRequest.onSendHeaders(null)

  let ingWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    show: false,
    webPreferences: {
      partition: ingPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  function closeWindow() {
    setTimeout(() => {
      ingWindow?.close()
    }, 1000)
  }

  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
  }

  ingSession.webRequest.onSendHeaders(
    { types: ["xhr"], urls: ["<all_urls>"] },
    details => {
      if (details.url.endsWith("/genoma_api/rest/client")) {
        const genomaHeader = details.requestHeaders["Cookie"]
        const cookieHasSessionId = genomaHeader.includes("genoma-session-id")

        if (genomaHeader && cookieHasSessionId) {
          result.credentials.genomaCookie = genomaHeader

          const genomaSessionId = genomaHeader
            .split("genoma-session-id=")[1]
            ?.split(";")[0]
          result.credentials.genomaSessionId = genomaSessionId

          if (
            result.credentials.apiCookie &&
            result.credentials.apiAuth &&
            result.credentials.apiExtendedSessionCtx
          ) {
            result.success = true
            sendCompletion(result)
            closeWindow()
          }
        }
      } else if (details.url.endsWith("/position-keeping")) {
        const cookieHeader = details.requestHeaders["Cookie"]
        const authHeader = details.requestHeaders["authorization"]
        const extHeader = details.requestHeaders["X-ING-ExtendedSessionContext"]

        if (cookieHeader && authHeader && extHeader) {
          result.credentials.apiCookie = cookieHeader
          result.credentials.apiAuth = authHeader
          result.credentials.apiExtendedSessionCtx = extHeader

          if (
            result.credentials.genomaCookie &&
            result.credentials.genomaSessionId
          ) {
            result.success = true
            sendCompletion(result)
            closeWindow()
          }
        }
      }
    },
  )

  ingWindow.once("ready-to-show", () => {
    ingWindow?.show()
  })

  try {
    await ingWindow.loadURL("https://ing.ingdirect.es/app-login/")
  } catch (error) {
    console.error("Failed to load ING login page:", error)
    ingWindow?.close()
    return { success: false }
  }

  ingWindow.on("closed", () => {
    ingSession.webRequest.onSendHeaders(null)
    ingWindow?.removeAllListeners()
    if (
      !result.credentials ||
      !result.credentials.genomaCookie ||
      !result.credentials.genomaSessionId ||
      !result.credentials.apiCookie ||
      !result.credentials.apiAuth ||
      !result.credentials.apiExtendedSessionCtx
    ) {
      sendCompletion(result)
    }
    ingWindow = null
  })

  return { success: true }
}
function sendCompletion(result: LoginHandlerResult) {
  console.debug("Sending completion for ING:", ING_ID)
  console.debug(
    "Result (credentials collected):",
    Object.keys(result.credentials),
  )

  ipcMain.emit("completed-external-login", null, ING_ID, result)
}
