import type { Entity } from "."
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

export interface HistoricQueryRequest {
  entities?: string[]
  product_types?: ProductType[]
}
