import { describe, it, expect } from "vitest"

import {
  calculateCryptoAssetValue,
  getCryptoRateKey,
} from "@/utils/financialDataUtils"
import {
  CryptoCurrencyType,
  type CryptoCurrencyPosition,
} from "@/types/position"
import { DataSource } from "@/types"
import type { ExchangeRates } from "@/types"

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
