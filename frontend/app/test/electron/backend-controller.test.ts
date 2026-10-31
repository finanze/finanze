// @vitest-environment node
import { EventEmitter } from "node:events"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { BackendController } from "../../electron/main/backend-controller"
import { OS } from "../../electron/types"

const { spawnMock } = vi.hoisted(() => ({ spawnMock: vi.fn() }))

vi.mock("node:child_process", () => ({ spawn: spawnMock }))
vi.mock("../../electron/main/logging", () => ({ rawLog: vi.fn() }))
vi.mock("../../electron/main/windows-process", () => ({
  findAndKillProcesses: vi.fn(),
}))

class FakeChild extends EventEmitter {
  pid = 1234
  stdout = new EventEmitter()
  stderr = new EventEmitter()
  kill = vi.fn(() => true)
}

async function startBackend() {
  const child = new FakeChild()
  spawnMock.mockReturnValue(child)
  const controller = new BackendController({
    appConfig: {
      isDev: true,
      os: OS.MAC,
      arch: "arm64",
      ports: { backend: 7592 },
      urls: { backend: "http://localhost:7592", vite: "" },
    },
    devEntryPoint: "finanze",
    defaultArgs: { port: 7592, logLevel: "INFO" },
  })
  await controller.start()
  child.emit("spawn")
  return { controller, child }
}

describe("BackendController.stop", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(console, "info").mockImplementation(() => {})
    vi.spyOn(console, "warn").mockImplementation(() => {})
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("does not force kill a backend that exits after SIGTERM", async () => {
    const { controller, child } = await startBackend()

    const stopping = controller.stop()
    expect(child.kill).toHaveBeenCalledWith()
    child.emit("close", 0)

    expect((await stopping).state).toBe("stopped")
    await vi.advanceTimersByTimeAsync(30_000)
    expect(child.kill).toHaveBeenCalledTimes(1)
  })

  it("force kills a backend that does not exit in time", async () => {
    const { controller, child } = await startBackend()

    const stopping = controller.stop()
    await vi.advanceTimersByTimeAsync(29_999)
    expect(child.kill).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1)
    expect(child.kill).toHaveBeenLastCalledWith("SIGKILL")

    child.emit("close", null)
    expect((await stopping).state).toBe("stopped")
  })
})
