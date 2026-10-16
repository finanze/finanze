import { describe, expect, it } from "vitest"
import {
  MAX_COMPOSITION_LABELS,
  buildCompositionChart,
  compositionPeriods,
} from "@/utils/cashflowComposition"
import { CashflowGranularity, type CashflowPoint } from "@/types/cashflow"

const point = (
  period: string,
  expenses_by_label: CashflowPoint["expenses_by_label"],
): CashflowPoint => ({
  period,
  income: 0,
  expenses: (expenses_by_label ?? []).reduce((sum, row) => sum + row.amount, 0),
  count: 1,
  expenses_by_label,
})

describe("compositionPeriods", () => {
  it("fills every day or month in the range", () => {
    expect(
      compositionPeriods("2025-02-27", "2025-03-02", CashflowGranularity.DAY),
    ).toEqual(["2025-02-27", "2025-02-28", "2025-03-01", "2025-03-02"])
    expect(
      compositionPeriods("2025-11-15", "2026-01-10", CashflowGranularity.MONTH),
    ).toEqual(["2025-11-01", "2025-12-01", "2026-01-01"])
  })
})

describe("buildCompositionChart", () => {
  it("stacks labels by total, groups the tail as other and fills gaps", () => {
    const labels = Array.from(
      { length: MAX_COMPOSITION_LABELS + 1 },
      (_, index) => ({ label_id: `l${index}`, amount: 100 - index }),
    )
    const chart = buildCompositionChart(
      "labels",
      [
        point("2025-01-01", [...labels, { label_id: null, amount: 5 }]),
        point("2025-03-01", [{ label_id: "l6", amount: 200 }]),
      ],
      [],
      "2025-01-01",
      "2025-03-31",
      CashflowGranularity.MONTH,
    )

    expect(chart.series.map(item => item.labelId ?? item.kind)).toEqual([
      "l6",
      "l0",
      "l1",
      "l2",
      "l3",
      "other",
      "unlabeled",
    ])
    expect(chart.series.find(item => item.kind === "other")?.total).toBe(
      96 + 95,
    )
    expect(chart.rows.map(row => row.period)).toEqual([
      "2025-01-01",
      "2025-02-01",
      "2025-03-01",
    ])
    expect(chart.rows[0]).toMatchObject({ other: 191, unlabeled: 5 })
    expect(chart.rows[1]).toMatchObject({ label0: 0, other: 0, unlabeled: 0 })
    expect(chart.rows[2]).toMatchObject({ label0: 200, label1: 0 })
  })

  it("keeps the four budget groups including negative remainders", () => {
    const chart = buildCompositionChart(
      "budget",
      [],
      [
        {
          period: "2025-03-02",
          needs: 50,
          wants: 30,
          invested: 0,
          remainder: -80,
        },
      ],
      "2025-03-01",
      "2025-03-02",
      CashflowGranularity.DAY,
    )

    expect(chart.series.map(item => [item.key, item.total])).toEqual([
      ["needs", 50],
      ["wants", 30],
      ["invested", 0],
      ["remainder", -80],
    ])
    expect(chart.rows).toEqual([
      { period: "2025-03-01", needs: 0, wants: 0, invested: 0, remainder: 0 },
      {
        period: "2025-03-02",
        needs: 50,
        wants: 30,
        invested: 0,
        remainder: -80,
      },
    ])
  })
})
