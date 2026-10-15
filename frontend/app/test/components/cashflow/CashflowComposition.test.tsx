import { beforeEach, describe, expect, it, vi } from "vitest"
import type { ReactNode } from "react"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { CashflowComposition } from "@/components/cashflow/CashflowComposition"
import { DataDisplayMode } from "@/types"
import { LabelCategory } from "@/types/labeling"
import {
  CashflowGranularity,
  type BudgetPoint,
  type CashflowPoint,
} from "@/types/cashflow"
import en from "@/i18n/locales/en.json"

let privateMode = false
const labels = {
  food: {
    id: "food",
    name: "Food",
    category: LabelCategory.EXPENSE,
    color: "#22c55e",
  },
}

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/LabelsContext", () => ({
  useLabels: () => ({
    getLabel: (id: keyof typeof labels) => labels[id],
    getLabelName: (label: { name: string }) => label.name,
  }),
}))
vi.mock("@/context/DataDisplayModeContext", () => ({
  useDataDisplayMode: () => ({
    mode: privateMode ? DataDisplayMode.PRIVATE : DataDisplayMode.NONE,
  }),
}))
vi.mock("recharts", () => ({
  AreaChart: ({
    children,
    data,
  }: {
    children?: ReactNode
    data?: unknown[]
  }) => (
    <div data-testid="area-chart" data-rows={JSON.stringify(data)}>
      {children}
    </div>
  ),
  Area: ({ dataKey, fill }: { dataKey: string; fill: string }) => (
    <div data-testid={`area-${dataKey}`} data-fill={fill} />
  ),
  CartesianGrid: () => null,
  ReferenceLine: () => <div data-testid="zero-line" />,
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: ({
    content,
  }: {
    content?: (props: {
      active: boolean
      payload: Array<{ payload: Record<string, number | string> }>
      label: string
    }) => ReactNode
  }) =>
    content?.({
      active: true,
      payload: [
        {
          payload: {
            period: "2025-03-01",
            label0: 120,
            unlabeled: 30,
            needs: 150,
            wants: 0,
            invested: 900,
            remainder: -50,
          },
        },
      ],
      label: "2025-03-01",
    }) ?? null,
  XAxis: () => null,
  YAxis: ({ tick }: { tick: unknown }) => (
    <div data-testid="y-axis" data-tick={JSON.stringify(tick)} />
  ),
}))

const series: CashflowPoint[] = [
  {
    period: "2025-03-01",
    income: 1000,
    expenses: 150,
    count: 3,
    expenses_by_label: [
      { label_id: "food", amount: 120 },
      { label_id: null, amount: 30 },
    ],
  },
]

const budgetSeries: BudgetPoint[] = [
  { period: "2025-03-01", needs: 150, wants: 0, invested: 900, remainder: -50 },
]

const renderComposition = (
  overrides: Partial<Parameters<typeof CashflowComposition>[0]> = {},
) =>
  render(
    <CashflowComposition
      series={series}
      budgetSeries={budgetSeries}
      granularity={CashflowGranularity.MONTH}
      fromDate="2025-03-01"
      toDate="2025-04-30"
      currency="EUR"
      {...overrides}
    />,
  )

beforeEach(() => {
  cleanup()
  localStorage.clear()
  privateMode = false
})

describe("CashflowComposition", () => {
  it("stacks spending by label with colors and fills empty periods", () => {
    renderComposition()

    expect(screen.getByTestId("composition-mode-labels")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(screen.getByTestId("area-label0")).toHaveAttribute(
      "data-fill",
      "#22c55e",
    )
    expect(screen.getByTestId("area-unlabeled")).toBeInTheDocument()
    expect(screen.getByTestId("composition-legend-label0")).toHaveTextContent(
      "Food",
    )
    expect(
      screen.getByTestId("composition-legend-unlabeled"),
    ).toHaveTextContent(en.labels.unlabeled)
    expect(
      JSON.parse(
        screen.getByTestId("area-chart").getAttribute("data-rows") ?? "[]",
      ),
    ).toEqual([
      { period: "2025-03-01", label0: 120, unlabeled: 30 },
      { period: "2025-04-01", label0: 0, unlabeled: 0 },
    ])
    expect(screen.queryByTestId("zero-line")).not.toBeInTheDocument()
  })

  it("switches to budget groups, grouping savings and persisting the mode", () => {
    renderComposition()

    fireEvent.click(screen.getByTestId("composition-mode-budget"))

    expect(localStorage.getItem("cashflowCompositionMode")).toBe("budget")
    expect(screen.getByText(en.cashflow.composition.spending)).toBeVisible()
    expect(screen.getByText(en.cashflow.composition.savings)).toBeVisible()
    for (const key of ["needs", "wants", "invested", "remainder"])
      expect(screen.getByTestId(`area-${key}`)).toBeInTheDocument()
    expect(
      screen.getByTestId("composition-legend-remainder"),
    ).toHaveTextContent(en.cashflow.composition.remainder)
    expect(screen.getByTestId("zero-line")).toBeInTheDocument()
  })

  it("shows each budget bucket as a percentage of period income", () => {
    renderComposition()

    fireEvent.click(screen.getByTestId("composition-mode-budget"))

    expect(screen.getByText("(15%)")).toBeInTheDocument()
    expect(screen.getByText("(0%)")).toBeInTheDocument()
    expect(screen.getByText("(90%)")).toBeInTheDocument()
    expect(screen.getByText("(-5%)")).toBeInTheDocument()
  })

  it("falls back to labels without budget groups when filtered by entity", () => {
    localStorage.setItem("cashflowCompositionMode", "budget")
    renderComposition({ budgetSeries: undefined })

    expect(screen.queryByTestId("composition-mode-budget")).toBeNull()
    expect(screen.getByTestId("area-label0")).toBeInTheDocument()
    expect(screen.queryByTestId("area-needs")).toBeNull()
  })

  it("restores the stored budget mode when available", () => {
    localStorage.setItem("cashflowCompositionMode", "budget")
    renderComposition()

    expect(screen.getByTestId("composition-mode-budget")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("shows an empty state when there is no spending", () => {
    renderComposition({ series: [], budgetSeries: undefined })

    expect(screen.getByText(en.cashflow.empty.noExpenses)).toBeVisible()
    expect(screen.queryByTestId("area-chart")).toBeNull()
  })

  it("hides axis amounts in private mode", () => {
    privateMode = true
    renderComposition()

    expect(screen.getByTestId("y-axis")).toHaveAttribute("data-tick", "false")
  })
})
