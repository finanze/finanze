import { Dezimal } from "@/domain/dezimal"
import { httpGetText } from "@/services/client/http/httpClient"

export class P2SClient {
  static readonly BASE_URL = "https://api.price2sheet.com/raw"
  static readonly DEFAULT_TIMEOUT = 7

  static readonly SYMBOLS = new Set<string>([
    "BTC",
    "ETH",
    "LTC",
    "TRON",
    "TRX",
    "BNB",
    "USDT",
    "USDC",
    "SOL",
    "ADA",
    "DOGE",
    "DOT",
    "XRP",
    "XMR",
    "AVAX",
    "MATIC",
    "LINK",
    "ATOM",
    "UNI",
    "XLM",
    "FTM",
  ])

  static readonly SYMBOL_OVERRIDES: Record<string, string> = {
    TRX: "tron",
  }

  supportsSymbol(symbol: string): boolean {
    return P2SClient.SYMBOLS.has(symbol.toUpperCase())
  }

  async getPrice(
    symbol: string,
    fiatIso: string,
    timeout?: number | null,
  ): Promise<Dezimal> {
    const effectiveTimeout = timeout ?? P2SClient.DEFAULT_TIMEOUT

    const override = P2SClient.SYMBOL_OVERRIDES[symbol.toUpperCase()]
    const cryptoSymbol = (override ?? symbol).toLowerCase()
    const fiat = fiatIso.toLowerCase()

    const url = `${P2SClient.BASE_URL}/${cryptoSymbol}/${fiat}`
    const { response, data } = await httpGetText(
      url,
      undefined,
      effectiveTimeout,
    )
    if (!response.ok) {
      console.error("Error Response Body:" + data)
      throw new Error(`P2S request failed: ${response.status}`)
    }

    return Dezimal.fromString(data)
  }
}
