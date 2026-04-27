import { isNativeMobile } from "@/lib/platform"

export interface LoginHandlerResult {
  success: boolean
  credentials: Record<string, string>
  flow?: "login" | "fetch"
}

export interface ExternalLoginAPI {
  requestExternalLogin(
    id: string,
    request?: {
      credentials?: Record<string, string>
      flow?: "login" | "fetch"
    },
  ): Promise<{ success: boolean }>
  onCompletedExternalLogin(
    callback: (id: string, result: LoginHandlerResult) => void,
  ): () => void
}

let mobileLoginAPI: ExternalLoginAPI | null = null

export function getExternalLoginAPI(): ExternalLoginAPI | null {
  if (typeof window !== "undefined" && window.ipcAPI) {
    return {
      requestExternalLogin: (id, request) =>
        window.ipcAPI!.requestExternalLogin(id, request),
      onCompletedExternalLogin: callback => {
        window.ipcAPI!.onCompletedExternalLogin(callback)
        return () => {}
      },
    }
  }

  if (isNativeMobile() || mobileLoginAPI) {
    return mobileLoginAPI
  }

  return null
}

export function setMobileLoginAPI(api: ExternalLoginAPI | null) {
  if (!__CONNECTIONS__) return
  mobileLoginAPI = api
}
