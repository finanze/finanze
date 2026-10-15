import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { createElement } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react"
import { FFStatus, type FeatureFlags } from "@/types"

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
    const debug = vi.spyOn(console, "debug").mockImplementation(() => {})
    const { isDeviceInRestrictedRegion } = await importModule()

    expect(await isDeviceInRestrictedRegion(FLAG_ON)).toBe(false)
    expect(debug).toHaveBeenCalledWith(
      "[RegionRestriction] Detected device region",
      {
        countryCodes: ["GB"],
        timezone: "Europe/Madrid",
        restricted: false,
      },
    )
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
  async function setupPendingRegionCheck(flags: FeatureFlags = {}) {
    mockTimezone("Europe/London")
    mockLanguage("en-GB")
    platform.electron = true
    const countryCode = Promise.withResolvers<string>()
    const getLocaleCountryCode = vi.fn(() => countryCode.promise)
    ;(window as any).ipcAPI = { getLocaleCountryCode }
    vi.resetModules()
    const { setFeatureFlags } = await import("@/context/featureFlagsStore")
    const { useRegionRestriction } =
      await import("@/hooks/useRegionRestriction")
    setFeatureFlags(flags)
    return {
      countryCode,
      getLocaleCountryCode,
      setFeatureFlags,
      useRegionRestriction,
    }
  }

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    platform.electron = false
    delete (window as { ipcAPI?: unknown }).ipcAPI
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

  it("preserves the login input while a late region check resolves", async () => {
    const {
      countryCode,
      getLocaleCountryCode,
      setFeatureFlags,
      useRegionRestriction,
    } = await setupPendingRegionCheck()

    function LoginGate() {
      const restricted = useRegionRestriction()
      if (restricted === null) return createElement("div", null, "Checking")
      if (restricted) return createElement("div", null, "Restricted")
      return createElement("input", {
        type: "password",
        "aria-label": "Encryption key",
      })
    }

    render(createElement(LoginGate))
    const input = screen.getByLabelText("Encryption key")
    fireEvent.change(input, { target: { value: "typed-password" } })
    expect(getLocaleCountryCode).not.toHaveBeenCalled()

    act(() => setFeatureFlags(FLAG_ON))

    expect(screen.getByLabelText("Encryption key")).toBe(input)
    expect(input).toHaveValue("typed-password")

    await act(async () => countryCode.resolve("ES"))

    expect(screen.getByLabelText("Encryption key")).toBe(input)
    expect(input).toHaveValue("typed-password")
  })

  it("still restricts the device after a late check confirms its country", async () => {
    const { countryCode, setFeatureFlags, useRegionRestriction } =
      await setupPendingRegionCheck()
    const { result } = renderHook(() => useRegionRestriction())

    act(() => setFeatureFlags(FLAG_ON))

    expect(result.current).toBe(false)

    await act(async () => countryCode.resolve("GB"))

    expect(result.current).toBe(true)
  })

  it.each(["GB", "ES"])(
    "waits for country %s when the flag is enabled on initial mount",
    async country => {
      const { countryCode, useRegionRestriction } =
        await setupPendingRegionCheck(FLAG_ON)
      const { result } = renderHook(() => useRegionRestriction())

      expect(result.current).toBeNull()

      await act(async () => countryCode.resolve(country))

      expect(result.current).toBe(country === "GB")
    },
  )

  it("ignores a pending restriction result after the flag is disabled", async () => {
    const { countryCode, setFeatureFlags, useRegionRestriction } =
      await setupPendingRegionCheck(FLAG_ON)
    const { result } = renderHook(() => useRegionRestriction())
    expect(result.current).toBeNull()

    act(() => setFeatureFlags({ RESTRICTED_COUNTRIES: FFStatus.OFF }))

    expect(result.current).toBe(false)

    await act(async () => countryCode.resolve("GB"))

    expect(result.current).toBe(false)
  })

  it("clears a previous restriction before checking a re-enabled flag", async () => {
    const { countryCode, setFeatureFlags, useRegionRestriction } =
      await setupPendingRegionCheck(FLAG_ON)
    const { result } = renderHook(() => useRegionRestriction())

    await act(async () => countryCode.resolve("GB"))

    expect(result.current).toBe(true)

    act(() => setFeatureFlags({ RESTRICTED_COUNTRIES: FFStatus.OFF }))

    expect(result.current).toBe(false)

    act(() => setFeatureFlags(FLAG_ON))

    expect(result.current).toBe(false)

    await waitFor(() => expect(result.current).toBe(true))
  })

  it("allows access when the country lookup fails without a fallback region", async () => {
    const { countryCode, useRegionRestriction } =
      await setupPendingRegionCheck(FLAG_ON)
    mockLanguage("en")
    vi.spyOn(console, "error").mockImplementation(() => {})
    const { result } = renderHook(() => useRegionRestriction())
    expect(result.current).toBeNull()

    await act(async () => countryCode.reject(new Error("Country unavailable")))

    expect(result.current).toBe(false)
  })
})
