import { WeightUnit } from "./commodity"
import { Dezimal } from "@/domain/dezimal"

export type ExchangeRates = Partial<Record<string, Record<string, Dezimal>>>

export interface CommodityExchangeRate {
  unit: WeightUnit
  currency: string
  price: Dezimal
}
