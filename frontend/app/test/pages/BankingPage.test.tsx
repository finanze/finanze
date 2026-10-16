import React, { type ReactNode } from "react"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import BankingPage from "@/pages/BankingPage"
import en from "@/i18n/locales/en.json"
import { formatCurrency } from "@/lib/formatters"
import { DataSource, EntityOrigin, EntityType, type Entity } from "@/types"
import {
  CardType,
  ProductType,
  type Card,
  type EntitiesPosition,
  type ProductPositions,
} from "@/types/position"
import type { useManualPositions } from "@/components/manual/ManualPositionsManager"
import type {
  ManualPositionAsset,
  ManualPositionDraft,
} from "@/components/manual/manualPositionTypes"

type ManualState = ReturnType<typeof useManualPositions>

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
  const AssetContext = createContext<ManualPositionAsset>("bankAccounts")

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

vi.mock("@/components/InvestmentFilters", () => ({
  InvestmentFilters: ({
    filteredEntities,
    selectedEntities,
    onEntitiesChange,
  }: {
    filteredEntities: Entity[]
    selectedEntities: string[]
    onEntitiesChange: (ids: string[]) => void
  }) => (
    <select
      aria-label="Entity filter"
      value={selectedEntities[0] ?? ""}
      onChange={event =>
        onEntitiesChange(event.target.value ? [event.target.value] : [])
      }
    >
      <option value="">All entities</option>
      {filteredEntities.map(entity => (
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

const makeCard = (overrides: Partial<Card> = {}): Card => ({
  id: "credit-eur",
  name: "EUR credit",
  type: CardType.CREDIT,
  used: 100,
  currency: "EUR",
  active: true,
  source: DataSource.MANUAL,
  ...overrides,
})

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
  isDraftDirty: () => true,
  collectSavePayload: () => new Map(),
  setSavingState: vi.fn(),
  handleExternalSaveSuccess: vi.fn(),
})

const setPositions = (cardsByEntity: Record<string, Card[]>) => {
  state.entities = Object.keys(cardsByEntity).map(
    (id, index) =>
      ({
        id,
        name: `Bank ${index + 1}`,
        type: EntityType.FINANCIAL_INSTITUTION,
        origin: EntityOrigin.MANUAL,
      }) as Entity,
  )
  state.positionsData = {
    positions: Object.fromEntries(
      state.entities.map(entity => [
        entity.id,
        [
          {
            id: `position-${entity.id}`,
            entity,
            date: "2026-01-01",
            source: DataSource.MANUAL,
            products: {
              [ProductType.CARD]: { entries: cardsByEntity[entity.id] },
            } as ProductPositions,
          },
        ],
      ]),
    ),
  }
}

const renderPage = () => {
  const content = () => (
    <MemoryRouter>
      <BankingPage />
    </MemoryRouter>
  )
  const view = render(content())
  return { rerender: () => view.rerender(content()) }
}

const expectUsage = (amount: number, count: number) => {
  const title = screen.getByText(en.banking.totalCreditCardUsed)
  const card = title.parentElement?.parentElement
  expect(card).toBeInTheDocument()
  expect(card).toHaveTextContent(
    formatCurrency(amount, "en-US", "EUR").replace(/[.,]/g, ""),
  )
  expect(
    within(card as HTMLElement).getByText(
      `${count} ${count === 1 ? en.banking.card : en.banking.cards}`,
    ),
  ).toBeInTheDocument()
}

const cardDraft = (card: Card): ManualPositionDraft<Card> => ({
  ...card,
  originalId: card.id,
  localId: `draft-${card.id}`,
  entityId: "bank-a",
  entityName: "Bank 1",
})

beforeEach(() => {
  localStorage.clear()
  state.manual.clear()
  setPositions({ "bank-a": [makeCard()] })
  for (const asset of [
    "bankAccounts",
    "bankCards",
    "bankLoans",
    "bankCredits",
  ] as const) {
    state.manual.set(asset, makeManualState(asset))
  }
})

afterEach(cleanup)

describe("Banking credit-card usage", () => {
  it("shows only converted credit usage and credit count while listing debit cards", () => {
    setPositions({
      "bank-a": [
        makeCard(),
        makeCard({
          id: "credit-usd",
          name: "USD credit",
          used: 125,
          currency: "USD",
        }),
        makeCard({
          id: "debit",
          name: "Debit card",
          type: CardType.DEBIT,
          used: 900,
        }),
      ],
    })
    renderPage()

    expectUsage(200, 2)
    expect(screen.getByText("Debit card")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: `${en.banking.cards}(3)` }),
    ).toBeInTheDocument()
  })

  it("keeps debit-only lists visible without a credit-card KPI", () => {
    setPositions({
      "bank-a": [makeCard({ name: "Debit card", type: CardType.DEBIT })],
    })
    renderPage()

    expect(
      screen.queryByText(en.banking.totalCreditCardUsed),
    ).not.toBeInTheDocument()
    expect(screen.getByText("Debit card")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: `${en.banking.cards}(1)` }),
    ).toBeInTheDocument()
  })

  it("respects selected entities without counting their debit usage", async () => {
    setPositions({
      "bank-a": [makeCard()],
      "bank-b": [
        makeCard({ id: "other-credit", used: 300 }),
        makeCard({ id: "other-debit", type: CardType.DEBIT, used: 900 }),
      ],
    })
    renderPage()
    expectUsage(400, 2)

    fireEvent.change(screen.getByRole("combobox", { name: "Entity filter" }), {
      target: { value: "bank-b" },
    })

    await waitFor(() => expectUsage(300, 1))
  })

  it("previews a manual type change without hiding the card", () => {
    const view = renderPage()
    expectUsage(100, 1)

    const manual = state.manual.get("bankCards") as ManualState
    manual.isEditMode = true
    manual.drafts = [cardDraft(makeCard({ type: CardType.DEBIT }))]
    view.rerender()

    expect(
      screen.queryByText(en.banking.totalCreditCardUsed),
    ).not.toBeInTheDocument()
    expect(screen.getByText("EUR credit")).toBeInTheDocument()
  })

  it("updates the credit count when a zero-usage debit draft becomes credit", () => {
    const debit = makeCard({ id: "debit", type: CardType.DEBIT, used: 0 })
    setPositions({ "bank-a": [makeCard({ used: 0 }), debit] })
    const view = renderPage()
    expectUsage(0, 1)

    const manual = state.manual.get("bankCards") as ManualState
    manual.drafts = [cardDraft({ ...debit, type: CardType.CREDIT })]
    view.rerender()

    expectUsage(0, 2)
  })

  it("removes deleted credit drafts from the KPI but keeps debit cards", () => {
    setPositions({
      "bank-a": [
        makeCard(),
        makeCard({ id: "other-credit", name: "Other credit", used: 50 }),
        makeCard({ id: "debit", name: "Debit card", type: CardType.DEBIT }),
      ],
    })
    const view = renderPage()
    expectUsage(150, 2)

    const manual = state.manual.get("bankCards") as ManualState
    manual.isEntryDeleted = id => id === "credit-eur"
    view.rerender()

    expectUsage(50, 1)
    expect(screen.getByText("Debit card")).toBeInTheDocument()
    expect(screen.queryByText("EUR credit")).not.toBeInTheDocument()
  })
})
