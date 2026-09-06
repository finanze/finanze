import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/platform", () => ({
  isNativeMobile: () => false,
}))

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: vi.fn(),
    set: vi.fn(),
  },
}))

const TELEMETRY_CONSENT_KEY = "telemetry_consent"

async function importConsent() {
  vi.resetModules()
  return await import("@/lib/telemetry/consent")
}

describe("telemetry consent store", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("defaults to everything disabled and creates an install id", async () => {
    const { loadConsent } = await importConsent()

    const consent = await loadConsent()

    expect(consent.errorReporting).toBe(false)
    expect(consent.installId).toBeTruthy()
    expect(localStorage.getItem(TELEMETRY_CONSENT_KEY)).toContain(
      consent.installId,
    )
  })

  it("keeps the install id when saving", async () => {
    const { loadConsent, saveConsent } = await importConsent()

    const initial = await loadConsent()
    const saved = await saveConsent({
      errorReporting: true,
    })

    expect(saved.installId).toBe(initial.installId)
    expect(saved.errorReporting).toBe(true)
  })

  it("recovers from a corrupt stored value", async () => {
    localStorage.setItem(TELEMETRY_CONSENT_KEY, "not-json")
    const { loadConsent } = await importConsent()

    const consent = await loadConsent()

    expect(consent.errorReporting).toBe(false)
    expect(consent.installId).toBeTruthy()
  })
})
