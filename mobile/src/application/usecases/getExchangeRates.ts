import {
  CommodityExchangeRate,
  CommodityType,
  ExchangeRates,
  PositionQueryRequest,
  ProductType,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"
import { GetExchangeRates } from "@/domain/usecases/core/getExchangeRates"

import {
  CryptoAssetInfoProvider,
  ExchangeRateProvider,
  ExchangeRateStorage,
  MetalPriceProvider,
  PositionPort,
} from "@/application/ports"
import { COMMODITY_SYMBOLS } from "@/domain/constants/commodity"

const SUPPORTED_CURRENCIES = ["EUR", "USD"] as const

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000)
}

function toDezimal(value: unknown): Dezimal | null {
  try {
    if (value == null) return null
    if (value instanceof Dezimal) return value

    if (typeof value === "string") return Dezimal.fromString(value)
    if (typeof value === "number") {
      if (!Number.isFinite(value)) return null
      return Dezimal.fromFloat(value)
    }
    if (typeof value === "bigint") return Dezimal.fromString(value.toString())

    if (typeof value === "object" && value && "val" in (value as any)) {
      return toDezimal((value as any).val)
    }
    return null
  } catch {
    return null
  }
}

function isNonEmptyMatrix(
  matrix: ExchangeRates | null | undefined,
): matrix is ExchangeRates {
  if (!matrix) return false
  return Object.keys(matrix).length > 0
}

class AsyncLock {
  private tail: Promise<void> = Promise.resolve()

  async runExclusive<T>(fn: () => Promise<T>): Promise<T> {
    let release: () => void = () => {}
    const next = new Promise<void>(resolve => {
      release = () => resolve()
    })

    const prev = this.tail
    this.tail = prev.then(() => next)

    await prev
    try {
      return await fn()
    } finally {
      release()
    }
  }
}

type TaskKind = "base" | "commodity" | "crypto" | "crypto_batch"

type CryptoAssetKey = {
  symbol: string
  contractAddress: string | null
}

type TaskResult =
  | {
      id: number
      kind: TaskKind
      meta: any
      ok: true
      value: any
    }
  | {
      id: number
      kind: TaskKind
      meta: any
      ok: false
      error: unknown
    }

export class GetExchangeRatesImpl implements GetExchangeRates {
  static readonly BASE_CRYPTO_SYMBOLS = [
    "BTC",
    "ETH",
    "LTC",
    "TRX",
    "BNB",
    "USDT",
    "USDC",
  ]
  static readonly DEFAULT_TIMEOUT = 4
  static readonly CACHE_TTL_SECONDS = 300
  static readonly STORAGE_REFRESH_SECONDS = 6 * 60 * 60
  static readonly POSITION_CRYPTO_TTL_SECONDS = 300

  private fiatMatrix: ExchangeRates | null = null
  private lastBaseRefreshTs = 0
  private lastPositionCryptoRefreshTs = 0
  private secondLoad = false

  private lock = new AsyncLock()
  private initPromise: Promise<void> | null = null

  private snapshotMatrix(matrix: ExchangeRates): ExchangeRates {
    const out: ExchangeRates = {}
    for (const [base, quotes] of Object.entries(matrix ?? {})) {
      out[base] = { ...(quotes ?? {}) }
    }
    return out
  }

  constructor(
    private exchangeRatesProvider: ExchangeRateProvider,
    private cryptoAssetInfoProvider: CryptoAssetInfoProvider,
    private metalPriceProvider: MetalPriceProvider,
    private exchangeRatesStorage: ExchangeRateStorage,
    private positionPort: PositionPort,
  ) {
    this.initPromise = this.loadFromStorage().catch(e => {
      console.warn("Failed to initialize exchange rates from storage", e)
    })
  }

  async execute(initialLoad: boolean = false): Promise<ExchangeRates> {
    return this.lock.runExclusive(async () =>
      this.getExchangeRates(initialLoad),
    )
  }

  private async loadFromStorage(): Promise<void> {
    const stored = await this.exchangeRatesStorage
      .get()
      .catch(() => ({}) as ExchangeRates)
    this.fiatMatrix = isNonEmptyMatrix(stored) ? stored : null

    if (this.fiatMatrix) {
      const lastSaved = await this.exchangeRatesStorage
        .getLastSaved()
        .catch(() => null)
      if (lastSaved) {
        const d = new Date(lastSaved)
        if (Number.isFinite(d.getTime())) {
          this.lastBaseRefreshTs = Math.floor(d.getTime() / 1000)
        }
      }
    }
  }

  private needsBaseRefresh(): boolean {
    if (this.fiatMatrix == null) return true
    return (
      nowSeconds() - this.lastBaseRefreshTs >=
      GetExchangeRatesImpl.CACHE_TTL_SECONDS
    )
  }

  private needsPositionCryptoRefresh(): boolean {
    // Always try to refresh position-based crypto rates.
    // The actual fetch is cheap when there are no positions, and we need
    // to pick up newly imported positions after data import.
    // The position crypto fetch is best-effort and uses its own internal
    // caching in the crypto provider.
    return true
  }

  private normalizeMatrix(matrix: ExchangeRates): ExchangeRates {
    for (const [base, quotes] of Object.entries(matrix)) {
      if (!quotes || typeof quotes !== "object") continue
      const invalid: string[] = []

      for (const [quote, rate] of Object.entries(quotes)) {
        const dec = toDezimal(rate)
        if (dec == null) {
          console.warn(`Dropping non-numeric rate ${base}->${quote}`)
          invalid.push(quote)
        } else {
          ;(quotes as any)[quote] = rate instanceof Dezimal ? rate : dec
        }
      }

      for (const k of invalid) {
        delete (quotes as any)[k]
      }
    }
    return matrix
  }

  private initEmptyMatrix(): ExchangeRates {
    const out: ExchangeRates = {}
    for (const c of SUPPORTED_CURRENCIES) out[c] = {}
    return out
  }

  private async getExchangeRates(initialLoad: boolean): Promise<ExchangeRates> {
    console.info(
      "Refreshing exchange rates " + (initialLoad ? "(initial load)" : ""),
    )

    if (this.initPromise) {
      await this.initPromise
      this.initPromise = null
    }

    // Second load (after import) needs more time to fetch position-based crypto rates
    // as this involves fetching the CoinGecko coin list and building the address index.
    const timeout = initialLoad
      ? 7
      : this.secondLoad
        ? 15
        : GetExchangeRatesImpl.DEFAULT_TIMEOUT

    const refreshBase = this.needsBaseRefresh()
    const refreshPositionCrypto = this.needsPositionCryptoRefresh()
    console.debug("[GetExchangeRates] refresh decision", {
      initialLoad,
      timeout,
      refreshBase,
      refreshPositionCrypto,
      hasFiatMatrix: this.fiatMatrix != null,
    })

    // Even when fiat rates are cached, we may still need to refresh crypto
    // rates derived from the user's imported positions.
    if (
      !refreshBase &&
      !refreshPositionCrypto &&
      !this.secondLoad &&
      this.fiatMatrix &&
      !initialLoad
    ) {
      console.info("Using cached exchange rates.")
      return this.fiatMatrix
    }

    if (this.fiatMatrix == null) {
      this.lastBaseRefreshTs = nowSeconds()
      this.fiatMatrix = this.initEmptyMatrix()
    }

    const commodityRates: Partial<
      Record<CommodityType, [CommodityExchangeRate, string]>
    > = {}
    const cryptoRates: Record<string, Record<string, Dezimal>> = {}
    let refreshedBase: ExchangeRates | null = null

    const tasks: Array<{ id: number; promise: Promise<TaskResult> }> = []
    let idCounter = 1
    const nextId = (): number => idCounter++

    if (refreshBase) {
      const id = nextId()
      tasks.push({
        id,
        promise: this.wrapTask(
          id,
          "base",
          null,
          this.exchangeRatesProvider.getMatrix({ timeout }),
        ),
      })

      for (const [commodity, symbol] of Object.entries(
        COMMODITY_SYMBOLS,
      ) as Array<[CommodityType, string]>) {
        const id = nextId()
        tasks.push({
          id,
          promise: this.wrapTask(
            id,
            "commodity",
            [commodity, symbol],
            this.metalPriceProvider.getPrice(commodity, { timeout }),
          ),
        })
      }
    }

    tasks.push(
      ...(await this.scheduleCryptoRates(timeout, initialLoad, nextId)),
    )

    const startMonotonic = Date.now()
    const sliceTimeoutMs = 200
    const globalTimeoutMs = timeout * 1000
    const deadline = startMonotonic + globalTimeoutMs

    const pending = new Map<number, Promise<TaskResult>>()
    for (const t of tasks) pending.set(t.id, t.promise)

    let gotPositionCryptoBatch = false

    while (pending.size) {
      const remainingGlobal = deadline - Date.now()
      if (remainingGlobal <= 0) {
        console.warn(
          `Global timeout (${timeout}s) reached; skipping ${pending.size} pending fetches.`,
        )
        break
      }

      const waitSliceMs = Math.min(sliceTimeoutMs, remainingGlobal)
      const sliceTimeout = new Promise<TaskResult | null>(resolve => {
        const t = setTimeout(() => {
          clearTimeout(t)
          resolve(null)
        }, waitSliceMs)
      })

      const settled = await Promise.race<TaskResult | null>([
        ...pending.values(),
        sliceTimeout,
      ])

      if (settled == null) {
        continue
      }

      pending.delete(settled.id)

      if (settled.kind === "crypto_batch") {
        if (settled.ok) {
          gotPositionCryptoBatch = true
        }
      }

      refreshedBase = this.consumeTaskResult(
        settled,
        commodityRates,
        cryptoRates,
        refreshedBase,
      )
    }

    if (refreshedBase) {
      for (const [base, quotes] of Object.entries(refreshedBase)) {
        this.fiatMatrix[base] ??= {}
        for (const [quote, rate] of Object.entries(quotes ?? {})) {
          const dz = rate instanceof Dezimal ? rate : toDezimal(rate)
          if (dz) {
            this.fiatMatrix[base]![quote] = dz
          }
        }
      }
      this.lastBaseRefreshTs = nowSeconds()
    }

    this.applyRates(commodityRates, cryptoRates)

    // Only mark position crypto as refreshed if we actually had position assets
    // and successfully fetched them. This ensures we retry on the next call if
    // the DB wasn't ready or fetch failed.
    if (gotPositionCryptoBatch) {
      this.lastPositionCryptoRefreshTs = nowSeconds()
    }

    // Force save when we got new position-based crypto rates, so address-keyed
    // rates are persisted and available on subsequent app launches.
    const forceSave = this.secondLoad || gotPositionCryptoBatch
    await this.saveRatesToStorage({ force: forceSave })

    if (this.secondLoad) {
      this.secondLoad = false
    } else if (initialLoad) {
      this.secondLoad = true
    }

    // Important: return a fresh object so React state updates.
    // `this.fiatMatrix` is mutated in-place across refreshes.
    return this.snapshotMatrix(this.fiatMatrix)
  }

  private wrapTask(
    id: number,
    kind: TaskKind,
    meta: any,
    promise: Promise<any>,
  ): Promise<TaskResult> {
    return promise
      .then(value => ({ id, kind, meta, ok: true as const, value }))
      .catch(error => ({ id, kind, meta, ok: false as const, error }))
  }

  private consumeTaskResult(
    result: TaskResult,
    commodityRates: Partial<
      Record<CommodityType, [CommodityExchangeRate, string]>
    >,
    cryptoRates: Record<string, Record<string, Dezimal>>,
    refreshedBase: ExchangeRates | null,
  ): ExchangeRates | null {
    const { kind, meta } = result

    if (!result.ok) {
      if (kind === "base") {
        console.error(`Failed base fiat matrix fetch:`, result.error)
      } else if (kind === "commodity") {
        const [commodity] = meta as [CommodityType, string]
        console.error(`Failed commodity price for ${commodity}:`, result.error)
      } else if (kind === "crypto_batch") {
        console.error(`Failed batched crypto prices fetch:`, result.error)
      } else {
        const [symbol, baseCurrency] = meta as [string, string]
        console.error(
          `Failed crypto price for ${symbol} in ${baseCurrency}:`,
          result.error,
        )
      }
      return refreshedBase
    }

    const value = result.value

    if (kind === "base") {
      if (value != null) {
        refreshedBase = this.normalizeMatrix(value as ExchangeRates)
      }
    } else if (kind === "commodity") {
      const [commodity, symbol] = meta as [CommodityType, string]
      if (value != null) {
        commodityRates[commodity] = [value as CommodityExchangeRate, symbol]
      }
    } else if (kind === "crypto") {
      const [symbol, baseCurrency] = meta as [string, string]
      cryptoRates[baseCurrency] ??= {}
      cryptoRates[baseCurrency][symbol] = value as Dezimal
    } else if (kind === "crypto_batch") {
      const payload = value as {
        bySymbol?: Record<string, Record<string, Dezimal>>
        byAddress?: Record<string, Record<string, Dezimal>>
      }

      for (const [symbol, fiatMap] of Object.entries(payload?.bySymbol ?? {})) {
        for (const [fiatIso, price] of Object.entries(fiatMap ?? {})) {
          cryptoRates[fiatIso] ??= {}
          cryptoRates[fiatIso][String(symbol).toUpperCase()] = price
        }
      }

      for (const [addr, fiatMap] of Object.entries(payload?.byAddress ?? {})) {
        for (const [fiatIso, price] of Object.entries(fiatMap ?? {})) {
          cryptoRates[fiatIso] ??= {}
          cryptoRates[fiatIso][`addr:${String(addr).toLowerCase()}`] = price
        }
      }
    }

    return refreshedBase
  }

  private async scheduleCryptoRates(
    timeout: number,
    initialLoad: boolean,
    getNextId: () => number,
  ): Promise<Array<{ id: number; promise: Promise<TaskResult> }>> {
    const out: Array<{ id: number; promise: Promise<TaskResult> }> = []

    if (initialLoad) {
      for (const baseCurrency of SUPPORTED_CURRENCIES) {
        for (const symbol of GetExchangeRatesImpl.BASE_CRYPTO_SYMBOLS) {
          const id = getNextId()
          out.push({
            id,
            promise: this.wrapTask(
              id,
              "crypto",
              [symbol, baseCurrency],
              this.cryptoAssetInfoProvider.getPrice(symbol, baseCurrency, {
                timeout,
              }),
            ),
          })
        }
      }
    }

    let assetKeys: CryptoAssetKey[] = []
    try {
      assetKeys = await this.getPositionCryptoAssets()
    } catch (e) {
      // On a fresh install the local DB may not be initialized yet.
      // Exchange-rate refresh must still proceed for fiat/commodities.
      assetKeys = []
    }

    if (assetKeys.length) {
      const id = getNextId()
      out.push({
        id,
        promise: this.wrapTask(
          id,
          "crypto_batch",
          { assetCount: assetKeys.length },
          this.getCryptoPriceMap(assetKeys),
        ),
      })
    }

    return out
  }

  private async getPositionCryptoAssets(): Promise<CryptoAssetKey[]> {
    const query: PositionQueryRequest = { products: [ProductType.CRYPTO] }
    let cryptoEntityPositions: any
    try {
      cryptoEntityPositions =
        await this.positionPort.getLastGroupedByEntity(query)
    } catch (e) {
      // Keep exchange-rate refresh independent from DB lifecycle.
      return []
    }

    const out: CryptoAssetKey[] = []

    for (const position of cryptoEntityPositions.values()) {
      const products = position?.products
      if (!products || !(ProductType.CRYPTO in products)) continue

      const entries = (products as any)[ProductType.CRYPTO]?.entries ?? []
      if (!Array.isArray(entries)) continue

      for (const entry of entries) {
        const assets = Array.isArray(entry?.assets) ? entry.assets : [entry]
        for (const asset of assets) {
          const symbol = String(asset?.symbol ?? "")
            .trim()
            .toUpperCase()
          if (!symbol) continue

          const addrRaw = asset?.contractAddress ?? asset?.contract_address
          const addr =
            typeof addrRaw === "string" && addrRaw.trim()
              ? addrRaw.trim().toLowerCase()
              : null

          out.push({ symbol, contractAddress: addr })
        }
      }
    }

    return out
  }

  private async getCryptoPriceMap(assetKeys: CryptoAssetKey[]): Promise<{
    bySymbol: Record<string, Record<string, Dezimal>>
    byAddress: Record<string, Record<string, Dezimal>>
  }> {
    const bySymbol: Record<string, Record<string, Dezimal>> = {}
    const byAddress: Record<string, Record<string, Dezimal>> = {}

    const nonAddressSymbols = new Set<string>()
    const addresses = new Set<string>()

    for (const a of assetKeys) {
      if (a.contractAddress) {
        // Prefer address-based lookup for tokens with contract addresses
        // to avoid symbol collisions across chains (e.g., different tokens
        // with the same symbol on different networks).
        addresses.add(a.contractAddress.toLowerCase())
      } else if (a.symbol) {
        // Only use symbol-based lookup when no contract address is available.
        nonAddressSymbols.add(a.symbol.toUpperCase())
      }
    }

    if (nonAddressSymbols.size) {
      const map = await this.cryptoAssetInfoProvider.getMultiplePricesBySymbol(
        Array.from(nonAddressSymbols),
        [...SUPPORTED_CURRENCIES],
        {},
      )

      for (const [sym, prices] of Object.entries(map ?? {})) {
        bySymbol[String(sym).toUpperCase()] = prices as Record<string, Dezimal>
      }
    }

    if (addresses.size) {
      const addressPrices =
        await this.cryptoAssetInfoProvider.getPricesByAddresses(
          Array.from(addresses),
          [...SUPPORTED_CURRENCIES],
          {},
        )

      for (const [addr, prices] of Object.entries(addressPrices ?? {})) {
        byAddress[String(addr).toLowerCase()] = prices as Record<
          string,
          Dezimal
        >
      }
    }

    return { bySymbol, byAddress }
  }

  private applyRates(
    commodityRates: Partial<
      Record<CommodityType, [CommodityExchangeRate, string]>
    >,
    cryptoRates: Record<string, Record<string, Dezimal>>,
  ): void {
    if (!this.fiatMatrix) return

    for (const baseCurrency of SUPPORTED_CURRENCIES) {
      this.applyCommodityRates(baseCurrency, commodityRates)
      this.applyCryptoRates(baseCurrency, cryptoRates)
    }
  }

  private applyCommodityRates(
    baseCurrency: string,
    commodityRates: Partial<
      Record<CommodityType, [CommodityExchangeRate, string]>
    >,
  ): void {
    if (!this.fiatMatrix) return

    for (const [commodity, tuple] of Object.entries(commodityRates) as Array<
      [CommodityType, [CommodityExchangeRate, string]]
    >) {
      const [rateData, symbol] = tuple
      try {
        const priceDec = toDezimal(rateData?.price)
        if (!priceDec || priceDec.isZero()) {
          continue
        }

        let rate: Dezimal
        if (baseCurrency !== rateData.currency) {
          const baseToRateCurrency = toDezimal(
            this.fiatMatrix?.[baseCurrency]?.[rateData.currency],
          )
          if (!baseToRateCurrency || baseToRateCurrency.isZero()) {
            continue
          }
          rate = baseToRateCurrency.truediv(priceDec)
        } else {
          rate = Dezimal.fromInt(1).truediv(priceDec)
        }

        this.fiatMatrix[baseCurrency] ??= {}
        this.fiatMatrix[baseCurrency]![symbol.toUpperCase()] = rate
      } catch (e) {
        console.error(
          `Failed to apply commodity ${commodity} for ${baseCurrency}:`,
          e,
        )
      }
    }
  }

  private applyCryptoRates(
    baseCurrency: string,
    cryptoRates: Record<string, Record<string, Dezimal>>,
  ): void {
    if (!this.fiatMatrix) return
    if (!(baseCurrency in cryptoRates)) return

    for (const [key, rate] of Object.entries(cryptoRates[baseCurrency] ?? {})) {
      try {
        const rateDec = toDezimal(rate)
        if (!rateDec || rateDec.isZero()) continue
        this.fiatMatrix[baseCurrency] ??= {}
        const normalizedKey = String(key).startsWith("addr:")
          ? String(key).toLowerCase()
          : String(key).toUpperCase()

        this.fiatMatrix[baseCurrency]![normalizedKey] =
          Dezimal.fromInt(1).truediv(rateDec)
      } catch (e) {
        console.error(`Failed to apply crypto ${key} for ${baseCurrency}:`, e)
      }
    }
  }

  private async saveRatesToStorage({
    force,
  }: {
    force: boolean
  }): Promise<void> {
    try {
      if (!this.fiatMatrix) return

      const lastSavedRaw = await this.exchangeRatesStorage
        .getLastSaved()
        .catch(() => null)
      const lastSaved = lastSavedRaw ? new Date(lastSavedRaw) : null
      const lastSavedValid = lastSaved && Number.isFinite(lastSaved.getTime())

      const shouldSave =
        force ||
        !lastSavedValid ||
        (Date.now() - (lastSaved as Date).getTime()) / 1000 >=
          GetExchangeRatesImpl.STORAGE_REFRESH_SECONDS

      if (shouldSave) {
        console.debug("Saving exchange rates to storage.")
        await this.exchangeRatesStorage.save(this.fiatMatrix)
      }
    } catch (e) {
      console.error("Failed to persist refreshed exchange rates:", e)
    }
  }
}
