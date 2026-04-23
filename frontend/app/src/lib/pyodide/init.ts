import {
  initPyodide,
  loadAppModules,
  loadDeferredModules,
  loadLazyModules,
  callPythonFunction,
  registerBridgeWithPyodide,
  installDeferredRequirements,
  installLazyRequirements,
} from "@/lib/pyodide"
import { appConsole } from "@/lib/capacitor/appConsole"

const API_PREFIX = "/api/v1"

const CORE_ENDPOINTS = new Set(["GET /api/v1/status"])

const DEFERRED_ENDPOINTS = new Set([
  "POST /api/v1/login",
  "POST /api/v1/signup",
  "POST /api/v1/change-password",
  "POST /api/v1/logout",
  "GET /api/v1/settings",
  "GET /api/v1/entities",
  "GET /api/v1/positions",
  "GET /api/v1/contributions",
  "GET /api/v1/transactions",
  "GET /api/v1/exchange-rates",
  "GET /api/v1/events",
  "GET /api/v1/integrations",
  "GET /api/v1/flows/periodic",
  "GET /api/v1/flows/pending",
  "GET /api/v1/real-estate",
  "POST /api/v1/data/manual/positions/update-quotes",
  "POST /api/v1/data/manual/positions/update-loans",
  "GET /api/v1/cloud/backup",
  "POST /api/v1/cloud/auth",
  "GET /api/v1/cloud/auth",
  "GET /api/v1/cloud/backup/settings",
])

function logInfo(message: string, data?: any) {
  appConsole.info(`[PyodideInit] ${message}`, data)
}

let isCoreInitialized = false
let isDeferredInitialized = false
let isLazyInitialized = false
let coreInitPromise: Promise<void> | null = null
let deferredInitPromise: Promise<void> | null = null
let lazyInitPromise: Promise<void> | null = null

let lazyReadyResolve: (() => void) | null = null
const lazyReadyPromise = new Promise<void>(resolve => {
  lazyReadyResolve = resolve
})

function withApiPrefix(path: string): string {
  if (path.startsWith(API_PREFIX)) {
    return path
  }
  return `${API_PREFIX}${path}`
}

function isCoreEndpoint(method: string, path: string): boolean {
  const fullPath = withApiPrefix(path).split("?")[0]
  return CORE_ENDPOINTS.has(`${method.toUpperCase()} ${fullPath}`)
}

function isDeferredEndpoint(method: string, path: string): boolean {
  const fullPath = withApiPrefix(path).split("?")[0]
  return DEFERRED_ENDPOINTS.has(`${method.toUpperCase()} ${fullPath}`)
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

async function ensureLazyInitialized() {
  await ensureDeferredInitialized()

  if (isLazyInitialized) return
  if (lazyInitPromise) return lazyInitPromise

  lazyInitPromise = (async () => {
    logInfo("Starting lazy initialization...")

    await installLazyRequirements()

    await loadLazyModules()

    await callPythonFunction("init", "initialize_lazy")

    isLazyInitialized = true
    lazyReadyResolve?.()
    logInfo("Lazy initialization complete (all lazy routes ready)")
  })().catch(e => {
    appConsole.error("[PyodideInit] Lazy initialization failed:", e)
    throw e
  })

  return lazyInitPromise
}

async function ensureInitialized(method: string, path: string) {
  if (isCoreEndpoint(method, path)) {
    return ensureCoreInitialized()
  }
  if (isDeferredEndpoint(method, path)) {
    return ensureDeferredInitialized()
  }
  return ensureLazyInitialized()
}

function triggerDeferredInit(): void {
  if (!isCoreInitialized || isDeferredInitialized || deferredInitPromise) return
  ensureDeferredInitialized()
}

function triggerLazyInit(): void {
  if (!isDeferredInitialized || isLazyInitialized || lazyInitPromise) return
  ensureLazyInitialized()
}

function waitForLazyInit(): Promise<void> {
  if (isLazyInitialized) return Promise.resolve()
  return lazyReadyPromise
}

export {
  API_PREFIX,
  withApiPrefix,
  ensureInitialized,
  ensureCoreInitialized,
  triggerDeferredInit,
  triggerLazyInit,
  waitForLazyInit,
}
