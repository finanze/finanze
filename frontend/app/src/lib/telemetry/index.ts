import { getApiClient } from "@/services/apiClient"

import { loadConsent, saveConsent, type TelemetryConsent } from "./consent"
import {
  initRendererTelemetry,
  reportError,
  setTelemetryContext,
} from "./renderer"

export type { TelemetryConsent } from "./consent"
export { getCachedConsent, loadConsent } from "./consent"
export { reportError, setTelemetryContext }

async function propagateConsent(consent: TelemetryConsent): Promise<void> {
  const payload = {
    errorReporting: consent.errorReporting,
  }

  try {
    const client = await getApiClient()
    await client.post("/telemetry/consent", payload)
  } catch {
    // Backend may be unreachable; the device level consent is still stored.
  }

  try {
    await window.ipcAPI?.setTelemetryConsent?.({
      ...payload,
      installId: consent.installId,
    })
  } catch {
    // Not running under Electron.
  }
}

export async function initTelemetry(): Promise<TelemetryConsent> {
  const consent = await loadConsent()
  await initRendererTelemetry()
  return consent
}

export async function updateTelemetryConsent(consent: {
  errorReporting: boolean
}): Promise<TelemetryConsent> {
  const saved = await saveConsent(consent)

  await propagateConsent(saved)

  return saved
}
