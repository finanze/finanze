import { BS_ENVIRONMENT, BS_MOBILE_BACKEND_DSN } from "@/env"
import { appConsole } from "@/lib/capacitor/appConsole"
import { loadConsent } from "@/lib/telemetry/consent"
import {
  buildEvent,
  sendEvent,
  type SentryExceptionPayload,
  type SentryOsContext,
} from "@/lib/telemetry/sentryEnvelope"

async function capture(payload: string): Promise<void> {
  if (!BS_MOBILE_BACKEND_DSN) return

  try {
    const consent = await loadConsent()
    if (!consent.errorReporting) return

    const parsed = JSON.parse(payload) as SentryExceptionPayload & {
      release?: string
      user_id?: string
      os?: SentryOsContext | null
    }

    const event = buildEvent(parsed, {
      platform: "python",
      environment: BS_ENVIRONMENT,
      release: parsed.release,
      installId: consent.installId,
      userId: parsed.user_id,
      osContext: parsed.os ?? undefined,
    })

    await sendEvent(BS_MOBILE_BACKEND_DSN, event)
  } catch (error) {
    appConsole.debug("[Telemetry] Failed to report backend error", error)
  }
}

export const telemetryBridge = {
  capture,
  environment: BS_ENVIRONMENT,
}
