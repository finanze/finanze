// Country codes supported by financial institutions integrations.
export const AVAILABLE_COUNTRIES = [
  "AT", // Austria
  "BE", // Belgium
  "BG", // Bulgaria
  "CY", // Cyprus
  "CZ", // Czech Republic
  "DE", // Germany
  "DK", // Denmark
  "EE", // Estonia
  "ES", // Spain
  "FI", // Finland
  "FR", // France
  "GB", // United Kingdom
  "GR", // Greece
  "HR", // Croatia
  "HU", // Hungary
  "IE", // Ireland
  "IS", // Iceland
  "IT", // Italy
  "LI", // Liechtenstein
  "LT", // Lithuania
  "LU", // Luxembourg
  "LV", // Latvia
  "MT", // Malta
  "NL", // Netherlands
  "NO", // Norway
  "PL", // Poland
  "PT", // Portugal
  "RO", // Romania
  "SE", // Sweden
  "SI", // Slovenia
  "SK", // Slovakia
  "XX", // Other
] as const

export const OTHER_COUNTRY_CODE = "XX" as const

export type AvailableCountry = (typeof AVAILABLE_COUNTRIES)[number]

export const COUNTRY_FLAGS: Record<AvailableCountry, string> = {
  AT: "🇦🇹",
  BE: "🇧🇪",
  BG: "🇧🇬",
  CY: "🇨🇾",
  CZ: "🇨🇿",
  DE: "🇩🇪",
  DK: "🇩🇰",
  EE: "🇪🇪",
  ES: "🇪🇸",
  FI: "🇫🇮",
  FR: "🇫🇷",
  GB: "🇬🇧",
  GR: "🇬🇷",
  HR: "🇭🇷",
  HU: "🇭🇺",
  IE: "🇮🇪",
  IS: "🇮🇸",
  IT: "🇮🇹",
  LI: "🇱🇮",
  LT: "🇱🇹",
  LU: "🇱🇺",
  LV: "🇱🇻",
  MT: "🇲🇹",
  NL: "🇳🇱",
  NO: "🇳🇴",
  PL: "🇵🇱",
  PT: "🇵🇹",
  RO: "🇷🇴",
  SE: "🇸🇪",
  SI: "🇸🇮",
  SK: "🇸🇰",
  XX: "🌐", // Other
}

export const getCountryFlag = (code: string): string => {
  return COUNTRY_FLAGS[(code as AvailableCountry) || OTHER_COUNTRY_CODE] || "🌐"
}

export interface CountryOption {
  code: AvailableCountry
  flag: string
}

export const COUNTRY_OPTIONS: CountryOption[] = AVAILABLE_COUNTRIES.map(c => ({
  code: c,
  flag: COUNTRY_FLAGS[c],
}))

export const buildCountrySelectOptions = <T extends string | number = string>(
  resolveLabel: (code: AvailableCountry) => string,
  valueMapper?: (code: AvailableCountry) => T,
) => {
  return AVAILABLE_COUNTRIES.map(code => ({
    code,
    value: (valueMapper ? valueMapper(code) : code) as T,
    label: resolveLabel(code),
    flag: COUNTRY_FLAGS[code],
  }))
}
