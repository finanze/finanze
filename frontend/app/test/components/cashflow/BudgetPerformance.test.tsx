import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  waitForElementToBeRemoved,
  within,
} from "@testing-library/react"
import { BudgetPerformance } from "@/components/cashflow/BudgetPerformance"
import { DataDisplayMode, FlowType } from "@/types"
import { LabelCategory } from "@/types/labeling"
import type { BudgetSummary } from "@/types/cashflow"
import en from "@/i18n/locales/en.json"

let privateMode = false
const label = {
  id: "food",
  name: "Food",
  category: LabelCategory.EXPENSE,
  color: "#22c55e",
}

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/LabelsContext", () => ({
  useLabels: () => ({ getLabel: () => label, getLabelName: () => label.name }),
}))
vi.mock("@/context/DataDisplayModeContext", () => ({
  useDataDisplayMode: () => ({
    mode: privateMode ? DataDisplayMode.PRIVATE : DataDisplayMode.NONE,
  }),
}))

const budget = (overrides: Partial<BudgetSummary> = {}): BudgetSummary => ({
  from_month: "2025-03-01",
  to_month: "2025-03-01",
  entry_count: 3,
  missing_conversion_count: 0,
  income: { expected: 1000, actual: 650, ratio: 0.65, difference: -350 },
  expenses: { expected: 800, actual: 850, ratio: 1.0625, difference: 50 },
  needs: { expected: 600, actual: 750, ratio: 1.25, difference: 150 },
  wants: { expected: 200, actual: 100, ratio: 0.5, difference: -100 },
  saved: { expected: 200, actual: -200, ratio: -1, difference: -400 },
  invested: { expected: 500, actual: 300, ratio: 0.6, difference: -200 },
  invested_breakdown: { savings: 100, transactions: 200 },
  by_label: [
    {
      label_id: "food",
      flow_type: FlowType.EXPENSE,
      comparison: { expected: 600, actual: 750, ratio: 1.25, difference: 150 },
    },
  ],
  ...overrides,
})

beforeEach(() => {
  cleanup()
  privateMode = false
})

const renderBudget = (value = budget(), loading = false, expand = true) => {
  const onLabelClick = vi.fn()
  const onOpenBudget = vi.fn()
  const onTargetClick = vi.fn()
  render(
    <BudgetPerformance
      budget={value}
      currency="EUR"
      loading={loading}
      onLabelClick={onLabelClick}
      onOpenBudget={onOpenBudget}
      onTargetClick={onTargetClick}
    />,
  )
  const toggle = screen.queryByTestId("budget-details-toggle")
  if (expand && toggle) fireEvent.click(toggle)
  return { onLabelClick, onOpenBudget, onTargetClick }
}

describe("BudgetPerformance", () => {
  it("starts collapsed with only the heading, months, and help available", () => {
    renderBudget(budget(), false, false)
    expect(screen.getByTestId("budget-details-toggle")).toHaveAttribute(
      "aria-expanded",
      "false",
    )
    expect(screen.getByTestId("cashflow-budget")).toHaveTextContent(
      en.cashflow.budget.title,
    )
    expect(screen.getByTestId("budget-target-months")).toHaveTextContent(
      "Mar 2025",
    )
    expect(
      screen.getByRole("button", { name: en.cashflow.budget.targetInfo }),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId("budget-details-content"),
    ).not.toBeInTheDocument()
    expect(screen.queryByTestId("budget-needs")).not.toBeInTheDocument()
    expect(screen.queryByTestId("budget-wants")).not.toBeInTheDocument()
    expect(screen.queryByTestId("budget-invested")).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("budget-label-details-toggle"),
    ).not.toBeInTheDocument()
  })

  it("animates card expansion and collapse while retaining the label expansion state", async () => {
    renderBudget(budget(), false, false)
    const toggle = screen.getByTestId("budget-details-toggle")
    const region = document.getElementById(
      toggle.getAttribute("aria-controls")!,
    )!
    expect(region).toHaveAttribute("aria-hidden", "true")
    expect(region).toHaveAttribute("inert")
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    expect(region).toHaveAttribute("aria-hidden", "false")
    expect(region).not.toHaveAttribute("inert")
    expect(screen.getByTestId("budget-details-content")).toHaveClass(
      "overflow-hidden",
    )
    await waitFor(() =>
      expect(screen.getByTestId("budget-needs")).toBeVisible(),
    )
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(screen.getByTestId("budget-label-EXPENSE-food")).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    expect(region).toHaveAttribute("aria-hidden", "true")
    expect(region).toHaveAttribute("inert")
    await waitForElementToBeRemoved(() =>
      screen.queryByTestId("budget-details-content"),
    )
    expect(screen.queryByTestId("budget-needs")).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.getByTestId("budget-label-details-toggle")).toHaveAttribute(
      "aria-expanded",
      "true",
    )
    expect(screen.getByTestId("budget-label-EXPENSE-food")).toBeInTheDocument()
  })

  it("opens card help without expanding the card or nesting buttons", async () => {
    renderBudget(budget(), false, false)
    const toggle = screen.getByTestId("budget-details-toggle")
    const help = screen.getByRole("button", {
      name: en.cashflow.budget.targetInfo,
    })
    expect(help.parentElement).toBe(toggle.parentElement)
    expect(toggle.querySelector("button")).toBeNull()
    fireEvent.click(help)
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      en.cashflow.budget.targetInfo,
    )
    expect(
      screen.queryByTestId("budget-details-content"),
    ).not.toBeInTheDocument()
  })

  it("shows Needs, Wants, and Invested without generic expense or savings cards", () => {
    renderBudget()
    expect(screen.getByTestId("budget-needs")).toHaveTextContent("Needs")
    expect(screen.getByTestId("budget-wants")).toHaveTextContent("Wants")
    expect(screen.getByTestId("budget-invested")).toBeInTheDocument()
    expect(screen.queryByTestId("budget-expenses")).not.toBeInTheDocument()
    expect(screen.queryByTestId("budget-saved")).not.toBeInTheDocument()
    expect(screen.queryByTestId("budget-income")).not.toBeInTheDocument()
    expect(screen.getByTestId("cashflow-budget")).not.toHaveTextContent(
      "Income",
    )
  })

  it("shows available or exceeded amounts for spending and remaining or extra for investing", () => {
    renderBudget()
    expect(screen.getByTestId("budget-needs")).toHaveTextContent(
      /Exceeded.*150/,
    )
    expect(screen.getByTestId("budget-wants")).toHaveTextContent(
      /Available.*100/,
    )
    expect(screen.getByTestId("budget-invested")).toHaveTextContent(
      /Remaining.*200/,
    )
    expect(
      screen.queryByText(en.cashflow.budget.notSet),
    ).not.toBeInTheDocument()
  })

  it.each([0, -100, null])(
    "omits earnings percentages for non-positive or unknown earnings (%s)",
    earnings => {
      renderBudget(
        budget({
          income: {
            expected: 1000,
            actual: earnings,
            ratio: null,
            difference: null,
          },
        }),
      )
      expect(
        screen.queryByTitle(en.management.ofEarnings),
      ).not.toBeInTheDocument()
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
      expect(screen.getByTestId("cashflow-budget")).not.toHaveTextContent(
        /NaN|Infinity/,
      )
    },
  )

  it("waits for classified comparisons instead of relabeling legacy totals", () => {
    renderBudget(budget({ needs: undefined, wants: undefined }))
    expect(screen.queryByTestId("cashflow-budget")).not.toBeInTheDocument()
  })

  it("shows investing as a share of actual earnings with the remaining amount to target", () => {
    renderBudget()
    const invested = screen.getByTestId("budget-invested")
    expect(invested).toHaveTextContent("Invested")
    expect(
      within(invested).getByTitle(en.management.ofEarnings),
    ).toHaveTextContent("46.2%")
    expect(invested).toHaveTextContent(/300/)
    expect(invested).toHaveTextContent(/Remaining.*200/)
    const progress = within(invested).getByRole("progressbar")
    expect(Number(progress.getAttribute("aria-valuenow"))).toBeCloseTo(46.1538)
    expect(progress).toHaveAttribute("aria-valuetext", "46.2% of earnings")
  })

  it("shows savings movements and investment transactions separately in KPI details", async () => {
    renderBudget()
    fireEvent.click(
      screen.getByRole("button", {
        name: en.cashflow.budget.investedBreakdown,
      }),
    )
    const details = await screen.findByRole("dialog")
    expect(details).toHaveTextContent(en.cashflow.budget.savingsMovements)
    expect(details).toHaveTextContent(en.cashflow.budget.investmentTransactions)
    expect(
      within(details).getByTestId("budget-invested-savings"),
    ).toHaveTextContent("100")
    expect(
      within(details).getByTestId("budget-invested-transactions"),
    ).toHaveTextContent("200")
    expect(screen.getByTestId("budget-invested")).toHaveTextContent("300")
  })

  it("retains the known subtotal when one part of investing cannot be converted", async () => {
    renderBudget(
      budget({
        missing_conversion_count: 1,
        invested: {
          expected: 500,
          actual: null,
          ratio: null,
          difference: null,
        },
        invested_breakdown: { savings: null, transactions: 200 },
      }),
    )
    fireEvent.click(
      screen.getByRole("button", {
        name: en.cashflow.budget.investedBreakdown,
      }),
    )
    const details = await screen.findByRole("dialog")
    expect(
      within(details).getByTestId("budget-invested-savings"),
    ).toHaveTextContent("Incomplete")
    expect(
      within(details).getByTestId("budget-invested-transactions"),
    ).toHaveTextContent("200")
    expect(screen.getByTestId("budget-invested")).toHaveTextContent(
      /Actual.*Incomplete/,
    )
  })

  it("masks both invested subtotals in private mode", async () => {
    privateMode = true
    renderBudget()
    fireEvent.click(
      screen.getByRole("button", {
        name: en.cashflow.budget.investedBreakdown,
      }),
    )
    const details = await screen.findByRole("dialog")
    expect(details).not.toHaveTextContent(/100|200/)
    expect(screen.getByTestId("budget-invested")).not.toHaveTextContent(
      /300|46\.2%/,
    )
  })

  it("shows Needs as a share of actual earnings and keeps the monetary overspend and capped fill", () => {
    renderBudget()
    const needs = screen.getByTestId("budget-needs")
    expect(
      within(needs).getByTitle(en.management.ofEarnings),
    ).toHaveTextContent("115.4%")
    expect(needs).toHaveTextContent(/Exceeded.*150/)
    expect(within(needs).getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    )
    expect(screen.getByTestId("budget-target-months")).toHaveTextContent(
      "Mar 2025",
    )
  })

  it("shows Wants as a share of actual earnings with the available budget amount", () => {
    renderBudget()
    const wants = screen.getByTestId("budget-wants")
    expect(
      within(wants).getByTitle(en.management.ofEarnings),
    ).toHaveTextContent("15.4%")
    expect(wants).toHaveTextContent(/Available.*100/)
    const progress = screen.getByRole("progressbar", { name: "Wants" })
    expect(Number(progress.getAttribute("aria-valuenow"))).toBeCloseTo(15.3846)
    expect(progress).toHaveAttribute("aria-valuetext", "15.4% of earnings")
  })

  it("opens the recurring section matching each KPI target", () => {
    const { onTargetClick } = renderBudget()
    fireEvent.click(
      within(screen.getByTestId("budget-needs")).getByRole("button", {
        name: /target/,
      }),
    )
    expect(onTargetClick).toHaveBeenLastCalledWith("expenses")
    fireEvent.click(
      within(screen.getByTestId("budget-invested")).getByRole("button", {
        name: /target/,
      }),
    )
    expect(onTargetClick).toHaveBeenLastCalledWith("investments")
  })

  it("shows net investment withdrawals without a negative-width bar", () => {
    renderBudget(
      budget({
        invested: {
          expected: 500,
          actual: -100,
          ratio: -0.2,
          difference: -600,
        },
      }),
    )
    const invested = screen.getByTestId("budget-invested")
    expect(invested).toHaveTextContent("-15.4%")
    expect(invested).toHaveTextContent(/Remaining.*600/)
    const progress = within(invested).getByRole("progressbar")
    expect(progress).toHaveAttribute("aria-valuenow", "0")
    expect(progress.firstElementChild).toHaveStyle({ width: "0%" })
  })

  it("animates label expansion and collapse while retaining the drilldown", async () => {
    const { onLabelClick } = renderBudget()
    expect(
      screen.queryByTestId("budget-label-EXPENSE-food"),
    ).not.toBeInTheDocument()
    const toggle = screen.getByTestId("budget-label-details-toggle")
    const region = document.getElementById(
      toggle.getAttribute("aria-controls")!,
    )!
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByTestId("budget-label-details-content")).toHaveClass(
      "overflow-hidden",
    )
    fireEvent.click(screen.getByTestId("budget-label-EXPENSE-food"))
    expect(onLabelClick).toHaveBeenCalledWith("food", FlowType.EXPENSE)
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    expect(region).toHaveAttribute("aria-hidden", "true")
    expect(region).toHaveAttribute("inert")
    await waitForElementToBeRemoved(() =>
      screen.queryByTestId("budget-label-details-content"),
    )
    expect(
      screen.queryByTestId("budget-label-EXPENSE-food"),
    ).not.toBeInTheDocument()
  })

  it("shows a minimal label row with amounts and a thin capped bar", () => {
    renderBudget()
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    const row = screen.getByTestId("budget-label-EXPENSE-food")
    expect(row).toHaveTextContent("Food")
    expect(row).toHaveTextContent(/750.*\/.*600/)
    expect(row).toHaveTextContent("125%")
    expect(row).not.toHaveTextContent("Expenses")
    expect(row).not.toHaveTextContent("Actual:")
    expect(row).not.toHaveTextContent("Target:")
    const progress = within(row).getByRole("progressbar", { name: "Food" })
    expect(progress).toHaveClass("h-1")
    expect(progress).toHaveAttribute("aria-valuenow", "100")
    expect(progress.firstElementChild).toHaveStyle({
      width: "100%",
      backgroundColor: label.color,
    })
  })

  it("shows help in the expanded header without toggling or bubbling clicks", async () => {
    const onParentClick = vi.fn()
    render(
      <div onClick={onParentClick}>
        <BudgetPerformance
          budget={budget()}
          currency="EUR"
          onLabelClick={vi.fn()}
          onOpenBudget={vi.fn()}
          onTargetClick={vi.fn()}
        />
      </div>,
    )
    fireEvent.click(screen.getByTestId("budget-details-toggle"))
    const toggle = screen.getByTestId("budget-label-details-toggle")
    expect(
      screen.queryByRole("button", { name: en.cashflow.overlapHint }),
    ).not.toBeInTheDocument()
    fireEvent.click(toggle)
    const help = screen.getByRole("button", {
      name: en.cashflow.overlapHint,
    })
    expect(help.parentElement).toBe(toggle.parentElement)
    expect(toggle.querySelector("button")).toBeNull()
    onParentClick.mockClear()
    fireEvent.click(help)
    expect(onParentClick).not.toHaveBeenCalled()
    expect(toggle).toHaveAttribute("aria-expanded", "true")
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      en.cashflow.overlapHint,
    )
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute("aria-expanded", "false")
    expect(
      screen.queryByRole("button", { name: en.cashflow.overlapHint }),
    ).not.toBeInTheDocument()
  })

  it("omits label rows without expense targets", async () => {
    renderBudget(
      budget({
        by_label: [
          ...budget().by_label,
          {
            label_id: "salary",
            flow_type: FlowType.EARNING,
            comparison: {
              expected: 1000,
              actual: 650,
              ratio: 0.65,
              difference: -350,
            },
          },
          {
            label_id: "travel",
            flow_type: FlowType.EXPENSE,
            comparison: {
              expected: 0,
              actual: 200,
              ratio: null,
              difference: 200,
            },
          },
        ],
      }),
    )
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    await waitFor(() =>
      expect(screen.getByTestId("budget-label-EXPENSE-food")).toBeVisible(),
    )
    expect(
      screen.queryByTestId("budget-label-EARNING-salary"),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("budget-label-EXPENSE-travel"),
    ).not.toBeInTheDocument()
  })

  it("shows a compact empty state instead of an unassigned-only label row", () => {
    const { onOpenBudget, onLabelClick } = renderBudget(
      budget({
        by_label: [
          {
            label_id: null,
            flow_type: FlowType.EXPENSE,
            comparison: {
              expected: 600,
              actual: null,
              ratio: null,
              difference: null,
            },
          },
        ],
      }),
    )
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(
      screen.queryByTestId("budget-label-EXPENSE-unassigned"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("budget-label-empty")).toHaveTextContent(
      en.cashflow.budget.noLabelTargets,
    )
    expect(screen.getByTestId("budget-needs")).toHaveTextContent(
      /Exceeded.*150/,
    )
    fireEvent.click(screen.getByRole("button", { name: "Open budget" }))
    expect(onOpenBudget).toHaveBeenCalledOnce()
    expect(onLabelClick).not.toHaveBeenCalled()
  })

  it("shows the label empty state when there are no targeted expense labels", () => {
    renderBudget(budget({ by_label: [] }))
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(screen.getByTestId("budget-label-empty")).toHaveTextContent(
      en.cashflow.budget.noLabelTargets,
    )
  })

  it.each(["needs", "wants", "invested"] as const)(
    "shows %s earnings shares without a budget comparison",
    key => {
      const { onOpenBudget } = renderBudget(
        budget({
          [key]: { expected: 0, actual: 100, ratio: null, difference: 100 },
        }),
      )
      const card = screen.getByTestId(`budget-${key}`)
      expect(card).toHaveTextContent(/Actual.*100/)
      expect(card).not.toHaveTextContent(en.cashflow.budget.difference)
      expect(card).not.toHaveTextContent(en.cashflow.budget.noTarget)
      expect(card).not.toHaveTextContent(/Available|Exceeded|Remaining|Extra/)
      expect(
        within(card).getByTitle(en.management.ofEarnings),
      ).toHaveTextContent("15.4%")
      const progress = within(card).getByRole("progressbar")
      expect(Number(progress.getAttribute("aria-valuenow"))).toBeCloseTo(
        15.3846,
      )
      expect(progress).toHaveAttribute("aria-valuetext", "15.4% of earnings")
      const setup = within(card).getByRole("button", { name: /Not set/ })
      expect(
        within(card).getAllByRole("button", { name: /Not set/ }),
      ).toHaveLength(1)
      expect(setup).toHaveTextContent(en.cashflow.budget.notSet)
      expect(setup).toHaveClass("dark:text-gray-500")
      expect(setup.parentElement).toHaveClass(
        "flex",
        "min-h-10",
        "items-center",
        "justify-end",
      )
      expect(setup.parentElement?.parentElement).toHaveClass("grid-cols-2")
      const percentage = within(card).getByTitle(en.management.ofEarnings)
      expect(percentage.parentElement).toHaveClass("flex-wrap")
      expect(percentage.parentElement).not.toContainElement(setup)
      expect(setup).toHaveAttribute("title", en.cashflow.budget.openBudget)
      fireEvent.click(setup)
      expect(onOpenBudget).toHaveBeenCalledOnce()
    },
  )

  it("shows actual earnings shares in empty months without budget comparisons", () => {
    const { onOpenBudget } = renderBudget(
      budget({
        entry_count: 0,
        to_month: "2025-05-01",
        needs: { expected: 0, actual: 750, ratio: null, difference: 750 },
        wants: { expected: 0, actual: 100, ratio: null, difference: 100 },
        invested: { expected: 0, actual: 300, ratio: null, difference: 300 },
        by_label: [],
      }),
    )
    for (const key of ["needs", "wants", "invested"]) {
      const card = screen.getByTestId(`budget-${key}`)
      expect(card).toHaveTextContent(en.cashflow.budget.actual)
      expect(card).not.toHaveTextContent(en.cashflow.budget.difference)
      expect(card).not.toHaveTextContent(en.cashflow.budget.noTarget)
      expect(
        within(card).getByRole("button", { name: /Not set/ }),
      ).toBeInTheDocument()
    }
    expect(screen.getByTestId("budget-needs")).toHaveTextContent("750")
    expect(screen.getByTestId("budget-wants")).toHaveTextContent("100")
    expect(screen.getByTestId("budget-invested")).toHaveTextContent("300")
    expect(screen.getByTestId("budget-needs")).toHaveTextContent("115.4%")
    expect(screen.getByTestId("budget-wants")).toHaveTextContent("15.4%")
    expect(screen.getByTestId("budget-invested")).toHaveTextContent("46.2%")
    expect(screen.getAllByRole("progressbar")).toHaveLength(3)
    expect(screen.getByTestId("cashflow-budget")).not.toHaveTextContent(
      /NaN|Infinity/,
    )
    expect(screen.getByTestId("budget-target-months")).toHaveTextContent(
      "Mar 2025 - May 2025",
    )
    fireEvent.click(screen.getByRole("button", { name: "Open budget" }))
    expect(onOpenBudget).toHaveBeenCalledOnce()
  })

  it("offers budget setup when exchange rates are missing only for actual amounts", () => {
    const { onOpenBudget } = renderBudget(
      budget({
        entry_count: 0,
        missing_conversion_count: 1,
        needs: { expected: 0, actual: 750, ratio: null, difference: null },
        wants: { expected: 0, actual: 100, ratio: null, difference: null },
        invested: { expected: 0, actual: null, ratio: null, difference: null },
        by_label: [],
      }),
    )
    const invested = screen.getByTestId("budget-invested")
    expect(invested).toHaveTextContent(/Actual.*Incomplete/)
    expect(
      within(invested).queryByTitle(en.management.ofEarnings),
    ).not.toBeInTheDocument()
    expect(within(invested).queryByRole("progressbar")).not.toBeInTheDocument()
    fireEvent.click(within(invested).getByRole("button", { name: /Not set/ }))
    expect(onOpenBudget).toHaveBeenCalledOnce()
  })

  it("signals incomplete exchange rates and prevents drilldowns while loading", () => {
    renderBudget(
      budget({
        missing_conversion_count: 1,
        needs: { expected: 600, actual: 750, ratio: null, difference: null },
      }),
      true,
    )
    expect(screen.getByRole("status")).toHaveTextContent("no exchange rate")
    expect(screen.getByTestId("budget-needs")).toHaveTextContent(
      /Available.*Incomplete/,
    )
    expect(screen.getByTestId("budget-needs")).toHaveTextContent("115.4%")
    expect(screen.getByTestId("budget-invested")).toHaveTextContent(
      /Remaining.*200/,
    )
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(screen.getByTestId("budget-label-EXPENSE-food")).toBeDisabled()
  })

  it("retains the exchange-rate warning without showing an unknown maximum as zero", () => {
    renderBudget(
      budget({
        missing_conversion_count: 1,
        needs: { expected: 0, actual: 750, ratio: null, difference: null },
      }),
    )
    const needs = screen.getByTestId("budget-needs")
    expect(screen.getByRole("status")).toHaveTextContent("no exchange rate")
    expect(needs).toHaveTextContent(/Actual.*750/)
    expect(needs).not.toHaveTextContent("€0.00")
    expect(needs).not.toHaveTextContent(en.cashflow.budget.noTarget)
    expect(needs).not.toHaveTextContent(en.cashflow.budget.notSet)
    expect(
      within(needs).getByTitle(en.management.ofEarnings),
    ).toHaveTextContent("115.4%")
    expect(within(needs).getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    )
  })

  it("does not describe an incomplete positive label target as absent", () => {
    renderBudget(
      budget({
        missing_conversion_count: 1,
        by_label: [
          {
            label_id: "food",
            flow_type: FlowType.EXPENSE,
            comparison: {
              expected: 600,
              actual: 750,
              ratio: null,
              difference: null,
            },
          },
        ],
      }),
    )
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(screen.getByTestId("budget-label-EXPENSE-food")).toHaveTextContent(
      "Incomplete",
    )
    expect(
      screen.getByTestId("budget-label-EXPENSE-food"),
    ).not.toHaveTextContent("No target")
  })

  it("does not report unconverted investment actuals as zero", () => {
    renderBudget(
      budget({
        missing_conversion_count: 1,
        invested: {
          expected: 500,
          actual: null,
          ratio: null,
          difference: null,
        },
      }),
    )
    const invested = screen.getByTestId("budget-invested")
    expect(invested).toHaveTextContent(/Actual.*Incomplete/)
    expect(invested).not.toHaveTextContent("€0.00")
    expect(within(invested).queryByRole("progressbar")).not.toBeInTheDocument()
  })

  it.each(["needs", "wants"] as const)(
    "does not report unconverted %s spending as zero",
    key => {
      renderBudget(
        budget({
          missing_conversion_count: 1,
          [key]: { expected: 600, actual: null, ratio: null, difference: null },
        }),
      )
      const card = screen.getByTestId(`budget-${key}`)
      expect(card).toHaveTextContent(/Actual.*Incomplete/)
      expect(card).not.toHaveTextContent("€0.00")
      expect(within(card).queryByRole("progressbar")).not.toBeInTheDocument()
    },
  )

  it("keeps unbudgeted earnings shares private while leaving setup available", () => {
    privateMode = true
    renderBudget(
      budget({
        entry_count: 0,
        needs: { expected: 0, actual: 750, ratio: null, difference: 750 },
        wants: { expected: 0, actual: 100, ratio: null, difference: 100 },
        invested: { expected: 0, actual: 300, ratio: null, difference: 300 },
        by_label: [],
      }),
    )
    for (const [key, percentage] of [
      ["needs", "115.4%"],
      ["wants", "15.4%"],
      ["invested", "46.2%"],
    ]) {
      const card = screen.getByTestId(`budget-${key}`)
      expect(
        within(card).getByTitle(en.management.ofEarnings),
      ).not.toHaveTextContent(percentage)
      expect(
        within(card).getByRole("button", { name: /Not set/ }),
      ).toBeInTheDocument()
    }
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
  })

  it("masks amounts and percentages and removes progress in private mode", () => {
    privateMode = true
    renderBudget()
    fireEvent.click(screen.getByTestId("budget-label-details-toggle"))
    expect(screen.getByTestId("budget-needs")).not.toHaveTextContent(
      /750|150|115\.4/,
    )
    expect(screen.getByTestId("budget-wants")).not.toHaveTextContent(
      /100|200|15\.4%/,
    )
    expect(
      screen.getByTestId("budget-label-EXPENSE-food"),
    ).not.toHaveTextContent(/750|600|125/)
    expect(screen.getByTestId("budget-invested")).not.toHaveTextContent(
      /300|200|46\.2%/,
    )
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
  })
})
