import { Dezimal } from "@/domain/dezimal"

export enum SavingsPeriodicity {
  MONTHLY = "MONTHLY",
  QUARTERLY = "QUARTERLY",
  YEARLY = "YEARLY",
}

export interface SavingsScenarioRequest {
  scenarioId: string
  annualMarketPerformance: Dezimal
  periodicContribution?: Dezimal | null
  targetAmount?: Dezimal | null
}

export interface SavingsRetirementRequest {
  withdrawalAmount?: Dezimal | null
  withdrawalYears?: number | null
}

export interface SavingsCalculationRequest {
  baseAmount: Dezimal | null
  years: number | null
  periodicity: SavingsPeriodicity
  scenarios: SavingsScenarioRequest[]
  retirement?: SavingsRetirementRequest | null
}

export interface SavingsPeriodEntry {
  periodIndex: number
  contributed: Dezimal
  totalContributed: Dezimal
  revaluation: Dezimal
  totalRevaluation: Dezimal
  totalInvested: Dezimal
  balance: Dezimal
}

export interface SavingsRetirementPeriodEntry {
  periodIndex: number
  withdrawal: Dezimal
  totalWithdrawn: Dezimal
  revaluation: Dezimal
  balance: Dezimal
}

export interface SavingsScenarioResult {
  scenarioId: string
  annualMarketPerformance: Dezimal
  periodicContribution: Dezimal
  accumulationPeriods: SavingsPeriodEntry[]
  totalContributions: Dezimal
  totalRevaluation: Dezimal
  finalBalance: Dezimal
  retirement: SavingsRetirementResult | null
}

export interface SavingsRetirementResult {
  withdrawalAmount: Dezimal
  durationPeriods: number
  durationYears: Dezimal
  totalWithdrawn: Dezimal
  periods: SavingsRetirementPeriodEntry[]
}

export interface SavingsCalculationResult {
  scenarios: SavingsScenarioResult[]
}
