import type { LoginHandlerResult } from "@/lib/externalLogin"

export interface ExternalLoginRequestResult {
  success: boolean
}

export interface ExternalLoginRequest {
  credentials?: Record<string, string>
}

export type { LoginHandlerResult }
