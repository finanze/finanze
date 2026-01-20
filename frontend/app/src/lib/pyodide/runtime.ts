import { loadPyodide, PyodideInterface } from "pyodide"
import { appConsole } from "../capacitor/appConsole"

let pyodideInstance: PyodideInterface | null = null
let initPromise: Promise<PyodideInterface> | null = null

export interface PyodideRuntimeOptions {
  indexURL?: string
  installMobileRequirements?: boolean
}

const PY_LOG_LEVEL_RE = /\|\s*(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\s*\|/

function logPyodideStdout(text: string): void {
  const line = (text ?? "").toString()
  if (!line) return

  const match = PY_LOG_LEVEL_RE.exec(line)
  const level = match?.[1]

  if (level === "INFO") {
    appConsole.info("[Pyodide stdout]", line)
    return
  }

  if (level === "WARNING" || level === "WARN") {
    appConsole.warn("[Pyodide stdout]", line)
    return
  }

  if (level === "ERROR" || level === "CRITICAL") {
    appConsole.error("[Pyodide stdout]", line)
    return
  }

  if (line.startsWith("Traceback") || line.includes("Exception")) {
    appConsole.error("[Pyodide stdout]", line)
    return
  }

  appConsole.debug("[Pyodide stdout]", line)
}

function normalizeIndexURL(indexURL: string): string {
  return indexURL.endsWith("/") ? indexURL : `${indexURL}/`
}

async function ensurePyodideAssetsAvailable(indexURL: string): Promise<void> {
  const normalized = normalizeIndexURL(indexURL)
  const probeUrl = `${normalized}pyodide-lock.json`

  const response = await fetch(probeUrl, { cache: "no-store" })
  if (response.ok) return

  throw new Error(
    `[Pyodide] Missing runtime assets at ${normalized}. ` +
      `Expected ${probeUrl} (${response.status} ${response.statusText}).\n` +
      `Run: pnpm -C frontend/app install:pyodide`,
  )
}

async function installMobileRequirements(
  pyodide: PyodideInterface,
): Promise<void> {
  // Python imports come from Pyodide's virtual filesystem (FS), not from HTTP.
  // We still fetch our installer sources over HTTP, but we must write any
  // importable modules (like wheels_manifest.py) into the FS first.
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

  try {
    pyodide.FS.mkdirTree("/python")
    pyodide.FS.writeFile("/python/wheels_manifest.py", wheelsManifestSource)
  } catch (e) {
    appConsole.error("[Pyodide] Failed to write wheels_manifest.py into FS:", e)
    throw new Error(
      "[Pyodide] Failed to write wheels_manifest.py into the Pyodide filesystem.",
      { cause: e },
    )
  }

  await pyodide.loadPackage("micropip")
  await pyodide.loadPackage("packaging")
  await pyodide.loadPackage("pyparsing")

  // Validate that the loaded packages are actually importable before executing
  // our installer script. This avoids masking failures as "micropip is not available".
  try {
    await pyodide.runPythonAsync(
      ["import sys", 'print("[Pyodide] sys.path:", sys.path)'].join("\n"),
    )

    await pyodide.runPythonAsync(
      [
        "import micropip",
        "import packaging",
        "import pyparsing",
        'print("[Pyodide] micropip OK")',
      ].join("\n"),
    )

    await pyodide.runPythonAsync(
      [
        "import sys",
        'if "/python" not in sys.path:',
        '    sys.path.append("/python")',
        "import wheels_manifest",
        'print("[Pyodide] wheels_manifest OK")',
      ].join("\n"),
    )
  } catch (e) {
    appConsole.error("[Pyodide] Core package import probe failed:", e)
    throw new Error(
      "[Pyodide] Failed to import core packages after loadPackage(). " +
        "This usually means the local /pyodide bundle is missing wheels/metadata or is mismatched with the JS runtime. " +
        "Re-run: pnpm -C frontend/app install:pyodide",
      { cause: e },
    )
  }

  try {
    await pyodide.runPythonAsync(
      [
        "import sys",
        'if "/python" not in sys.path:',
        '    sys.path.append("/python")',
        "",
        source,
        "",
        "await install()",
        "",
      ].join("\n"),
    )
  } catch (e) {
    appConsole.error("[Pyodide] Mobile requirements install failed:", e)
    throw e
  }
}

export async function initPyodide(
  options: PyodideRuntimeOptions = {},
): Promise<PyodideInterface> {
  if (pyodideInstance) {
    return pyodideInstance
  }

  if (initPromise) {
    return initPromise
  }

  initPromise = (async () => {
    appConsole.info("[Pyodide] Loading runtime...")

    const indexURL = normalizeIndexURL(options.indexURL ?? "/pyodide/")
    await ensurePyodideAssetsAvailable(indexURL)

    const pyodide = await loadPyodide({
      indexURL,
      stdout: (text: string) => {
        logPyodideStdout(text)
      },
      stderr: (text: string) => {
        if (text) appConsole.error("[Pyodide stderr]", text)
      },
    })

    if (options.installMobileRequirements) {
      appConsole.info("[Pyodide] Installing mobile requirements...")
      await installMobileRequirements(pyodide)
    }

    appConsole.info("[Pyodide] Runtime ready")
    pyodideInstance = pyodide
    return pyodide
  })()

  return initPromise
}

export function getPyodide(): PyodideInterface {
  if (!pyodideInstance) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  return pyodideInstance
}

export function isPyodideReady(): boolean {
  return pyodideInstance !== null
}

export async function runPythonAsync<T = unknown>(code: string): Promise<T> {
  const pyodide = getPyodide()
  return pyodide.runPythonAsync(code)
}

export function runPython<T = unknown>(code: string): T {
  const pyodide = getPyodide()
  return pyodide.runPython(code)
}

export function registerJsFunction(
  name: string,
  fn: (...args: unknown[]) => unknown,
): void {
  const pyodide = getPyodide()
  pyodide.globals.set(name, fn)
}

export function registerJsFunctions(
  functions: Record<string, (...args: unknown[]) => unknown>,
): void {
  for (const [name, fn] of Object.entries(functions)) {
    registerJsFunction(name, fn)
  }
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

export async function callPythonFunction<T = unknown>(
  modulePath: string,
  functionName: string,
  ...args: unknown[]
): Promise<T> {
  const pyodide = getPyodide()

  const argsJson = JSON.stringify(args)
  const code = `
import json
import inspect
import ${modulePath}
args = json.loads('''${argsJson}''')
result = ${modulePath}.${functionName}(*args)
if inspect.isawaitable(result):
    result = await result
result
`

  const rawResult = await pyodide.runPythonAsync(code)
  if (!isPyProxy(rawResult)) {
    return rawResult as T
  }

  try {
    const converted = rawResult.toJs({
      create_proxies: false,
      dict_converter: Object.fromEntries,
    })
    rawResult.destroy()
    return converted as T
  } catch {
    return rawResult as unknown as T
  }
}

export async function importPythonModule(moduleName: string): Promise<unknown> {
  const pyodide = getPyodide()
  return pyodide.pyimport(moduleName)
}

export async function loadPythonSource(source: string): Promise<void> {
  const pyodide = getPyodide()
  await pyodide.runPythonAsync(source)
}

export function resetPyodide(): void {
  pyodideInstance = null
  initPromise = null
}
