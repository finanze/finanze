import { describe, it, expect, beforeEach, vi } from "vitest"

// Keep the REAL ../sqlite/webDev (it only needs @capacitor/core, which we mock
// to report a native platform so its web-store / encryption branches no-op).
// Everything touching the native plugin is faked so these tests exercise ONLY
// the cross-worker transaction-span mutex + shared-connection logic.

vi.mock("@capacitor/core", () => ({
  Capacitor: { getPlatform: () => "android" },
}))

vi.mock("@/lib/capacitor/appConsole", () => ({
  appConsole: { debug: vi.fn(), warn: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const backupProcessorMocks = vi.hoisted(() => ({
  deleteFile: vi.fn(),
  getFilePath: vi.fn(),
}))

const sqliteMocks = vi.hoisted(() => ({
  isConnection: vi.fn(),
  isSecretStored: vi.fn(),
  checkEncryptionSecret: vi.fn(),
  clearEncryptionSecret: vi.fn(),
  setEncryptionSecret: vi.fn(),
  createConnection: vi.fn(),
  retrieveConnection: vi.fn(),
}))

vi.mock("@/lib/capacitor/plugins", () => ({
  BackupProcessor: backupProcessorMocks,
}))

vi.mock("@capacitor-community/sqlite", () => {
  function makeFakeDb() {
    return {
      getConnectionDBName: () => "testdb",
      open: vi.fn().mockResolvedValue(undefined),
      isDBOpen: vi.fn().mockResolvedValue({ result: true }),
      beginTransaction: vi.fn().mockResolvedValue({ changes: { changes: 0 } }),
      commitTransaction: vi.fn().mockResolvedValue({ changes: { changes: 0 } }),
      rollbackTransaction: vi
        .fn()
        .mockResolvedValue({ changes: { changes: 0 } }),
      run: vi.fn().mockResolvedValue({ changes: { changes: 1, lastId: 1 } }),
      query: vi.fn().mockResolvedValue({ values: [] }),
      execute: vi.fn().mockResolvedValue({ changes: { changes: 0 } }),
      close: vi.fn().mockResolvedValue(undefined),
    }
  }

  class SQLiteConnection {
    checkConnectionsConsistency = vi.fn().mockResolvedValue({ result: true })
    isConnection = sqliteMocks.isConnection
    isSecretStored = sqliteMocks.isSecretStored
    checkEncryptionSecret = sqliteMocks.checkEncryptionSecret
    clearEncryptionSecret = sqliteMocks.clearEncryptionSecret
    setEncryptionSecret = sqliteMocks.setEncryptionSecret
    createConnection = sqliteMocks.createConnection.mockImplementation(
      async () => makeFakeDb(),
    )
    retrieveConnection = sqliteMocks.retrieveConnection.mockImplementation(
      async () => makeFakeDb(),
    )
    closeConnection = vi.fn().mockResolvedValue(undefined)
    saveToStore = vi.fn().mockResolvedValue(undefined)
    initWebStore = vi.fn().mockResolvedValue(undefined)
  }

  return { CapacitorSQLite: {}, SQLiteConnection }
})

type Bridge = typeof import("@/lib/pyodide/bridges/sqliteBridge")
let bridge: Bridge

beforeEach(async () => {
  // Fresh module state per test: txOwner / readyDbName / waiters /
  // opLock / currentDb all reset.
  for (const mock of Object.values(sqliteMocks)) mock.mockReset()
  sqliteMocks.isConnection.mockResolvedValue({ result: false })
  sqliteMocks.isSecretStored.mockResolvedValue({ result: true })
  sqliteMocks.checkEncryptionSecret.mockResolvedValue({ result: false })
  sqliteMocks.clearEncryptionSecret.mockResolvedValue(undefined)
  sqliteMocks.setEncryptionSecret.mockResolvedValue(undefined)
  backupProcessorMocks.deleteFile.mockReset()
  backupProcessorMocks.deleteFile.mockResolvedValue({ success: true })
  backupProcessorMocks.getFilePath.mockReset()
  backupProcessorMocks.getFilePath.mockResolvedValue({
    path: "/tmp/staging.db",
    exists: false,
  })
  vi.resetModules()
  bridge = await import("@/lib/pyodide/bridges/sqliteBridge")
})

function track<T>(p: Promise<T>) {
  const state = {
    settled: false,
    value: undefined as T | undefined,
    error: undefined as unknown,
  }
  p.then(
    v => {
      state.settled = true
      state.value = v
    },
    e => {
      state.settled = true
      state.error = e
    },
  )
  return state
}

async function flush() {
  await Promise.resolve()
  await new Promise(resolve => setTimeout(resolve, 0))
  await Promise.resolve()
}

async function openShared(dbName = "testdb.db") {
  const main = bridge.getSqliteBridge("main")
  const db = await main.openDatabase(dbName, false, "no-encryption", 1, false)
  return { main, db }
}

describe("sqliteBridge encryption secret", () => {
  it.each([false, true])(
    "classifies an active database state error as a wrong key (reuse: %s)",
    async reuse => {
      const nativeError = new Error(
        "SetEncryptionSecret: State for: testdbSQLite.db not correct",
      )
      sqliteMocks.isConnection.mockResolvedValue({ result: reuse })
      sqliteMocks.setEncryptionSecret.mockRejectedValueOnce(nativeError)
      const main = bridge.getSqliteBridge("main")

      await expect(
        main.openDatabase("testdb.db", true, "secret", 1, false, "wrong"),
      ).rejects.toMatchObject({
        message: "[Bridge][sqlite] wrong key for testdb",
        cause: nativeError,
      })
      expect(sqliteMocks.clearEncryptionSecret).toHaveBeenCalledOnce()
      expect(sqliteMocks.setEncryptionSecret).toHaveBeenCalledWith("wrong")
      expect(sqliteMocks.createConnection).not.toHaveBeenCalled()
      expect(sqliteMocks.retrieveConnection).not.toHaveBeenCalled()

      await expect(
        main.openDatabase("testdb.db", true, "secret", 1, false, "correct"),
      ).resolves.toBeDefined()
    },
  )

  it.each([
    "SetEncryptionSecret: State for: otherSQLite.db not correct",
    "Keychain unavailable",
  ])("preserves other secret errors: %s", async message => {
    const nativeError = new Error(message)
    sqliteMocks.setEncryptionSecret.mockRejectedValueOnce(nativeError)
    const main = bridge.getSqliteBridge("main")

    await expect(
      main.openDatabase("testdb.db", true, "secret", 1, false, "wrong"),
    ).rejects.toBe(nativeError)
    expect(sqliteMocks.createConnection).not.toHaveBeenCalled()
  })
})

describe("sqliteBridge staging export", () => {
  it("clears the previous export before each staging export", async () => {
    const { main, db } = await openShared()
    const executeMock = db.execute as ReturnType<typeof vi.fn>
    const queryMock = db.query as ReturnType<typeof vi.fn>
    const operations: string[] = []
    let stagingExists = true

    backupProcessorMocks.deleteFile.mockImplementation(async () => {
      operations.push("delete")
      stagingExists = false
      return { success: true }
    })
    backupProcessorMocks.getFilePath.mockImplementation(async () => {
      operations.push("verify")
      return { path: "/tmp/staging.db", exists: stagingExists }
    })
    executeMock.mockClear()
    executeMock.mockImplementation(async (statement: string) => {
      operations.push(statement.startsWith("ATTACH") ? "attach" : "detach")
      return { changes: { changes: 0 } }
    })
    queryMock.mockClear()
    queryMock.mockImplementation(async () => {
      operations.push("export")
      stagingExists = true
      return { values: [] }
    })

    await main.exportDatabaseToStaging("EXPORTED_DATA")
    await main.exportDatabaseToStaging("EXPORTED_DATA")

    expect(operations).toEqual([
      "delete",
      "verify",
      "attach",
      "export",
      "detach",
      "delete",
      "verify",
      "attach",
      "export",
      "detach",
    ])
  })

  it("does not attach when the old staging file remains after cleanup", async () => {
    const { main, db } = await openShared()
    const executeMock = db.execute as ReturnType<typeof vi.fn>
    backupProcessorMocks.getFilePath.mockResolvedValue({
      path: "/tmp/staging.db",
      exists: true,
    })

    await expect(main.exportDatabaseToStaging("EXPORTED_DATA")).rejects.toThrow(
      "Staging file still exists after cleanup: EXPORTED_DATA",
    )
    expect(executeMock).not.toHaveBeenCalled()
  })

  it("detaches after export fails and preserves the export error", async () => {
    const { main, db } = await openShared()
    const executeMock = db.execute as ReturnType<typeof vi.fn>
    const queryMock = db.query as ReturnType<typeof vi.fn>
    const exportError = new Error("sqlcipher_export failed")

    executeMock.mockClear()
    queryMock.mockClear()
    queryMock.mockRejectedValueOnce(exportError)

    await expect(main.exportDatabaseToStaging("EXPORTED_DATA")).rejects.toBe(
      exportError,
    )
    expect(executeMock.mock.calls.map(([statement]) => statement)).toEqual([
      "ATTACH DATABASE '/tmp/staging.db' AS plaintext KEY '';",
      "DETACH DATABASE plaintext;",
    ])
  })
})

describe("sqliteBridge cross-worker transaction-span mutex", () => {
  it("blocks a non-owner read while the owner holds an open span, resumes after COMMIT", async () => {
    const { main } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    await main.executeSql("BEGIN")

    const bgRead = track(bg.querySql("SELECT 1"))
    await flush()
    expect(bgRead.settled).toBe(false)

    await main.executeSql("COMMIT")
    await flush()
    expect(bgRead.settled).toBe(true)
  })

  it("blocks a non-owner read during a span, resumes after ROLLBACK", async () => {
    const { main } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    await main.executeSql("BEGIN")

    const bgRead = track(bg.querySql("SELECT 1"))
    await flush()
    expect(bgRead.settled).toBe(false)

    await main.executeSql("ROLLBACK")
    await flush()
    expect(bgRead.settled).toBe(true)
  })

  it("lets the owner run multiple statements within its own span (re-entrant, no deadlock)", async () => {
    const { main } = await openShared()

    await main.executeSql("BEGIN")
    await main.executeSql("INSERT INTO t VALUES (1)")
    await main.querySql("SELECT * FROM t")
    await main.executeSql("INSERT INTO t VALUES (2)")
    await expect(main.executeSql("COMMIT")).resolves.toBeDefined()
  })

  it("does NOT release the outer span on SAVEPOINT / ROLLBACK TO SAVEPOINT", async () => {
    const { main } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    await main.executeSql("BEGIN")

    const bgRead = track(bg.querySql("SELECT 1"))
    await flush()
    expect(bgRead.settled).toBe(false)

    // Nested savepoint ops are classified "other" and must keep the span open.
    await main.executeSql("SAVEPOINT sp1")
    await main.executeSql("ROLLBACK TO SAVEPOINT sp1")
    await flush()
    expect(bgRead.settled).toBe(false)

    await main.executeSql("COMMIT")
    await flush()
    expect(bgRead.settled).toBe(true)
  })

  it("frees a stuck span when the owning worker is terminated (releaseWorkerSpan)", async () => {
    const { main } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    await main.executeSql("BEGIN")

    const bgRead = track(bg.querySql("SELECT 1"))
    await flush()
    expect(bgRead.settled).toBe(false)

    // Simulate the main worker dying mid-span.
    bridge.releaseWorkerSpan("main")
    await flush()
    expect(bgRead.settled).toBe(true)
  })

  it("drains every queued waiter after the span is released", async () => {
    const { main } = await openShared()
    const bgA = bridge.getSqliteBridge("bgA")
    const bgB = bridge.getSqliteBridge("bgB")
    await bgA.openDatabase("testdb.db", false, "no-encryption", 1, false)

    await main.executeSql("BEGIN")

    const readA = track(bgA.querySql("SELECT 1"))
    const readB = track(bgB.querySql("SELECT 2"))
    await flush()
    expect(readA.settled).toBe(false)
    expect(readB.settled).toBe(false)

    await main.executeSql("COMMIT")
    await flush()
    expect(readA.settled).toBe(true)
    expect(readB.settled).toBe(true)
  })

  it("defers a second worker's write until the owner commits (write ordering)", async () => {
    const { main, db } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    const runMock = db.run as ReturnType<typeof vi.fn>

    await main.executeSql("BEGIN")
    await main.executeSql("INSERT INTO t VALUES ('owner')")

    const bgWrite = track(bg.executeSql("INSERT INTO t VALUES ('bg')"))
    await flush()

    expect(
      runMock.mock.calls.filter(c => String(c[0]).includes("'owner'")),
    ).toHaveLength(1)
    expect(
      runMock.mock.calls.filter(c => String(c[0]).includes("'bg'")),
    ).toHaveLength(0)
    expect(bgWrite.settled).toBe(false)

    await main.executeSql("COMMIT")
    await flush()
    expect(bgWrite.settled).toBe(true)
    expect(
      runMock.mock.calls.filter(c => String(c[0]).includes("'bg'")),
    ).toHaveLength(1)
  })
})

describe("sqliteBridge shared connection", () => {
  it("reuses the shared connection for a secondary worker openDatabase (same object)", async () => {
    const { db: mainDb } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    const bgDb = await bg.openDatabase(
      "testdb.db",
      false,
      "no-encryption",
      1,
      false,
    )
    expect(bgDb).toBe(mainDb)
    expect(sqliteMocks.createConnection).toHaveBeenCalledTimes(1)
  })

  it("makes a secondary worker closeDatabase a no-op while only main tears down", async () => {
    const { main, db } = await openShared()
    const bg = bridge.getSqliteBridge("bg")
    await bg.openDatabase("testdb.db", false, "no-encryption", 1, false)

    const closeMock = db.close as ReturnType<typeof vi.fn>

    await bg.closeDatabase()
    expect(closeMock.mock.calls).toHaveLength(0)

    await main.closeDatabase()
    expect(closeMock.mock.calls).toHaveLength(1)
  })

  it("never opens natively from a secondary worker after main closed; waits for main to reopen", async () => {
    const { main } = await openShared()
    await main.closeDatabase()
    sqliteMocks.createConnection.mockClear()

    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()
    expect(attach.settled).toBe(false)
    expect(sqliteMocks.createConnection).not.toHaveBeenCalled()

    const { db: reopened } = await openShared()
    await flush()
    expect(attach.value).toBe(reopened)
    expect(sqliteMocks.createConnection).toHaveBeenCalledTimes(1)
  })

  it("waits when a secondary worker attaches before main has opened", async () => {
    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()
    expect(attach.settled).toBe(false)
    expect(sqliteMocks.createConnection).not.toHaveBeenCalled()

    const { db } = await openShared()
    await flush()
    expect(attach.value).toBe(db)
  })

  it("keeps a pending attach waiting through an import until main reopens", async () => {
    const { main } = await openShared()
    await main.closeDatabase()

    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await main.importDatabaseFromStaging(
      "testdb.db",
      "test-secret",
      "DECOMPILED_DATA",
    )
    await flush()
    expect(attach.settled).toBe(false)

    const { db: reopened } = await openShared()
    await flush()
    expect(attach.value).toBe(reopened)
    for (const call of sqliteMocks.createConnection.mock.calls) {
      expect(call[0]).toBe("testdb")
    }
    expect(sqliteMocks.createConnection).toHaveBeenCalledTimes(3)
  })

  it("lets main reopen after a cloud restore when the secondary worker attached first", async () => {
    const main = bridge.getSqliteBridge("main")
    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()

    await main.importDatabaseFromStaging(
      "testdb.db",
      "test-secret",
      "DECOMPILED_DATA",
    )
    const { db } = await openShared()
    await flush()

    expect(attach.value).toBe(db)
    expect(sqliteMocks.createConnection).toHaveBeenCalledTimes(2)
  })

  it("does not attach to a connection whose main open failed", async () => {
    const { main } = await openShared()
    await main.closeDatabase()
    sqliteMocks.createConnection.mockImplementationOnce(async () => ({
      getConnectionDBName: () => "testdb",
      open: vi.fn().mockRejectedValue(new Error("Cannot open the DB")),
      close: vi.fn().mockResolvedValue(undefined),
    }))
    await expect(
      main.openDatabase("testdb.db", false, "no-encryption", 1, false),
    ).rejects.toThrow("Cannot open the DB")

    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()
    expect(attach.settled).toBe(false)

    bridge.blockSharedConnectionAttach("bg")
    await flush()
    expect(attach.error).toBeInstanceOf(Error)
  })

  it("rejects a pending attach when blocked and fails fast while blocked", async () => {
    const bg = bridge.getSqliteBridge("bg")
    const pending = track(bg.openDatabase("testdb.db"))
    await flush()

    bridge.blockSharedConnectionAttach("bg")
    await flush()
    expect(pending.error).toBeInstanceOf(Error)

    await openShared()
    await expect(bg.openDatabase("testdb.db")).rejects.toThrow("cancelled")

    bridge.unblockSharedConnectionAttach("bg")
    await expect(bg.openDatabase("testdb.db")).resolves.toBeDefined()
  })

  it("does not hold the op lock while waiting, so main can still open", async () => {
    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()

    const reopen = track(openShared())
    await flush()
    expect(reopen.settled).toBe(true)
    expect(attach.settled).toBe(true)
  })

  it("rejects a pending attach when the secondary worker is terminated", async () => {
    const attach = track(bridge.getSqliteBridge("bg").openDatabase("testdb.db"))
    await flush()

    bridge.releaseWorkerSpan("bg")
    await flush()
    expect(attach.error).toBeInstanceOf(Error)

    const { db } = await openShared()
    await expect(
      bridge.getSqliteBridge("bg").openDatabase("testdb.db"),
    ).resolves.toBe(db)
  })

  it("rejects attaching to a different database than the shared one", async () => {
    await openShared()

    await expect(
      bridge.getSqliteBridge("bg").openDatabase("other.db"),
    ).rejects.toThrow("not other")
  })
})
