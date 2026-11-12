import type { ReactNode } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest"

import FundsInvestmentPage from "@/pages/FundsInvestmentPage"
import en from "@/i18n/locales/en.json"
import { DataSource, EntityOrigin, EntityType, type Entity } from "@/types"
import {
  FundType,
  ProductType,
  type EntitiesPosition,
  type FundDetail,
  type ProductPositions,
} from "@/types/position"
import type { GainsTimelineQuery } from "@/types/gainsTimeline"
import type { useManualPositions } from "@/components/manual/ManualPositionsManager"
import type { ManualPositionAsset } from "@/components/manual/manualPositionTypes"

type ManualState = ReturnType<typeof useManualPositions>

interface TimelineProps {
  query: GainsTimelineQuery
  titleAddon?: ReactNode
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
}

const state = vi.hoisted(() => ({
  positionsData: null as EntitiesPosition | null,
  entities: [] as Entity[],
  manual: new Map<ManualPositionAsset, ManualState>(),
  settings: { general: { defaultCurrency: "EUR", editMode: "STANDARD" } },
  exchangeRates: { EUR: { USD: 1.25 } },
  showToast: vi.fn(),
  fetchEntities: vi.fn(),
  refreshEntity: vi.fn(),
  refreshData: vi.fn(),
}))

const timeline = vi.hoisted(() => ({
  props: null as TimelineProps | null,
}))

vi.mock("@/i18n", () => ({
  useI18n: () => ({ t: en, locale: "en-US" }),
}))

vi.mock("@/context/FinancialDataContext", () => ({
  useFinancialData: () => ({
    positionsData: state.positionsData,
    isLoading: false,
    refreshEntity: state.refreshEntity,
    refreshData: state.refreshData,
  }),
}))

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => state,
}))

vi.mock("@/components/manual/ManualPositionsManager", async () => {
  const { createContext, useContext } = await import("react")
  const AssetContext = createContext<ManualPositionAsset>("funds")

  return {
    ManualPositionsManager: ({
      asset,
      children,
    }: {
      asset: ManualPositionAsset
      children: ReactNode
    }) => (
      <AssetContext.Provider value={asset}>{children}</AssetContext.Provider>
    ),
    useManualPositions: () => state.manual.get(useContext(AssetContext)),
  }
})

vi.mock("@/components/InvestmentEvolutionTimeline", () => ({
  InvestmentEvolutionTimeline: (props: TimelineProps) => {
    timeline.props = props
    return (
      <section
        data-testid="evolution-timeline"
        data-expanded={String(props.expanded)}
      >
        {props.titleAddon}
      </section>
    )
  },
}))

vi.mock("@/components/InvestmentDistributionChart", () => ({
  InvestmentDistributionChart: () => null,
}))

vi.mock("@/components/EntitySelector", () => ({
  EntitySelector: ({
    entities,
    selectedEntityIds,
    onSelectionChange,
  }: {
    entities: Entity[]
    selectedEntityIds: string[]
    onSelectionChange: (ids: string[]) => void
  }) => (
    <select
      aria-label="Entity filter"
      value={selectedEntityIds[0] ?? ""}
      onChange={event =>
        onSelectionChange(event.target.value ? [event.target.value] : [])
      }
    >
      <option value="">All entities</option>
      {entities.map(entity => (
        <option key={entity.id} value={entity.id}>
          {entity.name}
        </option>
      ))}
    </select>
  ),
}))

vi.mock("@/components/ui/PinAssetButton", () => ({
  PinAssetButton: () => null,
}))

vi.mock("@/components/ui/Sensitive", () => ({
  Sensitive: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock("@/services/api", () => ({ saveManualPositions: vi.fn() }))

const makeManualState = (asset: ManualPositionAsset): ManualState => ({
  asset,
  drafts: [],
  isEditMode: false,
  isQuickMode: false,
  hasLocalChanges: false,
  isSaving: false,
  manualEntities: state.entities,
  assetTitle: asset,
  assetDescription: asset,
  assetPath: asset,
  addLabel: "Add",
  editLabel: "Edit",
  cancelLabel: "Cancel",
  doneLabel: "Done",
  saveLabel: "Save",
  translate: path => path,
  beginCreate: vi.fn(),
  editByOriginalId: vi.fn(),
  editByLocalId: vi.fn(),
  deleteByOriginalId: vi.fn(),
  deleteByLocalId: vi.fn(),
  enterEditMode: vi.fn(),
  requestSave: vi.fn().mockResolvedValue(undefined),
  requestCancel: vi.fn(),
  getDraftByOriginalId: vi.fn(),
  getDraftByLocalId: vi.fn(),
  getInitialDraftByOriginalId: vi.fn(),
  isEntryDeleted: () => false,
  isDraftDirty: () => false,
  collectSavePayload: () => new Map(),
  setSavingState: vi.fn(),
  handleExternalSaveSuccess: vi.fn(),
})

const makeFund = (overrides: Partial<FundDetail> = {}): FundDetail => ({
  id: "fund-sp500",
  name: "Vanguard US 500",
  isin: "IE00BFPM9V94",
  market: "",
  shares: 10,
  initial_investment: 1000,
  average_buy_price: 100,
  market_value: 1200,
  type: FundType.MUTUAL_FUND,
  currency: "EUR",
  source: DataSource.REAL,
  ...overrides,
})

const setFunds = (funds: FundDetail[]) => {
  const entity = {
    id: "entity-a",
    name: "Indexa Capital",
    type: EntityType.FINANCIAL_INSTITUTION,
    origin: EntityOrigin.NATIVE,
  } as Entity
  state.entities = [entity]
  state.positionsData = {
    positions: {
      [entity.id]: [
        {
          id: "position-a",
          entity,
          date: "2026-01-01",
          source: DataSource.REAL,
          products: {
            [ProductType.FUND]: { entries: funds },
          } as ProductPositions,
        },
      ],
    },
  }
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <FundsInvestmentPage />
    </MemoryRouter>,
  )

const fundHeader = (name: string) =>
  screen
    .getByRole("heading", { name })
    .closest('[role="button"]') as HTMLElement

const evolutionButton = (name: string) => {
  const header = fundHeader(name)
  if (header.getAttribute("aria-expanded") !== "true") fireEvent.click(header)
  return within(header.parentElement as HTMLElement).getByTestId(
    "fund-evolution-button",
  )
}

const selectedAssetKeys = () => timeline.props?.query.assets[0].asset_keys

let scrollIntoView: Mock<Element["scrollIntoView"]>

beforeEach(() => {
  timeline.props = null
  scrollIntoView = vi.fn<Element["scrollIntoView"]>()
  Element.prototype.scrollIntoView = scrollIntoView
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      media: query,
      matches: false,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: () => true,
    })),
  )
  state.manual.clear()
  setFunds([
    makeFund(),
    makeFund({
      id: "fund-no-isin",
      name: "Unlisted Fund",
      isin: "",
      market_value: 500,
    }),
  ])
  state.manual.set("funds", makeManualState("funds"))
  state.manual.set("fundPortfolios", makeManualState("fundPortfolios"))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("FundsInvestmentPage fund evolution", () => {
  it("shows the aggregate evolution by default", () => {
    renderPage()

    expect(selectedAssetKeys()).toBeUndefined()
    expect(timeline.props?.expanded).toBe(false)
    expect(screen.queryByTestId("selected-fund-chip")).toBeNull()
  })

  it("filters the chart to the selected fund and expands it", () => {
    renderPage()

    fireEvent.click(evolutionButton("Vanguard US 500"))

    expect(selectedAssetKeys()).toEqual(["IE00BFPM9V94"])
    expect(timeline.props?.expanded).toBe(true)
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId("selected-fund-chip")).toHaveTextContent(
      "Vanguard US 500",
    )
  })

  it("deselects the fund when clicking it again without scrolling", () => {
    renderPage()

    fireEvent.click(evolutionButton("Vanguard US 500"))
    fireEvent.click(evolutionButton("Vanguard US 500"))

    expect(selectedAssetKeys()).toBeUndefined()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId("selected-fund-chip")).toBeNull()
  })

  it("falls back to the fund name when it has no ISIN", () => {
    renderPage()

    fireEvent.click(evolutionButton("Unlisted Fund"))

    expect(selectedAssetKeys()).toEqual(["Unlisted Fund"])
  })

  it("re-expands a collapsed chart when selecting another fund", () => {
    renderPage()

    fireEvent.click(evolutionButton("Vanguard US 500"))
    act(() => timeline.props?.onExpandedChange?.(false))
    expect(timeline.props?.expanded).toBe(false)

    fireEvent.click(evolutionButton("Unlisted Fund"))

    expect(timeline.props?.expanded).toBe(true)
    expect(selectedAssetKeys()).toEqual(["Unlisted Fund"])
  })

  it("resets to all funds from the chip", () => {
    renderPage()

    fireEvent.click(evolutionButton("Vanguard US 500"))
    fireEvent.click(screen.getByTestId("selected-fund-chip"))

    expect(selectedAssetKeys()).toBeUndefined()
    expect(screen.queryByTestId("selected-fund-chip")).toBeNull()
  })

  it("resets the selected fund when clearing filters", () => {
    renderPage()

    fireEvent.click(evolutionButton("Vanguard US 500"))
    fireEvent.change(screen.getByLabelText("Entity filter"), {
      target: { value: "entity-a" },
    })
    expect(timeline.props?.query.entities).toEqual(["entity-a"])
    expect(selectedAssetKeys()).toEqual(["IE00BFPM9V94"])

    fireEvent.click(screen.getByRole("button", { name: en.transactions.clear }))

    expect(selectedAssetKeys()).toBeUndefined()
    expect(timeline.props?.query.entities).toBeUndefined()
  })

  it("shows the evolution toggle only in the expanded card", () => {
    renderPage()

    expect(screen.queryByTestId("fund-evolution-button")).toBeNull()

    const toggle = evolutionButton("Vanguard US 500")
    expect(toggle).toHaveTextContent(en.investments.viewEvolution)

    fireEvent.click(toggle)

    expect(toggle).toHaveAttribute("aria-pressed", "true")
    expect(toggle).toHaveTextContent(en.investments.showAllFunds)
  })

  it("lets nested header buttons handle Enter instead of expanding the card", () => {
    renderPage()

    const header = fundHeader("Vanguard US 500")
    const notPrevented = fireEvent.keyDown(
      within(header).getByRole("button", { name: "Indexa Capital" }),
      { key: "Enter" },
    )

    expect(notPrevented).toBe(true)
    expect(header).toHaveAttribute("aria-expanded", "false")

    fireEvent.keyDown(header, { key: "Enter" })

    expect(header).toHaveAttribute("aria-expanded", "true")
  })
})
