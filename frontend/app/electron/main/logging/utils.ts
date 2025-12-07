import { existsSync, mkdirSync, readdirSync, statSync, unlinkSync } from "fs"
import { join } from "path"

const LOG_FILE_BASE = "finanze-electron"
const LOG_FILE_EXTENSION = ".log"

export function ensureLogDirectory(logDir: string): void {
  if (!existsSync(logDir)) {
    mkdirSync(logDir, { recursive: true })
  }
}

export function getLogFileName(index = 0): string {
  if (index === 0) {
    return `${LOG_FILE_BASE}${LOG_FILE_EXTENSION}`
  }
  return `${LOG_FILE_BASE}.${index}${LOG_FILE_EXTENSION}`
}

export function getLogFilePath(logDir: string, index = 0): string {
  return join(logDir, getLogFileName(index))
}

export function getExistingLogFiles(logDir: string): string[] {
  if (!existsSync(logDir)) {
    return []
  }

  return readdirSync(logDir)
    .filter(
      file =>
        file.startsWith(LOG_FILE_BASE) && file.endsWith(LOG_FILE_EXTENSION),
    )
    .map(file => join(logDir, file))
    .sort((a, b) => {
      const statA = statSync(a)
      const statB = statSync(b)
      return statB.mtime.getTime() - statA.mtime.getTime()
    })
}

export function getFileSize(filePath: string): number {
  try {
    return statSync(filePath).size
  } catch {
    return 0
  }
}

export function cleanupOldLogFiles(logDir: string, maxFiles: number): void {
  const files = getExistingLogFiles(logDir)

  // Keep only the newest (maxFiles - 1) files to make room for the current one
  const filesToDelete = files.slice(maxFiles)

  for (const file of filesToDelete) {
    try {
      unlinkSync(file)
    } catch (error) {
      console.error(`Failed to delete old log file: ${file}`, error)
    }
  }
}

export function formatTimestamp(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  const hours = String(date.getHours()).padStart(2, "0")
  const minutes = String(date.getMinutes()).padStart(2, "0")
  const seconds = String(date.getSeconds()).padStart(2, "0")

  const tzOffset = -date.getTimezoneOffset()
  const tzSign = tzOffset >= 0 ? "+" : "-"
  const tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, "0")
  const tzMinutes = String(Math.abs(tzOffset) % 60).padStart(2, "0")

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}${tzSign}${tzHours}${tzMinutes}`
}

export function formatLogEntry(
  timestamp: Date,
  level: string,
  message: string,
  args?: unknown[],
  source?: string,
): string {
  const timestampStr = formatTimestamp(timestamp)
  const levelChar = level.charAt(0).toUpperCase()
  const sourceStr = source || "electron"
  let logLine = `${timestampStr} | ${levelChar} | ${sourceStr} | ${message}`

  if (args && args.length > 0) {
    const argsStr = args
      .map(arg => {
        if (arg instanceof Error) {
          return `${arg.message}\n${arg.stack || ""}`
        }
        if (typeof arg === "object") {
          try {
            return JSON.stringify(arg)
          } catch {
            return String(arg)
          }
        }
        return String(arg)
      })
      .join(" ")
    logLine += ` ${argsStr}`
  }

  return logLine + "\n"
}
