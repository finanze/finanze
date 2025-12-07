export type LogLevel = "NONE" | "DEBUG" | "INFO" | "WARN" | "ERROR"

export type BackendLogLevel =
  | "NONE"
  | "DEBUG"
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "CRITICAL"

export interface LogEntry {
  timestamp: Date
  level: LogLevel
  message: string
  args?: unknown[]
}

export interface LoggerConfig {
  logDir: string
  maxFileSize: number // in bytes
  maxFiles: number
  minLevel: LogLevel
  minFileLevel?: LogLevel // if not provided, uses minLevel
}

export const LOG_LEVEL_PRIORITY: Record<LogLevel, number> = {
  NONE: 999,
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
}

export const DEFAULT_CONFIG: Omit<LoggerConfig, "logDir"> = {
  maxFileSize: 5 * 1024 * 1024, // 5MB
  maxFiles: 3,
  minLevel: "INFO",
}

export function mapBackendLogLevel(backendLevel: BackendLogLevel): LogLevel {
  switch (backendLevel) {
    case "NONE":
      return "NONE"
    case "DEBUG":
      return "DEBUG"
    case "INFO":
      return "INFO"
    case "WARNING":
      return "WARN"
    case "ERROR":
    case "CRITICAL":
      return "ERROR"
    default:
      return "INFO"
  }
}
