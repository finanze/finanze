import { FFStatus, type FeatureFlags } from "@/types"
import { isElectron, isNativeMobile } from "@/lib/platform"

export const RESTRICTED_COUNTRIES_FLAG = "RESTRICTED_COUNTRIES"

const RESTRICTED_COUNTRY_CODES = new Set(["GB", "IE"])

// Matched by IANA ID only: Lisbon, Canary, Madeira share London's offset and DST.
const RESTRICTED_TIMEZONES = new Set([
  "Europe/London",
  "Europe/Belfast",
  "Europe/Dublin",
  "GB",
  "GB-Eire",
  "Eire",
])

let countryCodesPromise: Promise<string[]> | null = null

export function isRegionCheckEnabled(flags: FeatureFlags): boolean {
  return flags?.[RESTRICTED_COUNTRIES_FLAG] === FFStatus.ON
}

export function getDeviceTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}

export function isRestrictedTimezone(timezone: string | null): boolean {
  return !!timezone && RESTRICTED_TIMEZONES.has(timezone)
}

export function isRestrictedCountry(countryCodes: string[]): boolean {
  return countryCodes.some(code => RESTRICTED_COUNTRY_CODES.has(code))
}

export function isRegionRestricted(
  flags: FeatureFlags,
  timezone: string | null,
  countryCodes: string[],
): boolean {
  return (
    isRegionCheckEnabled(flags) &&
    isRestrictedTimezone(timezone) &&
    isRestrictedCountry(countryCodes)
  )
}

function normalizeCountryCode(code: unknown): string | null {
  if (typeof code !== "string") return null
  const value = code.trim().toUpperCase()
  return /^[A-Z]{2}$/.test(value) ? value : null
}

function compactCodes(codes: unknown[]): string[] {
  return codes
    .map(normalizeCountryCode)
    .filter((code): code is string => code !== null)
}

function readLanguageCountryCodes(): string[] {
  if (typeof navigator === "undefined" || !navigator.language) return []
  try {
    return compactCodes([new Intl.Locale(navigator.language).region])
  } catch {
    return compactCodes([navigator.language.split(/[-_]/)[1]])
  }
}

async function readNativeCountryCodes(): Promise<string[]> {
  if (!__MOBILE__) return []
  const { DeviceCountry } = await import("@/lib/capacitor/plugins")
  const result = await DeviceCountry.getCountryCodes()
  return compactCodes([
    result.network,
    result.sim,
    result.locale,
    result.region,
  ])
}

async function readElectronCountryCodes(): Promise<string[]> {
  const code = await window.ipcAPI?.getLocaleCountryCode?.()
  return compactCodes([code])
}

async function readPlatformCountryCodes(): Promise<string[]> {
  try {
    if (isNativeMobile()) return await readNativeCountryCodes()
    if (isElectron()) return await readElectronCountryCodes()
  } catch (error) {
    console.error("Failed to read device country:", error)
  }
  return []
}

export function getDeviceCountryCodes(): Promise<string[]> {
  if (!countryCodesPromise) {
    countryCodesPromise = readPlatformCountryCodes().then(codes =>
      codes.length > 0 ? codes : readLanguageCountryCodes(),
    )
  }
  return countryCodesPromise
}

export async function isDeviceInRestrictedRegion(
  flags: FeatureFlags,
): Promise<boolean> {
  if (!isRegionCheckEnabled(flags)) return false
  const timezone = getDeviceTimezone()
  if (!isRestrictedTimezone(timezone)) return false
  try {
    return isRegionRestricted(flags, timezone, await getDeviceCountryCodes())
  } catch {
    return false
  }
}

export function resetDeviceCountryCache(): void {
  countryCodesPromise = null
}
