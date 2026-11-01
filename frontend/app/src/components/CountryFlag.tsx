import { Globe } from "lucide-react"
import {
  AT,
  BE,
  BG,
  CY,
  CZ,
  DE,
  DK,
  EE,
  ES,
  FI,
  FR,
  GB,
  GR,
  HR,
  HU,
  IE,
  IS,
  IT,
  LI,
  LT,
  LU,
  LV,
  MT,
  NL,
  NO,
  PL,
  PT,
  RO,
  SE,
  SI,
  SK,
} from "country-flag-icons/react/3x2"
import {
  OTHER_COUNTRY_CODE,
  type AvailableCountry,
} from "@/constants/countries"

const COUNTRY_FLAG_COMPONENTS = {
  AT,
  BE,
  BG,
  CY,
  CZ,
  DE,
  DK,
  EE,
  ES,
  FI,
  FR,
  GB,
  GR,
  HR,
  HU,
  IE,
  IS,
  IT,
  LI,
  LT,
  LU,
  LV,
  MT,
  NL,
  NO,
  PL,
  PT,
  RO,
  SE,
  SI,
  SK,
} satisfies Record<
  Exclude<AvailableCountry, typeof OTHER_COUNTRY_CODE>,
  typeof AT
>

interface CountryFlagProps {
  code: string
  className?: string
}

function isCountryFlagCode(
  code: string,
): code is keyof typeof COUNTRY_FLAG_COMPONENTS {
  return Object.prototype.hasOwnProperty.call(COUNTRY_FLAG_COMPONENTS, code)
}

export function CountryFlag({ code, className }: CountryFlagProps) {
  const Flag = isCountryFlagCode(code)
    ? COUNTRY_FLAG_COMPONENTS[code]
    : undefined

  return (
    <span
      className={`inline-flex items-center justify-center overflow-hidden rounded-sm ${className ?? ""}`}
    >
      {Flag ? (
        <Flag className="h-full w-full" aria-hidden="true" />
      ) : (
        <Globe className="h-4 w-4" aria-hidden="true" />
      )}
    </span>
  )
}
