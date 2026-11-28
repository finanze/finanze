import { ExchangeRates } from "@/types"
import { convertCurrency } from "@/utils/financialDataUtils"

export const formatCurrency = (
  value: number,
  locale: string,
  defaultCurrency: string,
  currencyCode?: string,
  options?: {
    narrowSymbol?: boolean
    minimumFractionDigits?: number
    maximumFractionDigits?: number
  },
): string => {
  const displayCurrency = (currencyCode || defaultCurrency)?.toUpperCase()
  const formatCurrencyValue = (currency: string) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: options?.minimumFractionDigits ?? 2,
      maximumFractionDigits: options?.maximumFractionDigits ?? 2,
      ...(options?.narrowSymbol && { currencyDisplay: "narrowSymbol" }),
    }).format(value)

  try {
    if (displayCurrency) {
      return formatCurrencyValue(displayCurrency)
    }
  } catch (error) {
    if (!(error instanceof RangeError)) {
      throw error
    }
  }

  const formattedNumber = new Intl.NumberFormat(locale, {
    minimumFractionDigits: options?.minimumFractionDigits ?? 2,
    maximumFractionDigits: options?.maximumFractionDigits ?? 2,
  }).format(value)

  return displayCurrency
    ? `${formattedNumber} ${displayCurrency}`
    : formattedNumber
}

export const formatPercentage = (value: number, locale: string): string => {
  return new Intl.NumberFormat(locale, {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(value / 100)
}

// Lowercases a label so it can be used mid-sentence. German capitalizes nouns,
// so labels keep their casing there.
export const lowercaseLabel = (label: string, locale?: string): string =>
  locale?.startsWith("de") ? label : label.toLowerCase()

export const formatNumber = (value: number, locale: string): string => {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(value)
}

export const formatIban = (iban?: string | null, reveal?: boolean) => {
  if (!iban) return null
  if (reveal) {
    return iban.replace(/(.{4})/g, "$1 ").trim()
  }
  return `•••• •••• •••• ${iban.slice(-4)}`
}

export const shortIban = (iban: string) => `•• ${iban.slice(-4)}`

export const formatDate = (
  dateInput: string | Date | null | undefined,
  locale: string,
  options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  },
): string => {
  if (!dateInput) {
    return "—"
  }

  const date = dateInput instanceof Date ? dateInput : new Date(dateInput)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }

  if (locale === "pt-PT" && options.month === "short") {
    // Portuguese short-date patterns use numeric months, even with month: "short".
    const month = new Intl.DateTimeFormat(locale, {
      month: "short",
      timeZone: options.timeZone,
    }).format(date)
    return new Intl.DateTimeFormat(locale, { ...options, month: "long" })
      .formatToParts(date)
      .map(part =>
        part.type === "month"
          ? month
          : part.type === "literal"
            ? part.value.replaceAll(" de ", " ")
            : part.value,
      )
      .join("")
  }

  return new Intl.DateTimeFormat(locale, options).format(date)
}

export const formatGainLoss = (
  value: number,
  locale: string,
  currency: string,
): string => {
  const formatted = formatCurrency(Math.abs(value), locale, currency)
  return value >= 0 ? `+${formatted}` : `-${formatted}`
}

export const formatCompactCurrency = (
  value: number,
  locale: string,
  currency: string,
): string => {
  const formatter = new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    notation: "compact",
    compactDisplay: "short",
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  })
  return formatter.format(value)
}

export const formatConvertedCurrency = (
  value: number,
  locale: string,
  fromCurrency: string,
  toCurrency: string,
  exchangeRates: ExchangeRates | null,
): string => {
  const convertedValue = convertCurrency(
    value,
    fromCurrency,
    toCurrency,
    exchangeRates,
  )
  return formatCurrency(convertedValue, locale, fromCurrency, toCurrency)
}
