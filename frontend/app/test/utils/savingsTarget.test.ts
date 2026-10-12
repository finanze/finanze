import { describe, expect, it } from "vitest"
import { FlowFrequency, FlowType, type PeriodicFlow } from "@/types"
import {
  getMonthlyFlowTotals,
  getSavingsTargetRate,
} from "@/utils/savingsTarget"

const flow = (overrides: Partial<PeriodicFlow>): PeriodicFlow => ({
  name: "flow",
  amount: 0,
  flow_type: FlowType.EARNING,
  frequency: FlowFrequency.MONTHLY,
  enabled: true,
  since: "2025-01-01",
  currency: "EUR",
  ...overrides,
})

describe("getMonthlyFlowTotals", () => {
  it("normalizes frequencies and skips disabled and excluded flows", () => {
    const totals = getMonthlyFlowTotals(
      [
        flow({ amount: 1000 }),
        flow({
          amount: 100,
          flow_type: FlowType.EXPENSE,
          frequency: FlowFrequency.WEEKLY,
        }),
        flow({ amount: 300, flow_type: FlowType.EXPENSE, enabled: false }),
        flow({
          amount: 500,
          flow_type: FlowType.EXPENSE,
          label_id: "excluded",
        }),
        flow({ amount: 200, flow_type: FlowType.EXPENSE, label_id: "kept" }),
      ],
      new Set(["excluded"]),
      "EUR",
      null,
    )

    expect(totals.monthlyEarnings).toBe(1000)
    expect(totals.monthlyExpenses).toBeCloseTo(100 * 4.33 + 200)
  })
})

describe("getSavingsTargetRate", () => {
  it("returns null without earnings", () => {
    expect(
      getSavingsTargetRate({ monthlyEarnings: 0, monthlyExpenses: 0 }),
    ).toBeNull()
  })

  it("returns null when the savings percent is below 1% or above 99.5%", () => {
    expect(
      getSavingsTargetRate({ monthlyEarnings: 1000, monthlyExpenses: 995 }),
    ).toBeNull()
    expect(
      getSavingsTargetRate({ monthlyEarnings: 1000, monthlyExpenses: 0 }),
    ).toBeNull()
    expect(
      getSavingsTargetRate({ monthlyEarnings: 1000, monthlyExpenses: 4 }),
    ).toBeNull()
  })

  it("returns the savings ratio inside the allowed range", () => {
    expect(
      getSavingsTargetRate({ monthlyEarnings: 2000, monthlyExpenses: 1500 }),
    ).toBeCloseTo(0.25)
    expect(
      getSavingsTargetRate({ monthlyEarnings: 1000, monthlyExpenses: 10 }),
    ).toBeCloseTo(0.99)
  })
})
