import { LoginWebView } from "../loginWebView"
import { emitCompletion } from "."
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

export const MINTOS_ID = "e0000000-0000-0000-0000-000000000007"

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
    console.debug("Sending completion for Mintos:", MINTOS_ID)
    emitCompletion(MINTOS_ID, r)
    LoginWebView.removeAllListeners()
  }

  try {
    await LoginWebView.addListener("requestIntercepted", async data => {
      if (data.url.includes("/api/auth/login")) {
        try {
          const domResult = await LoginWebView.executeScript({
            code: `JSON.stringify({ user: document.querySelector('#login-username')?.value || '', password: document.querySelector('#login-password')?.value || '' })`,
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
      if (data.url.includes("/webapp-api/user")) {
        try {
          const cookies = await LoginWebView.getCookies({
            url: "https://www.mintos.com",
          })
          if (cookies.raw) {
            result.success = true
            result.credentials.cookie = cookies.raw

            if (!result.credentials.user) {
              // User not captured yet — clear and reload to force fresh login
              await LoginWebView.clearData()
              await LoginWebView.reload()
              result.success = false
              return
            }

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

    // Build auto-fill script if credentials provided
    let injectScript: string | undefined
    if (request.credentials?.user && request.credentials?.password) {
      const user = JSON.stringify(request.credentials.user)
      const password = JSON.stringify(request.credentials.password)
      injectScript = `
        (function() {
          function tryFill() {
            var u = document.getElementById('login-username');
            var p = document.getElementById('login-password');
            if (u && p) {
              u.focus(); u.value = ${user};
              u.dispatchEvent(new Event('input', {bubbles: true}));
              p.focus(); p.value = ${password};
              p.dispatchEvent(new Event('input', {bubbles: true}));
            } else {
              setTimeout(tryFill, 500);
            }
          }
          if (document.readyState === 'complete') tryFill();
          else window.addEventListener('load', tryFill);
        })();
      `
    }

    await LoginWebView.open({
      url: "https://www.mintos.com/en/login",
      title: "Mintos",
      clearSession: false,
      interceptUrlPatterns: ["/api/auth/login", "/webapp-api/user"],
      injectScript,
    })

    return { success: true }
  } catch (error) {
    console.error("Failed to open Mintos login:", error)
    return { success: false }
  }
}
