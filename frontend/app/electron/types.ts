export interface PlatformInfo {
  type: OS
  arch?: string
  osVersion?: string
  electronVersion?: string
}

export type ThemeMode = "light" | "dark" | "system"

export enum OS {
  MAC = "mac",
  WINDOWS = "windows",
  LINUX = "linux",
}

export interface AboutAppInfo {
  appName: string
  version: string
  author?: string | null
  repository?: string | null
  homepage?: string | null
  electronVersion?: string | null
  chromiumVersion?: string | null
  nodeVersion?: string | null
  platform: PlatformInfo
}

export interface AppConfig {
  readonly isDev: boolean
  readonly os: OS
  readonly ports: {
    backend: number
  }
  readonly urls: {
    backend: string
    vite: string
  }
}
