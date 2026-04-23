import type { LoginHandlerResult } from "@/lib/externalLogin"

export interface ExternalLoginRequestResult {
  success: boolean
}

export interface ExternalLoginRequest {
  credentials?: Record<string, string>
  flow?: "login" | "fetch"
}

export type { LoginHandlerResult }
