import { Preferences } from "@capacitor/preferences"

import { isNativeMobile } from "@/lib/platform"
import { randomUuid } from "@/lib/telemetry/uuid"

export const TELEMETRY_CONSENT_KEY = "telemetry_consent"

export interface TelemetryConsent {
  errorReporting: boolean
  installId: string
}

let cached: TelemetryConsent | null = null

function defaultConsent(): TelemetryConsent {
  return {
    errorReporting: false,
    installId: randomUuid(),
  }
}

function parse(raw: string | null): TelemetryConsent | null {
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed !== "object" || parsed === null) return null

    return {
      errorReporting: parsed.errorReporting === true,
      installId:
        typeof parsed.installId === "string" && parsed.installId
          ? parsed.installId
          : randomUuid(),
    }
  } catch {
    return null
  }
}

async function readRaw(): Promise<string | null> {
  if (isNativeMobile()) {
    const { value } = await Preferences.get({ key: TELEMETRY_CONSENT_KEY })
    return value
  }

  return localStorage.getItem(TELEMETRY_CONSENT_KEY)
}

async function writeRaw(raw: string): Promise<void> {
  if (isNativeMobile()) {
    await Preferences.set({ key: TELEMETRY_CONSENT_KEY, value: raw })
    return
  }

  localStorage.setItem(TELEMETRY_CONSENT_KEY, raw)
}

export async function loadConsent(): Promise<TelemetryConsent> {
  if (cached) return cached

  const stored = parse(await readRaw())
  if (stored) {
    cached = stored
    return stored
  }

  const created = defaultConsent()
  await writeRaw(JSON.stringify(created))
  cached = created
  return created
}

export async function saveConsent(
  consent: Omit<TelemetryConsent, "installId">,
): Promise<TelemetryConsent> {
  const current = await loadConsent()
  const updated: TelemetryConsent = {
    errorReporting: consent.errorReporting,
    installId: current.installId,
  }

  await writeRaw(JSON.stringify(updated))
  cached = updated
  return updated
}

export function getCachedConsent(): TelemetryConsent | null {
  return cached
}
