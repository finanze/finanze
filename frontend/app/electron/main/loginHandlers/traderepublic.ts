import { BrowserWindow, ipcMain, session } from "electron"
import {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "."

export const TRADE_REPUBLIC_ID = "e0000000-0000-0000-0000-000000000003"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const trPartition = `persist:traderepublic`
  const trSession = session.fromPartition(trPartition)

  let trWindow: BrowserWindow | null = new BrowserWindow({
    width: 1250,
    height: 900,
    show: false,
    webPreferences: {
      partition: trPartition,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const credentials = request.credentials || {}
  const result: LoginHandlerResult = {
    success: false,
    credentials: { ...credentials },
  }
  trSession.clearStorageData()

  const dbg = trWindow.webContents.debugger
  const pendingRequests = new Map<string, string>()

  try {
    dbg.attach("1.3")
  } catch {
    trWindow.close()
    return { success: false }
  }

  dbg.sendCommand("Network.enable")

  dbg.on("message", (_event, method, params) => {
    if (method === "Network.requestWillBeSent") {
      const url: string = params.request?.url || ""
      if (url.includes("token.awswaf.com") && url.includes("/telemetry")) {
        pendingRequests.set(params.requestId, url)
      }
    } else if (method === "Network.loadingFinished") {
      if (!pendingRequests.has(params.requestId)) return
      pendingRequests.delete(params.requestId)

      dbg
        .sendCommand("Network.getResponseBody", {
          requestId: params.requestId,
        })
        .then(({ body }) => {
          const json = JSON.parse(body)
          if (json.token) {
            result.credentials.awsWafToken = json.token
            result.success = true
            sendCompletion(result)
            trWindow?.close()
          }
        })
        .catch(() => {})
    }
  })

  trWindow.once("ready-to-show", () => {
    trWindow?.show()
  })

  try {
    await trWindow.loadURL("https://app.traderepublic.com/login")
  } catch (error: any) {
    const isAborted =
      error?.message?.includes("ERR_ABORTED") ||
      error?.toString?.()?.includes("ERR_ABORTED")
    if (!isAborted) {
      console.error("Failed to load Trade Republic login page:", error)
      trWindow?.close()
      return { success: false }
    }
  }

  trWindow.on("closed", () => {
    try {
      dbg.detach()
    } catch {
      // already detached
    }
    trWindow?.removeAllListeners()
    if (!result.success) {
      sendCompletion(result)
    }
    trWindow = null
  })

  return { success: true }
}

function sendCompletion(result: LoginHandlerResult) {
  console.debug("Sending completion for Trade Republic:", TRADE_REPUBLIC_ID)
  ipcMain.emit("completed-external-login", null, TRADE_REPUBLIC_ID, result)
}
