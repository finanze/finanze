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

export interface AutoUpdateFileInfo {
  url: string
  sha512: string
  size: number
}

export interface AutoUpdateReleaseNote {
  version: string
  note: string
}

export interface AutoUpdateInfo {
  version: string
  releaseName?: string | null
  releaseNotes?: string | AutoUpdateReleaseNote[] | null
  releaseDate?: string
  files?: AutoUpdateFileInfo[]
}

export interface AutoUpdateProgressInfo {
  percent: number
  bytesPerSecond: number
  transferred: number
  total: number
}

export interface AutoUpdateErrorInfo {
  message: string
  stack: string | null
  name: string
}

export interface AutoUpdateCheckResult {
  supported: boolean
  updateInfo?: AutoUpdateInfo | null
  error?: AutoUpdateErrorInfo
}

export interface AutoUpdateActionResult {
  supported: boolean
  error?: AutoUpdateErrorInfo
}
