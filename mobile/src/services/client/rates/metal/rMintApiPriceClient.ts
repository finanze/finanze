import { CommodityExchangeRate, CommodityType, WeightUnit } from "@/domain"
import { Dezimal } from "@/domain/dezimal"

import { httpGetJson } from "@/services/client/http/httpClient"
import { COMMODITY_SYMBOLS } from "@/domain/constants/commodity"

export class RMintApiPriceClient {
  static readonly BASE_URL =
    "https://www.royalmint.com/mvcApi/MetalPrice/GetChartData"
  static readonly TIMEOUT = 3

  static readonly SUPPORTED_COMMODITIES = new Set<CommodityType>([
    CommodityType.PLATINUM,
    CommodityType.GOLD,
    CommodityType.SILVER,
  ])

  async getPrice(
    commodity: CommodityType,
    timeout?: number | null,
  ): Promise<CommodityExchangeRate | null> {
    if (!RMintApiPriceClient.SUPPORTED_COMMODITIES.has(commodity)) {
      throw new Error(`Unsupported commodity type: ${commodity}`)
    }

    const symbol = COMMODITY_SYMBOLS[commodity].toLowerCase()
    return this.fetchPrice(symbol, timeout ?? RMintApiPriceClient.TIMEOUT)
  }

  private async fetchPrice(
    symbol: string,
    timeoutSec: number,
  ): Promise<CommodityExchangeRate | null> {
    const params = {
      period: "Live",
      currency: "eur",
      commodity: symbol,
      noCache: String(Math.floor(Date.now())),
    }

    try {
      const { response, data } = await httpGetJson<any>(
        RMintApiPriceClient.BASE_URL,
        params,
        timeoutSec,
      )

      if (!response.ok) {
        console.error("Error Response Body:" + JSON.stringify(data))
        throw new Error(`RoyalMint API request failed: ${response.status}`)
      }

      if (!(data as any)?.success) {
        throw new Error("API request was not successful")
      }

      const chartData = (data as any)?.chartData
      if (!Array.isArray(chartData) || chartData.length === 0) {
        throw new Error("No chart data available")
      }

      const latest = chartData[chartData.length - 1]
      const price = (latest as any)?.Value

      return {
        unit: WeightUnit.TROY_OUNCE,
        currency: "EUR",
        price: Dezimal.fromString(String(price)),
      }
    } catch (e: any) {
      if (e?.name === "HttpTimeoutError" || e?.name === "AbortError") {
        console.error(`Timeout fetching price for ${symbol}:`, e)
        return null
      }
      throw e
    }
  }
}
