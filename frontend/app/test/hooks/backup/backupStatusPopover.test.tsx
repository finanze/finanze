import { describe, it, expect, beforeEach } from "vitest"
import { screen, waitFor, act, cleanup } from "@testing-library/react"
import { BackupFileType, BackupMode, SyncStatus } from "@/types"
import { buildBackupsInfo, buildSyncResult } from "./builders"
import {
  mockGetBackupsInfo,
  mockUploadBackup,
  mockImportBackup,
  renderPopoverUI,
  renderDualPopoverUI,
  resetAllMocks,
  setBackupMode,
} from "./setup"

beforeEach(() => {
  cleanup()
  resetAllMocks()
})

async function openPopover() {
  await act(async () => {
    screen.getByRole("button", { name: "Backup" }).click()
  })
}

describe("popover status display", () => {
  it.each([
    { data: SyncStatus.SYNC, label: "Synced" },
    { data: SyncStatus.PENDING, label: "Pending" },
    { data: SyncStatus.OUTDATED, label: "Outdated" },
    { data: SyncStatus.MISSING, label: "Not backed up" },
  ])("shows '$label' when DATA=$data", async ({ data, label }) => {
    const info = buildBackupsInfo(data)
    mockGetBackupsInfo.mockResolvedValue(info)

    renderPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText(label)).toBeInTheDocument()
    })

    expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
  })
})

describe("popover conflict resolution — Use Local", () => {
  it("DATA=CONFLICT", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
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
      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })
  })
})

describe("popover conflict resolution — Use Remote", () => {
  it("DATA=CONFLICT", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
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
      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument()
    })
  })
})

describe("popover multi-instance state sync", () => {
  it("Use Local resolves conflict in popover with background instance", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    })
  })

  it("Use Remote resolves conflict in popover with background instance", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(SyncStatus.SYNC))

    await act(async () => {
      screen.getByText("Use remote").click()
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    })
  })
})

describe("popover manual sync", () => {
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

      renderPopoverUI()
      await openPopover()

      await waitFor(() => {
        expect(screen.getByText("Sync")).toBeInTheDocument()
      })

      await act(async () => {
        screen.getByText("Sync").click()
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
