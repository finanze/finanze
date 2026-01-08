import { User } from "./user"

export enum FFStatus {
  ON = "ON",
  OFF = "OFF",
}

export type FFValue = FFStatus | string

export enum LoginStatusCode {
  LOCKED = "LOCKED",
  UNLOCKED = "UNLOCKED",
}

export enum BackendLogLevel {
  NONE = "NONE",
  DEBUG = "DEBUG",
  INFO = "INFO",
  WARNING = "WARNING",
  ERROR = "ERROR",
  CRITICAL = "CRITICAL",
}

export interface BackendOptions {
  dataDir?: string | null
  port?: number | null
  logLevel?: BackendLogLevel | null
  logDir?: string | null
  logFileLevel?: BackendLogLevel | null
  thirdPartyLogLevel?: BackendLogLevel | null
}

export interface BackendDetails {
  version: string
  options: BackendOptions
}

export interface GlobalStatus {
  status: LoginStatusCode
  server: BackendDetails
  features: Record<string, FFStatus | string>
  user?: User | null
  lastLogged?: string | null
}
