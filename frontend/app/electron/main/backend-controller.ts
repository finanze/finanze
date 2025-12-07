import { ChildProcess, spawn } from "node:child_process"
import { join } from "node:path"
import { readdirSync } from "node:fs"
import { EventEmitter } from "node:events"
import {
  AppConfig,
  BackendRuntimeArgs,
  BackendStartOptions,
  BackendStatus,
  BackendErrorInfo,
  OS,
} from "../types"
import { findAndKillProcesses } from "./windows-process"
import { rawLog } from "./logging"

interface BackendControllerOptions {
  appConfig: AppConfig
  devEntryPoint: string
  defaultArgs: BackendRuntimeArgs
}

type StatusListener = (status: BackendStatus) => void

export class BackendController extends EventEmitter {
  private process: ChildProcess | null = null
  private status: BackendStatus = {
    state: "stopped",
    pid: null,
    args: null,
    startedAt: null,
    exitedAt: null,
    error: null,
  }
  private stoppingPromise: Promise<BackendStatus> | null = null

  constructor(private readonly options: BackendControllerOptions) {
    super()
  }

  getStatus(): BackendStatus {
    return {
      ...this.status,
      args: this.status.args ? { ...this.status.args } : null,
      error: this.status.error ? { ...this.status.error } : null,
    }
  }

  async start(options?: BackendStartOptions): Promise<BackendStatus> {
    if (this.process) {
      throw new Error("Backend process is already running")
    }

    if (this.status.state === "starting" || this.status.state === "stopping") {
      throw new Error("Backend process is busy")
    }

    const resolvedArgs = this.resolveArgs(options)
    const cliArgs = this.buildCliArgs(resolvedArgs)

    console.info(
      `Starting backend with args: port=${resolvedArgs.port}, logLevel=${resolvedArgs.logLevel}, dataDir=${resolvedArgs.dataDir ?? "default"}, logDir=${resolvedArgs.logDir ?? "default"}, logFileLevel=${resolvedArgs.logFileLevel ?? "default"}, thirdPartyLogLevel=${resolvedArgs.thirdPartyLogLevel ?? "default"}`,
    )

    this.updateStatus({
      state: "starting",
      args: resolvedArgs,
      startedAt: Date.now(),
      exitedAt: null,
      error: null,
      pid: null,
    })

    try {
      const child = this.options.appConfig.isDev
        ? this.spawnDev(cliArgs)
        : this.spawnProd(cliArgs)

      this.attachProcess(child)
      console.info("Backend initiated successfully")
      return this.getStatus()
    } catch (error) {
      this.process = null
      const serializedError = this.serializeError(error)
      console.error(
        `Failed to start backend: ${serializedError.message}`,
        serializedError,
      )
      this.updateStatus({
        state: "error",
        error: serializedError,
        pid: null,
        exitedAt: Date.now(),
      })
      throw error
    }
  }

  async stop(): Promise<BackendStatus> {
    if (!this.process) {
      if (
        this.status.state === "running" ||
        this.status.state === "starting" ||
        this.status.state === "stopping"
      ) {
        console.info("Backend stopped (no active process)")
        this.updateStatus({
          state: "stopped",
          pid: null,
          exitedAt: Date.now(),
        })
      }
      return this.getStatus()
    }

    if (this.status.state === "stopping" && this.stoppingPromise) {
      return this.stoppingPromise
    }

    console.info("Stopping backend...")
    this.updateStatus({ state: "stopping" })

    const waitForExit = new Promise<BackendStatus>(resolve => {
      const listener: StatusListener = status => {
        if (status.state === "stopped" || status.state === "error") {
          this.removeListener("status-changed", listener)
          resolve(status)
        }
      }
      this.on("status-changed", listener)
    })

    this.stoppingPromise = waitForExit

    try {
      if (this.options.appConfig.os === OS.WINDOWS) {
        await this.terminateWindowsProcess()
      } else {
        this.process.kill()
      }
    } catch (error) {
      const serializedError = this.serializeError(error)
      console.error(
        `Error during backend stop: ${serializedError.message}`,
        serializedError,
      )
      this.updateStatus({
        state: "error",
        error: serializedError,
        exitedAt: Date.now(),
      })
    }

    const result = await waitForExit
    this.stoppingPromise = null
    return result
  }

  private resolveArgs(options?: BackendStartOptions): BackendRuntimeArgs {
    const args = options ?? {}

    return {
      port:
        typeof args.port === "number"
          ? args.port
          : this.options.defaultArgs.port,
      logLevel: args.logLevel ?? this.options.defaultArgs.logLevel,
      dataDir: Object.prototype.hasOwnProperty.call(args, "dataDir")
        ? args.dataDir
        : this.options.defaultArgs.dataDir,
      logDir: Object.prototype.hasOwnProperty.call(args, "logDir")
        ? args.logDir
        : this.options.defaultArgs.logDir,
      logFileLevel: Object.prototype.hasOwnProperty.call(args, "logFileLevel")
        ? args.logFileLevel
        : this.options.defaultArgs.logFileLevel,
      thirdPartyLogLevel: Object.prototype.hasOwnProperty.call(
        args,
        "thirdPartyLogLevel",
      )
        ? args.thirdPartyLogLevel
        : this.options.defaultArgs.thirdPartyLogLevel,
    }
  }

  private buildCliArgs(args: BackendRuntimeArgs): string[] {
    const cliArgs = [
      "--port",
      args.port.toString(),
      "--log-level",
      args.logLevel,
    ]

    if (args.dataDir) {
      cliArgs.push("--data-dir", args.dataDir)
    }

    if (args.logDir) {
      cliArgs.push("--log-dir", args.logDir)
    }

    if (args.logFileLevel) {
      cliArgs.push("--log-file-level", args.logFileLevel)
    }

    if (args.thirdPartyLogLevel) {
      cliArgs.push("--third-party-log-level", args.thirdPartyLogLevel)
    }

    return cliArgs
  }

  private spawnDev(args: string[]) {
    const devArgs = [this.options.devEntryPoint, ...args]
    return spawn("python", devArgs, { shell: true })
  }

  private spawnProd(args: string[]) {
    const binPath = join(process.resourcesPath, "bin")
    const entries = readdirSync(binPath)
    const serverDir = entries.find(entry => entry.startsWith("finanze-server-"))

    if (!serverDir) {
      throw new Error(`Expected one finanze-server-* dir in ${binPath}`)
    }

    const serverDirPath = join(binPath, serverDir)
    const serverFile = readdirSync(serverDirPath).find(entry =>
      entry.startsWith("finanze-server-"),
    )

    if (!serverFile) {
      throw new Error(`Expected one finanze-server-* file in ${serverDirPath}`)
    }

    const executablePath = join(serverDirPath, serverFile)
    return spawn(executablePath, args)
  }

  private attachProcess(child: ChildProcess) {
    this.process = child

    if (child.pid) {
      console.info(`Backend process spawned with PID ${child.pid}`)
      this.updateStatus({ pid: child.pid })
    }

    child.stdout?.on("data", data => {
      const output = String(data).trimEnd()
      if (output) rawLog(output)
    })

    child.stderr?.on("data", data => {
      const output = String(data).trimEnd()
      if (output) rawLog(output)
    })

    child.once("spawn", () => {
      console.info("Backend process running")
      this.updateStatus({ state: "running", pid: child.pid ?? null })
    })

    child.once("error", error => {
      this.process = null
      const serializedError = this.serializeError(error)
      console.error(
        `Backend process error: ${serializedError.message}`,
        serializedError,
      )
      this.updateStatus({
        state: "error",
        error: serializedError,
        pid: null,
        exitedAt: Date.now(),
      })
    })

    child.once("close", code => {
      this.process = null
      const hadError = typeof code === "number" && code !== 0
      if (hadError) {
        console.warn(`Backend process exited with error code ${code}`)
      } else {
        console.info("Backend process stopped")
      }
      this.updateStatus({
        state:
          this.status.state === "stopping" || !hadError ? "stopped" : "error",
        pid: null,
        exitedAt: Date.now(),
        error: hadError
          ? {
              message: `Backend exited with code ${code}`,
              code,
              stack: null,
            }
          : null,
      })
    })
  }

  private async terminateWindowsProcess() {
    if (!this.process) {
      return
    }

    if (this.options.appConfig.isDev) {
      const pid = this.process.pid
      if (!pid) {
        this.process.kill()
        return
      }

      await new Promise<void>((resolve, reject) => {
        const killer = spawn("taskkill", ["/pid", pid.toString(), "/f", "/t"])
        killer.once("exit", () => resolve())
        killer.once("error", reject)
      })
    } else {
      await findAndKillProcesses()
    }
  }

  private updateStatus(patch: Partial<BackendStatus>) {
    const nextStatus: BackendStatus = {
      ...this.status,
      ...patch,
      args:
        patch.args !== undefined
          ? patch.args
            ? { ...patch.args }
            : null
          : this.status.args
            ? { ...this.status.args }
            : null,
      error:
        patch.error !== undefined
          ? patch.error
            ? { ...patch.error }
            : null
          : this.status.error
            ? { ...this.status.error }
            : null,
    }

    this.status = nextStatus
    this.emit("status-changed", this.getStatus())
  }

  private serializeError(error: unknown): BackendErrorInfo {
    if (error instanceof Error) {
      const err = error as NodeJS.ErrnoException
      return {
        message: error.message,
        stack: error.stack ?? null,
        code: err.code ?? null,
      }
    }

    return {
      message: typeof error === "string" ? error : "Unknown error",
      stack: null,
      code: null,
    }
  }
}
