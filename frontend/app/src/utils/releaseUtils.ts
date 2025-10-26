import { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"
import { PlatformType } from "@/types"
import { formatDate } from "@/lib/formatters"

export type { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"

const GITHUB_API_URL =
  "https://api.github.com/repos/finanze/finanze/releases/latest"

/**
 * Compares two semantic version strings
 * @param version1 First version (e.g., "1.2.3")
 * @param version2 Second version (e.g., "1.2.4")
 * @returns 1 if version1 > version2, -1 if version1 < version2, 0 if equal
 */
export function compareVersions(version1: string, version2: string): number {
  const v1 = version1.replace(/^v/, "").split("-")[0]
  const v2 = version2.replace(/^v/, "").split("-")[0]

  const parts1 = v1.split(".").map(Number)
  const parts2 = v2.split(".").map(Number)

  const maxLength = Math.max(parts1.length, parts2.length)

  for (let i = 0; i < maxLength; i++) {
    const part1 = parts1[i] || 0
    const part2 = parts2[i] || 0

    if (part1 > part2) return 1
    if (part1 < part2) return -1
  }

  return 0
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
export async function checkForUpdates(): Promise<ReleaseUpdateInfo> {
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
