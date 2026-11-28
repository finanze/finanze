import { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"
import { PlatformType } from "@/types"
import { formatDate } from "@/lib/formatters"
import { getPlatformType } from "@/lib/platform"
import {
  getNextBaseVersion,
  isNewerMinorOrMajorVersion,
  isNewerStableVersion,
  isStableVersion,
} from "./buildVersion"

export type { GitHubRelease, ReleaseUpdateInfo } from "@/types/release"

const GITHUB_API_URL =
  "https://api.github.com/repos/finanze/finanze/releases/latest"

export function isStableUpdateAvailable(
  currentVersion: string,
  release: GitHubRelease,
): boolean {
  if (release.draft || release.prerelease) return false
  const candidate = release.tag_name.replace(/^v/, "")
  if (isStableVersion(currentVersion)) {
    return isNewerStableVersion(candidate, currentVersion)
  }

  const base = getNextBaseVersion(currentVersion)
  return base !== undefined && isNewerMinorOrMajorVersion(candidate, base)
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
  const release =
    isStableVersion(currentVersion) || getNextBaseVersion(currentVersion)
      ? await fetchLatestRelease()
      : null

  if (!release) {
    return {
      currentVersion,
      latestVersion: currentVersion,
      hasUpdate: false,
      release: null,
    }
  }

  const latestVersion = release.tag_name
  const isEligible = isStableUpdateAvailable(currentVersion, release)
  let hasUpdate = isEligible
  if (hasUpdate && getNextBaseVersion(currentVersion)) {
    const platform = getPlatformType()
    hasUpdate =
      platform === PlatformType.WEB
        ? Boolean(release.assets?.length)
        : getPlatformAssets(release, platform).length > 0
  }

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
      case PlatformType.ANDROID:
        return name.endsWith("android-full.apk")
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

/**
 * Removes the auto-generated "Build Assets" section (download links and tables)
 * from release notes, keeping only the human-written changelog.
 */
export function cleanReleaseNotes(body: string | null | undefined): string {
  if (!body) return ""

  const lines = body.split("\n")
  const cutIndex = lines.findIndex(line =>
    /^#{1,6}\s.*build assets/i.test(line.trim()),
  )

  let result = cutIndex >= 0 ? lines.slice(0, cutIndex).join("\n") : body

  // Drop a trailing "View the full CHANGELOG.md" pointer and horizontal rules
  result = result
    .replace(/\n+.*view the full.*changelog.*$/gim, "")
    .replace(/(\n+\s*-{3,}\s*)+$/g, "")
    .trimEnd()

  return result
}
