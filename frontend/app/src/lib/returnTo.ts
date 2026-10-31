export interface ReturnTo {
  path: string
  label: string
}

export function readReturnTo(state: unknown): ReturnTo | null {
  if (!state || typeof state !== "object") return null
  const returnTo = (state as { returnTo?: unknown }).returnTo
  if (!returnTo || typeof returnTo !== "object") return null
  const { path, label } = returnTo as Record<string, unknown>
  if (typeof path !== "string" || typeof label !== "string") return null
  if (!path.startsWith("/") || path.startsWith("//")) return null
  return { path, label }
}

export const returnScrollKey = (locationKey: string) =>
  `returnScroll:${locationKey}`
