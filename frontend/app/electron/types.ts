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
