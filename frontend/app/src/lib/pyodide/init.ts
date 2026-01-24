import {
  initPyodide,
  loadAppModules,
  loadDeferredModules,
  callPythonFunction,
  registerBridgeWithPyodide,
  installDeferredRequirements,
} from "@/lib/pyodide"
import { appConsole } from "@/lib/capacitor/appConsole"

const API_PREFIX = "/api/v1"

const CORE_ENDPOINTS = new Set(["GET /api/v1/status"])

function logInfo(message: string, data?: any) {
  appConsole.info(`[PyodideInit] ${message}`, data)
}

let isCoreInitialized = false
let isDeferredInitialized = false
let coreInitPromise: Promise<void> | null = null
let deferredInitPromise: Promise<void> | null = null

function withApiPrefix(path: string): string {
  if (path.startsWith(API_PREFIX)) {
    return path
  }
  return `${API_PREFIX}${path}`
}

function isCoreEndpoint(method: string, path: string): boolean {
  const fullPath = withApiPrefix(path)
  return CORE_ENDPOINTS.has(`${method.toUpperCase()} ${fullPath}`)
}

async function ensureCoreInitialized() {
  if (isCoreInitialized) return
  if (coreInitPromise) return coreInitPromise

  coreInitPromise = (async () => {
    const t0 = performance.now()
    logInfo("Starting core initialization...")

    await initPyodide({ installMobileRequirements: true })
    logInfo(`initPyodide done in ${(performance.now() - t0).toFixed(0)}ms`)

    registerBridgeWithPyodide()

    const t1 = performance.now()
    await loadAppModules()
    logInfo(`loadAppModules done in ${(performance.now() - t1).toFixed(0)}ms`)

    const t2 = performance.now()
    const platformType = (window as any)?.platform?.type
    await callPythonFunction(
      "init",
      "initialize",
      typeof platformType === "string" ? platformType : null,
    )
    logInfo(
      `Python init.initialize done in ${(performance.now() - t2).toFixed(0)}ms`,
    )

    isCoreInitialized = true
    logInfo(
      `Core initialization complete in ${(performance.now() - t0).toFixed(0)}ms (/status ready)`,
    )
  })().catch(e => {
    appConsole.error("[PyodideInit] Core initialization failed:", e)
    throw e
  })

  return coreInitPromise
}

async function ensureDeferredInitialized() {
  await ensureCoreInitialized()

  if (isDeferredInitialized) return
  if (deferredInitPromise) return deferredInitPromise

  deferredInitPromise = (async () => {
    logInfo("Starting deferred initialization...")

    await installDeferredRequirements()

    await loadDeferredModules()

    await callPythonFunction("init", "initialize_deferred")

    isDeferredInitialized = true
    logInfo("Deferred initialization complete (all routes ready)")
  })().catch(e => {
    appConsole.error("[PyodideInit] Deferred initialization failed:", e)
    throw e
  })

  return deferredInitPromise
}

async function ensureInitialized(method: string, path: string) {
  if (isCoreEndpoint(method, path)) {
    return ensureCoreInitialized()
  }
  return ensureDeferredInitialized()
}

function triggerDeferredInit(): void {
  if (!isCoreInitialized || isDeferredInitialized || deferredInitPromise) return
  ensureDeferredInitialized()
}

export { API_PREFIX, withApiPrefix, ensureInitialized, triggerDeferredInit }
