import { Entity } from "./entity"
import { DataSource } from "./fetchRecord"
import { Dezimal } from "@/domain/dezimal"

export enum ContributionFrequency {
  WEEKLY = "WEEKLY",
  BIWEEKLY = "BIWEEKLY",
  MONTHLY = "MONTHLY",
  BIMONTHLY = "BIMONTHLY",
  EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS",
  QUARTERLY = "QUARTERLY",
  SEMIANNUAL = "SEMIANNUAL",
  YEARLY = "YEARLY",
}

export enum ContributionTargetType {
  STOCK_ETF = "STOCK_ETF",
  FUND = "FUND",
  FUND_PORTFOLIO = "FUND_PORTFOLIO",
  CRYPTO = "CRYPTO",
}

export enum ContributionTargetSubtype {
  STOCK = "STOCK",
  ETF = "ETF",
  MUTUAL_FUND = "MUTUAL_FUND",
  PRIVATE_EQUITY = "PRIVATE_EQUITY",
  PENSION_FUND = "PENSION_FUND",
}

export interface PeriodicContribution {
  id: string
  alias: string | null
  target: string
  targetName: string
  targetType: ContributionTargetType
  amount: Dezimal
  currency: string
  since: string
  until: string | null
  frequency: ContributionFrequency
  active: boolean
  source: DataSource
  nextDate?: string | null
  targetSubtype?: ContributionTargetSubtype | null
  entity?: Entity | null
}

export interface AutoContributions {
  periodic: PeriodicContribution[]
}

export interface EntityContributions {
  contributions: Record<string, AutoContributions>
}

export interface ContributionQueryRequest {
  entities?: string[] | null
  excludedEntities?: string[] | null
  real?: boolean | null
}

export interface ManualPeriodicContribution {
  entityId: string
  name: string
  target: string
  targetName: string | null
  targetType: ContributionTargetType
  targetSubtype: ContributionTargetSubtype | null
  amount: Dezimal
  currency: string
  since: string
  until: string | null
  frequency: ContributionFrequency
}
