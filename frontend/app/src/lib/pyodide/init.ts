import {
  initPyodide,
  loadAppModules,
  loadDeferredModules,
  loadLazyModules,
  callPythonFunction,
  registerBridgeWithPyodide,
  installDeferredRequirements,
  installLazyRequirements,
  initBackgroundWorker,
  callBackgroundPythonFunction,
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
  "GET /api/v1/cloud/backup",
  "POST /api/v1/cloud/auth",
  "GET /api/v1/cloud/auth",
  "GET /api/v1/cloud/backup/settings",
])

function logInfo(message: string, data?: any) {
  appConsole.info(`[PyodideInit] ${message}`, data === undefined ? "" : data)
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

// ---------------------------------------------------------------------------
// Background worker (worker 2) orchestration: tracked quote/loan updates run in
// a second Pyodide worker sharing the main worker's SQLite connection.
// ---------------------------------------------------------------------------
let backgroundWarmStarted = false
let backgroundConnectedPromise: Promise<void> | null = null
let isBackgroundConnected = false

function warmStartBackgroundWorker(): void {
  if (backgroundWarmStarted) return
  backgroundWarmStarted = true
  initBackgroundWorker().catch(e => {
    appConsole.error("[PyodideInit][bg] Background warm-start failed:", e)
  })
}

function connectBackgroundWorker(username: string): Promise<void> {
  // Idempotent: a single connect per session. Subsequent calls reuse the
  // in-flight / resolved promise.
  if (backgroundConnectedPromise) return backgroundConnectedPromise

  warmStartBackgroundWorker()

  backgroundConnectedPromise = (async () => {
    await initBackgroundWorker()
    const platformType = (window as any)?.platform?.type
    await callBackgroundPythonFunction(
      "init_background",
      "initialize",
      typeof platformType === "string" ? platformType : null,
    )
    logInfo("[bg] Connecting background worker to shared DB...")
    await callBackgroundPythonFunction(
      "init_background",
      "connect",
      username ?? null,
    )
    isBackgroundConnected = true
    logInfo("[bg] Background worker connected.")
  })().catch(e => {
    // Reset so a later attempt (e.g. next login) can retry.
    backgroundConnectedPromise = null
    isBackgroundConnected = false
    appConsole.error("[PyodideInit][bg] Background connect failed:", e)
    throw e
  })

  return backgroundConnectedPromise
}

async function disconnectBackgroundWorker(): Promise<void> {
  const wasConnecting = backgroundConnectedPromise
  backgroundConnectedPromise = null
  isBackgroundConnected = false
  if (!wasConnecting) return

  try {
    // Make sure connect finished before we drop the reference, to avoid racing
    // an in-flight attach.
    await wasConnecting.catch(() => undefined)
    await callBackgroundPythonFunction("init_background", "disconnect")
    logInfo("[bg] Background worker disconnected.")
  } catch (e) {
    appConsole.error("[PyodideInit][bg] Background disconnect failed:", e)
  }
}

function isBackgroundReady(): boolean {
  return isBackgroundConnected
}

async function backgroundUpdateQuotes(): Promise<unknown> {
  if (backgroundConnectedPromise) {
    await backgroundConnectedPromise
  }
  return callBackgroundPythonFunction("init_background", "update_quotes")
}

async function backgroundUpdateLoans(): Promise<unknown> {
  if (backgroundConnectedPromise) {
    await backgroundConnectedPromise
  }
  return callBackgroundPythonFunction("init_background", "update_loans")
}

async function backgroundGetNetworthTimeline(query?: {
  base_currency?: string
  from_date?: string
  to_date?: string
  no_calculation?: boolean
}): Promise<unknown> {
  if (backgroundConnectedPromise) {
    await backgroundConnectedPromise
  }
  return callBackgroundPythonFunction(
    "init_background",
    "get_networth_timeline",
    query?.base_currency,
    query?.from_date,
    query?.to_date,
    query?.no_calculation ?? false,
  )
}

export {
  API_PREFIX,
  withApiPrefix,
  ensureInitialized,
  ensureCoreInitialized,
  triggerDeferredInit,
  triggerLazyInit,
  waitForLazyInit,
  warmStartBackgroundWorker,
  connectBackgroundWorker,
  disconnectBackgroundWorker,
  isBackgroundReady,
  backgroundUpdateQuotes,
  backgroundUpdateLoans,
  backgroundGetNetworthTimeline,
}
