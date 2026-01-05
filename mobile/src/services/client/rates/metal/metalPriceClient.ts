import { MetalPriceProvider } from "@/application/ports"
import { CommodityExchangeRate, CommodityType } from "@/domain"

import { TtlCache } from "@/services/utils/ttlCache"

import { GoldApiPriceClient } from "./goldApiPriceClient"
import { RMintApiPriceClient } from "./rMintApiPriceClient"

export class MetalPriceClient implements MetalPriceProvider {
  static readonly PRICE_CACHE_TTL_MS = 20 * 60 * 1000
  static readonly NONE_PRICE_CACHE_TTL_MS = 30 * 1000

  private goldApiPriceClient = new GoldApiPriceClient()
  private rMintApiPriceClient = new RMintApiPriceClient()

  private symbolMappings: Record<
    CommodityType,
    {
      getPrice: (
        c: CommodityType,
        timeout?: number | null,
      ) => Promise<CommodityExchangeRate | null>
    }
  > = {
    [CommodityType.GOLD]: this.goldApiPriceClient,
    [CommodityType.SILVER]: this.goldApiPriceClient,
    [CommodityType.PLATINUM]: this.rMintApiPriceClient,
    [CommodityType.PALLADIUM]: this.goldApiPriceClient,
  }

  private priceCache = new TtlCache<CommodityType, CommodityExchangeRate>(
    10,
    MetalPriceClient.PRICE_CACHE_TTL_MS,
  )

  private noneCache = new TtlCache<CommodityType, null>(
    10,
    MetalPriceClient.NONE_PRICE_CACHE_TTL_MS,
  )

  async getPrice(
    commodity: CommodityType,
    kwargs: any,
  ): Promise<CommodityExchangeRate | null> {
    const cached = this.priceCache.get(commodity)
    if (cached) return cached

    if (this.noneCache.has(commodity)) {
      return null
    }

    const timeout = kwargs?.timeout ?? null
    const client = this.symbolMappings[commodity]
    const price = await client.getPrice(commodity, timeout)

    if (price === null) {
      console.error(`Failed to fetch price for ${commodity}, skipping.`)
      this.priceCache.delete(commodity)
      this.noneCache.set(commodity, null)
    } else {
      this.noneCache.delete(commodity)
      this.priceCache.set(commodity, price)
    }

    return price
  }
}
