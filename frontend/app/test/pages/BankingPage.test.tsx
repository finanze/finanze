import React, { type ReactNode } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import BankingPage from "@/pages/BankingPage"
import en from "@/i18n/locales/en.json"
import { formatCurrency, formatIban, formatPercentage } from "@/lib/formatters"
import { DataSource, EntityOrigin, EntityType, type Entity } from "@/types"
import {
  AccountType,
  CardType,
  InstallmentFrequency,
  InterestType,
  LoanType,
  ProductType,
  type Account,
  type Card,
  type CreditDetail,
  type EntitiesPosition,
  type Loan,
  type ProductPositions,
} from "@/types/position"
import type { useManualPositions } from "@/components/manual/ManualPositionsManager"
import type {
  ManualPositionAsset,
  ManualPositionDraft,
} from "@/components/manual/manualPositionTypes"

type ManualState = ReturnType<typeof useManualPositions>

let viewportWidth = 1280
const viewportListeners = new Set<() => void>()

const setViewportWidth = (width: number) => {
  act(() => {
    viewportWidth = width
    viewportListeners.forEach(listener => listener())
  })
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

const makeLoan = (overrides: Partial<Loan> = {}): Loan => ({
  id: "home-loan",
  name: "Home loan",
  type: LoanType.MORTGAGE,
  currency: "EUR",
  current_installment: 450,
  interest_rate: 0.035,
  loan_amount: 100000,
  next_payment_date: "2026-11-01",
  principal_outstanding: 90000,
  principal_paid: 10000,
  interest_type: InterestType.FIXED,
  installment_frequency: InstallmentFrequency.MONTHLY,
  creation: "2020-01-01",
  maturity: "2045-01-01",
  source: DataSource.MANUAL,
  ...overrides,
})

const makeCredit = (overrides: Partial<CreditDetail> = {}): CreditDetail => ({
  id: "credit-line",
  name: "Flexible credit",
  currency: "EUR",
  credit_limit: 10000,
  drawn_amount: 3000,
  interest_rate: 0.055,
  pledged_amount: 2000,
  creation: "2025-01-01",
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

const setPositions = (
  cardsByEntity: Record<string, Card[]>,
  accountsByEntity: Record<string, Account[]> = {},
  loansByEntity: Record<string, Loan[]> = {},
  creditsByEntity: Record<string, CreditDetail[]> = {},
) => {
  state.entities = [
    ...new Set([
      ...Object.keys(cardsByEntity),
      ...Object.keys(accountsByEntity),
      ...Object.keys(loansByEntity),
      ...Object.keys(creditsByEntity),
    ]),
  ].map(
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
              [ProductType.CARD]: { entries: cardsByEntity[entity.id] ?? [] },
              [ProductType.ACCOUNT]: {
                entries: accountsByEntity[entity.id] ?? [],
              },
              [ProductType.LOAN]: { entries: loansByEntity[entity.id] ?? [] },
              [ProductType.CREDIT]: {
                entries: creditsByEntity[entity.id] ?? [],
              },
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
  viewportWidth = 1280
  viewportListeners.clear()
  vi.stubGlobal("scrollTo", vi.fn())
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      media: query,
      get matches() {
        return query === "(max-width: 767px)" && viewportWidth <= 767
      },
      onchange: null,
      addListener: (listener: () => void) => viewportListeners.add(listener),
      removeListener: (listener: () => void) =>
        viewportListeners.delete(listener),
      addEventListener: (_type: string, listener: () => void) =>
        viewportListeners.add(listener),
      removeEventListener: (_type: string, listener: () => void) =>
        viewportListeners.delete(listener),
      dispatchEvent: () => true,
    })),
  )
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

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("Banking section expansion", () => {
  it.each([
    [en.banking.accounts, "banking-accounts-content"],
    [en.banking.cards, "banking-cards-content"],
    [en.banking.loansAndCredits, "banking-loans-content"],
  ])("animates %s closed and open", async (title, contentId) => {
    renderPage()
    const button = screen
      .getByRole("heading", { name: new RegExp(`^${title}`) })
      .closest("button")!
    const content = document.getElementById(contentId)!
    const body = content.firstElementChild
    expect(button).toHaveAttribute("aria-expanded", "true")
    expect(button).toHaveAttribute("aria-controls", contentId)

    fireEvent.click(button)
    expect(button).toHaveAttribute("aria-expanded", "false")
    expect(content).toHaveAttribute("aria-hidden", "true")
    expect(content).toHaveAttribute("inert")
    expect(content.firstElementChild).toBe(body)
    await waitFor(() => expect(content).toBeEmptyDOMElement())

    fireEvent.click(button)
    expect(button).toHaveAttribute("aria-expanded", "true")
    expect(content).not.toHaveAttribute("inert")
    await waitFor(() => expect(content.firstElementChild).toBeVisible())
  })
})

describe("Responsive banking loans and credits", () => {
  const setDebts = () => {
    setPositions(
      {},
      {},
      { "bank-a": [makeLoan()] },
      { "bank-a": [makeCredit()] },
    )
  }
  const getCard = (name: string) =>
    screen
      .getByRole("heading", { name })
      .closest<HTMLDivElement>(".hover\\:shadow-lg")!

  it.each([390, 767])(
    "shows compact summaries at %spx with independently expandable details",
    async width => {
      setViewportWidth(width)
      setDebts()
      renderPage()
      const user = userEvent.setup()
      const loan = getCard("Home loan")
      const credit = getCard("Flexible credit")

      for (const label of [
        en.banking.principalOutstanding,
        en.banking.installment,
        en.banking.interestRate,
        en.banking.next,
      ]) {
        expect(within(loan).getByText(label)).toBeInTheDocument()
      }
      expect(loan).toHaveTextContent(
        formatCurrency(450, "en-US", "EUR").replace(/[.,]/g, ""),
      )
      expect(loan).toHaveTextContent(formatPercentage(3.5, "en-US"))
      for (const [label, amountClass, value] of [
        [
          en.banking.principalOutstanding,
          "text-xl",
          formatCurrency(90000, "en-US", "EUR"),
        ],
        [
          en.banking.installment,
          "text-lg",
          formatCurrency(450, "en-US", "EUR"),
        ],
      ]) {
        const amount = within(loan)
          .getByText(label)
          .parentElement?.querySelector(`:scope > span.${amountClass}`)
        expect(amount).toHaveTextContent(value.replace(".", ""))
        const formattedValue = amount?.querySelector("span.whitespace-nowrap")
        expect(formattedValue?.children[0]).toHaveClass("text-[1.1em]")
        expect(formattedValue?.children[2]).toHaveClass("align-super")
      }
      for (const label of [
        en.banking.creditDrawn,
        en.banking.creditLimit,
        en.banking.interestRate,
      ]) {
        expect(within(credit).getByText(label)).toBeInTheDocument()
      }
      expect(within(loan).queryByText(en.banking.originalAmount)).toBeNull()
      expect(within(credit).queryByText(en.banking.availableCredit)).toBeNull()

      const loanToggle = within(loan).getByRole("button", {
        name: `${en.common.viewDetails}: Home loan`,
      })
      expect(loanToggle).toHaveAttribute("aria-expanded", "false")
      await user.click(loanToggle)
      expect(loanToggle).toHaveAttribute("aria-expanded", "true")
      await waitFor(() => {
        expect(within(loan).getByText(en.banking.originalAmount)).toBeVisible()
      })
      expect(within(credit).queryByText(en.banking.availableCredit)).toBeNull()

      await user.click(
        within(credit).getByRole("button", {
          name: `${en.common.viewDetails}: Flexible credit`,
        }),
      )
      await waitFor(() => {
        expect(
          within(credit).getByText(en.banking.availableCredit),
        ).toBeVisible()
      })
      await user.click(
        within(loan).getByRole("button", {
          name: `${en.common.showLess}: Home loan`,
        }),
      )
      expect(loanToggle).toHaveAttribute("aria-expanded", "false")
      await waitFor(() => {
        expect(within(loan).queryByText(en.banking.originalAmount)).toBeNull()
      })
      expect(within(credit).getByText(en.banking.availableCredit)).toBeVisible()
    },
  )

  it.each([768, 1280])("keeps all details expanded at %spx", async width => {
    setViewportWidth(width)
    setDebts()
    renderPage()

    await waitFor(() => {
      expect(
        within(getCard("Home loan")).getByText(en.banking.originalAmount),
      ).toBeVisible()
      expect(
        within(getCard("Flexible credit")).getByText(
          en.banking.availableCredit,
        ),
      ).toBeVisible()
    })
    expect(
      screen.queryByRole("button", { name: new RegExp(en.common.viewDetails) }),
    ).not.toBeInTheDocument()
  })

  it("updates when resizing without leaking mobile collapse state into desktop", async () => {
    setViewportWidth(390)
    setDebts()
    renderPage()
    const loan = getCard("Home loan")
    const credit = getCard("Flexible credit")
    fireEvent.click(
      within(loan).getByRole("button", {
        name: `${en.common.viewDetails}: Home loan`,
      }),
    )

    setViewportWidth(1280)
    await waitFor(() => {
      expect(within(credit).getByText(en.banking.availableCredit)).toBeVisible()
    })
    expect(
      screen.queryByRole("button", { name: new RegExp(en.common.viewDetails) }),
    ).not.toBeInTheDocument()

    setViewportWidth(390)
    expect(
      within(loan).getByRole("button", {
        name: `${en.common.showLess}: Home loan`,
      }),
    ).toHaveAttribute("aria-expanded", "true")
    expect(
      within(credit).getByRole("button", {
        name: `${en.common.viewDetails}: Flexible credit`,
      }),
    ).toHaveAttribute("aria-expanded", "false")
    await waitFor(() => {
      expect(within(credit).queryByText(en.banking.availableCredit)).toBeNull()
    })
  })

  it("keeps manual edit and delete controls accessible on collapsed mobile cards", () => {
    setViewportWidth(390)
    setDebts()
    const loans = state.manual.get("bankLoans")!
    const credits = state.manual.get("bankCredits")!
    loans.isEditMode = true
    credits.isEditMode = true
    renderPage()

    for (const [name, manual, id] of [
      ["Home loan", loans, "home-loan"],
      ["Flexible credit", credits, "credit-line"],
    ] as const) {
      const card = getCard(name)
      fireEvent.click(
        within(card).getByRole("button", { name: en.common.edit }),
      )
      expect(manual.editByOriginalId).toHaveBeenCalledWith(id)
      fireEvent.click(
        within(card).getByRole("button", { name: en.common.delete }),
      )
      expect(manual.deleteByOriginalId).toHaveBeenCalledWith(id)
      expect(
        within(card).getByRole("button", {
          name: `${en.common.viewDetails}: ${name}`,
        }),
      ).toHaveAttribute("aria-expanded", "false")
    }
  })
})

describe("Banking account cards", () => {
  const account: Account = {
    id: "account-eur",
    name: "Everyday account",
    type: AccountType.CHECKING,
    total: 1000,
    currency: "EUR",
    iban: "ES9121000418450200051332",
    interest: 0.025,
    retained: 10,
    pending_transfers: 20,
    source: DataSource.MANUAL,
  }

  it("shows account details and unboxed indicators in the stacked paper card", () => {
    setPositions({}, { "bank-a": [account] })
    renderPage()

    const card = screen
      .getByRole("heading", { name: account.name! })
      .closest<HTMLDivElement>(".hover\\:shadow-lg")!
    expect(card).toHaveClass(
      "rounded-2xl",
      "rounded-tr-[2.5rem]",
      "rounded-bl-[2rem]",
    )
    const stack = card.parentElement!
    expect(stack).toHaveClass("relative", "pb-1", "pl-2")
    expect(stack.firstElementChild).toHaveClass("bg-transparent", "right-2")
    expect(stack.children[1]).toHaveClass("bottom-0.5", "left-1")
    expect(stack.lastElementChild).toBe(card)
    for (const layer of Array.from(stack.children).slice(0, -1)) {
      expect(layer).toHaveAttribute("aria-hidden", "true")
      expect(layer).toHaveClass("absolute", "pointer-events-none", "border")
    }
    expect(stack.children).toHaveLength(3)
    expect(within(card).getByText(en.accountTypes.CHECKING)).toBeInTheDocument()
    expect(within(card).getByText("Bank 1")).toBeInTheDocument()
    const iban = within(card).getByText(formatIban(account.iban)!)
    expect(iban).toBeInTheDocument()
    expect(iban.parentElement).not.toHaveClass("border")
    expect(
      within(card).getByRole("button", { name: en.common.copy }),
    ).toBeInTheDocument()
    expect(card).toHaveTextContent(
      formatCurrency(account.total, "en-US", "EUR").replace(".", ""),
    )
    const balance = within(card).getByText("€1,000").closest(".text-2xl")!
    expect(balance.parentElement).toHaveClass("flex", "items-baseline")
    for (const [label, amount] of [
      [en.banking.interestRate, formatPercentage(2.5, "en-US")],
      [en.banking.retainedAmount, formatCurrency(10, "en-US", "EUR")],
      [en.banking.pendingTransfers, formatCurrency(20, "en-US", "EUR")],
    ]) {
      const indicator = within(card).getByRole("button", { name: label })
      expect(indicator).toHaveTextContent(amount)
      expect(indicator.parentElement).toHaveClass("ml-auto", "justify-end")
      expect(indicator.parentElement?.parentElement).toBe(balance.parentElement)
      expect(indicator.parentElement).not.toHaveClass("bg-muted/40")
      expect(indicator.parentElement).not.toHaveClass("px-3")
      expect(indicator.parentElement).not.toHaveClass("py-2.5")
    }
  })

  it.each([
    en.banking.interestRate,
    en.banking.retainedAmount,
    en.banking.pendingTransfers,
  ])("shows a themed tooltip on hover, focus and tap for %s", async label => {
    setPositions({}, { "bank-a": [account] })
    renderPage()
    const user = userEvent.setup()
    const indicator = screen.getByRole("button", { name: label })

    await user.hover(indicator)
    const tooltip = await screen.findByRole("tooltip", { name: label })
    expect(tooltip).toHaveClass(
      "bg-popover",
      "text-popover-foreground",
      "border-border",
    )
    await user.unhover(indicator)
    await user.keyboard("{Escape}")
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    })

    fireEvent.focus(indicator)
    expect(
      await screen.findByRole("tooltip", { name: label }),
    ).toBeInTheDocument()
    fireEvent.blur(indicator)
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    })

    await user.pointer({
      keys: "[TouchA]",
      target: indicator,
    })
    expect(
      await screen.findByRole("tooltip", { name: label }),
    ).toBeInTheDocument()
    await user.pointer({
      keys: "[TouchA]",
      target: document.body,
    })
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument()
    })
  })

  it("uses a piggy-bank icon for savings accounts", () => {
    setPositions({}, { "bank-a": [{ ...account, type: AccountType.SAVINGS }] })
    renderPage()

    const card = screen
      .getByRole("heading", { name: account.name! })
      .closest<HTMLDivElement>(".hover\\:shadow-lg")!
    expect(within(card).getByText(en.accountTypes.SAVINGS)).toBeInTheDocument()
    expect(card.querySelector("svg.lucide-piggy-bank")).toBeInTheDocument()
  })

  it("keeps accounts without optional details compact", () => {
    setPositions(
      {},
      {
        "bank-a": [
          {
            ...account,
            name: null,
            iban: null,
            interest: null,
            retained: null,
            pending_transfers: null,
          },
        ],
      },
    )
    renderPage()

    const card = screen
      .getByText(en.accountTypes.CHECKING)
      .closest<HTMLDivElement>(".hover\\:shadow-lg")!
    const balance = within(card).getByText("€1,000").closest(".text-2xl")!
    expect(
      balance.parentElement?.parentElement?.parentElement?.children,
    ).toHaveLength(1)
    for (const label of [
      en.banking.interestRate,
      en.banking.retainedAmount,
      en.banking.pendingTransfers,
    ]) {
      expect(
        within(card).queryByRole("button", { name: label }),
      ).not.toBeInTheDocument()
    }
  })

  it("keeps manual account edit and delete actions available", () => {
    setPositions({}, { "bank-a": [account] })
    const manual = state.manual.get("bankAccounts")!
    manual.isEditMode = true
    renderPage()

    const card = screen
      .getByRole("heading", { name: account.name! })
      .closest<HTMLDivElement>(".hover\\:shadow-lg")!
    fireEvent.click(within(card).getByRole("button", { name: en.common.edit }))
    expect(manual.editByOriginalId).toHaveBeenCalledWith(account.id)
    fireEvent.click(
      within(card).getByRole("button", { name: en.common.delete }),
    )
    expect(manual.deleteByOriginalId).toHaveBeenCalledWith(account.id)
  })
})

describe("Banking credit-card usage", () => {
  it("uses classic embossed number styling without changing the masked number", () => {
    setPositions({ "bank-a": [makeCard({ ending: "4321" })] })
    renderPage()

    const number = screen.getByText(/4321$/)
    expect(number).toHaveTextContent("•••• •••• •••• 4321")
    expect(number).toHaveClass("tracking-[0.12em]", "font-semibold")
    expect(number.className).toContain("Courier")
    expect(number.className).toContain("[text-shadow:")
  })

  it("combines used and limit amounts in one row with a bottom-edge usage bar", () => {
    setPositions({ "bank-a": [makeCard({ used: 250, limit: 1000 })] })
    renderPage()

    const label = screen.getByText(en.banking.used)
    const row = label.parentElement
    const percentage = formatPercentage(25, "en-US")
    expect(row).toHaveTextContent(
      `${formatCurrency(250, "en-US", "EUR")} / ${formatCurrency(1000, "en-US", "EUR")} (${percentage})`,
    )
    expect(screen.queryByText(en.banking.limit)).not.toBeInTheDocument()
    expect(screen.queryByText(en.banking.utilization)).not.toBeInTheDocument()

    const progress = screen.getByRole("progressbar", {
      name: en.banking.utilization,
    })
    expect(progress).toHaveClass("h-1")
    expect(progress).toHaveAttribute("aria-valuenow", "25")
    expect(progress.parentElement?.lastElementChild).toBe(progress)
    expect(progress.firstElementChild).toHaveStyle({ width: "25%" })
  })

  it.each([undefined, null, 0])(
    "keeps the used-only layout when the limit is %s",
    limit => {
      setPositions({ "bank-a": [makeCard({ limit })] })
      renderPage()

      const label = screen.getByText(en.banking.used)
      expect(label.parentElement).toHaveTextContent(
        formatCurrency(100, "en-US", "EUR"),
      )
      expect(
        screen.queryByText(`${en.banking.used} / ${en.banking.limit}`),
      ).not.toBeInTheDocument()
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
    },
  )

  it.each([
    [0, "bg-emerald-500"],
    [60, "bg-emerald-500"],
    [61, "bg-yellow-400"],
    [80, "bg-yellow-400"],
    [81, "bg-red-500"],
    [120, "bg-red-500"],
  ])("preserves the usage indicator for %s%% utilization", (used, color) => {
    setPositions({ "bank-a": [makeCard({ used, limit: 100 })] })
    renderPage()

    const progress = screen.getByRole("progressbar", {
      name: en.banking.utilization,
    })
    expect(progress).toHaveAttribute(
      "aria-valuenow",
      String(Math.min(used, 100)),
    )
    expect(progress.firstElementChild).toHaveClass(color)
    expect(progress.firstElementChild).toHaveStyle({
      width: `${Math.min(used, 100)}%`,
    })
  })

  it("combines converted amounts while retaining the original currency row", () => {
    setPositions({
      "bank-a": [makeCard({ used: 125, limit: 1250, currency: "USD" })],
    })
    renderPage()

    const label = screen.getByText(en.banking.used)
    expect(label.parentElement).toHaveTextContent(
      `${formatCurrency(100, "en-US", "EUR")} / ${formatCurrency(1000, "en-US", "EUR")}`,
    )
    expect(
      screen.getByText(
        `${formatCurrency(125, "en-US", "USD")} / ${formatCurrency(1250, "en-US", "USD")}`,
      ),
    ).toBeInTheDocument()
  })

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
