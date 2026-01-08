import { Dezimal } from "@/domain/dezimal"

export enum FlowFrequency {
  DAILY = "DAILY",
  WEEKLY = "WEEKLY",
  MONTHLY = "MONTHLY",
  EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS",
  QUARTERLY = "QUARTERLY",
  EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS",
  SEMIANNUALLY = "SEMIANNUALLY",
  YEARLY = "YEARLY",
}

export enum FlowType {
  EARNING = "EARNING",
  EXPENSE = "EXPENSE",
}

export interface PeriodicFlow {
  id: string | null
  name: string
  amount: Dezimal
  currency: string
  flowType: FlowType
  frequency: FlowFrequency
  category: string | null
  enabled: boolean
  since: string
  until: string | null
  icon: string | null
  linked?: boolean | null
  nextDate?: string | null
  maxAmount?: Dezimal | null
}

export interface PendingFlow {
  id: string | null
  name: string
  amount: Dezimal
  currency: string
  flowType: FlowType
  category: string | null
  enabled: boolean
  date: string | null
  icon: string | null
}
