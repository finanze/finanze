import {
  CapacitorSQLite,
  SQLiteConnection,
  SQLiteDBConnection,
} from "@capacitor-community/sqlite"
import { Capacitor } from "@capacitor/core"
import { BackupProcessor } from "@/lib/capacitor/plugins"

import { appConsole } from "@/lib/capacitor/appConsole"

import {
  normalizeSqlForMatch,
  bumpWebTxDepth,
  coerceOpenDatabaseParamsForPlatform,
  assertNotWeb,
  isWebPlatform,
  maybeInitWebStore,
  maybePersistWebStore,
  maybeRewriteSqlForWeb,
} from "../sqlite/webDev"

let sqliteConnection: SQLiteConnection | null = null
let currentDb: SQLiteDBConnection | null = null
let currentDbName: string | null = null

function stripLeadingSqlComments(sql: string): string {
  let rest = sql
  while (true) {
    const trimmed = rest.trimStart()
    if (trimmed.startsWith("--")) {
      const nl = trimmed.indexOf("\n")
      rest = nl >= 0 ? trimmed.slice(nl + 1) : ""
      continue
    }
    if (trimmed.startsWith("/*")) {
      const end = trimmed.indexOf("*/", 2)
      rest = end >= 0 ? trimmed.slice(end + 2) : ""
      continue
    }
    return trimmed
  }
}

async function ensureEncryptionSecret(passphrase: string): Promise<void> {
  if (!passphrase) return
  if (isWebPlatform(Capacitor.getPlatform())) return

  const sqlite = await initSQLite()

  const hasIsSecretStored = typeof (sqlite as any).isSecretStored === "function"
  const hasCheck = typeof (sqlite as any).checkEncryptionSecret === "function"
  const hasClear = typeof (sqlite as any).clearEncryptionSecret === "function"

  if (!hasIsSecretStored || !hasCheck) {
    await withTimeout(
      "setEncryptionSecret",
      sqlite.setEncryptionSecret(passphrase),
      10_000,
    )
    return
  }

  const stored = await withTimeout(
    "isSecretStored",
    sqlite.isSecretStored(),
    10_000,
  )
  if (!stored?.result) {
    await withTimeout(
      "setEncryptionSecret",
      sqlite.setEncryptionSecret(passphrase),
      10_000,
    )
    return
  }

  const check = await withTimeout(
    "checkEncryptionSecret",
    sqlite.checkEncryptionSecret(passphrase),
    10_000,
  )

  if (!check?.result) {
    if (hasClear) {
      await withTimeout(
        "clearEncryptionSecret",
        sqlite.clearEncryptionSecret(),
        10_000,
      )
    }
    await withTimeout(
      "setEncryptionSecret",
      sqlite.setEncryptionSecret(passphrase),
      10_000,
    )
  }
}

function withTimeout<T>(
  label: string,
  promise: Promise<T>,
  ms: number,
): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  const timeoutPromise = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(
        new Error(`[Bridge][sqlite] Timeout during ${label} after ${ms}ms`),
      )
    }, ms)
  })

  return Promise.race([promise, timeoutPromise]).finally(() => {
    if (timeoutId) clearTimeout(timeoutId)
  }) as Promise<T>
}

async function initSQLite(): Promise<SQLiteConnection> {
  if (!sqliteConnection) {
    sqliteConnection = new SQLiteConnection(CapacitorSQLite)
  }

  await maybeInitWebStore(
    () => sqliteConnection!.initWebStore() as any,
    withTimeout,
    msg => appConsole.debug(msg),
  )

  return sqliteConnection
}

async function persistWebStoreIfNeeded(label: string): Promise<void> {
  if (!sqliteConnection) return
  if (!currentDbName) return

  await maybePersistWebStore(
    () => sqliteConnection!.saveToStore(currentDbName!),
    label,
    (msg, meta) => appConsole.debug(msg, { ...meta, dbName: currentDbName }),
    (msg, meta) => appConsole.warn(msg, { ...meta, dbName: currentDbName }),
  )
}

async function openDatabase(
  dbName: string,
  encrypted: boolean = true,
  mode: string = "no-encryption",
  version: number = 1,
  readonly: boolean = false,
  passphrase?: string | null,
): Promise<SQLiteDBConnection> {
  const platform = Capacitor.getPlatform()
  const effectiveDbName = dbName.endsWith(".db") ? dbName.slice(0, -3) : dbName

  ;({ encrypted, mode } = coerceOpenDatabaseParamsForPlatform(
    platform,
    { encrypted, mode },
    msg => appConsole.warn(msg),
  ))

  appConsole.debug("[Bridge][sqlite] openDatabase start", {
    dbName: effectiveDbName,
    encrypted,
    mode,
    version,
    readonly,
    platform,
  })

  const sqlite = await initSQLite()

  // The JS connection dict can get out of sync with native connections on iOS.
  // This call clears stale entries when native reports inconsistency.
  await sqlite.checkConnectionsConsistency().catch(() => undefined)

  currentDbName = effectiveDbName

  appConsole.debug("[Bridge][sqlite] isConnection", { dbName: effectiveDbName })
  const isConn = await withTimeout(
    "isConnection",
    sqlite.isConnection(effectiveDbName, readonly),
    10_000,
  )
  if (isConn.result) {
    appConsole.debug("[Bridge][sqlite] reusing existing connection", {
      dbName: effectiveDbName,
    })

    // Even if a connection exists in the plugin, it may not be open (e.g. after
    // calling close() we can still see isConnection=true). Ensure secret + open.
    if (encrypted && passphrase) {
      await ensureEncryptionSecret(passphrase)
    }

    try {
      const existing = await withTimeout(
        "retrieveConnection",
        sqlite.retrieveConnection(effectiveDbName, readonly),
        10_000,
      )

      try {
        const hasIsDbOpen = typeof (existing as any).isDBOpen === "function"
        const openRes = hasIsDbOpen ? await (existing as any).isDBOpen() : null
        const isOpen =
          typeof openRes === "object" && openRes !== null
            ? !!(openRes as any).result
            : !!openRes
        if (!isOpen) {
          await withTimeout("db.open(reuse)", existing.open(), 15_000)
        }
      } catch {
        // If open-state probing fails, still attempt open (it is usually idempotent).
        await withTimeout("db.open(reuse)", existing.open(), 15_000)
      }

      currentDb = existing
      currentDbName = existing.getConnectionDBName?.() ?? effectiveDbName
      return existing
    } catch (e) {
      appConsole.warn("[Bridge][sqlite] reuse failed; recreating connection", {
        dbName: effectiveDbName,
        error: e,
      })
      await sqlite
        .closeConnection(effectiveDbName, readonly)
        .catch(() => undefined)
      await sqlite.checkConnectionsConsistency().catch(() => undefined)
      // Fall through to createConnection path.
    }
  }

  try {
    if (encrypted && passphrase) {
      await ensureEncryptionSecret(passphrase)
    }

    appConsole.debug("[Bridge][sqlite] createConnection", {
      dbName: effectiveDbName,
    })
    const created = await withTimeout(
      "createConnection",
      sqlite.createConnection(
        effectiveDbName,
        encrypted,
        mode,
        version,
        readonly,
      ),
      15_000,
    )
    currentDb = created
    currentDbName = created.getConnectionDBName?.() ?? effectiveDbName
    appConsole.debug("[Bridge][sqlite] connection created, opening...", {
      dbName: effectiveDbName,
    })
    await withTimeout("db.open", created.open(), 15_000)
    await persistWebStoreIfNeeded("openDatabase")
    appConsole.debug("[Bridge][sqlite] openDatabase done", {
      dbName: effectiveDbName,
    })
    return created
  } catch (e) {
    appConsole.error("[Bridge][sqlite] openDatabase failed", {
      dbName: effectiveDbName,
      error: e,
    })
    throw e
  }
}

async function executeSql(
  sql: string,
  values: unknown[] = [],
): Promise<{ changes: number; lastId: number }> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }

  let effectiveSql = sql
  effectiveSql = maybeRewriteSqlForWeb(effectiveSql)

  const sqlForExecution = stripLeadingSqlComments(effectiveSql)
  if (!sqlForExecution) {
    return { changes: 0, lastId: -1 }
  }

  const sqlMatch = normalizeSqlForMatch(sqlForExecution)
  if (sqlMatch === "BEGIN" || sqlMatch === "BEGIN TRANSACTION") {
    bumpWebTxDepth(1)
    await currentDb.beginTransaction()
    return { changes: 0, lastId: -1 }
  }

  if (sqlMatch === "COMMIT" || sqlMatch === "COMMIT TRANSACTION") {
    bumpWebTxDepth(-1)
    await currentDb.commitTransaction()
    await persistWebStoreIfNeeded("commitTransaction")
    return { changes: 0, lastId: -1 }
  }

  if (sqlMatch === "ROLLBACK" || sqlMatch === "ROLLBACK TRANSACTION") {
    bumpWebTxDepth(-1)
    await currentDb.rollbackTransaction()
    await persistWebStoreIfNeeded("rollbackTransaction")
    return { changes: 0, lastId: -1 }
  }

  // On Android, PRAGMA statements are treated as queries internally and may fail
  // when executed through `run()`/`execute()`.
  if (sqlMatch.startsWith("PRAGMA")) {
    await currentDb.query(sqlForExecution, values)
    await persistWebStoreIfNeeded("executeSql(PRAGMA)")
    return { changes: 0, lastId: -1 }
  }

  const result = await currentDb.run(sqlForExecution, values, false)
  await persistWebStoreIfNeeded("executeSql")
  return {
    changes: result.changes?.changes ?? 0,
    lastId: result.changes?.lastId ?? -1,
  }
}

async function querySql(
  sql: string,
  values: unknown[] = [],
): Promise<unknown[]> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }

  const sqlForExecution = stripLeadingSqlComments(sql)
  if (!sqlForExecution) return []

  const result = await currentDb.query(sqlForExecution, values)
  return result.values ?? []
}

async function executeBatch(
  statements: string,
  transaction: boolean = true,
): Promise<{ changes: number }> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }

  const result = await currentDb.execute(statements, transaction)
  await persistWebStoreIfNeeded("executeBatch")
  return { changes: result.changes?.changes ?? 0 }
}

async function exportDatabaseToStaging(
  stagingFileName: string,
): Promise<{ ok: true }> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }
  assertNotWeb(
    Capacitor.getPlatform(),
    "exportDatabaseToStaging is not supported on web. Use mobile.",
  )

  const stagingPathRes = await BackupProcessor.getFilePath({
    fileName: stagingFileName,
  })
  const stagingPath = stagingPathRes?.path
  if (!stagingPath) throw new Error("Failed to get staging file path")

  const attachSql = `ATTACH DATABASE '${stagingPath.replace(/'/g, "''")}' AS plaintext KEY '';`
  await currentDb.execute(attachSql, false)
  // CapacitorSQLite on Android requires SELECT statements to go through query().
  await currentDb.query("SELECT sqlcipher_export('plaintext');", [])
  await currentDb.execute("DETACH DATABASE plaintext;", false)

  appConsole.debug("[Bridge][sqlite] Exported database to staging", {
    stagingFileName,
  })
  return { ok: true }
}

async function importDatabaseFromStaging(
  dbName: string,
  password: string,
  stagingFileName: string,
): Promise<{ ok: true }> {
  assertNotWeb(
    Capacitor.getPlatform(),
    "importDatabaseFromStaging is not supported on web. Use mobile.",
  )

  await closeDatabase()

  const stagingPathRes = await BackupProcessor.getFilePath({
    fileName: stagingFileName,
  })
  const stagingPath = stagingPathRes?.path
  if (!stagingPath) throw new Error("Failed to get staging file path")

  const db = await openDatabase(dbName, true, "secret", 1, false, password)
  await setEncryptionKey(password)

  {
    await db.execute("PRAGMA foreign_keys = OFF;", false)

    const viewsRes = await db.query(
      "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type = 'view'",
      [],
    )
    const tablesRes = await db.query(
      "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type = 'table'",
      [],
    )

    const views: Array<{ name?: string }> = (viewsRes?.values ?? []) as any
    const tables: Array<{ name?: string }> = (tablesRes?.values ?? []) as any
    const total = views.length + tables.length

    if (total > 0) {
      appConsole.warn(
        "[Bridge][sqlite] import: destination not empty; dropping objects",
        {
          count: total,
          names: [...views, ...tables]
            .map(o => o?.name)
            .filter(Boolean)
            .slice(0, 20),
        },
      )
    }

    for (const obj of views) {
      const name = typeof obj?.name === "string" ? obj.name : ""
      if (!name) continue
      const escaped = `"${name.replace(/"/g, '""')}"`
      await db
        .execute(`DROP VIEW IF EXISTS ${escaped};`, false)
        .catch(() => undefined)
    }

    for (const obj of tables) {
      const name = typeof obj?.name === "string" ? obj.name : ""
      if (!name) continue
      const escaped = `"${name.replace(/"/g, '""')}"`
      await db
        .execute(`DROP TABLE IF EXISTS ${escaped};`, false)
        .catch(() => undefined)
    }
  }

  const attachSql = `ATTACH DATABASE '${stagingPath.replace(/'/g, "''")}' AS plaintext KEY '';`
  await db.execute(attachSql, false)
  // CapacitorSQLite on Android requires SELECT statements to go through query().
  await db.query("SELECT sqlcipher_export('main', 'plaintext');", [])
  await db.execute("DETACH DATABASE plaintext;", false)

  appConsole.debug("[Bridge][sqlite] Imported database from staging", {
    stagingFileName,
  })

  await closeDatabase()
  return { ok: true }
}

async function executeTransaction(
  statements: Array<{ sql: string; values?: unknown[] }>,
): Promise<void> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }

  bumpWebTxDepth(1)
  await currentDb.beginTransaction()
  try {
    for (const stmt of statements) {
      await currentDb.run(stmt.sql, stmt.values ?? [], false)
    }
    bumpWebTxDepth(-1)
    await currentDb.commitTransaction()
    await persistWebStoreIfNeeded("executeTransaction")
  } catch (error) {
    bumpWebTxDepth(-1)
    await currentDb.rollbackTransaction()
    throw error
  }
}

async function closeDatabase(): Promise<void> {
  const name = currentDbName
  if (currentDb) {
    await persistWebStoreIfNeeded("closeDatabase")
    await currentDb.close()
    currentDb = null
  }
  currentDbName = null

  // Ensure the native plugin forgets the connection too, otherwise subsequent
  // openDatabase() calls may reuse a closed connection.
  if (sqliteConnection && name) {
    await sqliteConnection.closeConnection(name, false).catch(() => undefined)
  }
}

async function setEncryptionKey(key: string): Promise<void> {
  if (!currentDb) {
    throw new Error("Database not opened. Call openDatabase first.")
  }

  // For native mobile we rely on openDatabase(..., mode="secret", passphrase)
  // which stores the secret and keys the DB during open().
  if (Capacitor.getPlatform() !== "web") return

  // Web dev fallback (unencrypted): keep signature stable.
  void key
}

export const sqliteBridge = {
  openDatabase,
  executeSql,
  querySql,
  executeTransaction,
  executeBatch,
  closeDatabase,
  setEncryptionKey,
  exportDatabaseToStaging,
  importDatabaseFromStaging,
}
