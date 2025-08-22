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

export interface PeriodicContribution {
  id: string
  alias?: string
  target: string
  target_name: string
  target_type: ContributionTargetType
  amount: number
  currency: string
  since: string
  until?: string
  frequency: ContributionFrequency
  active: boolean
  is_real: boolean
  next_date: string
}

export interface AutoContributions {
  periodic: PeriodicContribution[]
}

export type EntityContributions = Record<string, AutoContributions>

export interface ContributionQueryRequest {
  entities?: string[]
  excluded_entities?: string[]
}
