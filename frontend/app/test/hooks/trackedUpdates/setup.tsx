import { vi } from "vitest"
import { render } from "@testing-library/react"
import { BackupMode } from "@/types"
import { FinancialDataProvider } from "@/context/FinancialDataContext"

export const mockRunTrackedUpdatesIfNeeded = vi
  .fn()
  .mockResolvedValue(undefined)
export const mockSetOnTrackedUpdateCompleted = vi.fn()
export const mockSetOnScrapeCompleted = vi.fn()
export const mockSetOnEntityDisconnected = vi.fn()
export const mockUpdateEntityLastFetch = vi.fn()

let currentBackupMode: BackupMode = BackupMode.OFF
let currentCloudInitialized = true

export function setBackupMode(mode: BackupMode) {
  currentBackupMode = mode
}

export function setCloudInitialized(initialized: boolean) {
  currentCloudInitialized = initialized
}

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    entities: [],
    entitiesLoaded: false,
    updateEntityLastFetch: mockUpdateEntityLastFetch,
    exchangeRates: {},
    exchangeRatesLoading: false,
    setOnTrackedUpdateCompleted: mockSetOnTrackedUpdateCompleted,
    runTrackedUpdatesIfNeeded: mockRunTrackedUpdatesIfNeeded,
  }),
}))

vi.mock("@/context/EntityWorkflowContext", () => ({
  useEntityWorkflow: () => ({
    setOnScrapeCompleted: mockSetOnScrapeCompleted,
    setOnEntityDisconnected: mockSetOnEntityDisconnected,
  }),
}))

vi.mock("@/context/CloudContext", () => ({
  useCloud: () => ({
    backupMode: currentBackupMode,
    isInitialized: currentCloudInitialized,
  }),
}))

vi.mock("@/lib/mobile", () => ({
  triggerLazyInit: vi.fn(),
}))

vi.mock("@/services/api", () => ({
  getPositions: vi.fn().mockResolvedValue({ positions: {} }),
  getContributions: vi.fn().mockResolvedValue({ contributions: {} }),
  getAllPeriodicFlows: vi.fn().mockResolvedValue([]),
  getAllPendingFlows: vi.fn().mockResolvedValue([]),
  getTransactions: vi.fn().mockResolvedValue({ transactions: [] }),
  getAllRealEstate: vi.fn().mockResolvedValue([]),
}))

let lastRenderResult: ReturnType<typeof render> | null = null

function Tree() {
  return (
    <FinancialDataProvider>
      <div data-testid="host" />
    </FinancialDataProvider>
  )
}

export function renderProvider() {
  const result = render(<Tree />)
  lastRenderResult = result
  return result
}

export function rerenderProvider() {
  if (!lastRenderResult) throw new Error("Nothing rendered yet")
  lastRenderResult.rerender(<Tree />)
}

export function resetAllMocks() {
  currentBackupMode = BackupMode.OFF
  currentCloudInitialized = true
  lastRenderResult = null
  mockRunTrackedUpdatesIfNeeded.mockClear().mockResolvedValue(undefined)
  mockSetOnTrackedUpdateCompleted.mockClear()
  mockSetOnScrapeCompleted.mockClear()
  mockSetOnEntityDisconnected.mockClear()
  mockUpdateEntityLastFetch.mockClear()
}
