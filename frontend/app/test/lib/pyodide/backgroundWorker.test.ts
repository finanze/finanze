import { beforeEach, describe, expect, it, vi } from "vitest"

const pyodideMocks = vi.hoisted(() => ({
  initBackgroundWorker: vi.fn(),
  callBackgroundPythonFunction: vi.fn(),
}))

const bridgeMocks = vi.hoisted(() => ({
  blockSharedConnectionAttach: vi.fn(),
  unblockSharedConnectionAttach: vi.fn(),
}))

const consoleMocks = vi.hoisted(() => ({
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
}))

vi.mock("@/lib/pyodide", () => ({
  initPyodide: vi.fn(),
  loadAppModules: vi.fn(),
  loadDeferredModules: vi.fn(),
  loadLazyModules: vi.fn(),
  callPythonFunction: vi.fn(),
  registerBridgeWithPyodide: vi.fn(),
  installDeferredRequirements: vi.fn(),
  installLazyRequirements: vi.fn(),
  initBackgroundWorker: pyodideMocks.initBackgroundWorker,
  callBackgroundPythonFunction: pyodideMocks.callBackgroundPythonFunction,
}))

vi.mock("@/lib/pyodide/bridges/sqliteBridge", () => bridgeMocks)

vi.mock("@/lib/capacitor/appConsole", () => ({ appConsole: consoleMocks }))

type Init = typeof import("@/lib/pyodide/init")
let init: Init
let rejectPendingConnect: ((error: Error) => void) | null

function pythonCalls(fn: string) {
  return pyodideMocks.callBackgroundPythonFunction.mock.calls.filter(
    call => call[1] === fn,
  )
}

async function flush() {
  for (let i = 0; i < 3; i++) {
    await new Promise(resolve => setTimeout(resolve, 0))
  }
}

beforeEach(async () => {
  vi.clearAllMocks()
  rejectPendingConnect = null
  pyodideMocks.initBackgroundWorker.mockResolvedValue(undefined)
  pyodideMocks.callBackgroundPythonFunction.mockImplementation(
    async (_module: string, fn: string) => {
      if (fn !== "connect") return undefined
      return new Promise((_, reject) => {
        rejectPendingConnect = reject
      })
    },
  )
  bridgeMocks.blockSharedConnectionAttach.mockImplementation(() =>
    rejectPendingConnect?.(new Error("attach cancelled")),
  )
  vi.resetModules()
  init = await import("@/lib/pyodide/init")
})

describe("background worker connect/disconnect", () => {
  it("cancels a pending connect on disconnect without hanging or failing", async () => {
    const connecting = init.connectBackgroundWorker("user")
    await flush()
    expect(pythonCalls("connect")).toHaveLength(1)

    await init.disconnectBackgroundWorker()

    await expect(connecting).resolves.toBeUndefined()
    expect(bridgeMocks.blockSharedConnectionAttach).toHaveBeenCalledWith("bg")
    expect(bridgeMocks.unblockSharedConnectionAttach).toHaveBeenCalledWith("bg")
    expect(pythonCalls("disconnect")).toHaveLength(1)
    expect(consoleMocks.error).not.toHaveBeenCalled()
    expect(init.isBackgroundReady()).toBe(false)
  })

  it("unblocks attach before the next connect after a disconnect", async () => {
    init.connectBackgroundWorker("user")
    await flush()
    await init.disconnectBackgroundWorker()

    pyodideMocks.callBackgroundPythonFunction.mockResolvedValue(undefined)
    await expect(init.connectBackgroundWorker("user")).resolves.toBeUndefined()

    const unblockOrder =
      bridgeMocks.unblockSharedConnectionAttach.mock.invocationCallOrder[0]
    const lastConnectOrder =
      pyodideMocks.callBackgroundPythonFunction.mock.invocationCallOrder.at(-1)!
    expect(unblockOrder).toBeLessThan(lastConnectOrder)
    expect(init.isBackgroundReady()).toBe(true)
  })

  it("still rejects and allows a retry on a genuine connect failure", async () => {
    pyodideMocks.callBackgroundPythonFunction.mockImplementation(
      async (_module: string, fn: string) => {
        if (fn === "connect") throw new Error("Cannot open the DB")
        return undefined
      },
    )

    await expect(init.connectBackgroundWorker("user")).rejects.toThrow(
      "Cannot open the DB",
    )
    expect(consoleMocks.error).toHaveBeenCalled()

    await expect(init.connectBackgroundWorker("user")).rejects.toThrow(
      "Cannot open the DB",
    )
    expect(pythonCalls("connect")).toHaveLength(2)
    expect(bridgeMocks.blockSharedConnectionAttach).not.toHaveBeenCalled()
  })

  it("does not block attach when nothing is connecting", async () => {
    await init.disconnectBackgroundWorker()

    expect(bridgeMocks.blockSharedConnectionAttach).not.toHaveBeenCalled()
    expect(pythonCalls("disconnect")).toHaveLength(0)
  })
})
