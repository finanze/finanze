import { describe, it, expect, beforeEach, vi } from "vitest"
import { screen, waitFor, act, cleanup } from "@testing-library/react"
import { render } from "@testing-library/react"
import { type ReactNode } from "react"
import { I18nProvider } from "@/i18n"
import {
  BackupAlertProvider,
  useBackupAlert,
} from "@/context/BackupAlertContext"
import { BackupAlertSync } from "@/components/BackupAlertSync"
import { BackupStatusPopover } from "@/components/layout/BackupStatusPopover"
import { FloatingBottomNav } from "@/components/layout/FloatingBottomNav"
import {
  useBackupStatus,
  resetBackupStatusCache,
} from "@/hooks/useBackupStatus"
import { BackupStatusContent } from "@/components/backup/BackupStatusContent"
import { BackupMode, SyncStatus } from "@/types"
import { ApiErrorException } from "@/utils/apiErrors"
import { buildBackupsInfo } from "./builders"

const mockSetBackupMode = vi.fn()
const mockRefreshData = vi.fn().mockResolvedValue(undefined)
const mockRefreshRealEstate = vi.fn().mockResolvedValue(undefined)
const mockRefreshFlows = vi.fn().mockResolvedValue(undefined)
const mockFetchEntities = vi.fn().mockResolvedValue(undefined)
const mockFetchSettings = vi.fn().mockResolvedValue(undefined)

let currentBackupMode = BackupMode.AUTO

vi.mock("@/context/CloudContext", () => ({
  useCloud: () => ({
    permissions: ["backup.info", "backup.create", "backup.import"],
    backupMode: currentBackupMode,
    setBackupMode: mockSetBackupMode,
    isInitialized: true,
  }),
}))

vi.mock("@/context/FinancialDataContext", () => ({
  useFinancialData: () => ({
    refreshData: mockRefreshData,
    refreshRealEstate: mockRefreshRealEstate,
    refreshFlows: mockRefreshFlows,
    positionsData: null,
    contributions: null,
    periodicFlows: [],
    pendingFlows: [],
    isLoading: false,
    isInitialLoading: false,
    error: null,
    refreshEntity: vi.fn(),
    refreshFlowsIfStale: vi.fn(),
    refreshPendingFlows: vi.fn(),
    ensureContributions: vi.fn(),
    ensurePeriodicFlows: vi.fn(),
    realEstateList: [],
    cachedLastTransactions: null,
    fetchCachedTransactions: vi.fn(),
    invalidateTransactionsCache: vi.fn(),
  }),
}))

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    fetchEntities: mockFetchEntities,
    fetchSettings: mockFetchSettings,
    featureFlags: {},
    entities: [],
    settings: null,
    isLoading: false,
  }),
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: "/" }),
}))

vi.mock("@/context/LayoutScrollContext", () => ({
  useLayoutScroll: () => ({
    scrolling: false,
    atTop: true,
    atBottom: false,
    handleScroll: vi.fn(),
    resetScroll: vi.fn(),
  }),
}))

const mockGetBackupsInfo = vi.fn()
const mockUploadBackup = vi.fn()
const mockImportBackup = vi.fn()

vi.mock("@/services/api", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    getBackupsInfo: (...args: unknown[]) => mockGetBackupsInfo(...args),
    uploadBackup: (...args: unknown[]) => mockUploadBackup(...args),
    importBackup: (...args: unknown[]) => mockImportBackup(...args),
  }
})

function AlertColorReader() {
  const { alertColor } = useBackupAlert()
  return <span data-testid="alert-color">{alertColor ?? "none"}</span>
}

function AlertSyncWithReader() {
  return (
    <>
      <BackupAlertSync />
      <AlertColorReader />
    </>
  )
}

function AlertSyncWithContent() {
  const status = useBackupStatus({ isActive: true })
  return (
    <>
      <BackupStatusContent {...status} showModeSelector={false} />
      <AlertColorReader />
    </>
  )
}

function FloatingNavWithSync() {
  return (
    <>
      <BackupAlertSync />
      <FloatingBottomNav />
    </>
  )
}

function PopoverWithSync() {
  return (
    <>
      <BackupAlertSync />
      <BackupStatusPopover collapsed={false} />
    </>
  )
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <BackupAlertProvider>{children}</BackupAlertProvider>
    </I18nProvider>
  )
}

function resetAllMocks() {
  resetBackupStatusCache()
  mockGetBackupsInfo.mockReset()
  mockUploadBackup.mockReset()
  mockImportBackup.mockReset()
  mockSetBackupMode.mockReset()
  mockRefreshData.mockReset().mockResolvedValue(undefined)
  mockRefreshRealEstate.mockReset().mockResolvedValue(undefined)
  mockRefreshFlows.mockReset().mockResolvedValue(undefined)
  mockFetchEntities.mockReset().mockResolvedValue(undefined)
  mockFetchSettings.mockReset().mockResolvedValue(undefined)
  currentBackupMode = BackupMode.AUTO
}

beforeEach(() => {
  cleanup()
  resetAllMocks()
})

describe("alert color from backup status", () => {
  it.each([
    {
      name: "CONFLICT → red",
      data: SyncStatus.CONFLICT,
      config: SyncStatus.SYNC,
      mode: BackupMode.AUTO,
      expected: "red",
    },
    {
      name: "MANUAL + OUTDATED → orange",
      data: SyncStatus.SYNC,
      config: SyncStatus.OUTDATED,
      mode: BackupMode.MANUAL,
      expected: "orange",
    },
    {
      name: "AUTO + OUTDATED → none",
      data: SyncStatus.SYNC,
      config: SyncStatus.OUTDATED,
      mode: BackupMode.AUTO,
      expected: "none",
    },
    {
      name: "SYNC → none",
      data: SyncStatus.SYNC,
      config: SyncStatus.SYNC,
      mode: BackupMode.AUTO,
      expected: "none",
    },
    {
      name: "PENDING → none",
      data: SyncStatus.PENDING,
      config: SyncStatus.SYNC,
      mode: BackupMode.MANUAL,
      expected: "none",
    },
    {
      name: "MISSING → none",
      data: SyncStatus.MISSING,
      config: SyncStatus.MISSING,
      mode: BackupMode.AUTO,
      expected: "none",
    },
  ])("$name", async ({ data, config, mode, expected }) => {
    currentBackupMode = mode
    mockGetBackupsInfo.mockResolvedValue(buildBackupsInfo(data, config))

    render(<AlertSyncWithReader />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByTestId("alert-color").textContent).toBe(expected)
    })
  })

  it("credentials mismatch → dark-red", async () => {
    currentBackupMode = BackupMode.MANUAL
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC),
    )
    mockUploadBackup.mockRejectedValue(
      new ApiErrorException("INVALID_BACKUP_CREDENTIALS"),
    )

    render(<AlertSyncWithContent />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      expect(screen.getByTestId("alert-color").textContent).toBe("dark-red")
    })
  })
})

describe("FloatingBottomNav alert dot", () => {
  it("shows red dot on More button when CONFLICT", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC),
    )

    render(<FloatingNavWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      const moreButton = screen.getByLabelText("More")
      const dot = moreButton.querySelector(".rounded-full.bg-red-500")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows amber dot on More button when MANUAL + OUTDATED", async () => {
    currentBackupMode = BackupMode.MANUAL
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.OUTDATED),
    )

    render(<FloatingNavWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      const moreButton = screen.getByLabelText("More")
      const dot = moreButton.querySelector(".rounded-full.bg-amber-500")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows no dot on More button when SYNC", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
    )

    render(<FloatingNavWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByLabelText("More")).toBeInTheDocument()
    })

    const moreButton = screen.getByLabelText("More")
    const dot = moreButton.querySelector(".rounded-full.h-1\\.5")
    expect(dot).not.toBeInTheDocument()
  })

  it("shows dark-red dot on More button when credentials mismatch", async () => {
    currentBackupMode = BackupMode.MANUAL
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC),
    )
    mockUploadBackup.mockRejectedValue(
      new ApiErrorException("INVALID_BACKUP_CREDENTIALS"),
    )

    render(
      <>
        <AlertSyncWithContent />
        <FloatingBottomNav />
      </>,
      { wrapper: Wrapper },
    )

    await waitFor(() => {
      expect(screen.getByText("Conflict detected")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      const moreButton = screen.getByLabelText("More")
      const dot = moreButton.querySelector(".rounded-full.bg-red-700")
      expect(dot).toBeInTheDocument()
    })
  })
})

describe("BackupStatusPopover trigger dot", () => {
  it("shows red dot when CONFLICT", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC),
    )

    render(<PopoverWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      const trigger = screen.getByLabelText("Backup")
      const dot = trigger.querySelector(".rounded-full.bg-red-500")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows foreground dot when PENDING", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.PENDING, SyncStatus.SYNC),
    )

    render(<PopoverWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      const trigger = screen.getByLabelText("Backup")
      const dot = trigger.querySelector(".rounded-full.bg-foreground")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows amber dot when OUTDATED", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.OUTDATED),
    )

    render(<PopoverWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      const trigger = screen.getByLabelText("Backup")
      const dot = trigger.querySelector(".rounded-full.bg-amber-500")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows dark-red dot when credentials mismatch", async () => {
    currentBackupMode = BackupMode.MANUAL
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.CONFLICT, SyncStatus.SYNC),
    )
    mockUploadBackup.mockRejectedValue(
      new ApiErrorException("INVALID_BACKUP_CREDENTIALS"),
    )

    render(<BackupStatusPopover collapsed={false} />, { wrapper: Wrapper })

    await act(async () => {
      screen.getByRole("button", { name: "Backup" }).click()
    })

    await waitFor(() => {
      expect(screen.getByText("Conflict")).toBeInTheDocument()
    })

    await act(async () => {
      screen.getByText("Use local").click()
    })

    await waitFor(() => {
      const trigger = screen.getByRole("button", { name: "Backup" })
      const dot = trigger.querySelector(".rounded-full.bg-red-700")
      expect(dot).toBeInTheDocument()
    })
  })

  it("shows no dot when SYNC", async () => {
    mockGetBackupsInfo.mockResolvedValue(
      buildBackupsInfo(SyncStatus.SYNC, SyncStatus.SYNC),
    )

    render(<PopoverWithSync />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByLabelText("Backup")).toBeInTheDocument()
    })

    const trigger = screen.getByLabelText("Backup")
    const dot = trigger.querySelector(".rounded-full.h-1\\.5")
    expect(dot).not.toBeInTheDocument()
  })
})
