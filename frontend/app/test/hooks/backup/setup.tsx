import { type ReactNode } from "react"
import { vi } from "vitest"
import { render } from "@testing-library/react"
import { I18nProvider } from "@/i18n"
import { BackupStatusContent } from "@/components/backup/BackupStatusContent"
import { BackupStatusPopover } from "@/components/layout/BackupStatusPopover"
import {
  useBackupStatus,
  resetBackupStatusCache,
} from "@/hooks/useBackupStatus"
import { BackupMode } from "@/types"

const mockSetBackupMode = vi.fn()
const mockRefreshData = vi.fn().mockResolvedValue(undefined)
const mockRefreshRealEstate = vi.fn().mockResolvedValue(undefined)
const mockRefreshFlows = vi.fn().mockResolvedValue(undefined)
const mockFetchEntities = vi.fn().mockResolvedValue(undefined)
const mockFetchSettings = vi.fn().mockResolvedValue(undefined)
const mockUpdateAlertStatus = vi.fn()

let currentBackupMode = BackupMode.MANUAL

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

vi.mock("@/context/BackupAlertContext", () => ({
  useBackupAlertUpdater: () => ({
    updateAlertStatus: mockUpdateAlertStatus,
  }),
}))

export const mockGetBackupsInfo = vi.fn()
export const mockUploadBackup = vi.fn()
export const mockImportBackup = vi.fn()

vi.mock("@/services/api", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    getBackupsInfo: (...args: unknown[]) => mockGetBackupsInfo(...args),
    uploadBackup: (...args: unknown[]) => mockUploadBackup(...args),
    importBackup: (...args: unknown[]) => mockImportBackup(...args),
  }
})

export function setBackupMode(mode: BackupMode) {
  currentBackupMode = mode
}

function SingleInstanceUI() {
  const status = useBackupStatus({ isActive: true })
  return <BackupStatusContent {...status} showModeSelector={false} />
}

function DualInstanceUI() {
  const status1 = useBackupStatus({ isActive: true })
  useBackupStatus({ isActive: true })
  return (
    <div>
      <div data-testid="instance-1">
        <BackupStatusContent {...status1} showModeSelector={false} />
      </div>
    </div>
  )
}

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider>{children}</I18nProvider>
}

function PopoverUI() {
  return <BackupStatusPopover collapsed={false} />
}

function DualPopoverUI() {
  useBackupStatus({ isActive: true })
  return <BackupStatusPopover collapsed={false} />
}

export function renderBackupUI() {
  return render(<SingleInstanceUI />, { wrapper: Wrapper })
}

export function renderDualBackupUI() {
  return render(<DualInstanceUI />, { wrapper: Wrapper })
}

export function renderPopoverUI() {
  return render(<PopoverUI />, { wrapper: Wrapper })
}

export function renderDualPopoverUI() {
  return render(<DualPopoverUI />, { wrapper: Wrapper })
}

export function resetAllMocks() {
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
  mockUpdateAlertStatus.mockReset()
  currentBackupMode = BackupMode.MANUAL
}
