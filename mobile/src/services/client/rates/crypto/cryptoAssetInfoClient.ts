import {
  AvailableCryptoAsset,
  CryptoAsset,
  CryptoAssetDetails,
  CryptoPlatform,
  Entity,
  ExternalIntegrationId,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"

import { CryptoAssetInfoProvider } from "@/application/ports"
import { TtlCache } from "@/services/utils/ttlCache"

import { P2SClient } from "./p2sClient"
import { CoinGeckoClient } from "./coinGeckoClient"
import { CryptoCompareClient } from "./cryptoCompareClient"

export class CryptoAssetInfoClient implements CryptoAssetInfoProvider {
  static readonly PRICE_CACHE_TTL_MS = 20 * 60 * 1000

  private p2sClient = new P2SClient()
  private coingeckoClient = new CoinGeckoClient()
  private ccClient = new CryptoCompareClient()

  private priceCache = new TtlCache<string, Dezimal>(
    200,
    CryptoAssetInfoClient.PRICE_CACHE_TTL_MS,
  )

  private multiSymbolCache = new TtlCache<
    string,
    Record<string, Record<string, Dezimal>>
  >(10, CryptoAssetInfoClient.PRICE_CACHE_TTL_MS)

  private addressPricesCache = new TtlCache<
    string,
    Record<string, Record<string, Dezimal>>
  >(50, CryptoAssetInfoClient.PRICE_CACHE_TTL_MS)

  private bySymbolCache = new TtlCache<string, CryptoAsset[]>(200, 86400 * 1000)

  private assetDetailsCache = new TtlCache<string, CryptoAssetDetails>(
    100,
    3600 * 1000,
  )

  async getPrice(
    symbol: string,
    fiatIso: string,
    kwargs: any,
  ): Promise<Dezimal> {
    const cacheKey = `${symbol.toUpperCase()}_${fiatIso.toUpperCase()}`
    const cached = this.priceCache.get(cacheKey)
    if (cached) return cached

    const timeout = kwargs?.timeout

    let result: Dezimal
    if (this.p2sClient.supportsSymbol(symbol)) {
      result = await this.p2sClient.getPrice(symbol, fiatIso, timeout)
    } else {
      // Mirror backend default fallback: Dezimal(1) when not found.
      const map = await this.getMultiplePricesBySymbol([symbol], [fiatIso], {})
      result =
        map?.[symbol]?.[fiatIso] ??
        map?.[symbol.toUpperCase()]?.[fiatIso.toUpperCase()] ??
        Dezimal.fromInt(1)
    }

    this.priceCache.set(cacheKey, result)
    return result
  }

  async getMultiplePricesBySymbol(
    symbols: string[],
    fiatIsos: string[],
    kwargs: any,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    const timeout = kwargs?.timeout

    const key = `${symbols
      .slice()
      .sort((a, b) => a.localeCompare(b))
      .map(s => s.toUpperCase())
      .join(",")}_${fiatIsos
      .slice()
      .sort((a, b) => a.localeCompare(b))
      .map(f => f.toUpperCase())
      .join(",")}`

    const cached = this.multiSymbolCache.get(key)
    if (cached) return cached

    const result: Record<string, Record<string, Dezimal>> = {}

    const cryptocomparePrices = await this.ccClient.getPrices(
      symbols,
      fiatIsos,
      timeout,
    )

    for (const [sym, prices] of Object.entries(cryptocomparePrices)) {
      const normalizedSym = String(sym).toUpperCase()
      result[normalizedSym] = prices
    }

    const missingSymbols = symbols.filter(s => !(s.toUpperCase() in result))
    if (missingSymbols.length) {
      const missingPrices = await this.coingeckoClient.getPrices({
        symbols: missingSymbols,
        vsCurrencies: fiatIsos,
        timeoutSec: timeout ?? CoinGeckoClient.TIMEOUT,
      })

      for (const [sym, prices] of Object.entries(missingPrices)) {
        const normalizedSym = String(sym).toUpperCase()
        result[normalizedSym] = prices
      }
    }

    this.multiSymbolCache.set(key, result)
    return result
  }

  async getPricesByAddresses(
    addresses: string[],
    fiatIsos: string[],
    kwargs: any,
  ): Promise<Record<string, Record<string, Dezimal>>> {
    const timeout = kwargs?.timeout

    const key = `${addresses
      .slice()
      .sort((a, b) => a.localeCompare(b))
      .map(a => a.toLowerCase())
      .join(",")}_${fiatIsos
      .slice()
      .sort((a, b) => a.localeCompare(b))
      .map(f => f.toUpperCase())
      .join(",")}`

    const cached = this.addressPricesCache.get(key)
    if (cached) return cached

    const res = await this.coingeckoClient.getPricesByAddresses(
      addresses,
      fiatIsos,
      timeout ?? CoinGeckoClient.TIMEOUT,
    )

    this.addressPricesCache.set(key, res)
    return res
  }

  async getBySymbol(symbol: string): Promise<CryptoAsset[]> {
    const cacheKey = symbol.trim().toUpperCase()
    const cached = this.bySymbolCache.get(cacheKey)
    if (cached) return cached

    try {
      const assets = await this.ccClient.search(symbol)
      if (assets?.length) {
        this.bySymbolCache.set(cacheKey, assets)
        return assets
      }
    } catch (e) {
      console.error(`CryptoCompare search failed for ${symbol}:`, e)
    }

    console.info(`Backing off to CoinGecko search for symbol ${symbol}`)
    const assets = await this.coingeckoClient.search(symbol)
    this.bySymbolCache.set(cacheKey, assets)
    return assets
  }

  async getMultipleOverviewByAddresses(
    addresses: string[],
  ): Promise<Record<string, CryptoAsset>> {
    if (!addresses?.length) return {}

    const overview =
      await this.coingeckoClient.getCoinOverviewByAddresses(addresses)

    const result: Record<string, CryptoAsset> = {}
    for (const [raw, coin] of Object.entries(overview)) {
      result[raw] = {
        name: (coin as any)?.name ?? null,
        symbol: (coin as any)?.symbol ?? null,
        iconUrls: [],
        externalIds: {
          [ExternalIntegrationId.COINGECKO]: String((coin as any)?.id ?? ""),
        },
        id: null,
      }
    }

    return result
  }

  async assetLookup(
    symbol?: string | null,
    name?: string | null,
  ): Promise<AvailableCryptoAsset[]> {
    return this.coingeckoClient.assetLookup(symbol, name)
  }

  async getAssetPlatforms(): Promise<Record<string, CryptoPlatform>> {
    return this.coingeckoClient.getAssetPlatforms()
  }

  async getAssetDetails(
    providerId: string,
    currencies: string[],
    provider: ExternalIntegrationId = ExternalIntegrationId.COINGECKO,
  ): Promise<CryptoAssetDetails> {
    const cacheKey = `${provider}_${providerId}_${currencies
      .slice()
      .sort((a, b) => a.localeCompare(b))
      .join("_")}`

    const cached = this.assetDetailsCache.get(cacheKey)
    if (cached) return cached

    if (provider === ExternalIntegrationId.COINGECKO) {
      const details = await this.coingeckoClient.getAssetDetails(
        providerId,
        currencies,
      )
      this.assetDetailsCache.set(cacheKey, details)
      return details
    }

    throw new Error(`Asset details not implemented for provider ${provider}`)
  }

  async getNativeEntityByPlatform(
    providerId: string,
    provider: ExternalIntegrationId,
  ): Promise<Entity | null> {
    if (provider === ExternalIntegrationId.COINGECKO) {
      return this.coingeckoClient.getNativeEntityByPlatform(
        providerId,
        provider,
      )
    }

    throw new Error(
      `Native entity lookup not implemented for provider ${provider}`,
    )
  }
}
