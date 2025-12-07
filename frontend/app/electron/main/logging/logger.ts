import {
  appendFileSync,
  writeFileSync,
  existsSync,
  unlinkSync,
  renameSync,
} from "fs"
import {
  LoggerConfig,
  LogLevel,
  LOG_LEVEL_PRIORITY,
  DEFAULT_CONFIG,
} from "./types"
import {
  ensureLogDirectory,
  getLogFilePath,
  getFileSize,
  formatLogEntry,
} from "./utils"

export class Logger {
  private config: LoggerConfig
  private currentLogFile: string | null = null
  private originalConsole: {
    log: typeof console.log
    info: typeof console.info
    warn: typeof console.warn
    error: typeof console.error
    debug: typeof console.debug
  }

  constructor(config: LoggerConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.originalConsole = {
      log: console.log.bind(console),
      info: console.info.bind(console),
      warn: console.warn.bind(console),
      error: console.error.bind(console),
      debug: console.debug.bind(console),
    }
  }

  initialize(): void {
    ensureLogDirectory(this.config.logDir)
    this.rotateIfNeeded()
    this.interceptConsole()

    const fileLevel = this.config.minFileLevel ?? this.config.minLevel
    this.info(
      `Logger initialized - logs at: ${this.currentLogFile} with console level: ${this.config.minLevel}, file level: ${fileLevel}`,
    )
  }

  private interceptConsole(): void {
    console.log = (...args: unknown[]) => {
      this.logWithConsole("INFO", args[0] as string, args.slice(1))
    }

    console.info = (...args: unknown[]) => {
      this.logWithConsole("INFO", args[0] as string, args.slice(1))
    }

    console.warn = (...args: unknown[]) => {
      this.logWithConsole("WARN", args[0] as string, args.slice(1))
    }

    console.error = (...args: unknown[]) => {
      this.logWithConsole("ERROR", args[0] as string, args.slice(1))
    }

    console.debug = (...args: unknown[]) => {
      this.logWithConsole("DEBUG", args[0] as string, args.slice(1))
    }
  }

  private shouldLogConsole(level: LogLevel): boolean {
    return LOG_LEVEL_PRIORITY[level] >= LOG_LEVEL_PRIORITY[this.config.minLevel]
  }

  private shouldLogFile(level: LogLevel): boolean {
    const fileLevel = this.config.minFileLevel ?? this.config.minLevel
    return LOG_LEVEL_PRIORITY[level] >= LOG_LEVEL_PRIORITY[fileLevel]
  }

  private rotateIfNeeded(): void {
    const mainLogFile = getLogFilePath(this.config.logDir, 0)

    // If we haven't set a current log file yet, check if the main file exists and is usable
    if (!this.currentLogFile) {
      if (existsSync(mainLogFile)) {
        const size = getFileSize(mainLogFile)
        if (size < this.config.maxFileSize) {
          // Reuse existing file
          this.currentLogFile = mainLogFile
          return
        }
        // File exists but is too large, rotate
        this.rotateLogFiles()
      }
      // Create new main log file
      this.currentLogFile = mainLogFile
      const header = `=== Finanze Electron Log Started at ${new Date().toISOString()} ===\n`
      writeFileSync(this.currentLogFile, header)
      return
    }

    // Check if current file needs rotation
    const size = getFileSize(this.currentLogFile)
    if (size >= this.config.maxFileSize) {
      this.rotateLogFiles()
      this.currentLogFile = mainLogFile
      const header = `=== Finanze Electron Log Started at ${new Date().toISOString()} ===\n`
      writeFileSync(this.currentLogFile, header)
    }
  }

  private rotateLogFiles(): void {
    const { logDir, maxFiles } = this.config

    // Delete the oldest file if it exists
    const oldestFile = getLogFilePath(logDir, maxFiles - 1)
    if (existsSync(oldestFile)) {
      try {
        unlinkSync(oldestFile)
      } catch {
        // Ignore deletion errors
      }
    }

    // Shift existing files: .2 -> .3, .1 -> .2, .log -> .1
    for (let i = maxFiles - 2; i >= 0; i--) {
      const currentFile = getLogFilePath(logDir, i)
      const nextFile = getLogFilePath(logDir, i + 1)
      if (existsSync(currentFile)) {
        try {
          renameSync(currentFile, nextFile)
        } catch {
          // Ignore rename errors
        }
      }
    }
  }

  private logWithConsole(
    level: LogLevel,
    message: string,
    args?: unknown[],
  ): void {
    const shouldConsole = this.shouldLogConsole(level)
    const shouldFile = this.shouldLogFile(level)

    if (!shouldConsole && !shouldFile) {
      return
    }

    const formattedMessage =
      typeof message === "string" ? message : String(message)
    const logEntry = formatLogEntry(new Date(), level, formattedMessage, args)

    // Output formatted log to console
    if (shouldConsole) {
      const consoleOutput = logEntry.trimEnd()
      switch (level) {
        case "DEBUG":
          this.originalConsole.debug(consoleOutput)
          break
        case "WARN":
          this.originalConsole.warn(consoleOutput)
          break
        case "ERROR":
          this.originalConsole.error(consoleOutput)
          break
        default:
          this.originalConsole.log(consoleOutput)
      }
    }

    // Also write to file
    if (shouldFile && this.currentLogFile) {
      this.rotateIfNeeded()
      try {
        appendFileSync(this.currentLogFile, logEntry)
      } catch (error) {
        this.originalConsole.error("Failed to write to log file:", error)
      }
    }
  }

  debug(message: string, ...args: unknown[]): void {
    this.logWithConsole("DEBUG", message, args)
  }

  info(message: string, ...args: unknown[]): void {
    this.logWithConsole("INFO", message, args)
  }

  warn(message: string, ...args: unknown[]): void {
    this.logWithConsole("WARN", message, args)
  }

  error(message: string, ...args: unknown[]): void {
    this.logWithConsole("ERROR", message, args)
  }

  /**
   * Output directly to original console without formatting or file logging.
   * Use this for backend output that already has its own formatting.
   */
  raw(message: string): void {
    this.originalConsole.log(message)
  }

  getLogDirectory(): string {
    return this.config.logDir
  }

  getCurrentLogFile(): string | null {
    return this.currentLogFile
  }

  updateConfig(options: {
    logDir?: string
    minLevel?: LogLevel
    minFileLevel?: LogLevel
  }): void {
    const oldLevel = this.config.minLevel
    const oldFileLevel = this.config.minFileLevel ?? this.config.minLevel
    const oldLogDir = this.config.logDir

    if (options.minLevel !== undefined) {
      this.config.minLevel = options.minLevel
    }
    if (options.minFileLevel !== undefined) {
      this.config.minFileLevel = options.minFileLevel
    }

    const newFileLevel = this.config.minFileLevel ?? this.config.minLevel
    const levelsChanged =
      oldLevel !== this.config.minLevel || oldFileLevel !== newFileLevel

    if (options.logDir && options.logDir !== oldLogDir) {
      this.config.logDir = options.logDir
      ensureLogDirectory(this.config.logDir)
      this.currentLogFile = null
      this.rotateIfNeeded()
      this.info(
        `Logger directory changed: ${oldLogDir} -> ${this.config.logDir}`,
      )
    }

    if (levelsChanged) {
      this.info(
        `Logger levels updated - console: ${oldLevel} -> ${this.config.minLevel}, file: ${oldFileLevel} -> ${newFileLevel}`,
      )
    }
  }
}
