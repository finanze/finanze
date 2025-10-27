import { DataSource } from "."

export enum ContributionFrequency {
  WEEKLY = "WEEKLY",
  BIWEEKLY = "BIWEEKLY",
  MONTHLY = "MONTHLY",
  BIMONTHLY = "BIMONTHLY",
  QUARTERLY = "QUARTERLY",
  SEMIANNUAL = "SEMIANNUAL",
  YEARLY = "YEARLY",
}

export enum ContributionTargetType {
  STOCK_ETF = "STOCK_ETF",
  FUND = "FUND",
  FUND_PORTFOLIO = "FUND_PORTFOLIO",
}

export enum ContributionTargetSubtype {
  STOCK = "STOCK",
  ETF = "ETF",
  MUTUAL_FUND = "MUTUAL_FUND",
  PENSION_FUND = "PENSION_FUND",
  PRIVATE_EQUITY = "PRIVATE_EQUITY",
}

export interface PeriodicContribution {
  id: string
  alias?: string
  target: string
  target_name: string
  target_type: ContributionTargetType
  target_subtype?: ContributionTargetSubtype
  amount: number
  currency: string
  since: string
  until?: string
  frequency: ContributionFrequency
  active: boolean
  source: DataSource
  next_date: string
}

export interface ManualPeriodicContribution {
  entity_id: string
  name: string
  target: string
  target_name?: string | null
  target_type: ContributionTargetType
  target_subtype?: ContributionTargetSubtype | null
  amount: number
  currency: string
  since: string
  until?: string | null
  frequency: ContributionFrequency
}

export interface ManualContributionsRequest {
  entries: ManualPeriodicContribution[]
}

export interface AutoContributions {
  periodic: PeriodicContribution[]
}

export type EntityContributions = Record<string, AutoContributions>

export interface ContributionQueryRequest {
  entities?: string[]
  excluded_entities?: string[]
}
