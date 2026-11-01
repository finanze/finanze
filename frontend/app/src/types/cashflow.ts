import type { FlowFrequency, FlowType } from "."
import type { TxType } from "./transactions"

export enum CashflowGranularity {
  DAY = "DAY",
  MONTH = "MONTH",
}

export interface CashflowQuery {
  currency: string
  from_date: string
  to_date: string
  entities?: string[]
  granularity?: CashflowGranularity
}

export interface CashflowTotals {
  income: number
  expenses: number
  net: number
  count: number
  savings_rate?: number | null
}

export interface CashflowLabelAmount {
  label_id: string | null
  amount: number
}

export interface CashflowPoint {
  period: string
  income: number
  expenses: number
  count: number
  expenses_by_label?: CashflowLabelAmount[]
}

export interface CashflowLabelBreakdown {
  label_id: string | null
  income: number
  expenses: number
  count: number
}

export interface CashflowCounterparty {
  name: string
  income: number
  expenses: number
  count: number
  label_ids: string[]
}

export interface BudgetComparison {
  expected: number
  actual: number | null
  ratio: number | null
  difference: number | null
}

export interface BudgetLabelComparison {
  label_id: string | null
  flow_type: FlowType
  comparison: BudgetComparison
}

export interface BudgetInvestmentBreakdown {
  savings: number | null
  transactions: number | null
}

export interface BudgetPoint {
  period: string
  needs: number
  wants: number
  invested: number
  remainder: number
}

export interface BudgetSummary {
  from_month: string
  to_month: string
  entry_count: number
  missing_conversion_count: number
  income: BudgetComparison
  expenses: BudgetComparison
  needs?: BudgetComparison
  wants?: BudgetComparison
  saved: BudgetComparison
  invested: BudgetComparison
  invested_breakdown?: BudgetInvestmentBreakdown
  by_label: BudgetLabelComparison[]
  series?: BudgetPoint[]
}

export interface CashflowSummary {
  currency: string
  from_date: string
  to_date: string
  totals: CashflowTotals
  previous: CashflowTotals
  series: CashflowPoint[]
  by_label: CashflowLabelBreakdown[]
  top_counterparties: CashflowCounterparty[]
  excluded_count: number
  budget?: BudgetSummary | null
}

export interface RecurringMovementsQuery {
  currency: string
  lookback_months?: number
  entities?: string[]
  type?: TxType
}

export interface RecurringMovement {
  key: string
  name: string
  search: string
  type: TxType
  currency: string
  amount: number
  average_amount: number
  max_amount: number
  variable: boolean
  frequency: FlowFrequency
  occurrences: number
  first_date: string
  last_date: string
  next_date: string
  label_ids: string[]
  entity_ids: string[]
  monthly_amount?: number | null
  tracked_flow_id?: string | null
  ignored_id?: string | null
}

export interface IgnoreRecurringMovementRequest {
  key: string
  type: TxType
  currency: string
  amount: number
}

export interface IgnoredRecurringMovement extends IgnoreRecurringMovementRequest {
  id: string
}

export interface RecurringMovements {
  currency: string
  movements: RecurringMovement[]
}
