import {
  FlowFrequency,
  FlowType,
  type ExchangeRates,
  type PeriodicFlow,
} from "@/types"
import { convertCurrency } from "@/utils/financialDataUtils"

const SAVINGS_TARGET_MIN_PERCENT = 1
const SAVINGS_TARGET_MAX_PERCENT = 99.5

export const MONTHLY_FLOW_MULTIPLIERS: Record<FlowFrequency, number> = {
  [FlowFrequency.DAILY]: 30,
  [FlowFrequency.WEEKLY]: 4.33,
  [FlowFrequency.BIWEEKLY]: 26 / 12,
  [FlowFrequency.SEMIMONTHLY]: 2,
  [FlowFrequency.MONTHLY]: 1,
  [FlowFrequency.EVERY_TWO_MONTHS]: 1 / 2,
  [FlowFrequency.QUARTERLY]: 1 / 3,
  [FlowFrequency.EVERY_FOUR_MONTHS]: 1 / 4,
  [FlowFrequency.SEMIANNUALLY]: 1 / 6,
  [FlowFrequency.YEARLY]: 1 / 12,
}

export interface MonthlyFlowTotals {
  monthlyEarnings: number
  monthlyExpenses: number
}

export const getMonthlyFlowTotals = (
  periodicFlows: PeriodicFlow[],
  excludedLabelIds: ReadonlySet<string>,
  currency: string,
  exchangeRates: ExchangeRates | null,
): MonthlyFlowTotals => {
  const baseFlows = periodicFlows.filter(
    flow => !flow.label_id || !excludedLabelIds.has(flow.label_id),
  )
  const sumEnabledFlows = (flowType: FlowType) =>
    baseFlows
      .filter(flow => flow.flow_type === flowType && flow.enabled)
      .reduce(
        (total, flow) =>
          total +
          convertCurrency(
            flow.amount * MONTHLY_FLOW_MULTIPLIERS[flow.frequency],
            flow.currency,
            currency,
            exchangeRates,
          ),
        0,
      )

  return {
    monthlyEarnings: sumEnabledFlows(FlowType.EARNING),
    monthlyExpenses: sumEnabledFlows(FlowType.EXPENSE),
  }
}

export const getSavingsTargetRate = ({
  monthlyEarnings,
  monthlyExpenses,
}: MonthlyFlowTotals): number | null => {
  if (monthlyEarnings <= 0) {
    return null
  }
  const percent = ((monthlyEarnings - monthlyExpenses) / monthlyEarnings) * 100
  if (
    percent < SAVINGS_TARGET_MIN_PERCENT ||
    percent > SAVINGS_TARGET_MAX_PERCENT
  ) {
    return null
  }
  return percent / 100
}
