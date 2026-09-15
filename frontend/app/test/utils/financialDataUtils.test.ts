import { describe, it, expect } from "vitest"

import {
  calculateCryptoAssetValue,
  calculateWalletAssetsValue,
  classifyCryptoPositionKind,
  getCryptoPositions,
  getCurrencyDisplayValue,
  getCryptoRateKey,
  getWalletAssets,
  tryConvertCurrency,
} from "@/utils/financialDataUtils"
import {
  CryptoCurrencyType,
  CryptoPositionType,
  ProductType,
  type CryptoCurrencyPosition,
  type EntitiesPosition,
  type ProductPositions,
} from "@/types/position"
import { DataSource, EntityOrigin } from "@/types"
import type { ExchangeRates } from "@/types"
import { formatCurrency } from "@/lib/formatters"

const makeAsset = (
  overrides: Partial<CryptoCurrencyPosition>,
): CryptoCurrencyPosition => ({
  id: "asset-id",
  name: "Asset",
  symbol: "BTC",
  amount: 1,
  type: CryptoCurrencyType.NATIVE,
  crypto_asset: { id: "ca", name: "Asset", symbol: "BTC" },
  source: DataSource.MANUAL,
  ...overrides,
})

describe("getCryptoRateKey", () => {
  it("keys native coins by uppercase symbol", () => {
    const asset = makeAsset({ type: CryptoCurrencyType.NATIVE, symbol: "btc" })
    expect(getCryptoRateKey(asset)).toBe("BTC")
  })

  it("keys tokens by lowercase contract address", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: "0xAbC123",
    })
    expect(getCryptoRateKey(asset)).toBe("0xabc123")
  })

  it("falls back to symbol when token has no contract address", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: null,
    })
    expect(getCryptoRateKey(asset)).toBe("BTCB")
  })

  it("returns null when no symbol and no address", () => {
    const asset = makeAsset({ type: CryptoCurrencyType.NATIVE, symbol: "" })
    expect(getCryptoRateKey(asset)).toBeNull()
  })
})

describe("tryConvertCurrency", () => {
  it("converts USDC using the direct target-currency rate", () => {
    const rates: ExchangeRates = { EUR: { USDC: 0.92 } }

    expect(tryConvertCurrency(300, "USDC", "EUR", rates)).toBeCloseTo(
      326.0869565,
      6,
    )
  })

  it("returns source value unchanged for same currency", () => {
    expect(tryConvertCurrency(300, "USDC", "USDC", null)).toBe(300)
  })

  it("returns null when source rate is unavailable", () => {
    expect(tryConvertCurrency(300, "USDC", "EUR", { EUR: {} })).toBeNull()
  })

  it("keeps zero valid without an exchange rate", () => {
    expect(tryConvertCurrency(0, "USDC", "EUR", null)).toBe(0)
  })

  it("uses target currency when direct conversion exists", () => {
    expect(
      getCurrencyDisplayValue(300, "USDC", "EUR", { EUR: { USDC: 0.92 } }),
    ).toEqual({ value: 300 / 0.92, currency: "EUR" })
  })

  it("keeps source currency when conversion is unavailable", () => {
    const displayValue = getCurrencyDisplayValue(300, "USDC", "EUR", {
      EUR: {},
    })

    expect(displayValue).toEqual({
      value: 300,
      currency: "USDC",
    })
    expect(
      formatCurrency(
        displayValue?.value ?? 0,
        "en-US",
        "EUR",
        displayValue?.currency,
      ),
    ).toContain("USDC")
  })
})

describe("calculateCryptoAssetValue crypto keying", () => {
  it("values native coins using the symbol-keyed rate", () => {
    const rates: ExchangeRates = {
      EUR: { BTC: 1 / 50000 },
    }
    const asset = makeAsset({
      type: CryptoCurrencyType.NATIVE,
      symbol: "BTC",
      amount: 2,
    })
    expect(calculateCryptoAssetValue(asset, "EUR", rates)).toBeCloseTo(
      100000,
      4,
    )
  })

  it("values tokens using the address-keyed rate, ignoring the symbol rate", () => {
    const rates: ExchangeRates = {
      EUR: { BTCB: 1 / 50000, "0xabc123": 1 / 0.06 },
    }
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: "0xAbC123",
      amount: 2,
    })
    expect(calculateCryptoAssetValue(asset, "EUR", rates)).toBeCloseTo(0.12, 6)
  })

  it("does not collide when two tokens share a symbol", () => {
    const rates: ExchangeRates = {
      EUR: { BTCB: 1 / 50000, "0xaaa": 1 / 50000, "0xbbb": 1 / 0.06 },
    }
    const tokenA = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: "0xAAA",
      amount: 1,
    })
    const tokenB = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: "0xBBB",
      amount: 1,
    })
    expect(calculateCryptoAssetValue(tokenA, "EUR", rates)).toBeCloseTo(
      50000,
      4,
    )
    expect(calculateCryptoAssetValue(tokenB, "EUR", rates)).toBeCloseTo(0.06, 6)
  })

  it("falls back to market_value when the address rate is missing", () => {
    const rates: ExchangeRates = {
      EUR: { BTCB: 1 / 50000 },
    }
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      symbol: "BTCB",
      contract_address: "0xAbC123",
      amount: 2,
      market_value: 0.12,
      currency: "EUR",
    })
    expect(calculateCryptoAssetValue(asset, "EUR", rates)).toBe(0.12)
  })
})

describe("classifyCryptoPositionKind", () => {
  it("classifies a SUPPLIED position with a protocol as defi", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      contract_address: "0xAave",
      position_type: CryptoPositionType.SUPPLIED,
      protocol: "Aave V3",
    })
    expect(classifyCryptoPositionKind(asset)).toBe("defi")
  })

  it("classifies a BORROWED position as defi even without a protocol", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      contract_address: "0xDebt",
      position_type: CryptoPositionType.BORROWED,
    })
    expect(classifyCryptoPositionKind(asset)).toBe("defi")
  })

  it("classifies a position with a truthy protocol as defi even without position_type", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      contract_address: "0xPendle",
      protocol: "Pendle",
    })
    expect(classifyCryptoPositionKind(asset)).toBe("defi")
  })

  it("classifies a plain HOLDING token as token", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      contract_address: "0xToken",
      position_type: CryptoPositionType.HOLDING,
    })
    expect(classifyCryptoPositionKind(asset)).toBe("token")
  })

  it("classifies a plain native coin as native", () => {
    const asset = makeAsset({
      type: CryptoCurrencyType.NATIVE,
      symbol: "ETH",
    })
    expect(classifyCryptoPositionKind(asset)).toBe("native")
  })

  it("falls back to native/token classification when position_type is undefined (pre-existing data)", () => {
    const nativeAsset = makeAsset({ type: CryptoCurrencyType.NATIVE })
    const tokenAsset = makeAsset({
      type: CryptoCurrencyType.TOKEN,
      contract_address: "0xLegacyToken",
    })
    expect(classifyCryptoPositionKind(nativeAsset)).toBe("native")
    expect(classifyCryptoPositionKind(tokenAsset)).toBe("token")
  })
})

describe("getWalletAssets / calculateWalletAssetsValue with DeFi (Zerion) positions", () => {
  // Zerion/DeFi positions are value-passthrough: the backend intentionally
  // skips CoinGecko/registry enrichment for them, so they carry a
  // `market_value` but no `crypto_asset`.
  const zerionAsset = makeAsset({
    id: "defi-1",
    name: "Aave V3 USDC",
    symbol: "AUSDC",
    crypto_asset: null,
    market_value: 250,
    currency: "EUR",
    amount: 2,
  })

  const valuelessAsset = makeAsset({
    id: "valueless-1",
    name: "Unknown Token",
    symbol: "UNK",
    crypto_asset: null,
    market_value: null,
    amount: 5,
  })

  it("includes a DeFi asset that has a market_value but no crypto_asset", () => {
    const wallet = { assets: [zerionAsset] }
    expect(getWalletAssets(wallet).map(a => a.id)).toEqual(["defi-1"])
  })

  it("counts the DeFi asset's market_value in calculateWalletAssetsValue", () => {
    const wallet = { assets: [zerionAsset] }
    const rates: ExchangeRates = {}
    expect(calculateWalletAssetsValue(wallet, "EUR", rates)).toBe(250)
  })

  it("still hides a genuinely value-less asset (no crypto_asset, no market_value)", () => {
    const wallet = { assets: [valuelessAsset] }
    expect(getWalletAssets(wallet)).toEqual([])
  })

  it("keeps a BORROWED position's signed market_value instead of using the amount > 0 fast path", () => {
    // A BORROWED position carries a negative amount and market_value. Since
    // amount is not > 0, calculateCryptoAssetValue must fall through to the
    // signed market_value rather than trying the (amount > 0) rate lookup.
    const borrowedAsset = makeAsset({
      id: "defi-borrowed-1",
      name: "Aave V3 GHO Debt",
      symbol: "GHO",
      crypto_asset: null,
      amount: -100,
      market_value: -250,
      currency: "EUR",
    })
    const wallet = { assets: [borrowedAsset] }
    const rates: ExchangeRates = {}

    expect(getWalletAssets(wallet).map(a => a.id)).toEqual(["defi-borrowed-1"])
    expect(calculateWalletAssetsValue(wallet, "EUR", rates)).toBe(-250)
  })

  it("uses market_value for a positive fetcher-priced position even when a colliding rate exists", () => {
    // A positive Zerion holding whose symbol rate was populated by another
    // wallet must still report its authoritative market_value, not amount*rate.
    const suppliedAsset = makeAsset({
      id: "defi-supplied-1",
      name: "Supplied ETH",
      symbol: "ETH",
      crypto_asset: null,
      amount: 3,
      market_value: 9000,
      currency: "EUR",
    })
    const wallet = { assets: [suppliedAsset] }
    // A colliding ETH rate (1 ETH = 1000 EUR) would give amount*rate = 3000.
    const rates: ExchangeRates = { EUR: { ETH: 1 / 1000 } }

    expect(calculateCryptoAssetValue(suppliedAsset, "EUR", rates)).toBe(9000)
    expect(calculateWalletAssetsValue(wallet, "EUR", rates)).toBe(9000)
  })
})

describe("getCryptoPositions with fetcher-priced (Zerion) positions", () => {
  const makePositions = (
    assets: CryptoCurrencyPosition[],
  ): EntitiesPosition => ({
    positions: {
      "entity-zerion": [
        {
          id: "global-position-1",
          entity: {
            id: "entity-zerion",
            name: "Zerion",
            origin: EntityOrigin.NATIVE,
          },
          date: "2026-01-01",
          products: {
            [ProductType.CRYPTO]: {
              entries: [
                {
                  id: "wallet-1",
                  name: "Test wallet",
                  addresses: ["0x000000000000000000000000000000000000dead"],
                  assets,
                  hd_wallet: null,
                },
              ],
            },
          } as ProductPositions,
          source: DataSource.REAL,
        },
      ],
    },
  })

  const suppliedEth = makeAsset({
    id: "defi-supplied-eth",
    name: "Supplied ETH",
    symbol: "ETH",
    type: CryptoCurrencyType.NATIVE,
    crypto_asset: null,
    amount: 2,
    market_value: 5000,
    currency: "EUR",
    chain: "arbitrum",
    protocol: "aave-v3",
    position_type: CryptoPositionType.SUPPLIED,
  })

  const borrowedGho = makeAsset({
    id: "defi-borrowed-gho",
    name: "Borrowed GHO",
    symbol: "GHO",
    type: CryptoCurrencyType.TOKEN,
    contract_address: "0x0000000000000000000000000000000000000001",
    crypto_asset: null,
    amount: -100,
    market_value: -250,
    currency: "EUR",
    chain: "arbitrum",
    protocol: "aave-v3",
    position_type: CryptoPositionType.BORROWED,
  })

  const walletUsdc = makeAsset({
    id: "wallet-usdc",
    name: "USD Coin",
    symbol: "USDC",
    type: CryptoCurrencyType.TOKEN,
    contract_address: "0x0000000000000000000000000000000000000002",
    crypto_asset: null,
    amount: 120,
    market_value: 120,
    currency: "EUR",
    chain: "arbitrum",
    position_type: CryptoPositionType.HOLDING,
  })

  it("includes a fetcher-priced position (no crypto_asset) valued at its market_value", () => {
    const result = getCryptoPositions(
      makePositions([suppliedEth]),
      "en-US",
      "EUR",
      {},
    )

    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({
      symbol: "ETH",
      name: "Supplied ETH",
      type: "CRYPTO",
      amount: 2,
      value: 5000,
      price: 2500,
      entities: ["Zerion"],
    })
  })

  it("excludes a BORROWED position (negative market_value) from the holdings list", () => {
    const result = getCryptoPositions(
      makePositions([suppliedEth, borrowedGho, walletUsdc]),
      "en-US",
      "EUR",
      {},
    )

    expect(result.map(p => p.symbol)).toEqual(["ETH", "USDC"])
    expect(result.find(p => p.symbol === "USDC")).toMatchObject({
      type: "CRYPTO_TOKEN",
      value: 120,
    })
    expect(result.reduce((sum, p) => sum + p.value, 0)).toBe(5120)
  })

  it("merges a fetcher-priced native position with a registry-enriched one of the same symbol", () => {
    const registryEth = makeAsset({
      id: "wallet-eth",
      name: "Ethereum",
      symbol: "ETH",
      type: CryptoCurrencyType.NATIVE,
      crypto_asset: { id: "ethereum", name: "Ethereum", symbol: "ETH" },
      amount: 1,
    })
    // 1 ETH = 1000 EUR
    const rates: ExchangeRates = { EUR: { ETH: 1 / 1000 } }

    const result = getCryptoPositions(
      makePositions([registryEth, suppliedEth]),
      "en-US",
      "EUR",
      rates,
    )

    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ symbol: "ETH", amount: 3, value: 6000 })
  })
})
