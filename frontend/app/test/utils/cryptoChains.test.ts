import { describe, expect, it } from "vitest"
import { formatChainName, normalizeCryptoChain } from "@/utils/cryptoChains"

describe("crypto chain identifiers", () => {
  it.each([
    ["ethereum", "1"],
    [" Ethereum ", "1"],
    ["binance-smart-chain", "56"],
    ["bsc", "56"],
    ["polygon", "137"],
    ["zksync-era", "324"],
    ["1", "1"],
    ["bitcoin", "bitcoin"],
    ["solana", "solana"],
    ["new-chain", "new-chain"],
    ["", null],
    [null, null],
    [undefined, null],
  ])("normalizes %s to %s", (input, expected) => {
    expect(normalizeCryptoChain(input)).toBe(expected)
  })

  it.each([
    ["1", "Ethereum"],
    ["ethereum", "Ethereum"],
    ["56", "BNB Chain"],
    ["binance-smart-chain", "BNB Chain"],
    ["42161", "Arbitrum"],
    ["324", "zkSync Era"],
    ["solana", "Solana"],
    ["litecoin", "Litecoin"],
    ["new-chain", "New Chain"],
    ["99999999", "99999999"],
  ])("labels %s as %s", (input, expected) => {
    expect(formatChainName(input)).toBe(expected)
  })
})
