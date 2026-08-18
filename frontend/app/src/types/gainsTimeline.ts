import type { EquityType, ProductType } from "./position"

export type GainsProductType =
  | ProductType.STOCK_ETF
  | ProductType.FUND
  | ProductType.CRYPTO
  | ProductType.COMMODITY
  | ProductType.DEPOSIT
  | ProductType.FACTORING
  | ProductType.REAL_ESTATE_CF

export type FixedIncomeAccrual = "NONE" | "NET" | "GROSS"

export type GainsCalculationMode = "HYBRID" | "SNAPSHOTS"

export type GainsMethod =
  "HYBRID_VALUE" | "SNAPSHOT_BOOK_BASIS" | "NOT_APPLICABLE"

export type GainsBasis = "NET_CONTRIBUTIONS" | "BOOK_BASIS" | "NOT_APPLICABLE"

export type GainsQuality = "COMPLETE" | "ESTIMATED" | "DEGRADED" | "UNAVAILABLE"

export type GainsBasisStatus =
  "COMPLETE" | "PARTIAL_UNKNOWN" | "UNKNOWN" | "NOT_APPLICABLE"

export interface GainsAssetFilter {
  product_type: GainsProductType
  asset_keys?: string[]
  portfolio_names?: string[]
  equity_types?: EquityType[]
  wallet_ids?: string[]
}

export interface GainsMetrics {
  value: number
  cost_basis: number
  net_contributions: number
  gain: number | null
  period_return: number | null
  index: number | null
}

export interface GainsTimelinePoint extends GainsMetrics {
  date: string
  breakdown: Record<string, GainsMetrics>
}

export interface GainsTimeline {
  currency: string
  method: GainsMethod
  basis: GainsBasis
  quality: GainsQuality
  basis_status: GainsBasisStatus
  xirr: number | null
  annualized_xirr: number | null
  opening_value: number | null
  warnings: string[]
  not_applicable_reasons: string[]
  points: GainsTimelinePoint[]
}

export interface GainsTimelineQuery {
  assets: GainsAssetFilter[]
  base_currency?: string
  entities?: string[]
  from_date?: string
  to_date?: string
  accrue_fixed_income?: FixedIncomeAccrual
  calculation_mode?: GainsCalculationMode
}
