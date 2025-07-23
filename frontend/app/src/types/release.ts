export interface GitHubRelease {
  url: string
  html_url: string
  tag_name: string
  name: string
  published_at: string
  body: string
  assets: GitHubReleaseAsset[]
}

export interface GitHubReleaseAsset {
  name: string
  browser_download_url: string
  size: number
  download_count: number
}

export interface ReleaseUpdateInfo {
  currentVersion: string
  latestVersion: string
  hasUpdate: boolean
  release: GitHubRelease | null
}
