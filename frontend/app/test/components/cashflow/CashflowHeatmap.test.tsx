import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import { CashflowHeatmap } from "@/components/cashflow/CashflowHeatmap"
import { DataDisplayMode } from "@/types"
import type { CashflowPoint } from "@/types/cashflow"
import en from "@/i18n/locales/en.json"

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/DataDisplayModeContext", () => ({
  useDataDisplayMode: () => ({ mode: DataDisplayMode.NONE }),
}))

const FROM_DATE = "2025-03-01"
const TO_DATE = "2025-03-31"

const props = {
  fromDate: FROM_DATE,
  toDate: TO_DATE,
  formatAmount: (value: number) => String(value),
  onOpenDay: vi.fn(),
}

const points: CashflowPoint[] = [
  {
    period: "2025-03-10",
    income: 500,
    expenses: 120,
    count: 2,
    expenses_by_label: [],
  },
]

const renderHeatmap = (series: CashflowPoint[] = []) =>
  render(<CashflowHeatmap series={series} {...props} />)

beforeEach(() => {
  cleanup()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe("CashflowHeatmap", () => {
  it("renders the full empty grid for the range before data arrives", () => {
    renderHeatmap()

    const days = screen.getAllByTestId("heatmap-day")
    expect(days).toHaveLength(31)
    days.forEach(day => expect(day).toHaveAttribute("data-level", "0"))
  })

  it("fills the existing cells when data arrives without rebuilding the grid", () => {
    const { container, rerender } = renderHeatmap()
    const before = screen.getAllByTestId("heatmap-day")

    rerender(<CashflowHeatmap series={points} {...props} />)

    const after = screen.getAllByTestId("heatmap-day")
    expect(after).toHaveLength(before.length)
    after.forEach((day, index) => expect(day).toBe(before[index]))
    expect(
      container.querySelector('[data-date="2025-03-10"]'),
    ).not.toHaveAttribute("data-level", "0")
  })

  it("lays out the filler weeks on the first render", () => {
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({
      width: 600,
    } as DOMRect)

    renderHeatmap()

    expect(screen.getAllByTestId("heatmap-filler-week").length).toBeGreaterThan(
      0,
    )
  })
})
