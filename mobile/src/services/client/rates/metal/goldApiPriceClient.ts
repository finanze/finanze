import { CommodityExchangeRate, CommodityType, WeightUnit } from "@/domain"
import { Dezimal } from "@/domain/dezimal"
import { COMMODITY_SYMBOLS } from "@/domain/constants/commodity"
import { httpGetJson } from "@/services/client/http/httpClient"

export class GoldApiPriceClient {
  static readonly BASE_URL = "https://api.gold-api.com/price"
  static readonly TIMEOUT = 3

  static readonly SUPPORTED_COMMODITIES = new Set<CommodityType>([
    CommodityType.GOLD,
    CommodityType.SILVER,
    CommodityType.PALLADIUM,
  ])

  async getPrice(
    commodity: CommodityType,
    timeout?: number | null,
  ): Promise<CommodityExchangeRate | null> {
    if (!GoldApiPriceClient.SUPPORTED_COMMODITIES.has(commodity)) {
      throw new Error(`Unsupported commodity type: ${commodity}`)
    }

    const symbol = COMMODITY_SYMBOLS[commodity].toUpperCase()
    return this.fetchPrice(symbol, timeout ?? GoldApiPriceClient.TIMEOUT)
  }

  private async fetchPrice(
    symbol: string,
    timeoutSec: number,
  ): Promise<CommodityExchangeRate | null> {
    const url = `${GoldApiPriceClient.BASE_URL}/${symbol}`

    try {
      // Use JSON helper to stay aligned with backend "requests.get().json()".
      const { response, data } = await httpGetJson<any>(
        url,
        undefined,
        timeoutSec,
      )
      if (!response.ok) {
        console.error("Error Response Body:" + JSON.stringify(data))
        throw new Error(`Gold API request failed: ${response.status}`)
      }

      return {
        unit: WeightUnit.TROY_OUNCE,
        currency: "USD",
        price: Dezimal.fromString(String((data as any).price)),
      }
    } catch (e: any) {
      // Backend returns None on Timeout only; our timeout throws AbortError.
      if (e?.name === "HttpTimeoutError" || e?.name === "AbortError") {
        console.error(`Timeout fetching price for ${symbol}:`, e)
        return null
      }
      throw e
    }
  }
}
