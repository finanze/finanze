import { type ReactNode } from "react"
import { vi } from "vitest"
import { render } from "@testing-library/react"
import { I18nProvider } from "@/i18n"
import { EntityRefreshDropdown } from "@/components/EntityRefreshDropdown"
import {
  EntityWorkflowProvider,
  useEntityWorkflow,
} from "@/context/EntityWorkflowContext"
import {
  type Entity,
  BackupMode,
  AutoRefreshMode,
  AutoRefreshMaxOutdatedTime,
} from "@/types"
import type { AutoRefreshCandidate } from "@/services/autoRefreshService"
import { buildAutoRefreshSettings } from "./builders"

// --- Mocks ---

export const mockScrape = vi.fn().mockResolvedValue(undefined)
export const mockShowToast = vi.fn()
export const mockNavigate = vi.fn()
export const mockUpdateEntityStatus = vi.fn()
export const mockUpdateEntityLastFetch = vi.fn()
export const mockUpdateEntityAccount = vi.fn()
export const mockFetchEntities = vi.fn().mockResolvedValue(undefined)

let currentEntities: Entity[] = []
let currentBackupMode = BackupMode.OFF
let currentAutoRefreshSettings = buildAutoRefreshSettings()
let currentEntitiesLoaded = true

export function setEntities(entities: Entity[]) {
  currentEntities = entities
}

export function setBackupMode(mode: BackupMode) {
  currentBackupMode = mode
}

export function setAutoRefreshSettings(
  settings: Partial<{
    mode: AutoRefreshMode
    max_outdated: AutoRefreshMaxOutdatedTime
    entities: { id: string }[]
  }>,
) {
  currentAutoRefreshSettings = buildAutoRefreshSettings(settings)
  currentSettings = {
    ...currentSettings,
    data: { autoRefresh: currentAutoRefreshSettings },
  }
}

export function setEntitiesLoaded(loaded: boolean) {
  currentEntitiesLoaded = loaded
}

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}))

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
  }),
}))

let currentSettings: Record<string, any> = {
  general: { defaultCurrency: "EUR", defaultCommodityWeightUnit: "oz" },
  assets: { crypto: { stablecoins: [], hideUnknownTokens: false } },
  data: { autoRefresh: currentAutoRefreshSettings },
}

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    showToast: mockShowToast,
    updateEntityStatus: mockUpdateEntityStatus,
    updateEntityLastFetch: mockUpdateEntityLastFetch,
    updateEntityAccount: mockUpdateEntityAccount,
    fetchEntities: mockFetchEntities,
    settings: currentSettings,
    entities: currentEntities,
    entitiesLoaded: currentEntitiesLoaded,
    featureFlags: {},
    isLoading: false,
  }),
}))

vi.mock("@/context/CloudContext", () => ({
  useCloud: () => ({
    backupMode: currentBackupMode,
    permissions: [],
    isInitialized: true,
  }),
}))

export const mockGetAutoRefreshCandidates = vi.fn<() => AutoRefreshCandidate[]>(
  () => [],
)

vi.mock("@/services/autoRefreshService", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    getAutoRefreshCandidates: (...args: unknown[]) =>
      mockGetAutoRefreshCandidates(...(args as [])),
  }
})

export const mockFetchFinancialEntity = vi
  .fn()
  .mockResolvedValue({ code: "COMPLETED" })
export const mockFetchCryptoEntity = vi
  .fn()
  .mockResolvedValue({ code: "COMPLETED" })

vi.mock("@/services/api", () => ({
  loginEntity: vi.fn().mockResolvedValue({ code: "CREATED" }),
  cancelEntityLogin: vi.fn().mockResolvedValue(undefined),
  fetchFinancialEntity: (...args: unknown[]) =>
    mockFetchFinancialEntity(...args),
  fetchCryptoEntity: (...args: unknown[]) => mockFetchCryptoEntity(...args),
  fetchExternalEntity: vi.fn().mockResolvedValue({ code: "COMPLETED" }),
  disconnectEntity: vi.fn().mockResolvedValue(undefined),
  getImageUrl: vi.fn().mockResolvedValue("test.png"),
}))

vi.mock("@/lib/externalLogin", () => ({
  getExternalLoginAPI: () => null,
}))

vi.mock("@/lib/challengeWindow", () => ({
  getChallengeWindowAPI: () => null,
}))

vi.mock("@/utils/autoRefreshUtils", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
  }
})

// @ts-expect-error -- global define
globalThis.__CONNECTIONS__ = true

// --- Render helpers ---

let capturedContext: ReturnType<typeof useEntityWorkflow> | null = null

function ContextCapture() {
  capturedContext = useEntityWorkflow()
  return null
}

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <EntityWorkflowProvider>
        {children}
        <ContextCapture />
      </EntityWorkflowProvider>
    </I18nProvider>
  )
}

let lastRenderResult: ReturnType<typeof render> | null = null

export function renderDropdown() {
  const result = render(<EntityRefreshDropdown />, { wrapper: Wrapper })
  lastRenderResult = result
  return result
}

export function renderContextOnly() {
  const result = render(<div data-testid="context-host" />, {
    wrapper: Wrapper,
  })
  lastRenderResult = result
  return result
}

export function rerenderView() {
  if (!lastRenderResult) throw new Error("Nothing rendered yet")
  lastRenderResult.rerender(
    <Wrapper>
      <div data-testid="context-host" />
      <ContextCapture />
    </Wrapper>,
  )
}

export function getContext() {
  if (!capturedContext) throw new Error("Context not captured — render first")
  return capturedContext
}

export function resetAllMocks() {
  currentEntities = []
  currentBackupMode = BackupMode.OFF
  currentAutoRefreshSettings = buildAutoRefreshSettings()
  currentSettings = {
    general: { defaultCurrency: "EUR", defaultCommodityWeightUnit: "oz" },
    assets: { crypto: { stablecoins: [], hideUnknownTokens: false } },
    data: { autoRefresh: currentAutoRefreshSettings },
  }
  currentEntitiesLoaded = true
  capturedContext = null
  lastRenderResult = null

  mockScrape.mockClear()
  mockShowToast.mockClear()
  mockNavigate.mockClear()
  mockUpdateEntityStatus.mockClear()
  mockUpdateEntityLastFetch.mockClear()
  mockUpdateEntityAccount.mockClear()
  mockFetchEntities.mockClear()
  mockFetchFinancialEntity.mockClear().mockResolvedValue({ code: "COMPLETED" })
  mockFetchCryptoEntity.mockClear().mockResolvedValue({ code: "COMPLETED" })
  mockGetAutoRefreshCandidates.mockReset().mockReturnValue([])
}
