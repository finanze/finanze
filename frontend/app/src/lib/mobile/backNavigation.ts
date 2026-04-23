const BACK_NAVIGATION_MAP: Record<string, string> = {
  "/banking": "/investments",
  "/real-estate": "/investments",
}

const BACK_NAVIGATION_PREFIXES = [
  "/investments/",
  "/management/",
  "/real-estate/",
]

export function getBackTarget(pathname: string): string | null {
  if (BACK_NAVIGATION_MAP[pathname]) {
    return BACK_NAVIGATION_MAP[pathname]
  }
  for (const prefix of BACK_NAVIGATION_PREFIXES) {
    if (pathname.startsWith(prefix)) {
      return prefix.slice(0, -1)
    }
  }
  return null
}

export function canNavigateBack(pathname: string): boolean {
  return getBackTarget(pathname) !== null
}
