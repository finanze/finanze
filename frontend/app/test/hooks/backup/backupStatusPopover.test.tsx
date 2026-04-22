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
    { data: SyncStatus.SYNC, config: SyncStatus.SYNC, label: "Synced" },
    { data: SyncStatus.PENDING, config: SyncStatus.PENDING, label: "Pending" },
    {
      data: SyncStatus.OUTDATED,
      config: SyncStatus.OUTDATED,
      label: "Outdated",
    },
    {
      data: SyncStatus.MISSING,
      config: SyncStatus.MISSING,
      label: "Not backed up",
    },
    { data: SyncStatus.PENDING, config: SyncStatus.SYNC, label: "Pending" },
    { data: SyncStatus.SYNC, config: SyncStatus.OUTDATED, label: "Outdated" },
    {
      data: SyncStatus.PENDING,
      config: SyncStatus.OUTDATED,
      label: "Pending",
    },
  ])(
    "shows '$label' when DATA=$data and CONFIG=$config",
    async ({ data, config, label }) => {
      const info = buildBackupsInfo(data, config)
      mockGetBackupsInfo.mockResolvedValue(info)

      renderPopoverUI()
      await openPopover()

      await waitFor(() => {
        expect(screen.getByText(label)).toBeInTheDocument()
      })

      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    },
  )
})

describe("popover conflict resolution — Use Local", () => {
  const cases = [
    {
      name: "DATA=CONFLICT, CONFIG=SYNC",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.SYNC,
      expectedUploadTypes: [BackupFileType.DATA],
      followUpImportTypes: null,
    },
    {
      name: "DATA=SYNC, CONFIG=CONFLICT",
      data: SyncStatus.SYNC,
      config: SyncStatus.CONFLICT,
      expectedUploadTypes: [BackupFileType.CONFIG],
      followUpImportTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=CONFLICT",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.CONFLICT,
      expectedUploadTypes: [BackupFileType.DATA, BackupFileType.CONFIG],
      followUpImportTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=OUTDATED",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.OUTDATED,
      expectedUploadTypes: [BackupFileType.DATA],
      followUpImportTypes: [BackupFileType.CONFIG],
    },
    {
      name: "DATA=CONFLICT, CONFIG=PENDING",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.PENDING,
      expectedUploadTypes: [BackupFileType.DATA, BackupFileType.CONFIG],
      followUpImportTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=MISSING",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.MISSING,
      expectedUploadTypes: [BackupFileType.DATA, BackupFileType.CONFIG],
      followUpImportTypes: null,
    },
  ]

  it.each(cases)(
    "$name",
    async ({ data, config, expectedUploadTypes, followUpImportTypes }) => {
      const initialInfo = buildBackupsInfo(data, config)
      mockGetBackupsInfo.mockResolvedValue(initialInfo)

      mockUploadBackup.mockResolvedValue(
        buildSyncResult(expectedUploadTypes, SyncStatus.SYNC),
      )
      if (followUpImportTypes) {
        mockImportBackup.mockResolvedValue(
          buildSyncResult(followUpImportTypes, SyncStatus.SYNC),
        )
      }

      renderPopoverUI()
      await openPopover()

      await waitFor(() => {
        expect(screen.getByText("Conflict")).toBeInTheDocument()
      })

      expect(screen.getByText("Use local")).toBeInTheDocument()
      expect(screen.getByText("Use remote")).toBeInTheDocument()

      mockGetBackupsInfo.mockResolvedValue(
        buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
      )

      await act(async () => {
        screen.getByText("Use local").click()
      })

      await waitFor(() => {
        expect(mockUploadBackup).toHaveBeenCalledWith({
          types: expectedUploadTypes,
          force: true,
        })
      })

      if (followUpImportTypes) {
        await waitFor(() => {
          expect(mockImportBackup).toHaveBeenCalledWith({
            types: followUpImportTypes,
          })
        })
      }

      await waitFor(() => {
        expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
      })

      await waitFor(() => {
        expect(screen.getByText("Synced")).toBeInTheDocument()
      })
    },
  )
})

describe("popover conflict resolution — Use Remote", () => {
  const cases = [
    {
      name: "DATA=CONFLICT, CONFIG=SYNC",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.SYNC,
      expectedImportTypes: [BackupFileType.DATA],
      followUpUploadTypes: null,
    },
    {
      name: "DATA=SYNC, CONFIG=CONFLICT",
      data: SyncStatus.SYNC,
      config: SyncStatus.CONFLICT,
      expectedImportTypes: [BackupFileType.CONFIG],
      followUpUploadTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=CONFLICT",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.CONFLICT,
      expectedImportTypes: [BackupFileType.DATA, BackupFileType.CONFIG],
      followUpUploadTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=OUTDATED",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.OUTDATED,
      expectedImportTypes: [BackupFileType.DATA, BackupFileType.CONFIG],
      followUpUploadTypes: null,
    },
    {
      name: "DATA=CONFLICT, CONFIG=PENDING",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.PENDING,
      expectedImportTypes: [BackupFileType.DATA],
      followUpUploadTypes: [BackupFileType.CONFIG],
    },
    {
      name: "DATA=CONFLICT, CONFIG=MISSING",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.MISSING,
      expectedImportTypes: [BackupFileType.DATA],
      followUpUploadTypes: [BackupFileType.CONFIG],
    },
  ]

  it.each(cases)(
    "$name",
    async ({ data, config, expectedImportTypes, followUpUploadTypes }) => {
      const initialInfo = buildBackupsInfo(data, config)
      mockGetBackupsInfo.mockResolvedValue(initialInfo)

      mockImportBackup.mockResolvedValue(
        buildSyncResult(expectedImportTypes, SyncStatus.SYNC),
      )
      if (followUpUploadTypes) {
        mockUploadBackup.mockResolvedValue(
          buildSyncResult(followUpUploadTypes, SyncStatus.SYNC),
        )
      }

      renderPopoverUI()
      await openPopover()

      await waitFor(() => {
        expect(screen.getByText("Conflict")).toBeInTheDocument()
      })

      mockGetBackupsInfo.mockResolvedValue(
        buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
      )

      await act(async () => {
        screen.getByText("Use remote").click()
      })

      await waitFor(() => {
        expect(mockImportBackup).toHaveBeenCalledWith({
          types: expectedImportTypes,
          force: true,
        })
      })

      if (followUpUploadTypes) {
        await waitFor(() => {
          expect(mockUploadBackup).toHaveBeenCalledWith({
            types: followUpUploadTypes,
          })
        })
      }

      await waitFor(() => {
        expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
      })

      await waitFor(() => {
        expect(screen.getByText("Synced")).toBeInTheDocument()
      })
    },
  )
})

describe("popover multi-instance state sync", () => {
  it("Use Local resolves conflict in popover with background instance", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockUploadBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
    )

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(screen.queryByText("Conflict")).not.toBeInTheDocument()
    })
  })

  it("Use Remote resolves conflict in popover with background instance", async () => {
    const initialInfo = buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC)
    mockGetBackupsInfo.mockResolvedValue(initialInfo)

    mockImportBackup.mockResolvedValue(
      buildSyncResult([BackupFileType.DATA], SyncStatus.SYNC),
    )

    renderDualPopoverUI()
    await openPopover()

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
    })

    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
    )

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
      name: "PENDING + SYNC → uploads DATA",
      data: SyncStatus.PENDING,
      config: SyncStatus.SYNC,
      expectedUploadTypes: [BackupFileType.DATA],
      expectedImportTypes: null,
    },
    {
      name: "SYNC + OUTDATED → imports CONFIG",
      data: SyncStatus.SYNC,
      config: SyncStatus.OUTDATED,
      expectedUploadTypes: null,
      expectedImportTypes: [BackupFileType.CONFIG],
    },
    {
      name: "PENDING + OUTDATED → uploads DATA, imports CONFIG",
      data: SyncStatus.PENDING,
      config: SyncStatus.OUTDATED,
      expectedUploadTypes: [BackupFileType.DATA],
      expectedImportTypes: [BackupFileType.CONFIG],
    },
    {
      name: "MISSING + SYNC → uploads DATA",
      data: SyncStatus.MISSING,
      config: SyncStatus.SYNC,
      expectedUploadTypes: [BackupFileType.DATA],
      expectedImportTypes: null,
    },
  ]

  it.each(cases)(
    "$name",
    async ({ data, config, expectedUploadTypes, expectedImportTypes }) => {
      setBackupMode(BackupMode.MANUAL)
      const info = buildBackupsInfo(data, config)
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
