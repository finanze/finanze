import { Entity } from "./entity"
import { ProductType } from "./globalPosition"
import { BaseInvestmentTx } from "./transactions"
import { Dezimal } from "@/domain/dezimal"

export interface BaseHistoricEntry {
  id: string
  name: string
  invested: Dezimal
  repaid: Dezimal | null
  returned: Dezimal | null
  currency: string
  lastInvestDate: string
  lastTxDate: string
  effectiveMaturity: string | null
  netReturn: Dezimal | null
  fees: Dezimal | null
  retentions: Dezimal | null
  interests: Dezimal | null
  state: string | null
  entity: Entity
  productType: ProductType
  relatedTxs: BaseInvestmentTx[]
}

export interface FactoringEntry extends BaseHistoricEntry {
  interestRate: Dezimal
  grossInterestRate: Dezimal
  maturity: string
  type: string
}

export interface RealEstateCFEntry extends BaseHistoricEntry {
  interestRate: Dezimal
  maturity: string
  extendedMaturity: string | null
  type: string
  businessType: string
}

export interface Historic {
  entries: BaseHistoricEntry[]
}

export interface HistoricQueryRequest {
  entities?: string[] | null
  excludedEntities?: string[] | null
  productTypes?: ProductType[] | null
}
