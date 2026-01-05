import { Dezimal } from "./dezimal"

export interface AssetDistributionItem {
  type: string
  value: Dezimal
  percentage: Dezimal
}

export interface OngoingProject {
  name: string
  type: string
  value: Dezimal
  currency: string
  roi: Dezimal | null
  maturity: string
  entity: string
  extendedMaturity?: string | null
  lateInterestRate?: Dezimal | null
}
