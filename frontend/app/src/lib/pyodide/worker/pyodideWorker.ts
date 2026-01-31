import { loadPyodide, type PyodideInterface } from "pyodide"

const CACHE_NAME = "pyodide-cache-v0.29.2"

function shouldInterceptUrl(url: string): boolean {
  const lowerUrl = url.toLowerCase()
  return (
    lowerUrl.includes("pyodide") ||
    lowerUrl.includes(".wasm") ||
    lowerUrl.includes(".whl") ||
    lowerUrl.includes("python_stdlib") ||
    lowerUrl.includes("repodata.json")
  )
}

function getMimeType(url: string): string | null {
  if (url.includes(".wasm")) return "application/wasm"
  if (url.includes(".js")) return "application/javascript"
  if (url.includes(".json")) return "application/json"
  if (url.includes(".zip")) return "application/zip"
  if (url.includes(".whl")) return "application/zip"
  return null
}

const originalFetch = self.fetch.bind(self)
self.fetch = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> => {
  if (init?.method && init.method !== "GET") {
    return originalFetch(input, init)
  }

  const url =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url

  if (!shouldInterceptUrl(url)) {
    return originalFetch(input, init)
  }

  const fileName = url.split("/").pop() || url

  try {
    const cache = await caches.open(CACHE_NAME)
    const cachedResponse = await cache.match(url)

    if (cachedResponse) {
      return cachedResponse
    }

    const response = await originalFetch(input, init)

    if (!response.ok) {
      console.warn(`[Pyodide] Fetch failed: ${fileName} (${response.status})`)
      return response
    }

    const mimeType = getMimeType(url)

    const arrayBuffer = await response.arrayBuffer()
    const newHeaders = new Headers(response.headers)
    if (mimeType) {
      newHeaders.set("Content-Type", mimeType)
    }

    const correctedResponse = new Response(arrayBuffer, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    })

    const responseToCache = new Response(arrayBuffer, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    })

    cache.put(url, responseToCache).catch(e => {
      console.warn(`[Pyodide] Failed to cache: ${fileName}`, e)
    })

    return correctedResponse
  } catch (e) {
    console.warn(`[Pyodide] Interceptor error for ${fileName}:`, e)
    return originalFetch(input, init)
  }
}

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

let pyodide: PyodideInterface | null = null

let nextMainRequestId = 1
const mainPending = new Map<
  number,
  { resolve: (value: any) => void; reject: (error: any) => void }
>()

function postEvent(message: EventMessage): void {
  ;(self as any).postMessage(message)
}

function sanitizeForPostMessage(
  value: any,
  seen = new WeakMap<object, any>(),
): any {
  if (value === null || value === undefined) return value

  const t = typeof value
  if (t === "string" || t === "number" || t === "boolean") return value
  if (t === "bigint") return value.toString()

  if (value instanceof ArrayBuffer) return value
  if (ArrayBuffer.isView(value)) return value

  if (t !== "object") return value

  // Fast path: if it already clones, keep it.
  try {
    structuredClone(value)
    return value
  } catch {
    // continue
  }

  // Pyodide proxies usually implement toJs()
  const maybeToJs = (value as any)?.toJs
  if (typeof maybeToJs === "function") {
    try {
      const converted = maybeToJs.call(value, {
        create_proxies: false,
        dict_converter: Object.fromEntries,
      })
      return sanitizeForPostMessage(converted, seen)
    } catch {
      // continue
    }
  }

  if (Array.isArray(value)) {
    return value.map(v => sanitizeForPostMessage(v, seen))
  }

  if (seen.has(value)) return seen.get(value)
  const out: any = {}
  seen.set(value, out)

  for (const [k, v] of Object.entries(value)) {
    out[k] = sanitizeForPostMessage(v, seen)
  }

  // Last resort: JSON roundtrip.
  try {
    structuredClone(out)
    return out
  } catch {
    try {
      return JSON.parse(JSON.stringify(out))
    } catch {
      return String(value)
    }
  }
}

function serializeError(error: any): {
  message: string
  name?: string
  stack?: string
} {
  if (!error) return { message: "Unknown error" }
  if (typeof error === "string") return { message: error }
  return {
    message: error.message ?? String(error),
    name: error.name,
    stack: error.stack,
  }
}

function postResponse(
  id: number,
  ok: boolean,
  result?: any,
  error?: any,
): void {
  const msg: ResponseMessage = ok
    ? { kind: "res", id, ok: true, result: sanitizeForPostMessage(result) }
    : { kind: "res", id, ok: false, error: serializeError(error) }
  ;(self as any).postMessage(msg)
}

function isPyProxy(
  value: unknown,
): value is { toJs: (options?: any) => unknown; destroy: () => void } {
  return (
    !!value &&
    typeof value === "object" &&
    "toJs" in (value as any) &&
    typeof (value as any).toJs === "function" &&
    "destroy" in (value as any) &&
    typeof (value as any).destroy === "function"
  )
}

function convertPyResult(value: any): any {
  if (!isPyProxy(value)) return value

  try {
    const converted = value.toJs({
      create_proxies: false,
      dict_converter: Object.fromEntries,
    })
    value.destroy()

    // JSON roundtrip ensures clean JS objects without any Pyodide proxy remnants
    // This matches the main-thread behavior where results naturally serialize cleanly
    try {
      return JSON.parse(JSON.stringify(converted))
    } catch {
      return converted
    }
  } catch {
    return value
  }
}

async function requestMain(method: string, args: any[]): Promise<any> {
  const id = nextMainRequestId++
  const message: RequestMessage = {
    kind: "req",
    id,
    action: "callMain",
    payload: { method, args: sanitizeForPostMessage(args) },
  }

  const promise = new Promise<any>((resolve, reject) => {
    mainPending.set(id, { resolve, reject })
  })

  ;(self as any).postMessage(message)
  return promise
}

function createMainProxy(methodPrefix: string): any {
  return new Proxy(
    {},
    {
      get(_target, prop) {
        if (prop === "then") {
          return undefined
        }

        const propName = String(prop)
        return (...args: any[]) =>
          requestMain(`${methodPrefix}.${propName}`, args)
      },
    },
  )
}

async function installMobileRequirements(): Promise<void> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  const wheelsManifestResponse = await fetch("/python/wheels_manifest.py", {
    cache: "no-store",
  })
  if (!wheelsManifestResponse.ok) {
    const body = await wheelsManifestResponse.text().catch(() => "")
    throw new Error(
      `Failed to load /python/wheels_manifest.py: ${wheelsManifestResponse.status} ${wheelsManifestResponse.statusText}${body ? `\n${body}` : ""}. ` +
        "Run: pnpm -C frontend/app build:python",
    )
  }

  const wheelsManifestSource = await wheelsManifestResponse.text()

  const response = await fetch("/python/mobile_requirements.py", {
    cache: "no-store",
  })
  if (!response.ok) {
    const body = await response.text().catch(() => "")
    throw new Error(
      `Failed to load /python/mobile_requirements.py: ${response.status} ${response.statusText}${body ? `\n${body}` : ""}`,
    )
  }

  const source = await response.text()

  pyodide.FS.mkdirTree("/python")
  pyodide.FS.writeFile("/python/wheels_manifest.py", wheelsManifestSource)
  pyodide.FS.writeFile("/python/mobile_requirements.py", source)

  await pyodide.runPythonAsync(
    [
      "import sys",
      'if "/python" not in sys.path: sys.path.append("/python")',
      "import wheels_manifest",
    ].join("\n"),
  )

  const hasCorePackages = await pyodide.runPythonAsync(
    [
      "from mobile_requirements import has_core_packages",
      "has_core_packages()",
    ].join("\n"),
  )

  if (hasCorePackages) {
    await pyodide.loadPackage("micropip")
  }

  await pyodide.runPythonAsync(
    ["from mobile_requirements import install", "await install()"].join("\n"),
  )
}

async function installDeferredRequirements(): Promise<void> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  await pyodide.loadPackage("micropip")

  await pyodide.runPythonAsync(
    [
      "from mobile_requirements import install_deferred",
      "await install_deferred()",
    ].join("\n"),
  )
}

async function loadModulesFromManifest(manifestPath: string): Promise<void> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  const response = await fetch(manifestPath)
  if (!response.ok) {
    throw new Error(
      `Failed to load manifest ${manifestPath}: ${response.statusText}`,
    )
  }

  const manifest: { files: string[] } = await response.json()

  await Promise.all(
    manifest.files.map(async filePath => {
      const fileRes = await fetch(`/python/${filePath}`)
      if (!fileRes.ok) throw new Error(fileRes.statusText)

      const content = await fileRes.arrayBuffer()
      const data = new Uint8Array(content)

      const targetPath = `/python/${filePath}`

      const dir = targetPath.substring(0, targetPath.lastIndexOf("/"))
      if (dir) {
        pyodide!.FS.mkdirTree(dir)
      }

      pyodide!.FS.writeFile(targetPath, data)
    }),
  )
}

async function loadAppModules(): Promise<void> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  await loadModulesFromManifest("/python/manifest_core.json")

  await pyodide.runPythonAsync(
    [
      "import sys",
      'if "/python" not in sys.path: sys.path.insert(0, "/python")',
      'if "/python/finanze" not in sys.path: sys.path.insert(0, "/python/finanze")',
    ].join("\n"),
  )

  await pyodide.runPythonAsync("import init")
}

async function loadDeferredModules(): Promise<void> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  await loadModulesFromManifest("/python/manifest_deferred.json")
}

function registerWorkerBridge(): void {
  ;(self as any).window = self

  const sqlite = {
    openDatabase: (...args: any[]) =>
      requestMain("jsBridge.sqlite.openDatabase", args),
    executeSql: (...args: any[]) =>
      requestMain("jsBridge.sqlite.executeSql", args),
    querySql: (...args: any[]) => requestMain("jsBridge.sqlite.querySql", args),
    executeTransaction: (...args: any[]) =>
      requestMain("jsBridge.sqlite.executeTransaction", args),
    executeBatch: (...args: any[]) =>
      requestMain("jsBridge.sqlite.executeBatch", args),
    closeDatabase: (...args: any[]) =>
      requestMain("jsBridge.sqlite.closeDatabase", args),
    setEncryptionKey: (...args: any[]) =>
      requestMain("jsBridge.sqlite.setEncryptionKey", args),
    exportDatabaseToStaging: (...args: any[]) =>
      requestMain("jsBridge.sqlite.exportDatabaseToStaging", args),
    importDatabaseFromStaging: (...args: any[]) =>
      requestMain("jsBridge.sqlite.importDatabaseFromStaging", args),
  }

  const preferences = {
    get: (...args: any[]) => requestMain("jsBridge.preferences.get", args),
    set: (...args: any[]) => requestMain("jsBridge.preferences.set", args),
    remove: (...args: any[]) =>
      requestMain("jsBridge.preferences.remove", args),
    clear: (...args: any[]) => requestMain("jsBridge.preferences.clear", args),
  }

  ;(self as any).jsBridge = { sqlite, preferences }
  ;(self as any).FileTransfer = createMainProxy("FileTransfer")
  ;(self as any).BackupProcessor = createMainProxy("BackupProcessor")
  ;(self as any).NativeCookies = createMainProxy("NativeCookies")
  ;(self as any).Capacitor = {
    Plugins: {
      NativeCookies: (self as any).NativeCookies,
      CapacitorHttp: createMainProxy("Capacitor.Plugins.CapacitorHttp"),
    },
  }
}

async function callPythonFunction(
  modulePath: string,
  functionName: string,
  args: any[],
): Promise<any> {
  if (!pyodide) throw new Error("Pyodide not initialized")

  // Use JSON serialization for args - same approach as main thread mode
  // This avoids complex Pyodide proxy conversion issues
  const argsJson = JSON.stringify(args)
  const escapedArgsJson = argsJson.replace(/\\/g, "\\\\").replace(/'/g, "\\'")

  const code = `
import json
import inspect
import ${modulePath}
args = json.loads('${escapedArgsJson}')
result = ${modulePath}.${functionName}(*args)
if inspect.isawaitable(result):
    result = await result
result
`

  const raw = await pyodide.runPythonAsync(code)
  return convertPyResult(raw)
}

;(self as any).onmessage = async (event: MessageEvent) => {
  const msg = event.data

  if (msg?.kind === "res" && typeof msg.id === "number") {
    const pending = mainPending.get(msg.id)
    if (!pending) return
    mainPending.delete(msg.id)

    if (msg.ok) pending.resolve(msg.result)
    else
      pending.reject(
        Object.assign(
          new Error(msg.error?.message ?? "Worker call failed"),
          msg.error,
        ),
      )
    return
  }

  if (msg?.kind !== "req" || typeof msg.id !== "number") {
    return
  }

  const { id, action, payload } = msg as RequestMessage

  try {
    if (action === "init") {
      const indexURL =
        typeof payload?.indexURL === "string" ? payload.indexURL : "/pyodide/"

      pyodide = await loadPyodide({
        indexURL,
        stdout: (text: string) =>
          postEvent({ kind: "event", event: "stdout", text }),
        stderr: (text: string) =>
          postEvent({ kind: "event", event: "stderr", text }),
      })

      registerWorkerBridge()

      if (payload?.installMobileRequirements) {
        await installMobileRequirements()
      }

      postResponse(id, true, { ok: true })
      return
    }

    if (!pyodide) {
      throw new Error("Pyodide not initialized")
    }

    if (action === "loadAppModules") {
      await loadAppModules()
      postResponse(id, true, { ok: true })
      return
    }

    if (action === "loadDeferredModules") {
      await loadDeferredModules()
      postResponse(id, true, { ok: true })
      return
    }

    if (action === "installDeferredRequirements") {
      await installDeferredRequirements()
      postResponse(id, true, { ok: true })
      return
    }

    if (action === "callPythonFunction") {
      const result = await callPythonFunction(
        String(payload?.modulePath ?? ""),
        String(payload?.functionName ?? ""),
        Array.isArray(payload?.args) ? payload.args : [],
      )
      postResponse(id, true, result)
      return
    }

    if (action === "runPythonAsync") {
      const raw = await pyodide.runPythonAsync(String(payload?.code ?? ""))
      postResponse(id, true, convertPyResult(raw))
      return
    }

    if (action === "runPython") {
      const raw = pyodide.runPython(String(payload?.code ?? ""))
      postResponse(id, true, convertPyResult(raw))
      return
    }

    postResponse(id, false, undefined, new Error(`Unknown action: ${action}`))
  } catch (e) {
    postResponse(id, false, undefined, e)
  }
}
