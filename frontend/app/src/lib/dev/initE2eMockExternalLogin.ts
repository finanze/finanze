import { setMobileLoginAPI } from "@/lib/externalLogin"
import type { ExternalLoginAPI, LoginHandlerResult } from "@/lib/externalLogin"

const MOCK_INTERNAL_CREDENTIALS: Record<string, Record<string, string>> = {
  // Trade Republic — only awsWafToken is internal
  "e0000000-0000-0000-0000-000000000003": { awsWafToken: "mock-waf-token" },
  // Unicaja — abck cookie is internal
  "e0000000-0000-0000-0000-000000000002": { abck: "mock-abck-cookie" },
  // ING — all 5 credentials are internal
  "e0000000-0000-0000-0000-000000000010": {
    genomaCookie: "mock-genoma-cookie",
    genomaSessionId: "mock-genoma-session",
    apiCookie: "mock-api-cookie",
    apiAuth: "mock-api-auth",
    apiExtendedSessionCtx: "mock-api-extended-session",
  },
  // Mintos — cookie is internal
  "e0000000-0000-0000-0000-000000000007": { cookie: "mock-mintos-cookie" },
  // IBKR — cookie is internal
  "e0000000-0000-0000-0000-000000000013": { cookie: "mock-ibkr-cookie" },
}

export function initE2eMockExternalLogin() {
  if (!import.meta.env.DEV) return
  if (!import.meta.env.VITE_E2E_MOCK_LOGIN) return

  let completionCallback:
    | ((id: string, result: LoginHandlerResult) => void)
    | null = null

  const mockAPI: ExternalLoginAPI = {
    requestExternalLogin: (id, request) => {
      const internalCreds = MOCK_INTERNAL_CREDENTIALS[id] || {}
      const mergedCredentials = {
        ...(request?.credentials || {}),
        ...internalCreds,
      }

      const result: LoginHandlerResult = {
        success: true,
        credentials: mergedCredentials,
        flow: request?.flow,
      }

      // Read completionCallback at fire time (not capture time) so React's
      // useEffect has a chance to re-register with the correct selectedEntity closure.
      setTimeout(() => {
        completionCallback?.(id, result)
      }, 500)

      return Promise.resolve({ success: true })
    },

    onCompletedExternalLogin: callback => {
      completionCallback = callback
      return () => {
        completionCallback = null
      }
    },
  }

  setMobileLoginAPI(mockAPI)

  // Expose toggle for e2e tests that need to verify the "requires app" error
  ;(window as any).__e2eDisableMockExternalLogin = () => {
    setMobileLoginAPI(null)
  }
  ;(window as any).__e2eEnableMockExternalLogin = () => {
    setMobileLoginAPI(mockAPI)
  }

  console.log("[Dev] E2E mock external login API registered")
}
