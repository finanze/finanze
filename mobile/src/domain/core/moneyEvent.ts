import {
  ContributionTargetSubtype,
  ContributionTargetType,
} from "./autoContributions"
import { ProductType } from "./globalPosition"
import { Dezimal } from "@/domain/dezimal"

export enum MoneyEventType {
  CONTRIBUTION = "CONTRIBUTION",
  PERIODIC_FLOW = "PERIODIC_FLOW",
  PENDING_FLOW = "PENDING_FLOW",
  MATURITY = "MATURITY",
}

export enum MoneyEventFrequency {
  DAILY = "DAILY",
  WEEKLY = "WEEKLY",
  BIWEEKLY = "BIWEEKLY",
  MONTHLY = "MONTHLY",
  EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS",
  EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS",
  QUARTERLY = "QUARTERLY",
  SEMIANNUAL = "SEMIANNUAL",
  YEARLY = "YEARLY",
}

export interface PeriodicContributionDetails {
  targetType: ContributionTargetType
  targetSubtype: ContributionTargetSubtype | null
  target: string
  targetName: string | null
}

export interface MoneyEvent {
  id: string | null
  name: string
  amount: Dezimal
  currency: string
  date: string
  type: MoneyEventType
  frequency?: MoneyEventFrequency | null
  icon?: string | null
  details?: PeriodicContributionDetails | null
  productType?: ProductType | null
}

export interface MoneyEventQuery {
  fromDate: string
  toDate: string
}

export interface MoneyEvents {
  events: MoneyEvent[]
}
