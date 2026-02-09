import { Capacitor } from "@capacitor/core"

export type OpenDatabaseParams = {
  encrypted: boolean
  mode: string
}

let webStoreInitialized = false
let webTransactionDepth = 0

export function isDevWeb(): boolean {
  return import.meta.env.DEV && Capacitor.getPlatform() === "web"
}

export function isWebPlatform(platform: string): boolean {
  return platform === "web"
}

export function assertNotWeb(platform: string, message: string): void {
  if (isWebPlatform(platform)) {
    throw new Error(message)
  }
}

export function normalizeSql(sql: string): string {
  return sql.trim().replace(/\s+/g, " ")
}

export function normalizeSqlForMatch(sql: string): string {
  return normalizeSql(sql).replace(/;$/, "").toUpperCase()
}

export function isJournalModeWalPragma(sql: string): boolean {
  const normalized = normalizeSql(sql).toUpperCase()
  return (
    normalized.startsWith("PRAGMA JOURNAL_MODE") && normalized.includes("WAL")
  )
}

export function bumpWebTxDepth(delta: 1 | -1): void {
  if (!isDevWeb()) return
  webTransactionDepth = Math.max(0, webTransactionDepth + delta)
}

export function canPersistWebStore(): boolean {
  return isDevWeb() && webTransactionDepth === 0
}

export function markWebStoreInitialized(): void {
  webStoreInitialized = true
}

export function isWebStoreInitialized(): boolean {
  return webStoreInitialized
}

export function coerceOpenDatabaseParamsForPlatform(
  platform: string,
  params: OpenDatabaseParams,
  warn: (msg: string) => void,
): OpenDatabaseParams {
  if (platform !== "web") return params
  if (!params.encrypted) return params

  warn(
    "[Bridge][sqlite] encryption requested on web; forcing no-encryption for dev web",
  )
  return { encrypted: false, mode: "no-encryption" }
}

export async function maybeInitWebStore(
  initWebStore: () => Promise<void>,
  withTimeout: <T>(
    label: string,
    promise: Promise<T>,
    ms: number,
  ) => Promise<T>,
  log: (msg: string) => void,
): Promise<void> {
  if (!import.meta.env.DEV) return
  if (Capacitor.getPlatform() !== "web") return
  if (isWebStoreInitialized()) return

  log("[Bridge][sqlite] initWebStore start")
  await ensureSqliteWebDevReady()
  try {
    await withTimeout("initWebStore", initWebStore(), 30_000)
  } catch {
    await withTimeout("initWebStore(retry)", initWebStore(), 30_000)
  }
  markWebStoreInitialized()
  log("[Bridge][sqlite] initWebStore done")
}

export async function maybePersistWebStore(
  saveToStore: () => Promise<void>,
  label: string,
  logDebug: (msg: string, meta?: any) => void,
  logWarn: (msg: string, meta?: any) => void,
): Promise<void> {
  if (!isDevWeb()) return
  if (!canPersistWebStore()) return

  try {
    await saveToStore()
    logDebug("[Bridge][sqlite] saveToStore ok", { label })
  } catch (e) {
    logWarn("[Bridge][sqlite] saveToStore failed", { label, error: e })
  }
}

export function maybeRewriteSqlForWeb(sql: string): string {
  if (!isDevWeb()) return sql
  if (!isJournalModeWalPragma(sql)) return sql
  return "PRAGMA journal_mode = DELETE"
}

export async function ensureSqliteWebDevReady(): Promise<void> {
  if (!import.meta.env.DEV) return
  if (Capacitor.getPlatform() !== "web") return

  const { defineCustomElements: defineJeepSqliteCustomElements } =
    await import("jeep-sqlite/loader")

  defineJeepSqliteCustomElements(window)

  await customElements.whenDefined("jeep-sqlite")

  let jeepEl = document.querySelector("jeep-sqlite") as HTMLElement | null
  if (!jeepEl) {
    jeepEl = document.createElement("jeep-sqlite")
    document.body.appendChild(jeepEl)
  }

  const maybeReady = (jeepEl as any).componentOnReady
  if (typeof maybeReady === "function") {
    await maybeReady.call(jeepEl)
  }
}
