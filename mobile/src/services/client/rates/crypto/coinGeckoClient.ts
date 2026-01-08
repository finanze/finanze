import AsyncStorage from "@react-native-async-storage/async-storage"
import { Buffer } from "buffer"
import { gzip, ungzip } from "pako"

import {
  AvailableCryptoAsset,
  CryptoAsset,
  CryptoAssetDetails,
  CryptoAssetPlatform,
  CryptoCurrencyType,
  CryptoPlatform,
  Entity,
  ExternalIntegrationId,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"
import { TooManyRequests } from "@/domain/exceptions"
import { BITCOIN, BSC, ETHEREUM, LITECOIN, TRON } from "@/domain/nativeEntities"

import { httpGetWithBackoff } from "@/services/client/http/backoff"
import { TtlCache } from "@/services/utils/ttlCache"

type CachedSection<T> = {
  last_updated: string
  result: T
}

type PersistedCache = {
  coins?: CachedSection<any[]>
  platforms?: CachedSection<any[]>
}

type CompressedSection = {
  last_updated: string
  compression: "gzip-base64"
  result: string
}

const COINS_CACHE_KEY = "finanze.coingecko.coins.v1"
const PLATFORMS_CACHE_KEY = "finanze.coingecko.platforms.v1"
const MAX_COINS_CACHE_BASE64_LEN = 900_000

export class CoinGeckoClient {
  static readonly BASE_URL = "https://api.coingecko.com/api/v3"
  static readonly TIMEOUT = 10
  static readonly CHUNK_SIZE = 50
  static readonly COOLDOWN_SEC = 1
  static readonly MAX_RETRIES = 4
  static readonly BACKOFF_EXPONENT_BASE = 2.8
  static readonly BACKOFF_FACTOR = 1.6
  static readonly CACHE_MAX_AGE_DAYS = 4

  static readonly ENTITY_CHAIN_MAP: Record<string, Entity> = {
    bitcoin: BITCOIN,
    ethereum: ETHEREUM,
    "binance-smart-chain": BSC,
    tron: TRON,
    litecoin: LITECOIN,
  }

  private coinListCache: any[] | null = null
  private coinListLastUpdated: Date | null = null
  private platformsCache: any[] | null = null
  private platformsLastUpdated: Date | null = null

  private memCoinList = new TtlCache<string, any[]>(1, 86400 * 1000)
  private memPlatforms = new TtlCache<string, Record<string, CryptoPlatform>>(
    1,
    86400 * 1000,
  )
  private memCoinAddressIndex = new TtlCache<string, Record<string, any>>(
    1,
    86400 * 1000,
  )

  constructor() {
    void this.loadPersistedCache()
  }

  async search(query: string): Promise<CryptoAsset[]> {
    if (!query || !query.trim()) {
      throw new Error("MissingFieldsError: query")
    }

    const data = await this.fetch("/search", { query: query.trim() })
    const coins = (data as any)?.coins ?? []
    return this.mapSearchResults(Array.isArray(coins) ? coins : [])
  }

  private mapSearchResults(coins: any[]): CryptoAsset[] {
    const results: CryptoAsset[] = []
    for (const coin of coins) {
      if (!coin || typeof coin !== "object") continue
      try {
        const coinId = (coin as any).id
        if (!coinId) continue

        const name = (coin as any).name ?? ""
        let symbol = (coin as any).symbol as string | undefined
        if (symbol) symbol = symbol.toUpperCase()

        const iconUrls: string[] = []
        const thumb = (coin as any).thumb
        const large = (coin as any).large
        if (large) iconUrls.push(String(large))
        if (!large && thumb) iconUrls.push(String(thumb))

        const externalIds: Record<string, string> = {
          [ExternalIntegrationId.COINGECKO]: String(coinId),
        }

        results.push({
          name,
          symbol: symbol ?? null,
          iconUrls: iconUrls.length ? iconUrls : null,
          externalIds,
          id: null,
        })
      } catch {
        continue
      }
    }
    return results
  }

  async assetLookup(
    symbol?: string | null,
    name?: string | null,
  ): Promise<AvailableCryptoAsset[]> {
    if (!symbol && !name) return []

    const queryLower = String(symbol ?? name ?? "")
      .trim()
      .toLowerCase()
    if (!queryLower) return []

    const coinList = await this.getCoinList()
    const platformsIndex = await this.getAssetPlatforms()

    const matches: AvailableCryptoAsset[] = []

    for (const coin of coinList) {
      if (!coin || typeof coin !== "object") continue

      if (symbol) {
        const coinSymbol = String((coin as any).symbol ?? "").toLowerCase()
        if (coinSymbol.startsWith(queryLower)) {
          matches.push(
            this.mapCoinToAvailableAsset(coin as any, platformsIndex),
          )
        }
      } else if (name) {
        const coinName = String((coin as any).name ?? "").toLowerCase()
        if (coinName.startsWith(queryLower)) {
          matches.push(
            this.mapCoinToAvailableAsset(coin as any, platformsIndex),
          )
        }
      }
    }

    return matches
  }

  private mapCoinToAvailableAsset(
    coin: any,
    platformsIndex: Record<string, CryptoPlatform>,
  ): AvailableCryptoAsset {
    const coinPlatforms = coin.platforms ?? {}
    const enrichedPlatforms: CryptoAssetPlatform[] = []

    if (coinPlatforms && typeof coinPlatforms === "object") {
      for (const [platformId, contractAddress] of Object.entries(
        coinPlatforms,
      )) {
        if (!platformId || !contractAddress) continue

        const platformInfo = platformsIndex[platformId]
        const platformName = platformInfo?.name ?? platformId
        const iconUrl = platformInfo?.iconUrl ?? null

        enrichedPlatforms.push({
          providerId: platformId,
          name: platformName,
          contractAddress: String(contractAddress),
          iconUrl,
          relatedEntityId: null,
        })
      }
    }

    return {
      name: String(coin.name ?? ""),
      symbol: String(coin.symbol ?? "").toUpperCase(),
      platforms: enrichedPlatforms,
      provider: ExternalIntegrationId.COINGECKO,
      providerId: String(coin.id ?? ""),
    }
  }

  async getAssetPlatforms(): Promise<Record<string, CryptoPlatform>> {
    const cached = this.memPlatforms.get("platforms")
    if (cached) return cached

    if (this.isPlatformsCacheValid() && this.platformsCache) {
      const index = this.buildPlatformsIndex(this.platformsCache)
      this.memPlatforms.set("platforms", index)
      return index
    }

    let data: any
    try {
      data = await this.fetch(
        "/asset_platforms",
        undefined,
        CoinGeckoClient.TIMEOUT,
      )
    } catch (e) {
      console.error("Failed to fetch asset platforms from CoinGecko:", e)
      if (this.platformsCache) {
        console.warn("Returning stale cached platforms due to API error")
        const index = this.buildPlatformsIndex(this.platformsCache)
        this.memPlatforms.set("platforms", index)
        return index
      }
      return {}
    }

    if (!Array.isArray(data)) {
      console.warn(
        `Unexpected response for /asset_platforms, expected list. Got type ${typeof data}`,
      )
      if (this.platformsCache) {
        console.warn("Returning stale cached platforms due to API error")
        const index = this.buildPlatformsIndex(this.platformsCache)
        this.memPlatforms.set("platforms", index)
        return index
      }
      return {}
    }

    await this.savePlatformsCache(data)
    const index = this.buildPlatformsIndex(data)
    this.memPlatforms.set("platforms", index)
    return index
  }

  private buildPlatformsIndex(
    platforms: any[],
  ): Record<string, CryptoPlatform> {
    const index: Record<string, CryptoPlatform> = {}

    for (const platform of platforms) {
      if (!platform || typeof platform !== "object") continue
      const platformId = (platform as any).id
      if (!platformId) continue

      const imageInfo = (platform as any).image ?? {}
      const iconUrl =
        (imageInfo as any).large ?? (imageInfo as any).small ?? null

      index[String(platformId)] = {
        providerId: String(platformId),
        name: String((platform as any).name ?? platformId),
        iconUrl: iconUrl ? String(iconUrl) : null,
      }
    }

    return index
  }

  async getCoinOverviewByAddresses(
    addresses: string[],
  ): Promise<Record<string, any>> {
    if (!addresses?.length) return {}

    const index = await this.getCoinAddressIndex()
    const result: Record<string, any> = {}

    const seen = new Set<string>()
    for (const raw of addresses) {
      if (typeof raw !== "string") continue
      const addr = raw.trim().toLowerCase()
      if (!addr || seen.has(addr)) continue
      seen.add(addr)

      const coin = index[addr]
      if (coin) {
        result[addr] = coin
      }
    }

    return result
  }

  async getPricesByAddresses(
    addresses: string[],
    vsCurrencies: string[],
    timeoutSec: number = CoinGeckoClient.TIMEOUT,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    if (!addresses?.length) return {}

    const normalized: string[] = []
    const seen = new Set<string>()

    for (const raw of addresses) {
      if (typeof raw !== "string") continue
      const addr = raw.trim().toLowerCase()
      if (!addr || seen.has(addr)) continue
      seen.add(addr)
      normalized.push(addr)
    }

    if (!normalized.length) return {}

    const overview = await this.getCoinOverviewByAddresses(normalized)
    const idToAddresses: Record<string, string[]> = {}

    for (const addr of normalized) {
      const coin = overview[addr]
      const coinId = coin ? (coin as any).id : null
      if (!coinId) continue
      const key = String(coinId)
      idToAddresses[key] ??= []
      idToAddresses[key].push(addr)
    }

    const coinIds = Object.keys(idToAddresses)
    if (!coinIds.length) return {}

    const pricesById = await this.getPrices({
      symbols: null,
      coinIds,
      vsCurrencies,
      timeoutSec,
    })

    const result: Record<string, Record<string, Dezimal>> = {}
    for (const [coinId, addrList] of Object.entries(idToAddresses)) {
      const prices = pricesById[coinId]
      if (!prices) continue
      for (const addr of addrList) {
        result[addr] = { ...prices }
      }
    }

    return result
  }

  async getPrices(args: {
    symbols: string[] | null
    vsCurrencies: string[]
    timeoutSec?: number
    coinIds?: string[] | null
  }): Promise<Record<string, Record<string, Dezimal>>> {
    const {
      symbols,
      vsCurrencies,
      timeoutSec = CoinGeckoClient.TIMEOUT,
      coinIds,
    } = args

    if (coinIds && coinIds.length) {
      const { deduped, vsParam } = this.validateIdsAndPrepare(
        coinIds,
        vsCurrencies,
      )
      return this.aggregatePricesByIds(deduped, vsParam, timeoutSec)
    }

    if (!symbols || !symbols.length) {
      throw new Error("MissingFieldsError: symbols")
    }

    const { deduped, vsParam } = this.validateAndPrepare(symbols, vsCurrencies)
    return this.aggregatePrices(deduped, vsParam, timeoutSec)
  }

  private validateAndPrepare(
    symbols: string[],
    vsCurrencies: string[],
  ): { deduped: string[]; vsParam: string } {
    if (!symbols?.length) throw new Error("MissingFieldsError: symbols")
    if (!vsCurrencies?.length)
      throw new Error("MissingFieldsError: vs_currencies")

    const deduped = this.dedupeItems(symbols, true)
    const vsParam = vsCurrencies.map(c => c.toLowerCase()).join(",")
    return { deduped, vsParam }
  }

  private validateIdsAndPrepare(
    coinIds: string[],
    vsCurrencies: string[],
  ): { deduped: string[]; vsParam: string } {
    if (!coinIds?.length) throw new Error("MissingFieldsError: ids")
    if (!vsCurrencies?.length)
      throw new Error("MissingFieldsError: vs_currencies")

    const deduped = this.dedupeItems(coinIds, true)
    const vsParam = vsCurrencies.map(c => c.toLowerCase()).join(",")
    return { deduped, vsParam }
  }

  private async aggregatePrices(
    deduped: string[],
    vsParam: string,
    timeoutSec: number,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    const result: Record<string, Record<string, Dezimal>> = {}

    for (const chunk of this.chunked(deduped, CoinGeckoClient.CHUNK_SIZE)) {
      const chunkResult = await this.fetchSimplePrice(
        chunk.map(s => s.toLowerCase()),
        vsParam,
        timeoutSec,
        "symbols",
      )
      this.mergePricesMap(chunkResult, result, k => k.toUpperCase())
    }

    return result
  }

  private async aggregatePricesByIds(
    deduped: string[],
    vsParam: string,
    timeoutSec: number,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    const result: Record<string, Record<string, Dezimal>> = {}

    for (const chunk of this.chunked(deduped, CoinGeckoClient.CHUNK_SIZE)) {
      const chunkResult = await this.fetchSimplePrice(
        chunk.map(c => c.toLowerCase()),
        vsParam,
        timeoutSec,
        "ids",
      )
      this.mergePricesMap(chunkResult, result, k => k)
    }

    return result
  }

  private mergePricesMap(
    rawMap: Record<string, any>,
    accumulator: Record<string, Record<string, Dezimal>>,
    keyTransform: (k: string) => string,
  ): void {
    for (const [key, prices] of Object.entries(rawMap ?? {})) {
      const converted = this.convertPrices(prices)
      if (Object.keys(converted).length) {
        accumulator[keyTransform(key)] = converted
      }
    }
  }

  private convertPrices(prices: any): Record<string, Dezimal> {
    if (!prices || typeof prices !== "object") return {}

    const converted: Record<string, Dezimal> = {}
    for (const [cur, val] of Object.entries(prices)) {
      try {
        converted[String(cur).toUpperCase()] = Dezimal.fromString(String(val))
      } catch {
        continue
      }
    }
    return converted
  }

  private chunked(seq: string[], size: number): string[][] {
    const out: string[][] = []
    for (let i = 0; i < seq.length; i += size) {
      out.push(seq.slice(i, i + size))
    }
    return out
  }

  private async fetchSimplePrice(
    values: string[],
    vsParam: string,
    timeoutSec: number,
    identifierKey: "symbols" | "ids",
  ): Promise<Record<string, any>> {
    return (await this.fetch(
      "/simple/price",
      {
        vs_currencies: vsParam,
        [identifierKey]: values.join(","),
        precision: "full",
      },
      timeoutSec,
    )) as any
  }

  async getAssetDetails(
    providerId: string,
    currencies: string[],
  ): Promise<CryptoAssetDetails> {
    const params = {
      community_data: "false",
      developer_data: "false",
      tickers: "false",
      localization: "false",
    }

    const data = await this.fetch(
      `/coins/${providerId}`,
      params,
      CoinGeckoClient.TIMEOUT,
    )

    const platformsIndex = await this.getAssetPlatforms()
    const enrichedPlatforms = this.extractPlatforms(data as any, platformsIndex)

    const iconUrl = this.extractIconUrl(data as any)
    const priceMap = this.extractPrices(data as any, currencies)

    return {
      name: String((data as any)?.name ?? ""),
      symbol: String((data as any)?.symbol ?? "").toUpperCase(),
      platforms: enrichedPlatforms,
      provider: ExternalIntegrationId.COINGECKO,
      providerId: String((data as any)?.id ?? providerId),
      price: priceMap,
      iconUrl,
      type: enrichedPlatforms.length
        ? CryptoCurrencyType.TOKEN
        : CryptoCurrencyType.NATIVE,
    }
  }

  private extractPlatforms(
    data: any,
    platformsIndex: Record<string, CryptoPlatform>,
  ): CryptoAssetPlatform[] {
    const coinPlatforms = data?.platforms ?? {}
    const enriched: CryptoAssetPlatform[] = []

    if (coinPlatforms && typeof coinPlatforms === "object") {
      for (const [platformId, contractAddress] of Object.entries(
        coinPlatforms,
      )) {
        if (!platformId || !contractAddress) continue

        const platformInfo = platformsIndex[platformId]
        const platformName = platformInfo?.name ?? platformId
        const iconUrl = platformInfo?.iconUrl ?? null

        enriched.push({
          providerId: String(platformId),
          name: String(platformName),
          contractAddress: String(contractAddress),
          iconUrl,
          relatedEntityId: null,
        })
      }
    }

    return enriched
  }

  private extractIconUrl(data: any): string | null {
    const image = data?.image ?? {}
    const large = (image as any)?.large
    const small = (image as any)?.small
    return large ? String(large) : small ? String(small) : null
  }

  private extractPrices(
    data: any,
    currencies: string[],
  ): Record<string, Dezimal> {
    const marketData = data?.market_data ?? {}
    const currentPrice = marketData?.current_price ?? {}
    const priceMap: Record<string, Dezimal> = {}

    for (const currency of currencies ?? []) {
      const currencyLower = String(currency).toLowerCase()
      if (currencyLower in currentPrice) {
        try {
          priceMap[String(currency).toUpperCase()] = Dezimal.fromString(
            String((currentPrice as any)[currencyLower]),
          )
        } catch {
          continue
        }
      }
    }

    return priceMap
  }

  getNativeEntityByPlatform(
    providerId: string,
    provider: ExternalIntegrationId,
  ): Entity | null {
    if (provider !== ExternalIntegrationId.COINGECKO) return null
    return CoinGeckoClient.ENTITY_CHAIN_MAP[providerId] ?? null
  }

  private async getCoinAddressIndex(): Promise<Record<string, any>> {
    const cached = this.memCoinAddressIndex.get("addrIndex")
    if (cached) return cached

    const index: Record<string, any> = {}
    let coinList: any[] = []

    try {
      coinList = await this.getCoinList()
    } catch (e) {
      console.error("Failed to fetch coin list for address overview:", e)
      this.memCoinAddressIndex.set("addrIndex", index)
      return index
    }

    for (const coin of coinList) {
      this.addPlatformAddresses(index, coin)
    }

    this.memCoinAddressIndex.set("addrIndex", index)
    return index
  }

  private addPlatformAddresses(index: Record<string, any>, coin: any): void {
    try {
      const coinId = coin?.id
      if (!coinId) return

      const platforms = coin?.platforms ?? {}
      if (!platforms || typeof platforms !== "object") return

      const symbol = coin?.symbol ? String(coin.symbol).toUpperCase() : null

      for (const addr of Object.values(platforms)) {
        if (typeof addr !== "string") continue
        const normalized = addr.trim().toLowerCase()
        if (!normalized || normalized in index) continue

        index[normalized] = {
          id: String(coinId),
          symbol,
          name: coin?.name,
        }
      }
    } catch {
      return
    }
  }

  private async getCoinList(): Promise<any[]> {
    const cached = this.memCoinList.get("coinList")
    if (cached) return cached

    if (this.isCoinListCacheValid() && this.coinListCache) {
      this.memCoinList.set("coinList", this.coinListCache)
      return this.coinListCache
    }

    const params = { include_platform: "true" }

    let data: any
    try {
      data = await this.fetch("/coins/list", params, CoinGeckoClient.TIMEOUT)
    } catch (e) {
      console.error("Failed to fetch coin list from CoinGecko:", e)
      if (this.coinListCache) {
        console.warn("Returning stale cached coin list due to API error")
        this.memCoinList.set("coinList", this.coinListCache)
        return this.coinListCache
      }
      return []
    }

    if (!Array.isArray(data)) {
      console.warn(
        `Unexpected response for /coins/list, expected list. Got type ${typeof data}`,
      )
      if (this.coinListCache) {
        console.warn("Returning stale cached coin list due to API error")
        this.memCoinList.set("coinList", this.coinListCache)
        return this.coinListCache
      }
      return []
    }

    await this.saveCoinListCache(data)
    this.memCoinList.set("coinList", data)
    return data
  }

  private isPlatformsCacheValid(): boolean {
    if (!this.platformsCache || !this.platformsLastUpdated) return false
    const ageMs = Date.now() - this.platformsLastUpdated.getTime()
    return ageMs < CoinGeckoClient.CACHE_MAX_AGE_DAYS * 24 * 60 * 60 * 1000
  }

  private isCoinListCacheValid(): boolean {
    if (!this.coinListCache || !this.coinListLastUpdated) return false
    const ageMs = Date.now() - this.coinListLastUpdated.getTime()
    return ageMs < CoinGeckoClient.CACHE_MAX_AGE_DAYS * 24 * 60 * 60 * 1000
  }

  private async loadPersistedCache(): Promise<void> {
    try {
      const raw = await AsyncStorage.getItem(PLATFORMS_CACHE_KEY)
      if (raw && raw.trim()) {
        const parsed = JSON.parse(raw) as CachedSection<any[]>
        if (
          parsed?.result &&
          Array.isArray(parsed.result) &&
          typeof parsed.last_updated === "string"
        ) {
          const d = new Date(parsed.last_updated)
          if (Number.isFinite(d.getTime())) {
            this.platformsCache = parsed.result
            this.platformsLastUpdated = d
          }
        }
      }
    } catch (e) {
      console.warn("Failed to load CoinGecko platforms cache:", e)
    }

    try {
      const raw = await AsyncStorage.getItem(COINS_CACHE_KEY)
      if (raw && raw.trim()) {
        const parsed = JSON.parse(raw) as CompressedSection
        if (
          typeof parsed?.last_updated === "string" &&
          parsed?.compression === "gzip-base64" &&
          typeof parsed?.result === "string" &&
          parsed.result
        ) {
          const d = new Date(parsed.last_updated)
          if (Number.isFinite(d.getTime())) {
            const bytes = Buffer.from(parsed.result, "base64")
            const json = ungzip(bytes, { to: "string" }) as string
            const list = JSON.parse(json)
            if (Array.isArray(list)) {
              this.coinListCache = list
              this.coinListLastUpdated = d
            }
          }
        }
      }
    } catch (e) {
      console.warn("Failed to load CoinGecko coins cache:", e)
    }
  }

  private async saveCoinListCache(coinList: any[]): Promise<void> {
    try {
      const now = new Date().toISOString()
      const json = JSON.stringify(coinList)
      const compressed = gzip(json)
      const base64 = Buffer.from(compressed).toString("base64")
      if (base64.length <= MAX_COINS_CACHE_BASE64_LEN) {
        const payload: CompressedSection = {
          last_updated: now,
          compression: "gzip-base64",
          result: base64,
        }
        await AsyncStorage.setItem(COINS_CACHE_KEY, JSON.stringify(payload))
      }

      this.coinListCache = coinList
      this.coinListLastUpdated = new Date(now)
    } catch (e) {
      console.error("Failed to persist coin list cache:", e)
    }
  }

  private async savePlatformsCache(platforms: any[]): Promise<void> {
    try {
      const now = new Date().toISOString()
      const payload: CachedSection<any[]> = {
        last_updated: now,
        result: platforms,
      }
      await AsyncStorage.setItem(PLATFORMS_CACHE_KEY, JSON.stringify(payload))

      this.platformsCache = platforms
      this.platformsLastUpdated = new Date(now)
    } catch (e) {
      console.error("Failed to persist platforms cache:", e)
    }
  }

  private dedupeItems(items: string[], caseInsensitive: boolean): string[] {
    const seen = new Set<string>()
    const deduped: string[] = []

    for (const raw of items) {
      const item = raw.trim()
      if (!item) continue

      const key = caseInsensitive ? item.toLowerCase() : item
      if (seen.has(key)) continue
      seen.add(key)
      deduped.push(item)
    }

    return deduped
  }

  private async fetch(
    path: string,
    params?: Record<string, string>,
    timeoutSec: number = CoinGeckoClient.TIMEOUT,
  ): Promise<any> {
    const url = `${CoinGeckoClient.BASE_URL}${path}`

    const response = await httpGetWithBackoff({
      url,
      params,
      timeoutSec,
      maxRetries: CoinGeckoClient.MAX_RETRIES,
      backoffExponentBase: CoinGeckoClient.BACKOFF_EXPONENT_BASE,
      backoffFactor: CoinGeckoClient.BACKOFF_FACTOR,
      cooldownSec: CoinGeckoClient.COOLDOWN_SEC,
    })

    if (!response.ok) {
      const status = response.status
      const body = await response.text().catch(() => "")

      if (status === 429) throw new TooManyRequests()
      if (status === 401 || status === 403) {
        throw new Error("InvalidProvidedCredentials")
      }
      if (status === 400) {
        console.error(`Bad request to CoinGecko ${url}: ${body}`)
        throw new Error("Invalid request to CoinGecko API")
      }
      if (status === 500 || status === 503) {
        throw new Error(`CoinGecko service error ${status}: ${body}`)
      }
      if (status === 408) {
        throw new Error(`CoinGecko timeout status for ${url}: ${body}`)
      }

      throw new Error(
        `Unexpected CoinGecko response ${status} for ${url}: ${body}`,
      )
    }

    try {
      return await response.json()
    } catch {
      const text = await response.text().catch(() => "")
      throw new Error(
        `Failed to decode JSON from CoinGecko for ${url}: ${text.slice(0, 200)}`,
      )
    }
  }
}
