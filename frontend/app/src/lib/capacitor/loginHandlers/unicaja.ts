import { LoginWebView } from "../loginWebView"
import { emitCompletion } from "."
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

export const UNICAJA_ID = "e0000000-0000-0000-0000-000000000002"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
    flow: request.flow,
  }

  let completed = false

  function sendCompletion(r: LoginHandlerResult) {
    if (completed) return
    completed = true
    console.debug("Sending completion for Unicaja:", UNICAJA_ID)
    emitCompletion(UNICAJA_ID, r)
    LoginWebView.removeAllListeners()
  }

  try {
    await LoginWebView.addListener("requestIntercepted", async data => {
      if (data.url.includes("/rest/autenticacion")) {
        try {
          const domResult = await LoginWebView.executeScript({
            code: `JSON.stringify({ user: document.querySelector('#username')?.value || '', password: document.querySelector('#pwd')?.value || '' })`,
          })
          const creds = JSON.parse(domResult.result)
          if (creds.user) result.credentials.user = creds.user
          if (creds.password) result.credentials.password = creds.password
        } catch {
          // ignore DOM read errors
        }
      }
    })

    await LoginWebView.addListener("requestIntercepted", async data => {
      if (data.url.includes("/rest/perfilusuario")) {
        try {
          const cookies = await LoginWebView.getCookies({
            url: "https://univia.unicajabanco.es",
          })
          if (cookies.cookies["_abck"]) {
            result.success = true
            result.credentials.abck = cookies.cookies["_abck"]
            sendCompletion(result)
            await LoginWebView.close()
          }
        } catch {
          // ignore cookie read errors
        }
      }
    })

    await LoginWebView.addListener("closed", () => {
      if (!result.success) {
        sendCompletion(result)
      }
    })

    await LoginWebView.open({
      url: "https://univia.unicajabanco.es/login",
      title: "Unicaja",
      clearSession: true,
      interceptUrlPatterns: ["/rest/autenticacion", "/rest/perfilusuario"],
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open Unicaja login:", error)
    return { success: false }
  }
}
