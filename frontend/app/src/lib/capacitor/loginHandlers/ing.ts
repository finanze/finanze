import { LoginWebView } from "../loginWebView"
import { emitCompletion } from "."
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

export const ING_ID = "e0000000-0000-0000-0000-000000000010"

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
    console.debug("Sending completion for ING:", ING_ID)
    console.debug("Result (credentials collected):", Object.keys(r.credentials))
    emitCompletion(ING_ID, r)
    LoginWebView.removeAllListeners()
  }

  function checkCompletion() {
    console.debug(
      "ING checkCompletion: " +
        JSON.stringify({
          genomaCookie: !!result.credentials.genomaCookie,
          genomaSessionId: !!result.credentials.genomaSessionId,
          apiCookie: !!result.credentials.apiCookie,
          apiAuth: !!result.credentials.apiAuth,
          apiExtendedSessionCtx: !!result.credentials.apiExtendedSessionCtx,
        }),
    )
    if (
      result.credentials.genomaCookie &&
      result.credentials.genomaSessionId &&
      result.credentials.apiCookie &&
      result.credentials.apiAuth &&
      result.credentials.apiExtendedSessionCtx
    ) {
      result.success = true
      sendCompletion(result)
      setTimeout(() => {
        LoginWebView.close()
      }, 1000)
    }
  }

  async function readNativeCookies(
    url = "https://ing.ingdirect.es",
  ): Promise<string> {
    try {
      const cookies = await LoginWebView.getCookies({ url })
      return cookies.raw
    } catch {
      return ""
    }
  }

  try {
    // Listen for request interception events.
    // On iOS, JS interception captures headers set via setRequestHeader
    // (authorization, X-ING-ExtendedSessionContext).
    // Cookie header is NOT visible to JS — we read it from the native cookie store.
    // We accumulate credentials incrementally rather than requiring all in one request.
    await LoginWebView.addListener("requestIntercepted", async data => {
      console.debug(
        "ING requestIntercepted: " +
          data.url +
          " headers: " +
          JSON.stringify(data.headers),
      )
      if (data.url.includes("/genoma_api/rest/client")) {
        // Cookie: read from native store using the full path (Android is path-sensitive)
        const cookieHeader = await readNativeCookies(
          "https://ing.ingdirect.es/genoma_api/rest/client",
        )

        if (cookieHeader && cookieHeader.includes("genoma-session-id")) {
          result.credentials.genomaCookie = cookieHeader
          const sessionId = cookieHeader
            .split("genoma-session-id=")[1]
            ?.split(";")[0]
          if (sessionId) {
            result.credentials.genomaSessionId = sessionId
          }
          checkCompletion()
        }
      }

      if (data.url.includes("/position-keeping")) {
        // Custom headers from JS interception (setRequestHeader captures these)
        const authHeader =
          data.headers["authorization"] || data.headers["Authorization"]
        const extHeader =
          data.headers["X-ING-ExtendedSessionContext"] ||
          data.headers["x-ing-extendedsessioncontext"]

        if (authHeader) {
          result.credentials.apiAuth = authHeader
        }
        if (extHeader) {
          result.credentials.apiExtendedSessionCtx = extHeader
        }

        // Cookie: read from native store (same domain, includes genoma cookies too)
        const cookieHeader = await readNativeCookies()
        if (cookieHeader) {
          result.credentials.apiCookie = cookieHeader
        }
        // Also capture genoma cookies if not yet captured (use genoma path for Android)
        if (!result.credentials.genomaCookie) {
          const genomaCookies = await readNativeCookies(
            "https://ing.ingdirect.es/genoma_api/rest/client",
          )
          if (genomaCookies && genomaCookies.includes("genoma-session-id")) {
            result.credentials.genomaCookie = genomaCookies
            const sessionId = genomaCookies
              .split("genoma-session-id=")[1]
              ?.split(";")[0]
            if (sessionId) {
              result.credentials.genomaSessionId = sessionId
            }
          }
        }

        checkCompletion()
      }
    })

    // Also listen for response events — they fire after the request completes,
    // giving cookies time to be committed to the native cookie store
    await LoginWebView.addListener("responseIntercepted", async data => {
      console.debug("ING responseIntercepted: " + data.url)
      if (data.url.includes("/genoma_api/rest/client")) {
        // After response, cookies are definitely committed
        const cookieHeader = await readNativeCookies(
          "https://ing.ingdirect.es/genoma_api/rest/client",
        )
        if (cookieHeader && cookieHeader.includes("genoma-session-id")) {
          result.credentials.genomaCookie = cookieHeader
          const sessionId = cookieHeader
            .split("genoma-session-id=")[1]
            ?.split(";")[0]
          if (sessionId) {
            result.credentials.genomaSessionId = sessionId
          }
          checkCompletion()
        }
      }

      if (data.url.includes("/position-keeping")) {
        // Read cookies after response to ensure they're up to date
        const cookieHeader = await readNativeCookies()
        if (cookieHeader) {
          result.credentials.apiCookie = cookieHeader
        }
        checkCompletion()
      }
    })

    await LoginWebView.addListener("closed", () => {
      if (!result.success) {
        sendCompletion(result)
      }
    })

    await LoginWebView.open({
      url: "https://ing.ingdirect.es/app-login/",
      title: "ING",
      clearSession: false,
      interceptUrlPatterns: ["/genoma_api/rest/client", "/position-keeping"],
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open ING login:", error)
    return { success: false }
  }
}
