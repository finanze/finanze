import { describe, it, expect, beforeEach } from "vitest"
import { screen, waitFor, act, cleanup } from "@testing-library/react"
import { BackupFileType, BackupMode, SyncStatus } from "@/types"
import { ApiErrorException } from "@/utils/apiErrors"
import { buildBackupsInfo, buildPiece, buildSyncResult } from "./builders"
import {
  mockGetBackupsInfo,
  mockUploadBackup,
  mockImportBackup,
  renderBackupHook,
  renderBackupUI,
  renderDualBackupUI,
  resetAllMocks,
  setBackupMode,
} from "./setup"

beforeEach(() => {
  cleanup()
  resetAllMocks()
})

describe("backup status display", () => {
  it.each([
    { data: SyncStatus.SYNC, label: "Synced" },
    { data: SyncStatus.PENDING, label: "Pending" },
    { data: SyncStatus.OUTDATED, label: "Outdated" },
    { data: SyncStatus.MISSING, label: "Missing" },
  ])("shows '$label' when DATA=$data", async ({ data, label }) => {
    const info = buildBackupsInfo(data)
    mockGetBackupsInfo.mockResolvedValue(info)

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText(label)).toBeInTheDocument()
    })

    expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
  })
})

describe("conflict resolution — Use Local", () => {
  it("DATA=CONFLICT", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    expect(screen.getByText("Use local")).toBeInTheDocument()
    expect(screen.getByText("Use remote")).toBeInTheDocument()

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(mockUploadBackup).toHaveBeenCalledWith({
        types: [BackupFileType.DATA],
        force: true,
      })
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })
  })
})

describe("conflict resolution — Use Remote", () => {
  it("DATA=CONFLICT", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use remote").click()
    })

    await waitFor(() => {
      expect(mockImportBackup).toHaveBeenCalledWith({
        types: [BackupFileType.DATA],
        force: true,
      })
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })
  })
})

describe("multi-instance state sync (bug fix)", () => {
  it("Use Local resolves conflict in both instances", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
    })
  })

  it("Use Remote resolves conflict in both instances", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use remote").click()
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
    })
  })
})

describe("manual sync", () => {
  const cases = [
    {
      name: "PENDING → uploads DATA",
      data: SyncStatus.PENDING,
      expectedUploadTypes: [BackupFileType.DATA],
      expectedImportTypes: null,
    },
    {
      name: "OUTDATED → imports DATA",
      data: SyncStatus.OUTDATED,
      expectedUploadTypes: null,
      expectedImportTypes: [BackupFileType.DATA],
    },
    {
      name: "MISSING → uploads DATA",
      data: SyncStatus.MISSING,
      expectedUploadTypes: [BackupFileType.DATA],
      expectedImportTypes: null,
    },
  ]

  it.each(cases)(
    "$name",
    async ({ data, expectedUploadTypes, expectedImportTypes }) => {
      setBackupMode(BackupMode.MANUAL)
      const info = buildBackupsInfo(data)
      mockGetBackupsInfo.mockResolvedValue(info)

      if (expectedUploadTypes) {
        mockUploadBackup.mockResolvedValue(
          buildSyncResult(expectedUploadTypes, SyncStatus.SYNC),
        )
      }
      if (expectedImportTypes) {
        mockImportBackup.mockResolvedValue(
          buildSyncResult(expectedImportTypes, SyncStatus.SYNC),
        )
      }

      renderBackupUI()

      await waitFor(() => {
        expect(screen.getByText("Sync now")).toBeInTheDocument()
      })

      await act(async () => {
        screen.getByText("Sync now").click()
      })

      if (expectedUploadTypes) {
        await waitFor(() => {
          expect(mockUploadBackup).toHaveBeenCalledWith({
            types: expectedUploadTypes,
          })
        })
      }

      if (expectedImportTypes) {
        await waitFor(() => {
          expect(mockImportBackup).toHaveBeenCalledWith({
            types: expectedImportTypes,
          })
        })
      }
    },
  )
})

function backupTransferError() {
  const err: any = new Error("Failed to download backup piece DATA")
  err.code = "BACKUP_TRANSFER_FAILED"
  return err
}

const TRANSFER_FAILED_MSG =
  "Could not connect to the backup server. Please try again later."

describe("transfer failed error handling", () => {
  it("shows transfer failed message on upload failure (Use Local)", async () => {
    const info = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockUploadBackup.mockRejectedValue(backupTransferError())

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Use local")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(screen.getByText(TRANSFER_FAILED_MSG)).toBeInTheDocument()
    })
  })

  it("shows transfer failed message on import failure (Use Remote)", async () => {
    const info = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockImportBackup.mockRejectedValue(backupTransferError())

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Use remote")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use remote").click()
    })

    await waitFor(() => {
      expect(screen.getByText(TRANSFER_FAILED_MSG)).toBeInTheDocument()
    })
  })

  it("shows transfer failed message on manual sync upload failure", async () => {
    setBackupMode(BackupMode.MANUAL)
    const info = buildBackupsInfo(SyncStatus.PENDING)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockUploadBackup.mockRejectedValue(backupTransferError())

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Sync now")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Sync now").click()
    })

    await waitFor(() => {
      expect(screen.getByText(TRANSFER_FAILED_MSG)).toBeInTheDocument()
    })
  })

  it("shows transfer failed message on manual sync import failure", async () => {
    setBackupMode(BackupMode.MANUAL)
    const info = buildBackupsInfo(SyncStatus.OUTDATED)
    mockGetBackupsInfo.mockResolvedValue(info)
    mockImportBackup.mockRejectedValue(backupTransferError())

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Sync now")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Sync now").click()
    })

    await waitFor(() => {
      expect(screen.getByText(TRANSFER_FAILED_MSG)).toBeInTheDocument()
    })
  })
})

describe("legacy persisted state", () => {
  it("ignores a stale persisted CONFIG piece", async () => {
    localStorage.setItem(
      "backup_data",
      JSON.stringify({
        pieces: {
          [BackupFileType.DATA]: buildPiece(SyncStatus.SYNC),
          CONFIG: buildPiece(SyncStatus.CONFLICT),
        },
      }),
    )
    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    renderBackupUI()

    await waitFor(() => {
      expect(mockGetBackupsInfo).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })

    expect(screen.queryByText("Conflict detected")).not.toBeInTheDocument()
    expect(mockUploadBackup).not.toHaveBeenCalledWith(
      expect.objectContaining({
        types: expect.arrayContaining(["CONFIG"]),
      }),
    )
  })
})

describe("outdated app handling (OUTDATED_APP)", () => {
  it("exposes outdated app state when DATA has OUTDATED_APP and remote.schema_revision=96", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.OUTDATED_APP, { remoteSchemaRevision: 96 }),
    )

    const { result } = renderBackupHook()

    await waitFor(() => {
      expect(result.current.overallStatus).toBe(SyncStatus.OUTDATED_APP)
    })

    expect(result.current.isOutdatedApp).toBe(true)
    expect(result.current.outdatedAppUploadTypes).toEqual([BackupFileType.DATA])
  })

  it("runManualSync does not call importBackup or uploadBackup when DATA is OUTDATED_APP", async () => {
    setBackupMode(BackupMode.MANUAL)
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.OUTDATED_APP, { remoteSchemaRevision: 96 }),
    )

    const { result } = renderBackupHook()

    await waitFor(() => {
      expect(result.current.isOutdatedApp).toBe(true)
    })

    mockGetBackupsInfo.mockClear()

    await act(async () => {
      await result.current.runManualSync()
    })

    expect(mockGetBackupsInfo).toHaveBeenCalled()
    expect(mockImportBackup).not.toHaveBeenCalled()
    expect(mockUploadBackup).not.toHaveBeenCalled()
  })

  it("Use Local (handleUpload) force-uploads DATA and resolves OUTDATED_APP", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.OUTDATED_APP, { remoteSchemaRevision: 96 }),
    )
    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderBackupUI()

    await waitFor(() => {
      expect(screen.getByText("Newer backup version")).toBeInTheDocument()
    })

    expect(screen.getByText("Update required")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Use remote" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Use local" })).not.toBeDisabled()

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByRole("button", { name: "Use local" }).click()
    })

    await waitFor(() => {
      expect(mockUploadBackup).toHaveBeenCalledWith({
        types: [BackupFileType.DATA],
        force: true,
      })
    })

    await waitFor(() => {
      expect(screen.queryByText("Newer backup version")).not.toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })
  })

  it("handleImport sets unsupportedVersionError message on UNSUPPORTED_BACKUP_VERSION", async () => {
    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.CONFLICT))

    const unsupportedError = Object.assign(
      new ApiErrorException(
        "UNSUPPORTED_BACKUP_VERSION",
        "Backup requires a newer app version",
      ),
      { details: { remote_schema_revision: 96 } },
    )
    mockImportBackup.mockRejectedValue(unsupportedError)

    const { result } = renderBackupHook()

    await waitFor(() => {
      expect(result.current.overallStatus).toBe(SyncStatus.CONFLICT)
    })

    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.OUTDATED_APP, { remoteSchemaRevision: 96 }),
    )

    await act(async () => {
      await result.current.handleImport([BackupFileType.DATA])
    })

    expect(result.current.feedbackMessage).toBe(
      "Backup was created with a newer version of Finanze. Please update the app.",
    )
    expect(result.current.isOutdatedApp).toBe(true)
  })
})
