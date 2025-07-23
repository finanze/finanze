import { ExchangeRates } from "@/types"
import { convertCurrency } from "@/utils/financialDataUtils"

export const formatCurrency = (
  value: number,
  locale: string,
  defaultCurrency: string,
  currencyCode?: string,
): string => {
  const displayCurrency = currencyCode || defaultCurrency
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: displayCurrency,
    minimumFractionDigits: 2,
  }).format(value)
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

export const formatDate = (dateString: string, locale: string): string => {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(dateString))
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
