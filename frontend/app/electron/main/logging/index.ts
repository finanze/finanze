import { app } from "electron"
import { Logger } from "./logger"
import { DEFAULT_CONFIG, type LogLevel } from "./types"
import path from "node:path"

export { Logger } from "./logger"
export {
  type LogLevel,
  type BackendLogLevel,
  type LoggerConfig,
  type LogEntry,
  mapBackendLogLevel,
} from "./types"

let loggerInstance: Logger | null = null

export function initializeLogger(options?: {
  logDir?: string
  maxFileSize?: number
  maxFiles?: number
  minLevel?: LogLevel
  minFileLevel?: LogLevel
}): Logger {
  if (loggerInstance) {
    return loggerInstance
  }

  let logDir: string
  if (options?.logDir) {
    logDir = options.logDir
  } else {
    app.setAppLogsPath(path.join(app.getPath("appData"), "finanze", "logs"))
    logDir = app.getPath("logs")
  }

  loggerInstance = new Logger({
    logDir,
    maxFileSize: options?.maxFileSize ?? DEFAULT_CONFIG.maxFileSize,
    maxFiles: options?.maxFiles ?? DEFAULT_CONFIG.maxFiles,
    minLevel: options?.minLevel ?? DEFAULT_CONFIG.minLevel,
    minFileLevel: options?.minFileLevel,
  })

  loggerInstance.initialize()

  return loggerInstance
}

export function getLogger(): Logger | null {
  return loggerInstance
}

export function updateLoggerConfig(options: {
  logDir?: string
  minLevel?: LogLevel
  minFileLevel?: LogLevel
}): void {
  if (loggerInstance) {
    loggerInstance.updateConfig(options)
  }
}

/**
 * Output raw text to console without formatting or file logging.
 * Use this for backend output that already has its own formatting.
 */
export function rawLog(message: string): void {
  if (loggerInstance) {
    loggerInstance.raw(message)
  } else {
    console.log(message)
  }
}
