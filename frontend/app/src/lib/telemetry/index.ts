import { BS_ENVIRONMENT, BS_FRONTEND_TOKEN } from "@/env"
import { getApiClient } from "@/services/apiClient"

import { isTagLoaded, loadTag } from "./betterstackTag"
import { loadConsent, saveConsent, type TelemetryConsent } from "./consent"

export type { TelemetryConsent } from "./consent"
export { getCachedConsent, loadConsent } from "./consent"
export { reportError } from "./betterstackTag"

function applyConsent(consent: TelemetryConsent): void {
  if (!consent.errorReporting || isTagLoaded()) return

  loadTag({
    token: BS_FRONTEND_TOKEN,
    environment: BS_ENVIRONMENT,
    release: __APP_VERSION__,
    sessionReplay: consent.sessionReplay,
    installId: consent.installId,
  })
}

async function propagateConsent(consent: TelemetryConsent): Promise<void> {
  const payload = {
    errorReporting: consent.errorReporting,
    sessionReplay: consent.sessionReplay,
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
  applyConsent(consent)
  return consent
}

export async function updateTelemetryConsent(consent: {
  errorReporting: boolean
  sessionReplay: boolean
}): Promise<TelemetryConsent> {
  const saved = await saveConsent(consent)

  await propagateConsent(saved)
  applyConsent(saved)

  return saved
}

export function requiresRestartToDisable(consent: TelemetryConsent): boolean {
  return !consent.errorReporting && isTagLoaded()
}
