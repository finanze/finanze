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

import StocksInvestmentPage from "@/pages/StocksInvestmentPage"
import en from "@/i18n/locales/en.json"
import { DataSource, EntityOrigin, EntityType, type Entity } from "@/types"
import {
  EquityType,
  ProductType,
  type EntitiesPosition,
  type ProductPositions,
  type StockDetail,
} from "@/types/position"
import type { GainsTimelineQuery } from "@/types/gainsTimeline"
import type { useManualPositions } from "@/components/manual/ManualPositionsManager"

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
  manual: null as ManualState | null,
  settings: { general: { defaultCurrency: "EUR", editMode: "STANDARD" } },
  exchangeRates: { EUR: { USD: 1.25 } },
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
  }),
}))

vi.mock("@/context/AppContext", () => ({
  useAppContext: () => state,
}))

vi.mock("@/components/manual/ManualPositionsManager", () => ({
  ManualPositionsManager: ({ children }: { children: ReactNode }) => (
    <>{children}</>
  ),
  ManualPositionsControls: () => null,
  ManualPositionsEditBanner: () => null,
  useManualPositions: () => state.manual,
}))

vi.mock("@/components/InvestmentEvolutionTimeline", () => ({
  InvestmentEvolutionTimeline: (props: TimelineProps) => {
    timeline.props = props
    return (
      <section data-testid="evolution-timeline">{props.titleAddon}</section>
    )
  },
}))

vi.mock("@/components/InvestmentDistributionChart", () => ({
  InvestmentDistributionChart: () => null,
}))

vi.mock("@/components/InvestmentFilters", () => ({
  InvestmentFilters: ({ extraFilters }: { extraFilters?: ReactNode }) => (
    <div>{extraFilters}</div>
  ),
}))

vi.mock("@/components/ui/PinAssetButton", () => ({
  PinAssetButton: () => null,
}))

vi.mock("@/components/ui/Sensitive", () => ({
  Sensitive: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

const makeManualState = (): ManualState =>
  ({
    asset: "stocks",
    drafts: [],
    isEditMode: false,
    translate: (path: string) => path,
    editByOriginalId: vi.fn(),
    editByLocalId: vi.fn(),
    deleteByOriginalId: vi.fn(),
    deleteByLocalId: vi.fn(),
    enterEditMode: vi.fn(),
    isEntryDeleted: () => false,
    isDraftDirty: () => false,
  }) as unknown as ManualState

const makeStock = (overrides: Partial<StockDetail> = {}): StockDetail => ({
  id: "stock-apple",
  name: "Apple",
  ticker: "AAPL",
  isin: "US0378331005",
  market: "NASDAQ",
  shares: 10,
  initial_investment: 1000,
  average_buy_price: 100,
  market_value: 1500,
  currency: "EUR",
  type: EquityType.STOCK,
  source: DataSource.REAL,
  ...overrides,
})

const setStocks = (stocks: StockDetail[]) => {
  const entity = {
    id: "entity-a",
    name: "Broker",
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
            [ProductType.STOCK_ETF]: { entries: stocks },
          } as ProductPositions,
        },
      ],
    },
  }
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <StocksInvestmentPage />
    </MemoryRouter>,
  )

const stockHeader = (name: string) =>
  screen
    .getByRole("heading", { name })
    .closest('[role="button"]') as HTMLElement

const evolutionButton = (name: string) => {
  const header = stockHeader(name)
  if (header.getAttribute("aria-expanded") !== "true") fireEvent.click(header)
  return within(header.parentElement as HTMLElement).getByTestId(
    "stock-evolution-button",
  )
}

const stockFilter = () => timeline.props?.query.assets[0]

let scrollIntoView: Mock<Element["scrollIntoView"]>

beforeEach(() => {
  timeline.props = null
  scrollIntoView = vi.fn<Element["scrollIntoView"]>()
  Element.prototype.scrollIntoView = scrollIntoView
  state.manual = makeManualState()
  setStocks([
    makeStock(),
    makeStock({
      id: "stock-no-isin",
      name: "Tesla",
      ticker: "TSLA",
      isin: "",
      market_value: 800,
    }),
    makeStock({
      id: "etf-no-codes",
      name: "Private ETF",
      ticker: "",
      isin: "",
      market_value: 300,
      type: EquityType.ETF,
    }),
  ])
})

afterEach(() => {
  cleanup()
})

describe("StocksInvestmentPage stock evolution", () => {
  it("shows the aggregate evolution by default", () => {
    renderPage()

    expect(stockFilter()?.asset_keys).toBeUndefined()
    expect(timeline.props?.expanded).toBe(false)
    expect(screen.queryByTestId("stock-evolution-button")).toBeNull()
  })

  it("filters the chart to the selected stock and expands it", () => {
    renderPage()

    const toggle = evolutionButton("Apple")
    expect(toggle).toHaveTextContent(en.investments.viewEvolution)
    fireEvent.click(toggle)

    expect(stockFilter()?.asset_keys).toEqual(["US0378331005"])
    expect(timeline.props?.expanded).toBe(true)
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId("selected-stock-chip")).toHaveTextContent("Apple")
    expect(toggle).toHaveAttribute("aria-pressed", "true")
    expect(toggle).toHaveTextContent(en.investments.showAllStocks)
  })

  it("falls back to the ticker and then the name", () => {
    renderPage()

    fireEvent.click(evolutionButton("Tesla"))
    expect(stockFilter()?.asset_keys).toEqual(["TSLA"])

    fireEvent.click(evolutionButton("Private ETF"))
    expect(stockFilter()?.asset_keys).toEqual(["Private ETF"])
  })

  it("deselects the stock when clicking it again without scrolling", () => {
    renderPage()

    fireEvent.click(evolutionButton("Apple"))
    fireEvent.click(evolutionButton("Apple"))

    expect(stockFilter()?.asset_keys).toBeUndefined()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId("selected-stock-chip")).toBeNull()
  })

  it("resets to all stocks from the chip", () => {
    renderPage()

    fireEvent.click(evolutionButton("Apple"))
    fireEvent.click(screen.getByTestId("selected-stock-chip"))

    expect(stockFilter()?.asset_keys).toBeUndefined()
    expect(screen.queryByTestId("selected-stock-chip")).toBeNull()
  })

  it("re-expands a collapsed chart when selecting another stock", () => {
    renderPage()

    fireEvent.click(evolutionButton("Apple"))
    act(() => timeline.props?.onExpandedChange?.(false))
    expect(timeline.props?.expanded).toBe(false)

    fireEvent.click(evolutionButton("Tesla"))

    expect(timeline.props?.expanded).toBe(true)
  })

  it("keeps the equity type filter alongside the selected stock", () => {
    renderPage()

    fireEvent.click(evolutionButton("Apple"))
    fireEvent.click(
      screen.getByRole("button", { name: en.enums.equityType.STOCK }),
    )

    expect(stockFilter()).toMatchObject({
      asset_keys: ["US0378331005"],
      equity_types: [EquityType.STOCK],
    })
  })

  it("lets nested header buttons handle Enter instead of expanding the card", () => {
    renderPage()

    const header = stockHeader("Apple")
    const notPrevented = fireEvent.keyDown(
      within(header).getByRole("button", { name: "Broker" }),
      { key: "Enter" },
    )

    expect(notPrevented).toBe(true)
    expect(header).toHaveAttribute("aria-expanded", "false")

    fireEvent.keyDown(header, { key: "Enter" })

    expect(header).toHaveAttribute("aria-expanded", "true")
  })
})
