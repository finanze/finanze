import { Dezimal } from "@/domain/dezimal"

export enum CommodityType {
  GOLD = "GOLD",
  SILVER = "SILVER",
  PLATINUM = "PLATINUM",
  PALLADIUM = "PALLADIUM",
}

export enum WeightUnit {
  GRAM = "GRAM",
  TROY_OUNCE = "TROY_OUNCE",
}

export interface CommodityRegister {
  name: string
  type: CommodityType
  amount: Dezimal
  unit: WeightUnit
  marketValue?: Dezimal | null
  initialInvestment?: Dezimal | null
  averageBuyPrice?: Dezimal | null
  currency?: string | null
}

export interface UpdateCommodityPosition {
  registers: CommodityRegister[]
}
