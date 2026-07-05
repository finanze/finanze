import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { act, cleanup } from "@testing-library/react"
import { BackupMode } from "@/types"
import {
  mockRunTrackedUpdatesIfNeeded,
  setBackupMode,
  setCloudInitialized,
  renderProvider,
  rerenderProvider,
  resetAllMocks,
} from "./setup"

beforeEach(() => {
  cleanup()
  resetAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

function dispatchSyncComplete(detail: Record<string, unknown> = {}) {
  window.dispatchEvent(new CustomEvent("backup-auto-sync-complete", { detail }))
}

describe("deferred tracked updates", () => {
  it("runs immediately when cloud is initialized and backup is OFF", async () => {
    setBackupMode(BackupMode.OFF)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("runs immediately in MANUAL backup mode", async () => {
    setBackupMode(BackupMode.MANUAL)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("does not run while cloud is not initialized", async () => {
    setBackupMode(BackupMode.OFF)
    setCloudInitialized(false)

    await act(async () => {
      renderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).not.toHaveBeenCalled()
  })

  it("runs once cloud finishes initializing", async () => {
    setBackupMode(BackupMode.OFF)
    setCloudInitialized(false)

    await act(async () => {
      renderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).not.toHaveBeenCalled()

    setCloudInitialized(true)
    await act(async () => {
      rerenderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("waits for backup sync in AUTO mode before running", async () => {
    setBackupMode(BackupMode.AUTO)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    expect(mockRunTrackedUpdatesIfNeeded).not.toHaveBeenCalled()

    await act(async () => {
      dispatchSyncComplete({ hadTransfer: false })
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("runs in AUTO mode even when the sync reports a conflict", async () => {
    setBackupMode(BackupMode.AUTO)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    await act(async () => {
      dispatchSyncComplete({ hadTransfer: false, conflict: true })
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("only runs tracked updates once across a conflict then a clean sync", async () => {
    setBackupMode(BackupMode.AUTO)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    await act(async () => {
      dispatchSyncComplete({ conflict: true })
    })
    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)

    await act(async () => {
      dispatchSyncComplete({ hadTransfer: true })
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })

  it("only runs tracked updates once across multiple sync events", async () => {
    setBackupMode(BackupMode.AUTO)
    setCloudInitialized(true)

    await act(async () => {
      renderProvider()
    })

    await act(async () => {
      dispatchSyncComplete({ hadTransfer: false })
    })
    await act(async () => {
      dispatchSyncComplete({ hadTransfer: true })
    })

    expect(mockRunTrackedUpdatesIfNeeded).toHaveBeenCalledTimes(1)
  })
})
