import { CommodityExchangeRate, CommodityType } from "@/domain"

export interface MetalPriceProvider {
  getPrice(
    commodity: CommodityType,
    kwargs: any,
  ): Promise<CommodityExchangeRate | null>
}
