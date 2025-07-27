import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getCurrencySymbol(currency: string): string {
  switch (currency) {
    case "EUR":
      return "€"
    case "USD":
      return "$"
    case "GBP":
      return "£"
    case "JPY":
      return "¥"
    case "CNY":
      return "¥"
    case "CAD":
      return "C$"
    case "AUD":
      return "A$"
    case "CHF":
      return "CHF"
    case "SEK":
      return "kr"
    case "NOK":
      return "kr"
    case "DKK":
      return "kr"
    default:
      return currency
  }
}
