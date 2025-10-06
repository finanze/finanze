import { format } from "date-fns"

export const generateLocalId = () => {
  const cryptoImpl = globalThis.crypto as Crypto | undefined
  if (cryptoImpl?.randomUUID) {
    return cryptoImpl.randomUUID()
  }
  return `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const parseNumberInput = (value: string): number | null => {
  if (typeof value !== "string") return null
  const trimmed = value.replace(/\s+/g, "").replace(",", ".")
  if (trimmed === "") return null
  const parsed = Number.parseFloat(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export const parseIntegerInput = (value: string): number | null => {
  if (typeof value !== "string") return null
  const trimmed = value.replace(/\s+/g, "")
  if (trimmed === "") return null
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isFinite(parsed) ? parsed : null
}

export const formatNumberInput = (
  value: number | null | undefined,
  options?: { maximumFractionDigits?: number; minimumFractionDigits?: number },
) => {
  if (value === null || value === undefined || Number.isNaN(value)) return ""
  if (!options) return `${value}`
  return value.toLocaleString(undefined, {
    useGrouping: false,
    maximumFractionDigits: options.maximumFractionDigits ?? 6,
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
  })
}

export const normalizeDateInput = (value: string) => {
  if (!value) return ""
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ""
  return format(parsed, "yyyy-MM-dd")
}
