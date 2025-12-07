import { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"
import { PlatformType } from "@/types"
import { formatDate } from "@/lib/formatters"

export type { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"

const GITHUB_API_URL =
  "https://api.github.com/repos/finanze/finanze/releases/latest"

/**
 * Compares two semantic version strings with prerelease support
 * @param version1 First version (e.g., "1.2.3" or "0.6.0-dev1-xxxx")
 * @param version2 Second version (e.g., "1.2.4" or "0.6.0-dev2-xxxx")
 * @returns 1 if version1 > version2, -1 if version1 < version2, 0 if equal
 *
 * Ordering: v0.6.0-dev1 < v0.6.0-dev2 < v0.7.0 < v1.0.0
 */
export function compareVersions(version1: string, version2: string): number {
  const v1 = parseVersion(version1)
  const v2 = parseVersion(version2)

  const maxCoreLength = Math.max(v1.core.length, v2.core.length, 3)

  for (let i = 0; i < maxCoreLength; i++) {
    const part1 = v1.core[i] ?? 0
    const part2 = v2.core[i] ?? 0

    if (part1 > part2) return 1
    if (part1 < part2) return -1
  }

  const hasPre1 = v1.pre.length > 0
  const hasPre2 = v2.pre.length > 0

  if (!hasPre1 && !hasPre2) {
    return 0
  }

  if (!hasPre1 && hasPre2) {
    return -1
  }

  if (!hasPre2) {
    return 1
  }

  const maxPreLength = Math.max(v1.pre.length, v2.pre.length)

  for (let i = 0; i < maxPreLength; i++) {
    const pre1 = v1.pre[i]
    const pre2 = v2.pre[i]

    if (pre1 === undefined) {
      return -1
    }

    if (pre2 === undefined) {
      return 1
    }

    if (pre1 === pre2) {
      continue
    }

    const isNumeric1 = /^\d+$/.test(pre1)
    const isNumeric2 = /^\d+$/.test(pre2)

    if (isNumeric1 && isNumeric2) {
      const diff = Number(pre1) - Number(pre2)
      if (diff !== 0) {
        return diff > 0 ? 1 : -1
      }
      continue
    }

    if (isNumeric1 !== isNumeric2) {
      return isNumeric1 ? -1 : 1
    }

    const diff = pre1.localeCompare(pre2)
    if (diff !== 0) {
      return diff > 0 ? 1 : -1
    }
  }

  return 0
}

function parseVersion(version: string): { core: number[]; pre: string[] } {
  const normalized = version.trim().replace(/^v/i, "")
  const [corePart, ...preParts] = normalized.split("-")
  const core = corePart
    .split(".")
    .map(part => Number.parseInt(part, 10))
    .filter(Number.isFinite)

  const pre = preParts.map(part => part.toLowerCase())

  return { core, pre }
}

/**
 * Fetches the latest release from GitHub
 */
export async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  try {
    const response = await fetch(GITHUB_API_URL)
    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`)
    }

    const release: GitHubRelease = await response.json()
    return release
  } catch (error) {
    console.error("Error fetching latest release:", error)
    return null
  }
}

/**
 * Checks if there's a new version available
 */
export async function getReleaseUpdateInfo(): Promise<ReleaseUpdateInfo> {
  const currentVersion = __APP_VERSION__ || "0.0.0"
  const release = await fetchLatestRelease()

  if (!release) {
    return {
      currentVersion,
      latestVersion: currentVersion,
      hasUpdate: false,
      release: null,
    }
  }

  const latestVersion = release.tag_name
  const hasUpdate = compareVersions(latestVersion, currentVersion) > 0

  return {
    currentVersion,
    latestVersion,
    hasUpdate,
    release,
  }
}

/**
 * Gets platform-specific download assets
 */
export function getPlatformAssets(
  release: GitHubRelease,
  platform: PlatformType | null,
): Array<{ name: string; url: string; size: number }> {
  if (!release.assets || release.assets.length === 0) {
    return []
  }

  const platformAssets = release.assets.filter(asset => {
    const name = asset.name.toLowerCase()

    switch (platform) {
      case PlatformType.MAC:
        return (
          name.endsWith(".dmg") ||
          (name.includes("mac") && name.endsWith(".zip"))
        )
      case PlatformType.WINDOWS:
        return name.endsWith(".exe")
      case PlatformType.LINUX:
        return name.endsWith(".appimage")
      case PlatformType.WEB:
      default:
        return false
    }
  })

  return platformAssets.map(asset => ({
    name: asset.name,
    url: asset.browser_download_url,
    size: asset.size,
  }))
}

/**
 * Formats file size in human readable format
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes"

  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

/**
 * Formats the published date with locale support
 */
export function formatReleaseDate(dateString: string, locale: string): string {
  return formatDate(dateString, locale)
}
