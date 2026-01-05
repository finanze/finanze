import { CryptoAsset } from "@/domain"
import { Dezimal } from "@/domain/dezimal"
import { TooManyRequests } from "@/domain/exceptions"

import { httpGetWithBackoff } from "@/services/client/http/backoff"

export class CryptoCompareClient {
  static readonly BASE_URL = "https://min-api.cryptocompare.com/data"
  static readonly ICON_BASE_URL = "https://www.cryptocompare.com"
  static readonly TIMEOUT = 10
  static readonly COOLDOWN_SEC = 0.15
  static readonly MAX_SYMBOLS_LEN = 300
  static readonly MAX_RETRIES = 3
  static readonly BACKOFF_FACTOR = 0.5

  async search(symbol: string): Promise<CryptoAsset[]> {
    if (!symbol || !symbol.trim()) {
      throw new Error("MissingFieldsError: symbol")
    }

    const data = await this.fetchJson("/all/coinlist", {
      fsym: symbol.trim().toUpperCase(),
    })

    if ((data as any)?.Response === "Error") {
      console.info(
        `CryptoCompare returned no data for symbol ${symbol}: ${(data as any)?.Message}`,
      )
      return []
    }

    const coinData = (data as any)?.Data ?? {}
    return this.mapSearchResults(coinData)
  }

  async getPrices(
    symbols: string[],
    vsCurrencies: string[],
    timeoutSec: number = CryptoCompareClient.TIMEOUT,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    if (!symbols?.length) {
      throw new Error("MissingFieldsError: symbols")
    }
    if (!vsCurrencies?.length) {
      throw new Error("MissingFieldsError: vs_currencies")
    }

    const deduped = this.dedupe(symbols)
    const tsyms = vsCurrencies.map(c => c.toUpperCase()).join(",")

    const result: Record<string, Record<string, Dezimal>> = {}

    for (const chunk of this.chunkSymbols(deduped)) {
      const fsyms = chunk.join(",")
      const data = await this.fetchJson(
        "/pricemulti",
        { fsyms, tsyms },
        timeoutSec,
      )
      this.mergePrices(result, data)
    }

    return result
  }

  private mapSearchResults(coinData: Record<string, any>): CryptoAsset[] {
    const assets: CryptoAsset[] = []
    for (const raw of Object.values(coinData)) {
      const mapped = this.mapSingleCoin(raw as any)
      if (mapped) assets.push(mapped)
    }
    return assets
  }

  private mapSingleCoin(raw: Record<string, any> | null): CryptoAsset | null {
    try {
      if (!raw) return null

      const symbol = (raw.Symbol ?? raw.Name) as string | undefined
      const coinName = (raw.CoinName ?? raw.FullName ?? symbol) as
        | string
        | undefined
      if (!coinName || !symbol) return null

      const imageRel = raw.ImageUrl as string | undefined
      const iconUrls: string[] = []
      if (typeof imageRel === "string" && imageRel) {
        iconUrls.push(
          `${CryptoCompareClient.ICON_BASE_URL}/${imageRel.replace(/^\/+/, "")}`,
        )
      }

      return {
        name: coinName,
        symbol,
        iconUrls,
        externalIds: {},
        id: null,
      }
    } catch {
      return null
    }
  }

  private mergePrices(
    accumulator: Record<string, Record<string, Dezimal>>,
    data: Record<string, any>,
  ): void {
    const converted = this.convertPrices(data)
    for (const [k, v] of Object.entries(converted)) {
      accumulator[k] = v
    }
  }

  private convertPrices(
    data: Record<string, any>,
  ): Record<string, Record<string, Dezimal>> {
    const result: Record<string, Record<string, Dezimal>> = {}
    for (const [sym, prices] of Object.entries(data ?? {})) {
      if (!prices || typeof prices !== "object") continue
      const converted: Record<string, Dezimal> = {}
      for (const [cur, val] of Object.entries(prices as any)) {
        try {
          converted[String(cur).toUpperCase()] = Dezimal.fromString(String(val))
        } catch {
          // skip
        }
      }
      if (Object.keys(converted).length) {
        result[String(sym).toUpperCase()] = converted
      }
    }
    return result
  }

  private dedupe(symbols: string[]): string[] {
    const seen = new Set<string>()
    const deduped: string[] = []

    for (const s of symbols) {
      const su = s.trim().toUpperCase()
      if (!su) continue
      if (seen.has(su)) continue
      seen.add(su)
      deduped.push(su)
    }

    return deduped
  }

  private chunkSymbols(symbols: string[]): string[][] {
    const chunks: string[][] = []
    let current: string[] = []
    let currentLen = 0

    for (const sym of symbols) {
      const symLen = sym.length
      if (symLen > CryptoCompareClient.MAX_SYMBOLS_LEN) {
        throw new Error(
          `Symbol ${sym} length exceeds max allowed ${CryptoCompareClient.MAX_SYMBOLS_LEN}`,
        )
      }

      if (!current.length) {
        current = [sym]
        currentLen = symLen
        continue
      }

      const proposedLen = currentLen + 1 + symLen
      if (proposedLen <= CryptoCompareClient.MAX_SYMBOLS_LEN) {
        current.push(sym)
        currentLen = proposedLen
      } else {
        chunks.push(current)
        current = [sym]
        currentLen = symLen
      }
    }

    if (current.length) chunks.push(current)
    return chunks
  }

  private async fetchJson(
    path: string,
    params?: Record<string, string>,
    timeoutSec: number = CryptoCompareClient.TIMEOUT,
  ): Promise<any> {
    const url = `${CryptoCompareClient.BASE_URL}${path}`

    const response = await httpGetWithBackoff({
      url,
      params,
      timeoutSec,
      maxRetries: CryptoCompareClient.MAX_RETRIES,
      backoffFactor: CryptoCompareClient.BACKOFF_FACTOR,
      cooldownSec: CryptoCompareClient.COOLDOWN_SEC,
    })

    if (!response.ok) {
      const status = response.status
      const body = await response.text().catch(() => "")

      if (status === 429) throw new TooManyRequests()
      if (status === 400) {
        console.error(`Bad request to CryptoCompare ${url}: ${body}`)
        throw new Error("Invalid request to CryptoCompare API")
      }

      if (status === 401 || status === 403) {
        throw new Error("InvalidProvidedCredentials")
      }

      if (status === 500 || status === 503 || status === 408) {
        throw new Error(`CryptoCompare service error ${status}: ${body}`)
      }

      throw new Error(
        `Unexpected CryptoCompare response ${status} for ${url}: ${body}`,
      )
    }

    try {
      return await response.json()
    } catch {
      const text = await response.text().catch(() => "")
      throw new Error(
        `Failed to decode JSON from CryptoCompare for ${url}: ${text.slice(0, 200)}`,
      )
    }
  }
}
