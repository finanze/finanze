const stableVersion = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/
const nextVersion = /^next-(\d+\.\d+\.\d+)-dev\d+-[a-f0-9]+$/

export function isStableVersion(version: string): boolean {
  return stableVersion.test(version)
}

export function getNextBaseVersion(version: string): string | undefined {
  const base = nextVersion.exec(version)?.[1]
  return base && isStableVersion(base) ? base : undefined
}

export function isNewerStableVersion(candidate: string, base: string): boolean {
  if (!isStableVersion(candidate) || !isStableVersion(base)) return false
  const current = base.split(".").map(Number)
  for (const [i, part] of candidate.split(".").map(Number).entries()) {
    if (part !== current[i]) return part > current[i]
  }
  return false
}

export function isNewerMinorOrMajorVersion(
  candidate: string,
  base: string,
): boolean {
  if (!isStableVersion(candidate) || !isStableVersion(base)) return false
  const [candMajor, candMinor] = candidate.split(".").map(Number)
  const [baseMajor, baseMinor] = base.split(".").map(Number)
  return (
    candMajor > baseMajor || (candMajor === baseMajor && candMinor > baseMinor)
  )
}
