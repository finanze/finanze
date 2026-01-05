export const ASSET_TYPE_COLOR_MAP: Record<string, string> = {
  STOCK_ETF: "#3b82f6",
  FUND: "#06b6d4",
  REAL_ESTATE_CF: "#10b981",
  REAL_ESTATE: "#059669",
  FACTORING: "#f59e0b",
  DEPOSIT: "#8b5cf6",
  CASH: "#6b7280",
  ACCOUNT: "#6b7280",
  CROWDLENDING: "#ec4899",
  CRYPTO: "#f97316",
  COMMODITY: "#eab308",
  PENDING_FLOWS: "#14b8a6",
}

// Palette mirrors frontend getColorForName (blue/green/yellow/red/purple/pink/indigo/teal)
export const ENTITY_COLOR_PALETTE: string[] = [
  "#3b82f6",
  "#10b981",
  "#eab308",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#6366f1",
  "#14b8a6",
]

export function hashNameToIndex(name?: string, modulo: number = 1): number {
  if (!name) return 0

  let hash = 0
  for (let i = 0; i < name.length; i++) {
    const char = name.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash = hash & hash
  }

  return modulo > 0 ? Math.abs(hash) % modulo : 0
}

export function getDeterministicColor(
  name: string | undefined,
  palette: string[],
): string {
  if (!palette.length) return "#6b7280"
  const idx = hashNameToIndex(name, palette.length)
  return palette[idx]
}
