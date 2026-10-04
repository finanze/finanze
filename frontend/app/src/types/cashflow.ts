import type { FlowFrequency } from "."
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

export interface CashflowPoint {
  period: string
  income: number
  expenses: number
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
