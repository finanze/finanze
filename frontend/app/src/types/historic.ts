import type { Entity } from "."
import { DataSource } from "."
import { ProductType } from "./position"
import type { BaseInvestmentTx } from "./transactions"

export interface BaseHistoricEntry {
  id: string
  name: string
  invested: number
  repaid?: number | null
  returned?: number | null
  currency: string
  last_invest_date: string
  last_tx_date: string
  effective_maturity?: string | null
  net_return?: number | null
  fees?: number | null
  retentions?: number | null
  interests?: number | null
  state?: string | null
  entity: Entity
  product_type: ProductType
  related_txs: BaseInvestmentTx[]
  entity_account_id?: string | null
  source?: DataSource
  manual_key?: string | null
}

export interface FactoringEntry extends BaseHistoricEntry {
  interest_rate: number
  gross_interest_rate: number
  maturity: string
  type: string
}

export interface RealEstateCFEntry extends BaseHistoricEntry {
  interest_rate: number
  maturity: string
  extended_maturity?: string | null
  type: string
  business_type: string
}

export interface Historic {
  entries: BaseHistoricEntry[]
}

export type HistoricSortBy = "maturity" | "last_invest_date" | "invested"
export type SortOrder = "asc" | "desc"

export interface HistoricQueryRequest {
  entities?: string[]
  product_types?: ProductType[]
  page?: number
  limit?: number
  sort_by?: HistoricSortBy
  sort_order?: SortOrder
}

export interface SettleManualInvestmentRequest {
  entity_id: string
  entry_id: string
  product_type: ProductType
  maturity?: string | null
  interests?: number | null
  fees?: number
  retentions?: number
  pending_capital?: number
  create_investment_tx?: boolean
}

export interface PartialAmortizeManualInvestmentRequest {
  entity_id: string
  entry_id: string
  product_type: ProductType
  amount: number
  date?: string | null
  interests?: number
  fees?: number
  retentions?: number
  create_investment_tx?: boolean
}

export enum HistoricTxDeletion {
  NONE = "NONE",
  SETTLEMENT = "SETTLEMENT",
  ALL = "ALL",
}
