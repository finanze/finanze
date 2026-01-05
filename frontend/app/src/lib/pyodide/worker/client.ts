import { appConsole } from "@/lib/capacitor/appConsole"
import type { PyodideRuntimeOptions } from "../runtime"

type RequestMessage = {
  kind: "req"
  id: number
  action: string
  payload?: any
}

type ResponseMessage = {
  kind: "res"
  id: number
  ok: boolean
  result?: any
  error?: { message: string; name?: string; stack?: string }
}

type EventMessage =
  | { kind: "event"; event: "stdout" | "stderr"; text: string }
  | {
      kind: "event"
      event: "log"
      level: "debug" | "info" | "warn" | "error"
      data: any[]
    }

type AnyMessage = RequestMessage | ResponseMessage | EventMessage

function isReq(msg: any): msg is RequestMessage {
  return (
    msg?.kind === "req" &&
    typeof msg.id === "number" &&
    typeof msg.action === "string"
  )
}

function isRes(msg: any): msg is ResponseMessage {
  return (
    msg?.kind === "res" &&
    typeof msg.id === "number" &&
    typeof msg.ok === "boolean"
  )
}

export class PyodideWorkerClient {
  private worker: Worker
  private nextId = 1
  private pending = new Map<
    number,
    { resolve: (value: any) => void; reject: (error: any) => void }
  >()

  constructor() {
    this.worker = new Worker(new URL("./pyodideWorker.ts", import.meta.url), {
      type: "module",
    })

    this.worker.onmessage = (event: MessageEvent<AnyMessage>) => {
      const msg: any = event.data

      if (isRes(msg)) {
        const pending = this.pending.get(msg.id)
        if (!pending) return
        this.pending.delete(msg.id)

        if (msg.ok) {
          pending.resolve(msg.result)
        } else {
          const err = Object.assign(
            new Error(msg.error?.message ?? "Worker call failed"),
            msg.error,
          )
          pending.reject(err)
        }
        return
      }

      if (isReq(msg) && msg.action === "callMain") {
        void this.handleCallMain(msg)
        return
      }

      if (msg?.kind === "event" && msg.event === "stdout") {
        if (msg.text) appConsole.debug("[Pyodide worker stdout]", msg.text)
        return
      }

      if (msg?.kind === "event" && msg.event === "stderr") {
        if (msg.text) appConsole.error("[Pyodide worker stderr]", msg.text)
        return
      }
    }
  }

  terminate(): void {
    this.worker.terminate()
    this.pending.clear()
  }

  private postRequest(action: string, payload?: any): Promise<any> {
    const id = this.nextId++
    const msg: RequestMessage = { kind: "req", id, action, payload }

    const promise = new Promise<any>((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
    })

    this.worker.postMessage(msg)
    return promise
  }

  async init(options: PyodideRuntimeOptions): Promise<void> {
    await this.postRequest("init", {
      indexURL: options.indexURL,
      installMobileRequirements: !!options.installMobileRequirements,
    })
  }

  async loadAppModules(): Promise<void> {
    await this.postRequest("loadAppModules")
  }

  async loadDeferredModules(): Promise<void> {
    await this.postRequest("loadDeferredModules")
  }

  async installDeferredRequirements(): Promise<void> {
    await this.postRequest("installDeferredRequirements")
  }

  async callPythonFunction(
    modulePath: string,
    functionName: string,
    args: any[],
  ): Promise<any> {
    return this.postRequest("callPythonFunction", {
      modulePath,
      functionName,
      args,
    })
  }

  async runPythonAsync(code: string): Promise<any> {
    return this.postRequest("runPythonAsync", { code })
  }

  runPython(code: string): Promise<any> {
    return this.postRequest("runPython", { code })
  }

  private async handleCallMain(msg: RequestMessage): Promise<void> {
    const id = msg.id
    const method = String(msg.payload?.method ?? "")
    const args = Array.isArray(msg.payload?.args) ? msg.payload.args : []

    try {
      const result = await this.invokeAllowed(method, args)
      const cloneableResult = this.ensureCloneable(result)
      const res: ResponseMessage = { kind: "res", id, ok: true, result }
      this.worker.postMessage({ ...res, result: cloneableResult })
    } catch (e: any) {
      const res: ResponseMessage = {
        kind: "res",
        id,
        ok: false,
        error: {
          message: e?.message ?? String(e),
          name: e?.name,
          stack: e?.stack,
        },
      }
      this.worker.postMessage(res)
    }
  }

  private ensureCloneable(value: any): any {
    try {
      structuredClone(value)
      return value
    } catch {
      try {
        return JSON.parse(JSON.stringify(value))
      } catch {
        return null
      }
    }
  }

  private async invokeAllowed(methodPath: string, args: any[]): Promise<any> {
    const allowedPrefixes = [
      "jsBridge.",
      "FileTransfer.",
      "BackupProcessor.",
      "NativeCookies.",
      "Capacitor.Plugins.CapacitorHttp.",
    ]

    if (!allowedPrefixes.some(p => methodPath.startsWith(p))) {
      throw new Error(
        `Worker attempted to call disallowed method: ${methodPath}`,
      )
    }

    const callable = this.resolveCallable(methodPath)
    const value = await callable(...args)

    if (methodPath === "jsBridge.sqlite.openDatabase") {
      return { ok: true }
    }

    return value
  }

  private resolveCallable(methodPath: string): (...args: any[]) => any {
    const parts = methodPath.split(".")
    if (parts.length < 2) throw new Error(`Invalid methodPath: ${methodPath}`)

    let current: any = globalThis

    for (const part of parts) {
      if (part === "jsBridge") {
        current = (globalThis as any).jsBridge
        continue
      }

      if (part === "Capacitor") {
        current = (globalThis as any).Capacitor
        continue
      }

      current = current?.[part]
    }

    if (typeof current !== "function") {
      throw new Error(`Resolved value is not callable for ${methodPath}`)
    }

    return current
  }
}
