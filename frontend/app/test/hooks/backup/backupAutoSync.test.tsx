import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { waitFor, act, cleanup, screen } from "@testing-library/react"
import { BackupFileType, BackupMode, CloudRole, SyncStatus } from "@/types"
import { buildBackupsInfo, buildSyncResult } from "./builders"
import {
  mockGetBackupsInfo,
  mockUploadBackup,
  mockImportBackup,
  mockShowToast,
  renderBackupUI,
  resetAllMocks,
  setBackupMode,
  setPermissions,
  setRole,
} from "./setup"

const ALL_PLUS_PERMISSIONS = [
  "backup.info",
  "backup.create",
  "backup.import",
  "backup.auto",
]

function tooManyRequestsError() {
  const err: any = new Error("Too many requests")
  err.code = "TOO_MANY_REQUESTS"
  return err
}

beforeEach(() => {
  cleanup()
  resetAllMocks()
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
})

describe("canAutoSync derivation", () => {
  it("is true when permissions include backup.auto", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.MANUAL)
    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    unmount()
  })

  it("is false when permissions lack backup.auto", async () => {
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)
    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalledWith({ only_local: true })
    })

    unmount()
  })

  it("Basic role never has backup.auto — initial fetch is local-only", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)
    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalledWith({ only_local: true })
    })

    unmount()
  })
})

describe("auto-sync interval (AUTO mode, Plus)", () => {
  it("runs auto-sync after interval elapses with PENDING pieces", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const initialInfo = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)
    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    expect(mockUploadBackup).toHaveBeenCalledWith({
      types: [BackupFileType.DATA],
    })

    mockGetBackupsInfo.mockClear()
    mockUploadBackup.mockClear()

    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC),
    )
    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    await act(async () => {
      vi.advanceTimersByTime(10 * 60_000)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockUploadBackup).toHaveBeenCalledWith({
        types: [BackupFileType.DATA],
      })
    })

    unmount()
  })

  it("skips upload/import when CONFLICT is detected", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const conflictInfo = buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(conflictInfo)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()
    expect(mockImportBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("does not upload/import when all pieces are SYNC", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const syncInfo = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(syncInfo)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()
    expect(mockImportBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("imports OUTDATED pieces during auto-sync", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.OUTDATED)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.CONFIG], SyncStatus.SYNC),
    )

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockImportBackup).toHaveBeenCalledWith({
        types: [BackupFileType.CONFIG],
      })
    })

    unmount()
  })
})

describe("manual-mode interval with Plus remote refresh", () => {
  it("Plus user with stale data does remote fetch in manual mode interval", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.MANUAL)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()

    await act(async () => {
      vi.advanceTimersByTime(10 * 60_000 + 1000)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    const lastCall =
      mockGetBackupsInfo.mock.calls[mockGetBackupsInfo.mock.calls.length - 1]
    expect(lastCall[0]).toBeUndefined()

    unmount()
  })

  it("Plus user with fresh data does local-only fetch in manual mode interval", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.MANUAL)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()

    await act(async () => {
      vi.advanceTimersByTime(2.5 * 60_000 + 1000)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    const lastCall =
      mockGetBackupsInfo.mock.calls[mockGetBackupsInfo.mock.calls.length - 1]
    expect(lastCall[0]).toEqual({ only_local: true })

    unmount()
  })

  it("Basic user always does local-only fetch in manual mode", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalledWith({ only_local: true })
    })

    mockGetBackupsInfo.mockClear()

    await act(async () => {
      vi.advanceTimersByTime(11 * 60_000)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    for (const call of mockGetBackupsInfo.mock.calls) {
      expect(call[0]).toEqual({ only_local: true })
    }

    unmount()
  })
})

describe("post-scrape auto-upload", () => {
  it("uploads PENDING pieces after scrapes-complete event (AUTO + Plus)", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const syncInfo = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(syncInfo)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()
    mockUploadBackup.mockClear()

    const pendingInfo = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(pendingInfo)
    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    await act(async () => {
      window.dispatchEvent(new CustomEvent("auto-refresh-scrapes-complete"))
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000 + 100)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockUploadBackup).toHaveBeenCalledWith({
        types: [BackupFileType.DATA],
      })
    })

    unmount()
  })

  it("does not upload when all pieces are SYNC after scrapes-complete", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const syncInfo = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(syncInfo)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()
    mockUploadBackup.mockClear()

    mockGetBackupsInfo.mockResolvedValue(syncInfo)

    await act(async () => {
      window.dispatchEvent(new CustomEvent("auto-refresh-scrapes-complete"))
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000 + 100)
    })

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("does not listen for scrapes-complete without backup.create permission", async () => {
    setPermissions(["backup.info", "backup.import", "backup.auto"])
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const syncInfo = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(syncInfo)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()

    const pendingInfo = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(pendingInfo)

    await act(async () => {
      window.dispatchEvent(new CustomEvent("auto-refresh-scrapes-complete"))
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000 + 100)
    })

    expect(mockGetBackupsInfo).not.toHaveBeenCalled()
    expect(mockUploadBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("does not listen for scrapes-complete in MANUAL mode", async () => {
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.MANUAL)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()
    mockUploadBackup.mockClear()

    const pendingInfo = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(pendingInfo)

    await act(async () => {
      window.dispatchEvent(new CustomEvent("auto-refresh-scrapes-complete"))
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000 + 100)
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("does not listen for scrapes-complete for Basic role (no backup.auto)", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.AUTO)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    mockGetBackupsInfo.mockClear()
    mockUploadBackup.mockClear()

    const pendingInfo = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(pendingInfo)

    await act(async () => {
      window.dispatchEvent(new CustomEvent("auto-refresh-scrapes-complete"))
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000 + 100)
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()

    unmount()
  })
})

describe("TOO_MANY_REQUESTS Plus upsell toast", () => {
  it("shows Plus upsell toast for Basic role on upload TOO_MANY_REQUESTS", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)

    const info = buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockUploadBackup.mockRejectedValue(tooManyRequestsError())

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Use local")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(expect.anything(), "info")
    })

    unmount()
  })

  it("does NOT show Plus upsell toast for Plus role on upload TOO_MANY_REQUESTS", async () => {
    setRole(CloudRole.PLUS)
    setPermissions(ALL_PLUS_PERMISSIONS)
    setBackupMode(BackupMode.MANUAL)

    const info = buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockUploadBackup.mockRejectedValue(tooManyRequestsError())

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Use local")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(mockUploadBackup).toHaveBeenCalled()
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100)
    })

    expect(mockShowToast).not.toHaveBeenCalled()

    unmount()
  })

  it("shows Plus upsell toast for Basic role on import TOO_MANY_REQUESTS", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockImportBackup.mockRejectedValue(tooManyRequestsError())

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Use remote")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use remote").click()
    })

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(expect.anything(), "info")
    })

    unmount()
  })

  it("shows Plus upsell toast for Basic role on manual sync TOO_MANY_REQUESTS", async () => {
    setRole(CloudRole.BASIC)
    setPermissions(["backup.info", "backup.create", "backup.import"])
    setBackupMode(BackupMode.MANUAL)

    const info = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockUploadBackup.mockRejectedValue(tooManyRequestsError())

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Sync now")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Sync now").click()
    })

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(expect.anything(), "info")
    })

    unmount()
  })
})

describe("permission gating in auto-sync", () => {
  it("skips uploads for PENDING pieces when backup.create is absent", async () => {
    setPermissions(["backup.info", "backup.import", "backup.auto"])
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect(mockUploadBackup).not.toHaveBeenCalled()

    unmount()
  })

  it("skips imports for OUTDATED pieces when backup.import is absent", async () => {
    setPermissions(["backup.info", "backup.create", "backup.auto"])
    setBackupMode(BackupMode.AUTO)
    setRole(CloudRole.PLUS)

    const info = buildBackupsInfo(SyncStatus.SYNC, SyncStatus.OUTDATED)
    mockGetBackupsInfo.mockResolvedValue(info)

    const { unmount } = renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })

    expect(mockImportBackup).not.toHaveBeenCalled()

    unmount()
  })
})
