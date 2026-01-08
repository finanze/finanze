import {
  AssetDistributionItem,
  OngoingProject,
  Dezimal,
  parseDezimalValue,
  ExchangeRates,
  WeightUnit,
  EntitiesPosition,
  ProductType,
  Crowdlending,
  ProductPosition,
  RealEstate,
} from "@/domain"

import {
  COMMODITY_SYMBOLS,
  WEIGHT_CONVERSIONS,
} from "@/domain/constants/commodity"

// Dashboard helpers (parity with frontend financialDataUtils)
export interface DashboardOptions {
  includePending: boolean
  includeCardExpenses: boolean
  includeRealEstate: boolean
  includeResidences: boolean
}

// Type guard to check if a product position has entries with at least one item
function hasEntries(
  product: ProductPosition | undefined | null,
): product is Exclude<ProductPosition, Crowdlending> {
  if (product === undefined || product === null) return false
  if (!("entries" in product)) return false
  const entries = (product as any).entries
  return Array.isArray(entries) && entries.length > 0
}

// Type guard for Crowdlending
function isCrowdlending(
  product: ProductPosition | undefined | null,
): product is Crowdlending {
  if (product === undefined || product === null) return false
  return "total" in product && (product as any).total != null
}

const getExchangeRateEntry = (
  exchangeRates: ExchangeRates | null | undefined,
  targetCurrency: string,
  key: string | null | undefined,
): Dezimal | null => {
  if (!exchangeRates || !targetCurrency || !key) return null

  const normalizedTarget = targetCurrency.toUpperCase()
  const targetCandidates = [
    exchangeRates[targetCurrency],
    exchangeRates[normalizedTarget],
    exchangeRates[targetCurrency.toLowerCase()],
  ]

  const variants = [key, key.toUpperCase(), key.toLowerCase()]

  for (const candidate of targetCandidates) {
    if (!candidate) continue
    for (const v of variants) {
      const raw = (candidate as any)[v]
      const dz = parseDezimalValue(raw)
      if (dz.isFinite() && !dz.isZero()) return dz
    }
  }

  return null
}

/**
 * Convert amount between currencies using exchange rates
 */
export function convertCurrency(
  amount: Dezimal | null | undefined,
  fromCurrency: string | null | undefined,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!amount || !amount.isFinite()) return Dezimal.zero()

  // Handle missing currency - assume target currency
  if (!fromCurrency) {
    return amount
  }

  if (fromCurrency.toUpperCase() === targetCurrency.toUpperCase()) {
    return amount
  }

  if (!exchangeRates) {
    // No exchange rates - return amount as-is (better than 0)
    return amount
  }

  const rateDz = getExchangeRateEntry(
    exchangeRates,
    targetCurrency,
    fromCurrency,
  )
  if (rateDz) {
    try {
      return amount.truediv(rateDz)
    } catch {
      return amount
    }
  }

  // No specific rate found - return amount as-is
  return amount
}

/**
 * Calculate crypto value from amount and symbol using exchange rates
 */
function calculateCryptoValue(
  amount: Dezimal,
  symbol: string,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!amount.isFinite() || amount.le(Dezimal.zero())) return Dezimal.zero()
  if (!symbol || !exchangeRates) return Dezimal.zero()

  const rateDz = getExchangeRateEntry(exchangeRates, targetCurrency, symbol)
  if (rateDz) {
    try {
      return amount.truediv(rateDz)
    } catch {
      return Dezimal.zero()
    }
  }

  return Dezimal.zero()
}

/**
 * Calculate commodity value from amount and symbol using exchange rates.
 * Handles unit conversion (market prices are in troy ounces).
 */
function calculateCommodityValue(
  amount: Dezimal,
  symbol: string,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
  unit: WeightUnit = WeightUnit.TROY_OUNCE,
): Dezimal {
  if (!amount.isFinite() || amount.le(Dezimal.zero())) return Dezimal.zero()
  if (!symbol || !exchangeRates) return amount

  // Convert amount to troy ounces since market prices are in troy ounces
  let amountInTroyOunces = amount
  if (unit === WeightUnit.GRAM) {
    const conversionFactor =
      WEIGHT_CONVERSIONS[WeightUnit.GRAM][WeightUnit.TROY_OUNCE]
    amountInTroyOunces = amount.mul(conversionFactor)
  }

  const rateDz = getExchangeRateEntry(exchangeRates, targetCurrency, symbol)
  if (rateDz) {
    try {
      return amountInTroyOunces.truediv(rateDz)
    } catch {
      return Dezimal.zero()
    }
  }

  console.warn(
    `No exchange rate found for commodity ${symbol} -> ${targetCurrency}`,
  )
  return amount
}

/**
 * Calculate the value of a crypto asset in target currency
 */
function calculateCryptoAssetValue(
  asset: any,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!asset) return Dezimal.zero()

  const symbol = asset.symbol?.toUpperCase()
  const contractAddressRaw = asset.contract_address ?? asset.contractAddress
  const contractAddress =
    typeof contractAddressRaw === "string" && contractAddressRaw.trim()
      ? contractAddressRaw.trim().toLowerCase()
      : null
  const amount = parseDezimalValue(asset.amount)

  // First try to compute value from amount and exchange-rate (address first)
  if (amount.gt(Dezimal.zero())) {
    if (contractAddress) {
      const computedByAddress = calculateCryptoValue(
        amount,
        `addr:${contractAddress}`,
        targetCurrency,
        exchangeRates,
      )
      if (computedByAddress.gt(Dezimal.zero())) {
        return computedByAddress
      }
    }

    if (symbol) {
      const computedValue = calculateCryptoValue(
        amount,
        symbol,
        targetCurrency,
        exchangeRates,
      )
      if (computedValue.gt(Dezimal.zero())) {
        return computedValue
      }
    }
  }

  // Fall back to backend-provided market_value if available
  if (asset.market_value != null) {
    const marketValue = parseDezimalValue(asset.market_value)
    if (marketValue.isFinite() && marketValue.gt(Dezimal.zero())) {
      const sourceCurrency = asset.currency || targetCurrency
      return convertCurrency(
        marketValue,
        sourceCurrency,
        targetCurrency,
        exchangeRates,
      )
    }
  }

  return Dezimal.zero()
}

/**
 * Calculate total value of all assets in a crypto wallet
 */
function calculateWalletAssetsValue(
  wallet: any,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!wallet) return Dezimal.zero()

  // Some payloads model wallets with `assets`, others return assets directly
  // under `products.CRYPTO.entries`. Support both shapes.
  const candidateArrays: any[] = []

  if (Array.isArray(wallet.assets)) candidateArrays.push(wallet.assets)
  if (Array.isArray(wallet.entries)) candidateArrays.push(wallet.entries)

  if (candidateArrays.length === 0) {
    // Treat wallet itself as an asset-like entry
    return calculateCryptoAssetValue(wallet, targetCurrency, exchangeRates)
  }

  return candidateArrays.flat().reduce((sum: Dezimal, asset: any) => {
    return sum.add(
      calculateCryptoAssetValue(asset, targetCurrency, exchangeRates),
    )
  }, Dezimal.zero())
}

/**
 * Format currency value for display
 */
export function formatCurrency(
  amount: Dezimal | null | undefined,
  currency: string,
  locale: string = "en-US",
): string {
  if (!amount || !amount.isFinite()) return "—"

  const rounded = amount.round(2)
  const asNumber = rounded.toNumber()
  if (!Number.isFinite(asNumber)) return "—"

  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(asNumber)
  } catch {
    return `${rounded.val.toFixed(2)} ${currency}`
  }
}

/**
 * Format percentage for display.
 * Backend stores percentages as decimals (0.07 = 7%), so we multiply by 100.
 */
export function formatPercentage(
  value: Dezimal | null | undefined,
  decimals: number = 1,
): string {
  if (!value || !value.isFinite()) return "—"

  const percentValue = value.val.mul(100)
  const sign = percentValue.isNegative() ? "" : "+"
  return `${sign}${percentValue.toFixed(decimals)}%`
}

/**
 * Format date for display
 */
export function formatDate(
  dateString: string,
  locale: string = "en-US",
): string {
  try {
    return new Date(dateString).toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return dateString
  }
}

export function formatDateTime(
  dateString: string,
  locale: string = "en-US",
): string {
  try {
    return new Date(dateString).toLocaleString(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return dateString
  }
}

/**
 * Get asset distribution from positions data
 */
export function getAssetDistribution(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
  pendingFlows?: any[] | null,
  realEstateList?: RealEstate[] | null,
): AssetDistributionItem[] {
  if (!positionsData?.positions) {
    return []
  }

  const assetTypes: Record<string, { type: string; value: Dezimal }> = {}
  let totalValue = Dezimal.zero()

  Object.values(positionsData.positions).forEach(entityPosition => {
    // Cash (accounts)
    const accounts = entityPosition.products?.[ProductType.ACCOUNT]
    if (hasEntries(accounts)) {
      const cashTotal = accounts.entries.reduce(
        (sum: Dezimal, account: any) => {
          const value = parseDezimalValue(account.total)
          const converted = convertCurrency(
            value,
            account.currency,
            targetCurrency,
            exchangeRates,
          )
          return sum.add(converted)
        },
        Dezimal.zero(),
      )

      if (cashTotal.gt(Dezimal.zero())) {
        if (!assetTypes["CASH"]) {
          assetTypes["CASH"] = { type: "CASH", value: Dezimal.zero() }
        }
        assetTypes["CASH"].value = assetTypes["CASH"].value.add(cashTotal)
        totalValue = totalValue.add(cashTotal)
      }
    }

    // Funds
    const funds = entityPosition.products?.[ProductType.FUND]
    if (hasEntries(funds)) {
      const fundsTotal = funds.entries.reduce((sum: Dezimal, fund: any) => {
        const value = parseDezimalValue(fund.market_value)
        const converted = convertCurrency(
          value,
          fund.currency,
          targetCurrency,
          exchangeRates,
        )
        return sum.add(converted)
      }, Dezimal.zero())

      if (fundsTotal.gt(Dezimal.zero())) {
        if (!assetTypes["FUND"]) {
          assetTypes["FUND"] = { type: "FUND", value: Dezimal.zero() }
        }
        assetTypes["FUND"].value = assetTypes["FUND"].value.add(fundsTotal)
        totalValue = totalValue.add(fundsTotal)
      }
    }

    // Stocks & ETFs
    const stocks = entityPosition.products?.[ProductType.STOCK_ETF]
    if (hasEntries(stocks)) {
      const stocksTotal = stocks.entries.reduce((sum: Dezimal, stock: any) => {
        const value = parseDezimalValue(stock.market_value)
        const converted = convertCurrency(
          value,
          stock.currency,
          targetCurrency,
          exchangeRates,
        )
        return sum.add(converted)
      }, Dezimal.zero())

      if (stocksTotal.gt(Dezimal.zero())) {
        if (!assetTypes["STOCK_ETF"]) {
          assetTypes["STOCK_ETF"] = {
            type: "STOCK_ETF",
            value: Dezimal.zero(),
          }
        }
        assetTypes["STOCK_ETF"].value =
          assetTypes["STOCK_ETF"].value.add(stocksTotal)
        totalValue = totalValue.add(stocksTotal)
      }
    }

    // Deposits
    const deposits = entityPosition.products?.[ProductType.DEPOSIT]
    if (hasEntries(deposits)) {
      const depositsTotal = deposits.entries.reduce(
        (sum: Dezimal, deposit: any) => {
          const value = parseDezimalValue(deposit.amount)
          const converted = convertCurrency(
            value,
            deposit.currency,
            targetCurrency,
            exchangeRates,
          )
          return sum.add(converted)
        },
        Dezimal.zero(),
      )

      if (depositsTotal.gt(Dezimal.zero())) {
        if (!assetTypes["DEPOSIT"]) {
          assetTypes["DEPOSIT"] = { type: "DEPOSIT", value: Dezimal.zero() }
        }
        assetTypes["DEPOSIT"].value =
          assetTypes["DEPOSIT"].value.add(depositsTotal)
        totalValue = totalValue.add(depositsTotal)
      }
    }

    // Real Estate CF
    const realEstateCf = entityPosition.products?.[ProductType.REAL_ESTATE_CF]
    if (hasEntries(realEstateCf)) {
      const reCfTotal = realEstateCf.entries.reduce((sum: Dezimal, re: any) => {
        const value = parseDezimalValue(re.pending_amount)
        const converted = convertCurrency(
          value,
          re.currency,
          targetCurrency,
          exchangeRates,
        )
        return sum.add(converted)
      }, Dezimal.zero())

      if (reCfTotal.gt(Dezimal.zero())) {
        if (!assetTypes["REAL_ESTATE_CF"]) {
          assetTypes["REAL_ESTATE_CF"] = {
            type: "REAL_ESTATE_CF",
            value: Dezimal.zero(),
          }
        }
        assetTypes["REAL_ESTATE_CF"].value =
          assetTypes["REAL_ESTATE_CF"].value.add(reCfTotal)
        totalValue = totalValue.add(reCfTotal)
      }
    }

    // Factoring
    const factoring = entityPosition.products?.[ProductType.FACTORING]
    if (hasEntries(factoring)) {
      const factoringTotal = factoring.entries.reduce(
        (sum: Dezimal, f: any) => {
          const value = parseDezimalValue(f.amount)
          const converted = convertCurrency(
            value,
            f.currency,
            targetCurrency,
            exchangeRates,
          )
          return sum.add(converted)
        },
        Dezimal.zero(),
      )

      if (factoringTotal.gt(Dezimal.zero())) {
        if (!assetTypes["FACTORING"]) {
          assetTypes["FACTORING"] = { type: "FACTORING", value: Dezimal.zero() }
        }
        assetTypes["FACTORING"].value =
          assetTypes["FACTORING"].value.add(factoringTotal)
        totalValue = totalValue.add(factoringTotal)
      }
    }

    // Crypto
    const crypto = entityPosition.products?.[ProductType.CRYPTO]
    if (hasEntries(crypto)) {
      crypto.entries.forEach((wallet: any) => {
        const walletValue = calculateWalletAssetsValue(
          wallet,
          targetCurrency,
          exchangeRates,
        )

        if (walletValue.gt(Dezimal.zero())) {
          if (!assetTypes["CRYPTO"]) {
            assetTypes["CRYPTO"] = { type: "CRYPTO", value: Dezimal.zero() }
          }
          assetTypes["CRYPTO"].value =
            assetTypes["CRYPTO"].value.add(walletValue)
          totalValue = totalValue.add(walletValue)
        }
      })
    }

    // Commodities
    const commodities = entityPosition.products?.[ProductType.COMMODITY]
    if (hasEntries(commodities)) {
      const commodityTotal = commodities.entries.reduce(
        (sum: Dezimal, c: any) => {
          // Prefer deriving from exchange rates (commodity symbol) when possible.
          const commodityTypeRaw = c?.type ?? c?.commodity ?? c?.commodity_type
          const commoditySymbol = (COMMODITY_SYMBOLS as any)[commodityTypeRaw]
          const amount = parseDezimalValue(c?.amount)
          const unit = (c?.unit as WeightUnit) ?? WeightUnit.TROY_OUNCE

          if (
            commoditySymbol &&
            amount.isFinite() &&
            amount.gt(Dezimal.zero())
          ) {
            const derived = calculateCommodityValue(
              amount,
              String(commoditySymbol).toUpperCase(),
              targetCurrency,
              exchangeRates,
              unit,
            )
            if (derived.gt(Dezimal.zero())) {
              return sum.add(derived)
            }
          }

          const value = parseDezimalValue(c?.market_value)
          const converted = convertCurrency(
            value,
            c?.currency || targetCurrency,
            targetCurrency,
            exchangeRates,
          )
          return sum.add(converted)
        },
        Dezimal.zero(),
      )

      if (commodityTotal.gt(Dezimal.zero())) {
        if (!assetTypes["COMMODITY"]) {
          assetTypes["COMMODITY"] = {
            type: "COMMODITY",
            value: Dezimal.zero(),
          }
        }
        assetTypes["COMMODITY"].value =
          assetTypes["COMMODITY"].value.add(commodityTotal)
        totalValue = totalValue.add(commodityTotal)
      }
    }

    // Real Estate is included separately via realEstateList (desktop parity)

    // Crowdlending (has 'total' property, not entries)
    const crowdlending = entityPosition.products?.[ProductType.CROWDLENDING]
    if (isCrowdlending(crowdlending)) {
      const value = parseDezimalValue(crowdlending.total)
      if (value.gt(Dezimal.zero())) {
        const converted = convertCurrency(
          value,
          crowdlending.currency || targetCurrency,
          targetCurrency,
          exchangeRates,
        )

        if (converted.gt(Dezimal.zero())) {
          if (!assetTypes["CROWDLENDING"]) {
            assetTypes["CROWDLENDING"] = {
              type: "CROWDLENDING",
              value: Dezimal.zero(),
            }
          }
          assetTypes["CROWDLENDING"].value =
            assetTypes["CROWDLENDING"].value.add(converted)
          totalValue = totalValue.add(converted)
        }
      }
    }

    // Bonds
    const bonds = entityPosition.products?.[ProductType.BOND]
    if (hasEntries(bonds)) {
      const bondTotal = bonds.entries.reduce((sum: Dezimal, bond: any) => {
        const value = parseDezimalValue(bond.market_value).isZero()
          ? parseDezimalValue(bond.nominal_value)
          : parseDezimalValue(bond.market_value)
        const converted = convertCurrency(
          value,
          bond.currency,
          targetCurrency,
          exchangeRates,
        )
        return sum.add(converted)
      }, Dezimal.zero())

      if (bondTotal.gt(Dezimal.zero())) {
        if (!assetTypes["BOND"]) {
          assetTypes["BOND"] = { type: "BOND", value: Dezimal.zero() }
        }
        assetTypes["BOND"].value = assetTypes["BOND"].value.add(bondTotal)
        totalValue = totalValue.add(bondTotal)
      }
    }

    // Derivatives
    const derivatives = entityPosition.products?.[ProductType.DERIVATIVE]
    if (hasEntries(derivatives)) {
      const derivativeTotal = derivatives.entries.reduce(
        (sum: Dezimal, d: any) => {
          const value = parseDezimalValue(d.market_value)
          const converted = convertCurrency(
            value,
            d.currency,
            targetCurrency,
            exchangeRates,
          )
          return sum.add(converted)
        },
        Dezimal.zero(),
      )

      if (derivativeTotal.gt(Dezimal.zero())) {
        if (!assetTypes["DERIVATIVE"]) {
          assetTypes["DERIVATIVE"] = {
            type: "DERIVATIVE",
            value: Dezimal.zero(),
          }
        }
        assetTypes["DERIVATIVE"].value =
          assetTypes["DERIVATIVE"].value.add(derivativeTotal)
        totalValue = totalValue.add(derivativeTotal)
      }
    }
  })

  // Pending flows (net future earnings). Desktop only shows it if net is positive.
  if (pendingFlows && pendingFlows.length > 0) {
    const pendingFlowsTotal = calculatePendingEarningsTotal(
      pendingFlows as any,
      targetCurrency,
      exchangeRates,
    )
    if (pendingFlowsTotal.gt(Dezimal.zero())) {
      if (!assetTypes["PENDING_FLOWS"]) {
        assetTypes["PENDING_FLOWS"] = {
          type: "PENDING_FLOWS",
          value: Dezimal.zero(),
        }
      }
      assetTypes["PENDING_FLOWS"].value =
        assetTypes["PENDING_FLOWS"].value.add(pendingFlowsTotal)
      totalValue = totalValue.add(pendingFlowsTotal)
    }
  }

  // Include Real Estate owned equity as its own asset category (market value - outstanding debt)
  if (realEstateList && realEstateList.length > 0) {
    const realEstateOwnedTotal = realEstateList.reduce((sum: Dezimal, re) => {
      const market = parseDezimalValue(re.valuationInfo?.estimatedMarketValue)

      const totalOutstanding = (re.flows || [])
        .filter(f => f.flowSubtype === "LOAN")
        .reduce((s: Dezimal, f) => {
          const principal = parseDezimalValue(
            (f.payload as any)?.principalOutstanding,
          )
          return s.add(principal)
        }, Dezimal.zero())

      const owned = market.sub(totalOutstanding)
      const ownedNonNeg = owned.lt(Dezimal.zero()) ? Dezimal.zero() : owned
      const converted = convertCurrency(
        ownedNonNeg,
        re.currency,
        targetCurrency,
        exchangeRates,
      )
      return sum.add(converted)
    }, Dezimal.zero())

    if (realEstateOwnedTotal.gt(Dezimal.zero())) {
      if (!assetTypes["REAL_ESTATE"]) {
        assetTypes["REAL_ESTATE"] = {
          type: "REAL_ESTATE",
          value: Dezimal.zero(),
        }
      }
      assetTypes["REAL_ESTATE"].value =
        assetTypes["REAL_ESTATE"].value.add(realEstateOwnedTotal)
      totalValue = totalValue.add(realEstateOwnedTotal)
    }
  }

  // Calculate percentages and sort by value
  return Object.values(assetTypes)
    .map(item => ({
      ...item,
      percentage: totalValue.gt(Dezimal.zero())
        ? item.value.truediv(totalValue).mul(Dezimal.fromInt(100)).round(1)
        : Dezimal.zero(),
    }))
    .sort((a, b) => (a.value.lt(b.value) ? 1 : a.value.gt(b.value) ? -1 : 0))
}

export interface EntityDistributionItem {
  name: string
  id: string
  value: Dezimal
  percentage: Dezimal
}

/**
 * Get entity distribution from positions data.
 * This groups values by entity.
 * Note: COMMODITY is shown as a separate fake entity (entity-agnostic),
 * while CRYPTO is attributed to each entity (wallet/provider) like any other product.
 */
export function getEntityDistribution(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
  pendingFlows?: any[] | null,
  realEstateList?: RealEstate[] | null,
): EntityDistributionItem[] {
  if (!positionsData?.positions) {
    return []
  }

  const entityValues: Record<
    string,
    { name: string; id: string; value: Dezimal }
  > = {}
  let totalValue = Dezimal.zero()

  // Track commodity separately as fake entity
  let totalCommodityValue = Dezimal.zero()
  let totalRealEstateValue = Dezimal.zero()

  // Important: group by actual entity UUID (web parity). The `positions` record key
  // is not guaranteed to be the entity UUID and may collide.
  Object.entries(positionsData.positions).forEach(
    ([positionKey, entityPosition]) => {
      const entityName = entityPosition.entity?.name || positionKey
      const resolvedEntityId = entityPosition.entity?.id || positionKey
      let entityTotal = Dezimal.zero()

      // Helper to sum entries with market_value, total, amount, etc.
      const sumEntriesValue = (product: any) => {
        if (!hasEntries(product)) return
        product.entries.forEach((entry: any) => {
          let value = Dezimal.zero()
          if (entry.total != null) {
            value = parseDezimalValue(entry.total)
          } else if (entry.market_value != null) {
            value = parseDezimalValue(entry.market_value)
          } else if (entry.pending_amount != null) {
            value = parseDezimalValue(entry.pending_amount)
          } else if (entry.value != null) {
            value = parseDezimalValue(entry.value)
          } else if (entry.amount != null) {
            value = parseDezimalValue(entry.amount)
          }
          const converted = convertCurrency(
            value,
            entry.currency,
            targetCurrency,
            exchangeRates,
          )
          entityTotal = entityTotal.add(converted)
        })
      }

      // Explicitly handle each product type (web parity - no FUND_PORTFOLIO, BOND, DERIVATIVE, LOAN, CARD)
      // This avoids double-counting from FUND_PORTFOLIO which wraps FUND entries.

      // Accounts (cash)
      sumEntriesValue(entityPosition.products?.[ProductType.ACCOUNT])

      // Funds
      sumEntriesValue(entityPosition.products?.[ProductType.FUND])

      // Stocks & ETFs
      sumEntriesValue(entityPosition.products?.[ProductType.STOCK_ETF])

      // Deposits
      sumEntriesValue(entityPosition.products?.[ProductType.DEPOSIT])

      // Real Estate CF
      sumEntriesValue(entityPosition.products?.[ProductType.REAL_ESTATE_CF])

      // Factoring
      sumEntriesValue(entityPosition.products?.[ProductType.FACTORING])

      // Crowdlending (has 'total' property, not entries)
      const crowdlending = entityPosition.products?.[ProductType.CROWDLENDING]
      if (isCrowdlending(crowdlending)) {
        const value = parseDezimalValue(crowdlending.total)
        const converted = convertCurrency(
          value,
          crowdlending.currency,
          targetCurrency,
          exchangeRates,
        )
        entityTotal = entityTotal.add(converted)
      }

      // Crypto - attribute to this entity (wallet/provider)
      const cryptoProduct = entityPosition.products?.[ProductType.CRYPTO]
      if (hasEntries(cryptoProduct)) {
        cryptoProduct.entries.forEach((wallet: any) => {
          entityTotal = entityTotal.add(
            calculateWalletAssetsValue(wallet, targetCurrency, exchangeRates),
          )
        })
      }

      // Commodity - track separately as fake entity (not added to entityTotal)
      const commodityProduct = entityPosition.products?.[ProductType.COMMODITY]
      if (hasEntries(commodityProduct)) {
        commodityProduct.entries.forEach((entry: any) => {
          const commodityTypeRaw =
            entry?.type ?? entry?.commodity ?? entry?.commodity_type
          const commoditySymbol = (COMMODITY_SYMBOLS as any)[commodityTypeRaw]
          const amount = parseDezimalValue(entry?.amount)
          const unit = (entry?.unit as WeightUnit) ?? WeightUnit.TROY_OUNCE

          if (
            commoditySymbol &&
            amount.isFinite() &&
            amount.gt(Dezimal.zero())
          ) {
            const derived = calculateCommodityValue(
              amount,
              String(commoditySymbol).toUpperCase(),
              targetCurrency,
              exchangeRates,
              unit,
            )
            if (derived.gt(Dezimal.zero())) {
              totalCommodityValue = totalCommodityValue.add(derived)
              return
            }
          }

          const value = parseDezimalValue(entry?.market_value)
          const converted = convertCurrency(
            value,
            entry?.currency || targetCurrency,
            targetCurrency,
            exchangeRates,
          )
          totalCommodityValue = totalCommodityValue.add(converted)
        })
      }

      if (entityTotal.gt(Dezimal.zero())) {
        const existing = entityValues[resolvedEntityId]
        if (existing) {
          existing.value = existing.value.add(entityTotal)
        } else {
          entityValues[resolvedEntityId] = {
            name: entityName,
            id: resolvedEntityId,
            value: entityTotal,
          }
        }
        totalValue = totalValue.add(entityTotal)
      }
    },
  )

  // Add REAL_ESTATE as a fake entity (desktop parity)
  if (realEstateList && realEstateList.length > 0) {
    totalRealEstateValue = realEstateList.reduce((sum: Dezimal, re) => {
      const market = parseDezimalValue(re.valuationInfo?.estimatedMarketValue)
      const totalOutstanding = (re.flows || [])
        .filter(f => f.flowSubtype === "LOAN")
        .reduce((s: Dezimal, f) => {
          const principal = parseDezimalValue(
            (f.payload as any)?.principalOutstanding,
          )
          return s.add(principal)
        }, Dezimal.zero())
      const owned = market.sub(totalOutstanding)
      const ownedNonNeg = owned.lt(Dezimal.zero()) ? Dezimal.zero() : owned
      const converted = convertCurrency(
        ownedNonNeg,
        re.currency,
        targetCurrency,
        exchangeRates,
      )
      return sum.add(converted)
    }, Dezimal.zero())

    if (totalRealEstateValue.gt(Dezimal.zero())) {
      entityValues["real-estate"] = {
        name: "REAL_ESTATE",
        id: "real-estate",
        value: totalRealEstateValue,
      }
      totalValue = totalValue.add(totalRealEstateValue)
    }
  }

  // Add COMMODITY as a fake entity
  if (totalCommodityValue.gt(Dezimal.zero())) {
    entityValues["commodity"] = {
      name: "COMMODITY",
      id: "commodity",
      value: totalCommodityValue,
    }
    totalValue = totalValue.add(totalCommodityValue)
  }

  // Calculate percentages and sort by value
  return Object.values(entityValues)
    .map(item => ({
      ...item,
      percentage: totalValue.gt(Dezimal.zero())
        ? item.value.truediv(totalValue).mul(Dezimal.fromInt(100)).round(1)
        : Dezimal.zero(),
    }))
    .sort((a, b) => (a.value.lt(b.value) ? 1 : a.value.gt(b.value) ? -1 : 0))
}

/**
 * Get total net worth from positions
 */
export function getTotalNetWorth(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
  pendingFlows?: any[] | null,
  realEstateList?: RealEstate[] | null,
  options?: DashboardOptions,
): Dezimal {
  const totalAssets = getTotalAssets(
    positionsData,
    targetCurrency,
    exchangeRates,
    options?.includePending === false ? [] : (pendingFlows as any[]) || [],
  )

  const filteredRealEstateList = filterRealEstateByOptions(
    (realEstateList as any) || [],
    options || {
      includePending: true,
      includeCardExpenses: false,
      includeRealEstate: true,
      includeResidences: false,
    },
  )

  const equity =
    options?.includeRealEstate === false
      ? Dezimal.zero()
      : getRealEstateOwnedEquityTotal(
          filteredRealEstateList,
          targetCurrency,
          exchangeRates,
        )

  const cardUsed = options?.includeCardExpenses
    ? getTotalCardUsed(positionsData, targetCurrency, exchangeRates)
    : Dezimal.zero()

  // Net worth should not consider loans as liabilities.
  // Real-estate equity already subtracts associated loans from the real-estate payload.
  return totalAssets.add(equity).sub(cardUsed)
}

export function filterRealEstateByOptions(
  realEstateList: RealEstate[] | null | undefined,
  options: DashboardOptions,
): RealEstate[] {
  if (!options.includeRealEstate) return []
  if (options.includeResidences) return realEstateList || []
  return (realEstateList || []).filter(re => !re.basicInfo?.isResidence)
}

export function calculatePendingEarningsTotal(
  pendingFlows: any[],
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!pendingFlows || pendingFlows.length === 0) return Dezimal.zero()

  const now = new Date()

  return pendingFlows
    .filter(flow => flow?.enabled)
    .filter(flow => {
      if (!flow?.date) return true
      const flowDate = new Date(flow.date)
      return flowDate >= now
    })
    .reduce((total: Dezimal, flow) => {
      const amount = parseDezimalValue(flow.amount)
      const convertedAmount = convertCurrency(
        amount,
        flow.currency,
        targetCurrency,
        exchangeRates,
      )
      return flow.flowType === "EARNING" || flow.flow_type === "EARNING"
        ? total.add(convertedAmount)
        : total.sub(convertedAmount)
    }, Dezimal.zero())
}

export function getTotalCardUsed(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!positionsData?.positions) return Dezimal.zero()
  let total = Dezimal.zero()
  Object.values(positionsData.positions).forEach((entityPosition: any) => {
    const cardsProduct = entityPosition.products?.[ProductType.CARD]
    if (cardsProduct?.entries) {
      cardsProduct.entries.forEach((card: any) => {
        total = total.add(
          convertCurrency(
            parseDezimalValue(card.used),
            card.currency,
            targetCurrency,
            exchangeRates,
          ),
        )
      })
    }
  })
  return total
}

export function getRealEstateOwnedEquityTotal(
  realEstateList: RealEstate[] | undefined,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!realEstateList || realEstateList.length === 0) return Dezimal.zero()
  return realEstateList.reduce((sum: Dezimal, re) => {
    const market = parseDezimalValue(re.valuationInfo?.estimatedMarketValue)
    const totalOutstanding = (re.flows || [])
      .filter(f => f.flowSubtype === "LOAN")
      .reduce((s: Dezimal, f) => {
        const principal = parseDezimalValue(
          (f.payload as any)?.principalOutstanding,
        )
        return s.add(principal)
      }, Dezimal.zero())
    const owned = market.sub(totalOutstanding)
    const ownedNonNeg = owned.lt(Dezimal.zero()) ? Dezimal.zero() : owned
    const converted = convertCurrency(
      ownedNonNeg,
      re.currency,
      targetCurrency,
      exchangeRates,
    )
    return sum.add(converted)
  }, Dezimal.zero())
}

export function getRealEstateInitialInvestmentTotal(
  realEstateList: RealEstate[] | undefined,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!realEstateList || realEstateList.length === 0) return Dezimal.zero()

  return realEstateList.reduce((sum: Dezimal, re) => {
    const purchasePrice = parseDezimalValue(re.purchaseInfo?.price)
    const purchaseExpenses = (re.purchaseInfo?.expenses || []).reduce(
      (expenseSum: Dezimal, expense: any) =>
        expenseSum.add(parseDezimalValue(expense?.amount)),
      Dezimal.zero(),
    )

    const financedAmount = (re.flows || [])
      .filter(flow => flow.flowSubtype === "LOAN")
      .reduce((loanSum: Dezimal, flow) => {
        const payload: any = flow.payload as any
        const loanValue =
          payload?.loanAmount != null
            ? parseDezimalValue(payload.loanAmount)
            : parseDezimalValue(payload?.principalOutstanding)
        return loanSum.add(loanValue)
      }, Dezimal.zero())

    const invested = purchasePrice.add(purchaseExpenses).sub(financedAmount)
    const investedNonNeg = invested.lt(Dezimal.zero())
      ? Dezimal.zero()
      : invested
    const converted = convertCurrency(
      investedNonNeg,
      re.currency,
      targetCurrency,
      exchangeRates,
    )
    return sum.add(converted)
  }, Dezimal.zero())
}

export function getTotalAssets(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
  pendingFlows: any[],
): Dezimal {
  if (!positionsData?.positions) return Dezimal.zero()

  let total = Dezimal.zero()
  const distribution = getAssetDistribution(
    positionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
    [],
  )
  total = total.add(
    distribution.reduce((sum, item) => sum.add(item.value), Dezimal.zero()),
  )
  return total
}

export function getTotalLiabilities(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): Dezimal {
  if (!positionsData?.positions) return Dezimal.zero()

  let total = Dezimal.zero()
  Object.values(positionsData.positions).forEach((entityPosition: any) => {
    const loans = entityPosition.products?.[ProductType.LOAN]
    if (loans?.entries) {
      loans.entries.forEach((loan: any) => {
        const value = parseDezimalValue(loan.current_debt)
        const valueFallback = value.isZero()
          ? parseDezimalValue(loan.pending_capital)
          : value
        const valueFallback2 = valueFallback.isZero()
          ? parseDezimalValue(loan.principal_outstanding)
          : valueFallback
        const valueFallback3 = valueFallback2.isZero()
          ? parseDezimalValue(loan.principalOutstanding)
          : valueFallback2
        total = total.add(
          convertCurrency(
            valueFallback3,
            loan.currency,
            targetCurrency,
            exchangeRates,
          ),
        )
      })
    }

    const cards = entityPosition.products?.[ProductType.CARD]
    if (cards?.entries) {
      cards.entries.forEach((card: any) => {
        total = total.add(
          convertCurrency(
            parseDezimalValue(card.current_balance),
            card.currency,
            targetCurrency,
            exchangeRates,
          ),
        )
      })
    }
  })

  return total
}

/**
 * Get ongoing investment projects (deposits, real estate CF, factoring)
 */
export function getOngoingProjects(
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
): OngoingProject[] {
  if (!positionsData?.positions) {
    return []
  }

  const projects: OngoingProject[] = []

  Object.values(positionsData.positions).forEach(entityPosition => {
    const entityName = entityPosition.entity?.name || "Unknown"

    // Deposits
    const deposits = entityPosition.products?.[ProductType.DEPOSIT]
    if (hasEntries(deposits)) {
      deposits.entries.forEach((deposit: any) => {
        projects.push({
          name: deposit.name || "Deposit",
          type: "DEPOSIT",
          value: parseDezimalValue(deposit.amount),
          currency: deposit.currency,
          roi: parseDezimalValue(deposit.interest_rate),
          maturity: deposit.maturity,
          entity: entityName,
        })
      })
    }

    // Real Estate CF
    const realEstateCf = entityPosition.products?.[ProductType.REAL_ESTATE_CF]
    if (hasEntries(realEstateCf)) {
      realEstateCf.entries.forEach((re: any) => {
        projects.push({
          name: re.name || "Real Estate Project",
          type: "REAL_ESTATE_CF",
          value: parseDezimalValue(re.pending_amount),
          currency: re.currency,
          roi: parseDezimalValue(re.interest_rate),
          maturity: re.maturity,
          entity: entityName,
          extendedMaturity: re.extended_maturity || null,
          lateInterestRate: re.late_interest_rate
            ? parseDezimalValue(re.late_interest_rate)
            : null,
        })
      })
    }

    // Factoring
    const factoring = entityPosition.products?.[ProductType.FACTORING]
    if (hasEntries(factoring)) {
      factoring.entries.forEach((f: any) => {
        projects.push({
          name: f.name || "Factoring",
          type: "FACTORING",
          value: parseDezimalValue(f.amount),
          currency: f.currency,
          roi: parseDezimalValue(f.interest_rate),
          maturity: f.maturity,
          entity: entityName,
          extendedMaturity: f.extended_maturity || null,
          lateInterestRate: f.late_interest_rate
            ? parseDezimalValue(f.late_interest_rate)
            : null,
        })
      })
    }
  })

  // Sort by days remaining (using getDaysStatus logic inline)
  return projects.sort((a, b) => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    const getEffectiveDays = (project: OngoingProject): number => {
      const baseDate = new Date(project.maturity)
      if (Number.isNaN(baseDate.getTime())) return Infinity
      baseDate.setHours(0, 0, 0, 0)

      const msPerDay = 1000 * 60 * 60 * 24
      let diffDays = Math.ceil(
        (baseDate.getTime() - today.getTime()) / msPerDay,
      )

      // If past maturity and has extended maturity, use that instead
      if (diffDays <= 0 && project.extendedMaturity) {
        const extDate = new Date(project.extendedMaturity)
        if (!Number.isNaN(extDate.getTime())) {
          extDate.setHours(0, 0, 0, 0)
          diffDays = Math.ceil((extDate.getTime() - today.getTime()) / msPerDay)
        }
      }
      return diffDays
    }

    return getEffectiveDays(a) - getEffectiveDays(b)
  })
}

/**
 * Get days status for an investment project
 */
export interface DaysStatus {
  days: number
  isDelayed: boolean
  statusText: string
  usedExtendedMaturity: boolean
}

export function getDaysStatus(
  dateString: string,
  extendedMaturity?: string | null,
): DaysStatus {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const parseDate = (value?: string | null): Date | null => {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return null
    date.setHours(0, 0, 0, 0)
    return date
  }

  const baseDate = parseDate(dateString)
  if (!baseDate) {
    return {
      days: 0,
      isDelayed: false,
      statusText: "0d",
      usedExtendedMaturity: false,
    }
  }

  const msPerDay = 1000 * 60 * 60 * 24
  const diffFromToday = (target: Date) =>
    Math.ceil((target.getTime() - today.getTime()) / msPerDay)

  let diffDays = diffFromToday(baseDate)
  let usedExtended = false

  if (diffDays <= 0 && extendedMaturity) {
    const extendedDate = parseDate(extendedMaturity)
    if (extendedDate) {
      diffDays = diffFromToday(extendedDate)
      usedExtended = true
    }
  }

  const isDelayed = diffDays < 0
  const absDiffDays = Math.abs(diffDays)

  return {
    days: absDiffDays,
    isDelayed,
    statusText: `${absDiffDays}d`,
    usedExtendedMaturity: usedExtended,
  }
}
