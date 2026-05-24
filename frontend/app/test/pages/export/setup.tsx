import { type ReactNode } from "react"
import { vi } from "vitest"
import { render } from "@testing-library/react"
import { I18nProvider } from "@/i18n"
import ExportPage from "@/pages/ExportPage"
import {
  FileImportPreviewDialog,
  type FileImportPreviewStrings,
} from "@/components/FileImportPreviewDialog"
import {
  TemplateType,
  type Feature,
  type Template,
  type ImportResult,
  type ImportedData,
  type ImportError,
} from "@/types"
import { ProductType } from "@/types/position"

const mockNavigate = vi.fn()
export const mockShowToast = vi.fn()
export const mockFetchEntities = vi.fn().mockResolvedValue(undefined)
export const mockFetchSettings = vi.fn().mockResolvedValue(undefined)
export const mockRefreshData = vi.fn().mockResolvedValue(undefined)
export const mockInvalidateTransactionsCache = vi.fn()
export const mockFetchExternalIntegrations = vi
  .fn()
  .mockResolvedValue(undefined)
export const mockSaveSettings = vi.fn().mockResolvedValue(undefined)
export const mockExportFile = vi.fn()
export const mockImportFile = vi.fn()
export const mockGetTemplates = vi.fn()
export const mockSaveBlobToDevice = vi.fn().mockResolvedValue(false)

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}))

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    settings: { export: null, importing: null },
    exportState: {},
    setExportState: vi.fn(),
    showToast: mockShowToast,
    fetchEntities: mockFetchEntities,
    entities: [
      { id: "entity-1", name: "Bank A", type: "BANK" },
      { id: "entity-2", name: "Broker B", type: "BROKER" },
    ],
    externalIntegrations: [],
    fetchExternalIntegrations: mockFetchExternalIntegrations,
    saveSettings: mockSaveSettings,
    fetchSettings: mockFetchSettings,
    featureFlags: {},
    isLoading: false,
  }),
}))

vi.mock("@/context/FinancialDataContext", () => ({
  useFinancialData: () => ({
    refreshData: mockRefreshData,
    refreshRealEstate: vi.fn(),
    refreshFlows: vi.fn(),
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
    invalidateTransactionsCache: mockInvalidateTransactionsCache,
  }),
}))

vi.mock("@/hooks/useModalBackHandler", () => ({
  useModalBackHandler: vi.fn(),
}))

vi.mock("@/services/api", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    exportFile: (...args: unknown[]) => mockExportFile(...args),
    importFile: (...args: unknown[]) => mockImportFile(...args),
    getTemplates: (...args: unknown[]) => mockGetTemplates(...args),
    getTemplateFields: vi.fn().mockResolvedValue([]),
    createTemplate: vi.fn().mockResolvedValue({}),
    updateTemplate: vi.fn().mockResolvedValue({}),
    deleteTemplate: vi.fn().mockResolvedValue(undefined),
  }
})

vi.mock("@/lib/mobile", async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    saveBlobToDevice: (...args: unknown[]) => mockSaveBlobToDevice(...args),
  }
})

vi.mock("framer-motion", () => {
  const handler = {
    get(_target: any, prop: string | symbol) {
      if (typeof prop === "symbol") return undefined
      return ({ children, ...rest }: any) => (
        <div data-motion={prop} {...rest}>
          {children}
        </div>
      )
    },
  }
  return {
    motion: new Proxy({}, handler),
    AnimatePresence: ({ children }: { children: any }) => <>{children}</>,
  }
})

vi.mock("@/components/ui/Tabs", async () => {
  const React = await import("react")
  const TabsContext = React.createContext({
    value: "",
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    onValueChange: (_: string) => {},
  })
  function Tabs({
    value,
    defaultValue,
    onValueChange,
    children,
    className,
    ...rest
  }: any) {
    const [internalValue, setInternalValue] = React.useState(
      value ?? defaultValue ?? "",
    )
    const activeValue = value !== undefined ? value : internalValue
    const handleChange = (newValue: string) => {
      setInternalValue(newValue)
      onValueChange?.(newValue)
    }
    return (
      <TabsContext.Provider
        value={{ value: activeValue, onValueChange: handleChange }}
      >
        <div
          data-orientation="horizontal"
          dir="ltr"
          className={className}
          {...rest}
        >
          {children}
        </div>
      </TabsContext.Provider>
    )
  }
  function TabsList({ children, className, ...rest }: any) {
    return (
      <div role="tablist" className={className} {...rest}>
        {children}
      </div>
    )
  }
  function TabsTrigger({ value, children, className, disabled, ...rest }: any) {
    const ctx = React.useContext(TabsContext)
    return (
      <button
        role="tab"
        data-state={ctx.value === value ? "active" : "inactive"}
        data-value={value}
        disabled={disabled}
        className={className}
        onClick={() => ctx.onValueChange(value)}
        {...rest}
      >
        {children}
      </button>
    )
  }
  function TabsContent({
    value,
    children,
    className,
    forceMount,
    ...rest
  }: any) {
    const ctx = React.useContext(TabsContext)
    if (!forceMount && ctx.value !== value) return null
    return (
      <div
        role="tabpanel"
        data-state={ctx.value === value ? "active" : "inactive"}
        data-value={value}
        className={className}
        {...rest}
      >
        {children}
      </div>
    )
  }
  return { Tabs, TabsList, TabsTrigger, TabsContent }
})

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider>{children}</I18nProvider>
}

export function renderExportPage() {
  return render(<ExportPage />, { wrapper: Wrapper })
}

export function renderPreviewDialog(
  props: Partial<Parameters<typeof FileImportPreviewDialog>[0]> = {},
) {
  const defaultStrings: FileImportPreviewStrings = {
    title: "Import Preview",
    description: "Review the data before importing",
    empty: "No data to import",
    positionsTitle: "Positions",
    positionsSubtitle: "The following positions will be imported",
    entityTotal: "{count} entries total",
    productTotal: "{count} entries",
    transactionsTitle: "Transactions",
    transactionsSubtitle: "The following transactions will be imported",
    transactionTotal: "{count} transactions",
    showProductDetails: "Show details",
    hideProductDetails: "Hide details",
    sampleEntriesLabel: "Sample entries:",
    moreEntries: "+{count} more",
    cancel: "Cancel",
    confirm: "Confirm Import",
  }

  const defaultProps = {
    isOpen: true,
    isLoading: false,
    locale: "en-US",
    previewStrings: defaultStrings,
    loadingLabel: "Loading...",
    productTypeLabels: {
      [ProductType.ACCOUNT]: "Accounts",
      [ProductType.STOCK_ETF]: "Stocks & ETFs",
      [ProductType.FUND]: "Funds",
      [ProductType.CRYPTO]: "Crypto",
    },
    importData: null as ImportedData | null,
    templateFieldLabels: {},
    previewUnnamedEntry: "Unnamed entry",
    warningStrings: {
      title: "Warnings",
      description: "Unexpected columns found in {entry}",
    },
    infoWarnings: null as ImportError[] | null,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    ...props,
  }

  const renderResult = render(<FileImportPreviewDialog {...defaultProps} />, {
    wrapper: Wrapper,
  })
  const originalRerender = renderResult.rerender

  return {
    ...renderResult,
    rerender: (ui: React.ReactElement) =>
      originalRerender(<Wrapper>{ui}</Wrapper>),
    props: defaultProps,
  }
}

export function buildExportResult(
  overrides?: Partial<{ blob: Blob; filename: string; contentType: string }>,
) {
  return {
    blob: new Blob(["test"], { type: "text/csv" }),
    filename: "export.csv",
    contentType: "text/csv",
    ...overrides,
  }
}

export function buildImportResult(
  overrides?: Partial<ImportResult>,
): ImportResult {
  return {
    code: "COMPLETED" as any,
    data: null,
    errors: [],
    ...overrides,
  }
}

export function buildImportedPositionData(): ImportedData {
  return {
    positions: [
      {
        entity: { id: "entity-1", name: "Bank A" },
        products: {
          [ProductType.ACCOUNT]: {
            entries: [
              {
                id: "acc-1",
                name: "Main Account",
                total: 1000,
                currency: "EUR",
              },
              {
                id: "acc-2",
                name: "Savings Account",
                total: 5000,
                currency: "EUR",
              },
            ],
          },
        },
      },
    ] as any,
  }
}

export function buildImportedTransactionData(): ImportedData {
  return {
    transactions: {
      account: [
        {
          id: "tx-1",
          description: "Payment",
          amount: -50,
          currency: "EUR",
          product_type: ProductType.ACCOUNT,
        },
        {
          id: "tx-2",
          description: "Salary",
          amount: 2000,
          currency: "EUR",
          product_type: ProductType.ACCOUNT,
        },
      ],
      investment: [],
    } as any,
  }
}

export function buildTemplate(overrides?: Partial<Template>): Template {
  return {
    id: "tpl-1",
    name: "Test Template",
    type: TemplateType.IMPORT,
    feature: "TRANSACTIONS" as Feature,
    product: ProductType.ACCOUNT,
    fields: [],
    ...overrides,
  } as Template
}

export function resetAllMocks() {
  mockNavigate.mockReset()
  mockShowToast.mockReset()
  mockFetchEntities.mockReset().mockResolvedValue(undefined)
  mockFetchSettings.mockReset().mockResolvedValue(undefined)
  mockRefreshData.mockReset().mockResolvedValue(undefined)
  mockInvalidateTransactionsCache.mockReset()
  mockFetchExternalIntegrations.mockReset().mockResolvedValue(undefined)
  mockSaveSettings.mockReset().mockResolvedValue(undefined)
  mockExportFile.mockReset()
  mockImportFile.mockReset()
  mockGetTemplates.mockReset().mockResolvedValue([])
  mockSaveBlobToDevice.mockReset().mockResolvedValue(false)
}
