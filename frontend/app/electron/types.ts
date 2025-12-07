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

export type BackendLogLevel =
  | "NONE"
  | "DEBUG"
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "CRITICAL"

export interface BackendStartOptions {
  dataDir?: string
  port?: number
  logLevel?: BackendLogLevel
  logDir?: string
  logFileLevel?: BackendLogLevel
  thirdPartyLogLevel?: BackendLogLevel
}

export interface BackendRuntimeArgs {
  port: number
  logLevel: BackendLogLevel
  dataDir?: string
  logDir?: string
  logFileLevel?: BackendLogLevel
  thirdPartyLogLevel?: BackendLogLevel
}

export type BackendState =
  | "stopped"
  | "starting"
  | "running"
  | "stopping"
  | "error"

export interface BackendErrorInfo {
  message: string
  stack?: string | null
  code?: string | number | null
}

export interface BackendStatus {
  state: BackendState
  pid: number | null
  args: BackendRuntimeArgs | null
  startedAt: number | null
  exitedAt: number | null
  error: BackendErrorInfo | null
}

export interface BackendActionResult {
  success: boolean
  status: BackendStatus
  error?: BackendErrorInfo
}

export interface FinanzeConfig {
  backend?: BackendStartOptions
  serverUrl?: string
}
