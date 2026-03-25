import { LoginWebView } from "../loginWebView"
import { emitCompletion } from "."
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

export const IBKR_ID = "e0000000-0000-0000-0000-000000000013"

const IBKR_URL = "https://www.interactivebrokers.ie"

export async function promptLogin(
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const result: LoginHandlerResult = {
    success: false,
    credentials: {},
  }

  let completed = false

  function sendCompletion(r: LoginHandlerResult) {
    if (completed) return
    completed = true
    console.debug("Sending completion for IBKR:", IBKR_ID)
    emitCompletion(IBKR_ID, r)
    LoginWebView.removeAllListeners()
  }

  try {
    await LoginWebView.addListener("requestIntercepted", async data => {
      if (data.url.includes("/sso/Authenticator")) {
        try {
          const domResult = await LoginWebView.executeScript({
            code: `(() => {
              const u = document.getElementById('xyz-field-username');
              const p = document.getElementById('xyz-field-password');
              return JSON.stringify({
                user: u ? u.value : '',
                password: p ? p.value : ''
              });
            })()`,
          })
          const creds = JSON.parse(domResult.result)
          if (creds.user) result.credentials.user = creds.user
          if (creds.password) result.credentials.password = creds.password
          console.debug(
            "Captured IBKR credentials:",
            creds ? { user: creds.user, password: "****" } : {},
          )
        } catch {
          // ignore DOM read errors
        }
      }
    })

    // Watch for successful authentication response
    await LoginWebView.addListener("requestIntercepted", async data => {
      if (data.url.includes("/AccountManagement/OneBarAuthentication")) {
        // Wait briefly for cookies to be committed
        setTimeout(async () => {
          try {
            const cookies = await LoginWebView.getCookies({
              url: IBKR_URL,
            })
            if (cookies.raw) {
              // Filter to IBKR-related cookies
              const allCookies = cookies.raw
              if (allCookies) {
                result.success = true
                result.credentials.cookie = allCookies
                sendCompletion(result)
                setTimeout(() => {
                  LoginWebView.close()
                }, 1000)
              }
            }
          } catch {
            console.error("Failed to read IBKR cookies")
          }
        }, 500)
      }
    })

    await LoginWebView.addListener("closed", () => {
      if (!result.success) {
        sendCompletion(result)
      }
    })

    // Build auto-fill script if credentials provided
    let injectScript: string | undefined
    if (request.credentials?.user && request.credentials?.password) {
      const user = JSON.stringify(request.credentials.user)
      const password = JSON.stringify(request.credentials.password)
      injectScript = `
        (function() {
          function tryFill() {
            var u = document.getElementById('xyz-field-username');
            var p = document.getElementById('xyz-field-password');
            if (u && p) {
              u.focus(); u.value = ${user};
              u.dispatchEvent(new Event('input', {bubbles: true}));
              p.focus(); p.value = ${password};
              p.dispatchEvent(new Event('input', {bubbles: true}));
            } else {
              setTimeout(tryFill, 500);
            }
          }
          setTimeout(tryFill, 500);
        })();
      `
    }

    await LoginWebView.open({
      url: `${IBKR_URL}/portal/`,
      title: "Interactive Brokers",
      clearSession: false,
      interceptUrlPatterns: [
        "/sso/Authenticator",
        "/AccountManagement/OneBarAuthentication",
      ],
      injectScript,
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open IBKR login:", error)
    return { success: false }
  }
}
