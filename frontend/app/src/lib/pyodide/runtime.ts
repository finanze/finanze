import { appConsole } from "../capacitor/appConsole"
import { PyodideWorkerClient } from "./worker/client"

let workerClient: PyodideWorkerClient | null = null
let workerInitPromise: Promise<void> | null = null

export interface PyodideRuntimeOptions {
  indexURL?: string
  installMobileRequirements?: boolean
}

export async function initPyodide(
  options: PyodideRuntimeOptions = {},
): Promise<void> {
  if (workerClient && workerInitPromise) {
    await workerInitPromise
    return
  }

  if (!workerClient) {
    workerClient = new PyodideWorkerClient()
  }

  workerInitPromise = (async () => {
    appConsole.info("[Pyodide] Loading runtime (worker)...")
    await workerClient!.init({
      indexURL: options.indexURL ?? "/pyodide/",
      installMobileRequirements: !!options.installMobileRequirements,
    })
    appConsole.info("[Pyodide] Runtime ready (worker)")
  })()

  await workerInitPromise
}

export function isPyodideReady(): boolean {
  return workerClient !== null && workerInitPromise !== null
}

export async function runPythonAsync<T = unknown>(code: string): Promise<T> {
  if (!workerClient || !workerInitPromise) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  await workerInitPromise
  return (await workerClient.runPythonAsync(code)) as T
}

export async function callPythonFunction<T = unknown>(
  modulePath: string,
  functionName: string,
  ...args: unknown[]
): Promise<T> {
  if (!workerClient || !workerInitPromise) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  await workerInitPromise
  return (await workerClient.callPythonFunction(
    modulePath,
    functionName,
    args,
  )) as T
}

export async function importPythonModule(moduleName: string): Promise<void> {
  await runPythonAsync(`import ${moduleName}`)
}

export async function loadPythonSource(source: string): Promise<void> {
  await runPythonAsync(source)
}

export function resetPyodide(): void {
  if (workerClient) {
    workerClient.terminate()
  }
  workerClient = null
  workerInitPromise = null
}

export async function loadAppModules(): Promise<void> {
  if (!workerClient || !workerInitPromise) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  await workerInitPromise
  appConsole.info("[Pyodide] Loading core app modules...")
  await workerClient.loadAppModules()
  appConsole.info("[Pyodide] Loaded core app modules.")
}

export async function loadDeferredModules(): Promise<void> {
  if (!workerClient || !workerInitPromise) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  await workerInitPromise
  appConsole.info("[Pyodide] Loading deferred app modules...")
  await workerClient.loadDeferredModules()
  appConsole.info("[Pyodide] Loaded deferred app modules.")
}

export async function installDeferredRequirements(): Promise<void> {
  if (!workerClient || !workerInitPromise) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }
  await workerInitPromise
  appConsole.info("[Pyodide] Installing deferred requirements...")
  await workerClient.installDeferredRequirements()
  appConsole.info("[Pyodide] Deferred requirements installed.")
}
