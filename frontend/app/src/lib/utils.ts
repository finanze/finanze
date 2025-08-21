import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getCurrencySymbol(currency: string): string {
  if (!currency) return ""
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

// Deterministic color classes (light/dark) based on a name string
export function getColorForName(name?: string): string {
  if (!name)
    return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"

  // Simple hash function to generate consistent colors for names
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    const char = name.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash // Convert to 32-bit integer
  }

  // Palette mirrors TransactionsPage.getEntityColor for consistency
  const colors = [
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100",
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100",
    "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-100",
    "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100",
    "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100",
  ]

  const colorIndex = Math.abs(hash) % colors.length
  return colors[colorIndex]
}
