import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"
import { FFStatus } from "@/types"

const platform = vi.hoisted(() => ({ electron: false }))

vi.mock("@/lib/platform", () => ({
  isNativeMobile: () => false,
  isElectron: () => platform.electron,
}))

const FLAG_ON = { RESTRICTED_COUNTRIES: FFStatus.ON }

function mockTimezone(timeZone: string) {
  vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
    timeZone,
  } as Intl.ResolvedDateTimeFormatOptions)
}

function mockLanguage(language: string) {
  vi.spyOn(navigator, "language", "get").mockReturnValue(language)
}

async function importModule() {
  vi.resetModules()
  return await import("@/lib/regionRestriction")
}

describe("isRegionRestricted", () => {
  it.each([
    [{}, "Europe/London", ["GB"]],
    [{ RESTRICTED_COUNTRIES: FFStatus.OFF }, "Europe/London", ["GB"]],
    [FLAG_ON, "Europe/Madrid", ["GB"]],
    [FLAG_ON, "Europe/London", ["ES"]],
    [FLAG_ON, "Europe/London", []],
    [FLAG_ON, null, ["GB"]],
  ])("allows flags=%o tz=%s countries=%o", async (flags, tz, codes) => {
    const { isRegionRestricted } = await importModule()
    expect(isRegionRestricted(flags, tz, codes)).toBe(false)
  })

  it.each([
    ["Europe/London", ["GB"]],
    ["Europe/Belfast", ["GB"]],
    ["Europe/Dublin", ["IE"]],
    ["Europe/London", ["ES", "GB"]],
  ])("restricts tz=%s countries=%o", async (tz, codes) => {
    const { isRegionRestricted } = await importModule()
    expect(isRegionRestricted(FLAG_ON, tz, codes)).toBe(true)
  })

  it.each([
    "Europe/Lisbon",
    "Atlantic/Canary",
    "Atlantic/Madeira",
    "Atlantic/Azores",
    "Etc/GMT",
    "UTC",
  ])("never restricts same-offset timezone %s", async tz => {
    const { isRegionRestricted } = await importModule()
    expect(isRegionRestricted(FLAG_ON, tz, ["GB", "IE"])).toBe(false)
  })
})

describe("isDeviceInRestrictedRegion", () => {
  beforeEach(() => {
    platform.electron = false
  })

  afterEach(() => {
    vi.restoreAllMocks()
    delete (window as { ipcAPI?: unknown }).ipcAPI
  })

  it("is not restricted when the flag is missing", async () => {
    mockTimezone("Europe/London")
    mockLanguage("en-GB")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion({})).toBe(false)
  })

  it("uses the language region on web", async () => {
    mockTimezone("Europe/London")
    mockLanguage("en-GB")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(true)
  })

  it("is not restricted with UK language outside UK timezone", async () => {
    mockTimezone("Europe/Madrid")
    mockLanguage("en-GB")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(false)
  })

  it("prefers the Electron OS country over the language", async () => {
    platform.electron = true
    ;(window as any).ipcAPI = {
      getLocaleCountryCode: vi.fn().mockResolvedValue("es"),
    }
    mockTimezone("Europe/London")
    mockLanguage("en-GB")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(false)
  })

  it("falls back to the language when Electron country lookup fails", async () => {
    platform.electron = true
    ;(window as any).ipcAPI = {
      getLocaleCountryCode: vi.fn().mockRejectedValue(new Error("boom")),
    }
    vi.spyOn(console, "error").mockImplementation(() => {})
    mockTimezone("Europe/Dublin")
    mockLanguage("ga-IE")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(true)
  })

  it("is not restricted when the timezone cannot be read", async () => {
    vi.spyOn(
      Intl.DateTimeFormat.prototype,
      "resolvedOptions",
    ).mockImplementation(() => {
      throw new Error("unsupported")
    })
    mockLanguage("en-GB")
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(false)
  })
})

describe("useRegionRestriction", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("reacts to the feature flag being enabled after startup", async () => {
    mockTimezone("Europe/London")
    mockLanguage("en-GB")
    vi.resetModules()
    const { setFeatureFlags } = await import("@/context/featureFlagsStore")
    const { useRegionRestriction } =
      await import("@/hooks/useRegionRestriction")
    setFeatureFlags({})

    const { result } = renderHook(() => useRegionRestriction())
    expect(result.current).toBe(false)

    act(() => setFeatureFlags(FLAG_ON))

    await waitFor(() => expect(result.current).toBe(true))
  })
})
