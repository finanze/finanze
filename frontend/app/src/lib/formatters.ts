import { ExchangeRates } from "@/types"
import { convertCurrency } from "@/utils/financialDataUtils"

export const formatCurrency = (
  value: number,
  locale: string,
  defaultCurrency: string,
  currencyCode?: string,
): string => {
  const displayCurrency = (currencyCode || defaultCurrency)?.toUpperCase()
  const formatCurrencyValue = (currency: string) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
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
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
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

export const formatNumber = (value: number, locale: string): string => {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(value)
}

export const formatDate = (
  dateInput: string | null | undefined,
  locale: string,
): string => {
  if (!dateInput) {
    return "—"
  }

  const date = new Date(dateInput)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date)
}

export const formatGainLoss = (
  value: number,
  locale: string,
  currency: string,
): string => {
  const formatted = formatCurrency(Math.abs(value), locale, currency)
  return value >= 0 ? `+${formatted}` : `-${formatted}`
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
