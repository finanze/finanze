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
  target_type: ContributionTargetType
  amount: number
  currency: string
  since: string
  until?: string
  frequency: ContributionFrequency
  active: boolean
  is_real: boolean
}

export interface AutoContributions {
  periodic: PeriodicContribution[]
}

export interface EntityContributions {
  contributions: Record<string, AutoContributions>
}

export interface ContributionQueryRequest {
  entities?: string[]
  excluded_entities?: string[]
}
