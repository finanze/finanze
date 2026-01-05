import { CommodityType, Dezimal, parseDezimalValue } from "@/domain"
import { WeightUnit } from "../core/commodity"

export const COMMODITY_SYMBOLS: Record<CommodityType, string> = {
  [CommodityType.GOLD]: "XAU",
  [CommodityType.SILVER]: "XAG",
  [CommodityType.PLATINUM]: "XPT",
  [CommodityType.PALLADIUM]: "XPD",
}

export const WEIGHT_CONVERSIONS: Record<
  WeightUnit,
  Record<WeightUnit, Dezimal>
> = {
  [WeightUnit.GRAM]: {
    [WeightUnit.TROY_OUNCE]: parseDezimalValue("0.032150746568628"),
    [WeightUnit.GRAM]: parseDezimalValue("1"),
  },
  [WeightUnit.TROY_OUNCE]: {
    [WeightUnit.GRAM]: parseDezimalValue("31.1034768"),
    [WeightUnit.TROY_OUNCE]: parseDezimalValue("1"),
  },
}
