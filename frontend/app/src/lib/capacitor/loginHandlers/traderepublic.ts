import { LoginWebView } from "../loginWebView"
import { emitCompletion } from "."
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

export const TRADE_REPUBLIC_ID = "e0000000-0000-0000-0000-000000000003"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const credentials = request.credentials || {}
  const result: LoginHandlerResult = {
    success: false,
    credentials: { ...credentials },
  }

  let completed = false

  function sendCompletion(r: LoginHandlerResult) {
    if (completed) return
    completed = true
    console.debug("Sending completion for Trade Republic:", TRADE_REPUBLIC_ID)
    emitCompletion(TRADE_REPUBLIC_ID, r)
    LoginWebView.removeAllListeners()
  }

  try {
    // Trade Republic uses AWS WAF tokens from telemetry responses.
    // We need response body interception, so we use a targeted fetch wrapper
    // injected via injectScript. The native interception fires responseIntercepted
    // events which include the body from the JS layer.
    await LoginWebView.addListener("responseIntercepted", data => {
      if (
        data.url.includes("token.awswaf.com") &&
        data.url.includes("/telemetry")
      ) {
        try {
          const body = (data as any).body
          if (body) {
            const json = JSON.parse(body)
            if (json.token) {
              result.credentials.awsWafToken = json.token
              result.success = true
              sendCompletion(result)
              LoginWebView.close()
            }
          }
        } catch {
          // ignore parse errors
        }
      }
    })

    await LoginWebView.addListener("closed", () => {
      if (!result.success) {
        sendCompletion(result)
      }
    })

    await LoginWebView.open({
      url: "https://app.traderepublic.com/login",
      title: "Trade Republic",
      clearSession: true,
      interceptUrlPatterns: ["token.awswaf.com", "/telemetry"],
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open Trade Republic login:", error)
    return { success: false }
  }
}
