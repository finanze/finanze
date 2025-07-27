import {
  EntitiesPosition,
  ProductType,
  COMMODITY_SYMBOLS,
  CommodityType,
  WEIGHT_CONVERSIONS,
  WeightUnit,
} from "@/types/position"
import { TransactionsResult, TxType } from "@/types/transactions"
import { formatCurrency, formatDate, formatGainLoss } from "@/lib/formatters"
import { ExchangeRates, PendingFlow } from "@/types"

export const convertCurrency = (
  amount: number,
  fromCurrency: string,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null,
): number => {
  if (!exchangeRates || fromCurrency === targetCurrency) {
    return amount
  }

  if (
    exchangeRates[targetCurrency] &&
    exchangeRates[targetCurrency][fromCurrency]
  ) {
    return amount / exchangeRates[targetCurrency][fromCurrency]
  }

  console.warn(
    `No exchange rate found for ${fromCurrency} -> ${targetCurrency}`,
  )
  return amount
}

export const calculateCryptoValue = (
  amount: number,
  symbol: string,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
): number => {
  if (!exchangeRates || !amount || amount <= 0) {
    return 0
  }

  if (exchangeRates[targetCurrency] && exchangeRates[targetCurrency][symbol]) {
    const cryptoPrice = exchangeRates[targetCurrency][symbol]
    return amount / cryptoPrice
  }

  console.warn(
    `No exchange rate found for cryptocurrency ${symbol} -> ${targetCurrency}`,
  )
  return 0
}

export const calculateCommodityValue = (
  amount: number,
  symbol: string,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
  unit: WeightUnit = WeightUnit.TROY_OUNCE,
): number => {
  if (!exchangeRates || !amount || amount <= 0) {
    return 0
  }

  // Convert amount to troy ounces since market prices are in troy ounces
  let amountInTroyOunces = amount
  if (unit === WeightUnit.GRAM) {
    amountInTroyOunces =
      amount * WEIGHT_CONVERSIONS[WeightUnit.GRAM][WeightUnit.TROY_OUNCE]
  }

  if (exchangeRates[targetCurrency] && exchangeRates[targetCurrency][symbol]) {
    const commodityPrice = exchangeRates[targetCurrency][symbol]
    return amountInTroyOunces / commodityPrice
  }

  console.warn(
    `No exchange rate found for commodity ${symbol} -> ${targetCurrency}`,
  )
  return 0
}

export const convertWeight = (
  amount: number,
  fromUnit: WeightUnit,
  toUnit: WeightUnit,
): number => {
  if (fromUnit === toUnit) {
    return amount
  }

  if (WEIGHT_CONVERSIONS[fromUnit] && WEIGHT_CONVERSIONS[fromUnit][toUnit]) {
    return amount * WEIGHT_CONVERSIONS[fromUnit][toUnit]
  }

  console.warn(`No weight conversion found for ${fromUnit} -> ${toUnit}`)
  return amount
}

export const convertCommodityAmountToDisplayUnit = (
  amount: number,
  originalUnit: WeightUnit,
  displayUnit: WeightUnit,
): number => {
  return convertWeight(amount, originalUnit, displayUnit)
}

export const getTransactionDisplayType = (txType: TxType): "in" | "out" => {
  if (
    [
      TxType.BUY,
      TxType.INVESTMENT,
      TxType.SUBSCRIPTION,
      TxType.SWAP_FROM,
      TxType.SWAP_TO,
    ].includes(txType)
  ) {
    return "out"
  } else {
    return "in"
  }
}

export interface AssetDistributionItem {
  type: string
  value: number
  percentage: number
  change: number
}

export interface EntityDistributionItem {
  name: string
  value: number
  percentage: number
  id: string
}

export interface OngoingProject {
  name: string
  type: string
  value: number
  currency: string
  formattedValue: string
  roi: number
  maturity: string
  entity: string
}

export interface StockFundPosition {
  symbol: string
  name: string
  portfolioName?: string | null
  shares: number
  price: number
  value: number
  originalValue: number
  currency: string
  formattedValue: string
  formattedOriginalValue: string
  type: string
  change: number
  entity: string
  percentageOfTotalVariableRent: number
  percentageOfTotalPortfolio: number
  id: string
  isin?: string
  gainLossAmount?: number
  formattedGainLossAmount?: string
}

export interface CryptoPosition {
  symbol: string
  name: string
  address: string
  amount: number
  price: number
  value: number
  currency: string
  formattedValue: string
  type: string
  change: number
  entities: string[]
  showEntityBadge: boolean
  percentageOfTotalVariableRent: number
  percentageOfTotalPortfolio: number
  id: string
  tokens?: {
    symbol: string
    name: string
    amount: number
    value: number
    formattedValue: string
  }[]
}

export interface CommodityPosition {
  symbol: string
  name: string
  type: string
  amount: number
  unit: string
  price: number
  value: number
  currency: string
  formattedValue: string
  change: number
  entities: string[]
  showEntityBadge: boolean
  percentageOfTotalVariableRent: number
  percentageOfTotalPortfolio: number
  id: string
}

export interface GroupedTransaction {
  date: string
  description: string
  amount: number
  currency: string
  formattedAmount: string
  type: TxType
  product_type: string
  displayType: "in" | "out"
  entity: string
}

export const getAssetDistribution = (
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
  pendingFlows?: any[],
): AssetDistributionItem[] => {
  if (!positionsData || !positionsData.positions) return []

  const assetTypes: Record<
    string,
    { type: string; value: number; percentage: number; change: number }
  > = {}
  let totalValue = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const accountsProduct = entityPosition.products[ProductType.ACCOUNT]
    if (
      accountsProduct &&
      "entries" in accountsProduct &&
      accountsProduct.entries.length > 0
    ) {
      const accountsTotal = accountsProduct.entries.reduce(
        (sum: number, account: any) => {
          const accountTotal = account.total || 0
          const convertedTotal =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  accountTotal,
                  account.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : accountTotal
          return sum + convertedTotal
        },
        0,
      )
      if (accountsTotal > 0) {
        if (!assetTypes["CASH"]) {
          assetTypes["CASH"] = {
            type: "CASH",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["CASH"].value += accountsTotal
        totalValue += accountsTotal
      }
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      if (!assetTypes["FUND"]) {
        assetTypes["FUND"] = {
          type: "FUND",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const fundsMarketValue = fundsProduct.entries.reduce(
        (sum: number, fund: any) => {
          const marketValue = fund.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  fund.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      assetTypes["FUND"].value += fundsMarketValue
      totalValue += fundsMarketValue
    }

    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      if (!assetTypes["STOCK_ETF"]) {
        assetTypes["STOCK_ETF"] = {
          type: "STOCK_ETF",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const stocksMarketValue = stocksProduct.entries.reduce(
        (sum: number, stock: any) => {
          const marketValue = stock.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  stock.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      assetTypes["STOCK_ETF"].value += stocksMarketValue
      totalValue += stocksMarketValue
    }

    const depositsProduct = entityPosition.products[ProductType.DEPOSIT]
    if (
      depositsProduct &&
      "entries" in depositsProduct &&
      depositsProduct.entries.length > 0
    ) {
      if (!assetTypes["DEPOSIT"]) {
        assetTypes["DEPOSIT"] = {
          type: "DEPOSIT",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const depositsTotal = depositsProduct.entries.reduce(
        (sum: number, deposit: any) => {
          const amount = deposit.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  deposit.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      assetTypes["DEPOSIT"].value += depositsTotal
      totalValue += depositsTotal
    }

    const realEstateCfProduct =
      entityPosition.products[ProductType.REAL_ESTATE_CF]
    if (
      realEstateCfProduct &&
      "entries" in realEstateCfProduct &&
      realEstateCfProduct.entries.length > 0
    ) {
      if (!assetTypes["REAL_ESTATE_CF"]) {
        assetTypes["REAL_ESTATE_CF"] = {
          type: "REAL_ESTATE_CF",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const realEstateCfTotal = realEstateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.pending_amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  project.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      assetTypes["REAL_ESTATE_CF"].value += realEstateCfTotal
      totalValue += realEstateCfTotal
    }

    const factoringProduct = entityPosition.products[ProductType.FACTORING]
    if (
      factoringProduct &&
      "entries" in factoringProduct &&
      factoringProduct.entries.length > 0
    ) {
      if (!assetTypes["FACTORING"]) {
        assetTypes["FACTORING"] = {
          type: "FACTORING",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const factoringTotal = factoringProduct.entries.reduce(
        (sum: number, factoring: any) => {
          const amount = factoring.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  factoring.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      assetTypes["FACTORING"].value += factoringTotal
      totalValue += factoringTotal
    }

    const crowdlendingProduct =
      entityPosition.products[ProductType.CROWDLENDING]
    if (
      crowdlendingProduct &&
      "total" in crowdlendingProduct &&
      crowdlendingProduct.total
    ) {
      if (!assetTypes["CROWDLENDING"]) {
        assetTypes["CROWDLENDING"] = {
          type: "CROWDLENDING",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const crowdlendingTotal = crowdlendingProduct.total
      const convertedCrowdlendingTotal =
        targetCurrency && exchangeRates
          ? convertCurrency(
              crowdlendingTotal,
              crowdlendingProduct.currency,
              targetCurrency,
              exchangeRates,
            )
          : crowdlendingTotal
      assetTypes["CROWDLENDING"].value += convertedCrowdlendingTotal
      totalValue += convertedCrowdlendingTotal
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      if (!assetTypes["CRYPTO"]) {
        assetTypes["CRYPTO"] = {
          type: "CRYPTO",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }

      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          targetCurrency,
          exchangeRates,
        )
        assetTypes["CRYPTO"].value += walletValue
        totalValue += walletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenValue = calculateCryptoValue(
              token.amount,
              token.symbol,
              targetCurrency,
              exchangeRates,
            )
            assetTypes["CRYPTO"].value += tokenValue
            totalValue += tokenValue
          })
        }
      })
    }

    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      if (!assetTypes["COMMODITY"]) {
        assetTypes["COMMODITY"] = {
          type: "COMMODITY",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }

      const commodityTotal = commodityProduct.entries.reduce(
        (sum: number, commodity: any) => {
          const commoditySymbol =
            COMMODITY_SYMBOLS[commodity.type as CommodityType]
          const commodityValue = calculateCommodityValue(
            commodity.amount,
            commoditySymbol,
            targetCurrency,
            exchangeRates,
            commodity.unit,
          )
          return sum + commodityValue
        },
        0,
      )
      assetTypes["COMMODITY"].value += commodityTotal
      totalValue += commodityTotal
    }
  })

  // Add pending flows if provided (both earnings and expenses)
  if (pendingFlows && pendingFlows.length > 0) {
    const pendingFlowsTotal = calculatePendingEarningsTotal(
      pendingFlows,
      targetCurrency,
      exchangeRates,
    )

    // Only show pending flows as a category if they're positive (net earnings)
    if (pendingFlowsTotal > 0) {
      assetTypes["PENDING_FLOWS"] = {
        type: "PENDING_FLOWS",
        value: pendingFlowsTotal, // Use actual positive value
        percentage: 0,
        change: 0,
      }
      totalValue += pendingFlowsTotal
    }
  }
  Object.values(assetTypes).forEach(asset => {
    asset.percentage =
      totalValue > 0 ? Math.round((asset.value / totalValue) * 100) : 0
  })

  return Object.values(assetTypes).sort((a, b) => b.value - a.value)
}

export const getEntityDistribution = (
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
  pendingFlows?: any[],
): EntityDistributionItem[] => {
  if (!positionsData || !positionsData.positions) return []

  const entities: Record<
    string,
    { name: string; value: number; percentage: number; id: string }
  > = {}
  let totalValue = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const entityName = entityPosition.entity?.name || "Unknown Entity"
    const entityId = entityPosition.entity?.id || "unknown"

    let entityTotal = 0

    const accountsProduct = entityPosition.products[ProductType.ACCOUNT]
    if (
      accountsProduct &&
      "entries" in accountsProduct &&
      accountsProduct.entries.length > 0
    ) {
      const accountsTotal = accountsProduct.entries.reduce(
        (sum: number, account: any) => {
          const accountTotal = account.total || 0
          const convertedTotal =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  accountTotal,
                  account.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : accountTotal
          return sum + convertedTotal
        },
        0,
      )
      entityTotal += accountsTotal
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      const fundsMarketValue = fundsProduct.entries.reduce(
        (sum: number, fund: any) => {
          const marketValue = fund.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  fund.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      entityTotal += fundsMarketValue
    }

    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      const stocksMarketValue = stocksProduct.entries.reduce(
        (sum: number, stock: any) => {
          const marketValue = stock.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  stock.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      entityTotal += stocksMarketValue
    }

    const depositsProduct = entityPosition.products[ProductType.DEPOSIT]
    if (
      depositsProduct &&
      "entries" in depositsProduct &&
      depositsProduct.entries.length > 0
    ) {
      const depositsTotal = depositsProduct.entries.reduce(
        (sum: number, deposit: any) => {
          const amount = deposit.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  deposit.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      entityTotal += depositsTotal
    }

    const realEstateCfProduct =
      entityPosition.products[ProductType.REAL_ESTATE_CF]
    if (
      realEstateCfProduct &&
      "entries" in realEstateCfProduct &&
      realEstateCfProduct.entries.length > 0
    ) {
      const realEstateCfTotal = realEstateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.pending_amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  project.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      entityTotal += realEstateCfTotal
    }

    const factoringProduct = entityPosition.products[ProductType.FACTORING]
    if (
      factoringProduct &&
      "entries" in factoringProduct &&
      factoringProduct.entries.length > 0
    ) {
      const factoringTotal = factoringProduct.entries.reduce(
        (sum: number, factoring: any) => {
          const amount = factoring.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  factoring.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      entityTotal += factoringTotal
    }

    const crowdlendingProduct =
      entityPosition.products[ProductType.CROWDLENDING]
    if (
      crowdlendingProduct &&
      "total" in crowdlendingProduct &&
      crowdlendingProduct.total
    ) {
      const amount = crowdlendingProduct.total
      const convertedAmount =
        targetCurrency && exchangeRates
          ? convertCurrency(
              amount,
              crowdlendingProduct.currency,
              targetCurrency,
              exchangeRates,
            )
          : amount
      entityTotal += convertedAmount
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          targetCurrency,
          exchangeRates,
        )
        entityTotal += walletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenValue = calculateCryptoValue(
              token.amount,
              token.symbol,
              targetCurrency,
              exchangeRates,
            )
            entityTotal += tokenValue
          })
        }
      })
    }

    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        const commoditySymbol =
          COMMODITY_SYMBOLS[commodity.type as CommodityType]
        const commodityValue = calculateCommodityValue(
          commodity.amount,
          commoditySymbol,
          targetCurrency,
          exchangeRates,
          commodity.unit,
        )
        entityTotal += commodityValue
      })
    }

    if (entityTotal > 0) {
      entities[entityId] = {
        name: entityName,
        value: entityTotal,
        percentage: 0,
        id: entityId,
      }
      totalValue += entityTotal
    }
  })

  // Add pending flows as a separate entity if provided
  if (pendingFlows && pendingFlows.length > 0) {
    const pendingFlowsTotal = calculatePendingEarningsTotal(
      pendingFlows,
      targetCurrency,
      exchangeRates,
    )

    // Show pending flows as a separate entity if there's a net positive amount
    if (pendingFlowsTotal > 0) {
      const entityId = "pending-flows"
      const entityName = "PENDING_FLOWS" // Use consistent naming with asset distribution

      entities[entityId] = {
        name: entityName,
        value: pendingFlowsTotal, // Use actual positive value
        percentage: 0,
        id: entityId,
      }
      totalValue += pendingFlowsTotal
    }
  }

  if (totalValue > 0) {
    const entityList = Object.values(entities)
    let remainingPercentage = 100

    const exactPercentages = entityList.map(entity => ({
      entity,
      exactPercentage: (entity.value / totalValue) * 100,
    }))

    exactPercentages.sort((a, b) => b.exactPercentage - a.exactPercentage)

    exactPercentages.forEach((item, index) => {
      if (index === exactPercentages.length - 1) {
        item.entity.percentage = remainingPercentage
      } else {
        const roundedPercentage = Math.round(item.exactPercentage)
        item.entity.percentage = roundedPercentage
        remainingPercentage -= roundedPercentage
      }
    })
  } else {
    Object.values(entities).forEach(entity => {
      entity.percentage = 0
    })
  }

  return Object.values(entities).sort((a, b) => b.value - a.value)
}

export const getTotalAssets = (
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
  pendingFlows: PendingFlow[],
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let total = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const accountsProduct = entityPosition.products[ProductType.ACCOUNT]
    if (
      accountsProduct &&
      "entries" in accountsProduct &&
      accountsProduct.entries.length > 0
    ) {
      const accountsTotal = accountsProduct.entries.reduce(
        (sum: number, account: any) => {
          const accountTotal = account.total || 0
          const convertedTotal =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  accountTotal,
                  account.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : accountTotal
          return sum + convertedTotal
        },
        0,
      )
      total += accountsTotal
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      const fundsMarketValue = fundsProduct.entries.reduce(
        (sum: number, fund: any) => {
          const marketValue = fund.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  fund.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      total += fundsMarketValue
    }

    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      const stocksMarketValue = stocksProduct.entries.reduce(
        (sum: number, stock: any) => {
          const marketValue = stock.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  stock.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      total += stocksMarketValue
    }

    const depositsProduct = entityPosition.products[ProductType.DEPOSIT]
    if (
      depositsProduct &&
      "entries" in depositsProduct &&
      depositsProduct.entries.length > 0
    ) {
      const depositsTotal = depositsProduct.entries.reduce(
        (sum: number, deposit: any) => {
          const amount = deposit.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  deposit.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      total += depositsTotal
    }

    const realEstateCfProduct =
      entityPosition.products[ProductType.REAL_ESTATE_CF]
    if (
      realEstateCfProduct &&
      "entries" in realEstateCfProduct &&
      realEstateCfProduct.entries.length > 0
    ) {
      const realEstateCfTotal = realEstateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.pending_amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  project.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      total += realEstateCfTotal
    }

    const factoringProduct = entityPosition.products[ProductType.FACTORING]
    if (
      factoringProduct &&
      "entries" in factoringProduct &&
      factoringProduct.entries.length > 0
    ) {
      const factoringTotal = factoringProduct.entries.reduce(
        (sum: number, factoring: any) => {
          const amount = factoring.amount || 0
          const convertedAmount =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  amount,
                  factoring.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          return sum + convertedAmount
        },
        0,
      )
      total += factoringTotal
    }

    const crowdlendingProduct =
      entityPosition.products[ProductType.CROWDLENDING]
    if (
      crowdlendingProduct &&
      "total" in crowdlendingProduct &&
      crowdlendingProduct.total
    ) {
      const amount = crowdlendingProduct.total
      const convertedAmount =
        targetCurrency && exchangeRates
          ? convertCurrency(
              amount,
              crowdlendingProduct.currency,
              targetCurrency,
              exchangeRates,
            )
          : amount
      total += convertedAmount
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          targetCurrency,
          exchangeRates,
        )
        total += walletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenValue = calculateCryptoValue(
              token.amount,
              token.symbol,
              targetCurrency,
              exchangeRates,
            )
            total += tokenValue
          })
        }
      })
    }

    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        const commoditySymbol =
          COMMODITY_SYMBOLS[commodity.type as CommodityType]
        const commodityValue = calculateCommodityValue(
          commodity.amount,
          commoditySymbol,
          targetCurrency,
          exchangeRates,
          commodity.unit,
        )
        total += commodityValue
      })
    }
  })

  // Add pending flows if provided
  if (pendingFlows && pendingFlows.length > 0) {
    const pendingFlowsTotal = calculatePendingEarningsTotal(
      pendingFlows,
      targetCurrency,
      exchangeRates,
    )
    total += pendingFlowsTotal
  }

  return total
}

export const getTotalInvestedAmount = (
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
  pendingFlows: PendingFlow[],
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let totalInvested = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const accountsProduct = entityPosition.products[ProductType.ACCOUNT]
    if (
      accountsProduct &&
      "entries" in accountsProduct &&
      accountsProduct.entries.length > 0
    ) {
      const accountsTotal = accountsProduct.entries.reduce(
        (sum: number, account: any) => {
          const accountTotal = account.total || 0
          const convertedTotal =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  accountTotal,
                  account.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : accountTotal
          return sum + convertedTotal
        },
        0,
      )
      totalInvested += accountsTotal
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      fundsProduct.entries.forEach((fund: any) => {
        const amount = fund.initial_investment || fund.market_value || 0
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                fund.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      stocksProduct.entries.forEach((stock: any) => {
        const amount =
          stock.initial_investment ||
          (stock.shares && stock.average_buy_price
            ? stock.shares * stock.average_buy_price
            : stock.market_value || 0)
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                stock.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const depositsProduct = entityPosition.products[ProductType.DEPOSIT]
    if (
      depositsProduct &&
      "entries" in depositsProduct &&
      depositsProduct.entries.length > 0
    ) {
      depositsProduct.entries.forEach((deposit: any) => {
        const amount = deposit.amount || 0
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                deposit.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const realEstateCfProduct =
      entityPosition.products[ProductType.REAL_ESTATE_CF]
    if (
      realEstateCfProduct &&
      "entries" in realEstateCfProduct &&
      realEstateCfProduct.entries.length > 0
    ) {
      realEstateCfProduct.entries.forEach((project: any) => {
        const amount = project.pending_amount || 0
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                project.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const factoringProduct = entityPosition.products[ProductType.FACTORING]
    if (
      factoringProduct &&
      "entries" in factoringProduct &&
      factoringProduct.entries.length > 0
    ) {
      factoringProduct.entries.forEach((factoring: any) => {
        const amount = factoring.amount || 0
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                factoring.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const crowdlendingProduct =
      entityPosition.products[ProductType.CROWDLENDING]
    if (
      crowdlendingProduct &&
      "details" in crowdlendingProduct &&
      crowdlendingProduct.details &&
      Array.isArray(crowdlendingProduct.details)
    ) {
      crowdlendingProduct.details.forEach((loan: any) => {
        const amount = loan.amount || 0
        const convertedAmount =
          targetCurrency &&
          exchangeRates &&
          "currency" in crowdlendingProduct &&
          crowdlendingProduct.currency
            ? convertCurrency(
                amount,
                crowdlendingProduct.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        totalInvested += convertedAmount
      })
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletAmount =
          wallet.initial_investment ||
          calculateCryptoValue(
            wallet.amount,
            wallet.symbol,
            targetCurrency,
            exchangeRates,
          )
        const convertedWalletAmount =
          wallet.initial_investment &&
          targetCurrency &&
          exchangeRates &&
          wallet.currency
            ? convertCurrency(
                wallet.initial_investment,
                wallet.currency,
                targetCurrency,
                exchangeRates,
              )
            : walletAmount
        totalInvested += convertedWalletAmount

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenAmount =
              token.initial_investment ||
              calculateCryptoValue(
                token.amount,
                token.symbol,
                targetCurrency,
                exchangeRates,
              )
            const convertedTokenAmount =
              token.initial_investment &&
              targetCurrency &&
              exchangeRates &&
              token.currency
                ? convertCurrency(
                    token.initial_investment,
                    token.currency,
                    targetCurrency,
                    exchangeRates,
                  )
                : tokenAmount
            totalInvested += convertedTokenAmount
          })
        }
      })
    }

    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        // calculate current market value for this commodity
        const marketValue = calculateCommodityValue(
          commodity.amount,
          COMMODITY_SYMBOLS[commodity.type as CommodityType],
          targetCurrency,
          exchangeRates,
          commodity.unit,
        )
        // use market value as initial investment if none provided
        const initialInvestment =
          commodity.initial_investment != null &&
          commodity.initial_investment > 0
            ? commodity.initial_investment
            : marketValue
        const convertedInvestment =
          targetCurrency && exchangeRates
            ? convertCurrency(
                initialInvestment,
                commodity.currency,
                targetCurrency,
                exchangeRates,
              )
            : initialInvestment
        totalInvested += convertedInvestment
      })
    }
  })

  // Add pending flows if provided
  if (pendingFlows && pendingFlows.length > 0) {
    const pendingFlowsTotal = calculatePendingEarningsTotal(
      pendingFlows,
      targetCurrency,
      exchangeRates,
    )
    totalInvested += pendingFlowsTotal
  }

  return totalInvested
}

export const getOngoingProjects = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
): OngoingProject[] => {
  if (!positionsData || !positionsData.positions) return []

  const projects: OngoingProject[] = []

  Object.values(positionsData.positions).forEach(entityPosition => {
    const depositsProduct = entityPosition.products[ProductType.DEPOSIT]
    if (
      depositsProduct &&
      "entries" in depositsProduct &&
      depositsProduct.entries.length > 0
    ) {
      depositsProduct.entries.forEach((deposit: any) => {
        if (deposit.maturity) {
          projects.push({
            name: deposit.name || "Deposit",
            type: "DEPOSIT",
            value: deposit.amount,
            currency: deposit.currency,
            formattedValue: formatCurrency(
              deposit.amount,
              locale,
              defaultCurrency,
              deposit.currency,
            ),
            roi: deposit.interest_rate * 100,
            maturity: deposit.maturity,
            entity: entityPosition.entity?.name || "Unknown",
          })
        }
      })
    }

    const realEstateCfProduct =
      entityPosition.products[ProductType.REAL_ESTATE_CF]
    if (
      realEstateCfProduct &&
      "entries" in realEstateCfProduct &&
      realEstateCfProduct.entries.length > 0
    ) {
      realEstateCfProduct.entries.forEach((project: any) => {
        if (project.maturity) {
          projects.push({
            name: project.name,
            type: "REAL_ESTATE_CF",
            value: project.pending_amount,
            currency: project.currency,
            formattedValue: formatCurrency(
              project.pending_amount,
              locale,
              defaultCurrency,
              project.currency,
            ),
            roi: project.interest_rate * 100,
            maturity: project.maturity,
            entity: entityPosition.entity?.name || "Unknown",
          })
        }
      })
    }

    const factoringProduct = entityPosition.products[ProductType.FACTORING]
    if (
      factoringProduct &&
      "entries" in factoringProduct &&
      factoringProduct.entries.length > 0
    ) {
      factoringProduct.entries.forEach((factoring: any) => {
        if (factoring.maturity) {
          projects.push({
            name: factoring.name,
            type: "FACTORING",
            value: factoring.amount,
            currency: factoring.currency,
            formattedValue: formatCurrency(
              factoring.amount,
              locale,
              defaultCurrency,
              factoring.currency,
            ),
            roi: factoring.interest_rate * 100,
            maturity: factoring.maturity,
            entity: entityPosition.entity?.name || "Unknown",
          })
        }
      })
    }
  })

  return projects
    .sort(
      (a, b) => new Date(a.maturity).getTime() - new Date(b.maturity).getTime(),
    )
    .slice(0, 12)
}

export const getStockAndFundPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates?: ExchangeRates | null,
): StockFundPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  // Calculate total value of only displayed asset types for the percentage bars
  const totalDisplayedValue = getTotalDisplayedAssets(
    positionsData,
    defaultCurrency,
    exchangeRates || {},
  )

  const allPositionsRaw: any[] = []

  Object.values(positionsData.positions).forEach(entityPosition => {
    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      // No need to calculate totalVariableRentValue anymore
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      // No need to calculate totalVariableRentValue anymore
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      // No need to calculate totalVariableRentValue anymore
    }
  })

  Object.values(positionsData.positions).forEach(entityPosition => {
    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      stocksProduct.entries.forEach((stock: any) => {
        const originalValue = stock.market_value || 0
        const initialInvestment = stock.initial_investment || 0
        const gainLossAmount = originalValue - initialInvestment

        const convertedValue = exchangeRates
          ? convertCurrency(
              originalValue,
              stock.currency,
              defaultCurrency,
              exchangeRates,
            )
          : originalValue

        const convertedGainLoss = exchangeRates
          ? convertCurrency(
              gainLossAmount,
              stock.currency,
              defaultCurrency,
              exchangeRates,
            )
          : gainLossAmount

        allPositionsRaw.push({
          symbol: stock.ticker || "",
          name: stock.name,
          shares: stock.shares || 0,
          price: stock.average_buy_price || 0,
          value: convertedValue, // Use converted value
          originalValue: originalValue, // Keep original for display
          currency: stock.currency,
          formattedValue: formatCurrency(
            convertedValue,
            locale,
            defaultCurrency,
          ),
          formattedOriginalValue: formatCurrency(
            originalValue,
            locale,
            stock.currency,
          ),
          type: "STOCK_ETF",
          change:
            (originalValue / (stock.initial_investment || originalValue || 1) -
              1) *
            100,
          entity: entityPosition.entity?.name,
          isin: stock.isin,
          gainLossAmount: convertedGainLoss,
          formattedGainLossAmount:
            initialInvestment > 0 && gainLossAmount !== 0
              ? formatGainLoss(convertedGainLoss, locale, defaultCurrency)
              : undefined,
        })
      })
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      fundsProduct.entries.forEach((fund: any) => {
        const originalValue = fund.market_value || 0
        const initialInvestment = fund.initial_investment || 0
        const gainLossAmount = originalValue - initialInvestment

        const convertedValue = exchangeRates
          ? convertCurrency(
              originalValue,
              fund.currency,
              defaultCurrency,
              exchangeRates,
            )
          : originalValue

        const convertedGainLoss = exchangeRates
          ? convertCurrency(
              gainLossAmount,
              fund.currency,
              defaultCurrency,
              exchangeRates,
            )
          : gainLossAmount

        allPositionsRaw.push({
          symbol: "",
          name: fund.name,
          portfolioName: fund.portfolio?.name || null,
          shares: fund.shares || 0,
          price: fund.average_buy_price || 0,
          value: convertedValue, // Use converted value
          originalValue: originalValue, // Keep original for display
          currency: fund.currency,
          formattedValue: formatCurrency(
            convertedValue,
            locale,
            defaultCurrency,
          ),
          formattedOriginalValue: formatCurrency(
            originalValue,
            locale,
            fund.currency,
          ),
          type: "FUND",
          change:
            (originalValue / (fund.initial_investment || originalValue || 1) -
              1) *
            100,
          entity: entityPosition.entity?.name,
          isin: fund.isin,
          gainLossAmount: convertedGainLoss,
          formattedGainLossAmount:
            initialInvestment > 0 && gainLossAmount !== 0
              ? formatGainLoss(convertedGainLoss, locale, defaultCurrency)
              : undefined,
        })
      })
    }
  })

  const sortedPositions = allPositionsRaw.sort((a, b) => b.value - a.value)

  // Calculate separate totals for stocks and funds (values are already converted)
  const totalStockValue = sortedPositions
    .filter(pos => pos.type === "STOCK_ETF")
    .reduce((sum, pos) => sum + pos.value, 0)

  const totalFundValue = sortedPositions
    .filter(pos => pos.type === "FUND")
    .reduce((sum, pos) => sum + pos.value, 0)

  // Calculate percentages relative to each asset type's total
  const enrichedPositions = sortedPositions.map((pos, index) => {
    // Values are already converted, no need to convert again
    const convertedValue = pos.value

    // Calculate percentage relative to the specific asset type total
    const relevantTotal =
      pos.type === "STOCK_ETF" ? totalStockValue : totalFundValue
    const percentageOfTotalVariableRent =
      relevantTotal > 0 ? (convertedValue / relevantTotal) * 100 : 0

    return {
      ...pos,
      percentageOfTotalVariableRent,
      percentageOfTotalPortfolio:
        totalDisplayedValue > 0
          ? (convertedValue / totalDisplayedValue) * 100
          : 0,
      id:
        pos.type === "FUND"
          ? `fund-${pos.name}-${pos.entity}-${pos.portfolioName || "default"}-${index}`
          : `${pos.symbol}-stock-${index}-${pos.entity}`,
    }
  })

  // Ensure percentages add up to 100% within each asset type with rounding adjustment
  const stockPositions = enrichedPositions.filter(
    pos => pos.type === "STOCK_ETF",
  )
  const fundPositions = enrichedPositions.filter(pos => pos.type === "FUND")

  // Adjust stock percentages
  if (stockPositions.length > 0 && totalStockValue > 0) {
    let remainingPercentage = 100
    stockPositions.forEach((pos, index) => {
      if (index === stockPositions.length - 1) {
        pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
      } else {
        const roundedPercentage =
          Math.round(pos.percentageOfTotalVariableRent * 100) / 100
        pos.percentageOfTotalVariableRent = roundedPercentage
        remainingPercentage -= roundedPercentage
      }
    })
  }

  // Adjust fund percentages
  if (fundPositions.length > 0 && totalFundValue > 0) {
    let remainingPercentage = 100
    fundPositions.forEach((pos, index) => {
      if (index === fundPositions.length - 1) {
        pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
      } else {
        const roundedPercentage =
          Math.round(pos.percentageOfTotalVariableRent * 100) / 100
        pos.percentageOfTotalVariableRent = roundedPercentage
        remainingPercentage -= roundedPercentage
      }
    })
  }

  return enrichedPositions
}

export const getCryptoPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates: ExchangeRates,
): CryptoPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  // Calculate total value of only displayed asset types for the percentage bars
  const totalDisplayedValue = getTotalDisplayedAssets(
    positionsData,
    defaultCurrency,
    exchangeRates,
  )

  const cryptoAggregation: Record<string, any> = {}

  Object.values(positionsData.positions).forEach(entityPosition => {
    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const entityName = entityPosition.entity?.name || "Unknown"

        const walletValue = calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          defaultCurrency,
          exchangeRates,
        )

        if (walletValue > 0) {
          const symbol = wallet.symbol
          const key = `${symbol}-${entityName}`

          const convertedInitialInvestment =
            wallet.initial_investment && exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.initial_investment,
                  wallet.currency,
                  defaultCurrency,
                  exchangeRates,
                )
              : wallet.initial_investment || walletValue

          if (!cryptoAggregation[key]) {
            cryptoAggregation[key] = {
              symbol: symbol,
              name: wallet.name,
              amount: 0,
              value: 0,
              currency: defaultCurrency,
              type: "CRYPTO",
              entities: new Set([entityName]),
              initialInvestment: 0,
              addresses: new Set(),
            }
          }

          cryptoAggregation[key].amount += wallet.amount || 0
          cryptoAggregation[key].value += walletValue
          cryptoAggregation[key].initialInvestment += convertedInitialInvestment
          cryptoAggregation[key].addresses.add(wallet.address)
        }

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenValue = calculateCryptoValue(
              token.amount,
              token.symbol,
              defaultCurrency,
              exchangeRates,
            )

            if (tokenValue > 0) {
              const symbol = token.symbol
              const key = symbol

              const convertedInitialInvestment =
                token.initial_investment && exchangeRates && token.currency
                  ? convertCurrency(
                      token.initial_investment,
                      token.currency,
                      defaultCurrency,
                      exchangeRates,
                    )
                  : token.initial_investment || tokenValue

              if (!cryptoAggregation[key]) {
                cryptoAggregation[key] = {
                  symbol: symbol,
                  name: token.name,
                  amount: 0,
                  value: 0,
                  currency: defaultCurrency,
                  type: "CRYPTO_TOKEN",
                  entities: new Set(),
                  initialInvestment: 0,
                  addresses: new Set(),
                }
              }

              cryptoAggregation[key].amount += token.amount || 0
              cryptoAggregation[key].value += tokenValue
              cryptoAggregation[key].initialInvestment +=
                convertedInitialInvestment
              cryptoAggregation[key].entities.add(entityName)
              cryptoAggregation[key].addresses.add(wallet.address)
            }
          })
        }
      })
    }
  })

  const allCryptoPositions = Object.keys(cryptoAggregation).map(
    (key, index) => {
      const crypto = cryptoAggregation[key]
      const value = crypto.value
      const change =
        crypto.initialInvestment > 0
          ? (value / crypto.initialInvestment - 1) * 100
          : 0

      const entitiesArray = Array.from(crypto.entities) as string[]
      const isToken = crypto.type === "CRYPTO_TOKEN"

      const displayName = isToken ? crypto.name : entitiesArray[0]

      return {
        symbol: crypto.symbol,
        name: displayName,
        address: Array.from(crypto.addresses).join(", "),
        amount: crypto.amount,
        price: crypto.amount > 0 ? value / crypto.amount : 0,
        value: value,
        currency: defaultCurrency,
        formattedValue: formatCurrency(
          value,
          locale,
          defaultCurrency,
          defaultCurrency,
        ),
        type: crypto.type,
        change: change,
        entities: entitiesArray,
        showEntityBadge: isToken,
        percentageOfTotalVariableRent: 0, // Will be calculated below
        percentageOfTotalPortfolio:
          totalDisplayedValue > 0 ? (value / totalDisplayedValue) * 100 : 0,
        id: `crypto-${crypto.symbol}-${entitiesArray.join("-")}-${index}`,
      }
    },
  )

  const sortedCryptoPositions = allCryptoPositions.sort(
    (a, b) => b.value - a.value,
  )

  // Calculate total crypto value for percentage calculation
  const totalCryptoValue = sortedCryptoPositions.reduce(
    (sum, pos) => sum + pos.value,
    0,
  )

  // Calculate percentages relative to crypto total, not all assets
  sortedCryptoPositions.forEach(pos => {
    pos.percentageOfTotalVariableRent =
      totalCryptoValue > 0 ? (pos.value / totalCryptoValue) * 100 : 0
  })

  // Ensure percentages add up to 100% with rounding adjustment
  if (sortedCryptoPositions.length > 0 && totalCryptoValue > 0) {
    let remainingPercentage = 100

    sortedCryptoPositions.forEach((pos, index) => {
      if (index === sortedCryptoPositions.length - 1) {
        pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
      } else {
        const roundedPercentage =
          Math.round(pos.percentageOfTotalVariableRent * 100) / 100
        pos.percentageOfTotalVariableRent = roundedPercentage
        remainingPercentage -= roundedPercentage
      }
    })
  }

  return sortedCryptoPositions
}

export const getCommodityPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates: ExchangeRates,
  settings: { general: { defaultCommodityWeightUnit: string } },
): CommodityPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  // Calculate total value of only displayed asset types for the percentage bars
  const totalDisplayedValue = getTotalDisplayedAssets(
    positionsData,
    defaultCurrency,
    exchangeRates,
  )

  const commodityAggregation: Record<string, any> = {}

  // Process commodities
  Object.values(positionsData.positions).forEach(entityPosition => {
    const entityName = entityPosition.entity?.name || "Unknown"
    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        const commoditySymbol =
          COMMODITY_SYMBOLS[commodity.type as CommodityType]
        const convertedValue = calculateCommodityValue(
          commodity.amount,
          commoditySymbol,
          defaultCurrency,
          exchangeRates,
          commodity.unit,
        )

        if (convertedValue > 0) {
          const symbol = commodity.type
          const key = `${symbol}-${entityName}`

          const convertedInitialInvestment =
            commodity.initial_investment && exchangeRates && commodity.currency
              ? convertCurrency(
                  commodity.initial_investment,
                  commodity.currency,
                  defaultCurrency,
                  exchangeRates,
                )
              : commodity.initial_investment || convertedValue

          if (!commodityAggregation[key]) {
            commodityAggregation[key] = {
              symbol: symbol,
              name: commodity.name,
              type: commodity.type,
              // Store amounts by unit to preserve precision
              amountsByUnit: {},
              value: 0,
              currency: defaultCurrency,
              entities: new Set([entityName]),
              initialInvestment: 0,
            }
          }

          // Aggregate amounts by their original unit
          const unit = commodity.unit
          if (!commodityAggregation[key].amountsByUnit[unit]) {
            commodityAggregation[key].amountsByUnit[unit] = 0
          }
          commodityAggregation[key].amountsByUnit[unit] += commodity.amount || 0

          commodityAggregation[key].value += convertedValue
          commodityAggregation[key].initialInvestment +=
            convertedInitialInvestment
        }
      })
    }
  })

  const allCommodityPositions = Object.keys(commodityAggregation).map(
    (key, index) => {
      const commodity = commodityAggregation[key]
      const entities = Array.from(commodity.entities) as string[]
      const value = commodity.value
      const initialInvestment = commodity.initialInvestment
      const change =
        initialInvestment > 0
          ? ((value - initialInvestment) / initialInvestment) * 100
          : 0

      // Calculate total amount in user's preferred display unit
      const displayUnit = settings.general
        .defaultCommodityWeightUnit as WeightUnit
      let totalDisplayAmount = 0

      // Convert each unit's amount to display unit and sum
      Object.keys(commodity.amountsByUnit).forEach(unit => {
        const amountInThisUnit = commodity.amountsByUnit[unit]
        const convertedAmount = convertWeight(
          amountInThisUnit,
          unit as WeightUnit,
          displayUnit,
        )
        totalDisplayAmount += convertedAmount
      })

      // Calculate price per display unit correctly
      const commoditySymbol = COMMODITY_SYMBOLS[commodity.type as CommodityType]
      const pricePerTroyOunce =
        exchangeRates[defaultCurrency] &&
        exchangeRates[defaultCurrency][commoditySymbol]
          ? 1 / exchangeRates[defaultCurrency][commoditySymbol]
          : 0

      // Convert price to display unit
      const pricePerDisplayUnit =
        displayUnit === WeightUnit.TROY_OUNCE
          ? pricePerTroyOunce
          : pricePerTroyOunce *
            WEIGHT_CONVERSIONS[WeightUnit.TROY_OUNCE][displayUnit]

      return {
        symbol: commodity.symbol,
        name: commodity.name,
        type: commodity.type,
        amount: totalDisplayAmount,
        unit: displayUnit,
        price: pricePerDisplayUnit,
        value: value,
        currency: commodity.currency,
        formattedValue: formatCurrency(value, locale, defaultCurrency),
        change: change,
        entities: entities,
        showEntityBadge: entities.length > 1,
        percentageOfTotalVariableRent: 0, // Will be calculated below
        percentageOfTotalPortfolio:
          totalDisplayedValue > 0 ? (value / totalDisplayedValue) * 100 : 0,
        id: `commodity-${commodity.symbol}-${entities.join("-")}-${index}`,
      }
    },
  )

  const sortedCommodityPositions = allCommodityPositions.sort(
    (a, b) => b.value - a.value,
  )

  // Calculate total commodity value for percentage calculation
  const totalCommodityValue = sortedCommodityPositions.reduce(
    (sum, pos) => sum + pos.value,
    0,
  )

  // Calculate percentages relative to commodity total, not all assets
  sortedCommodityPositions.forEach(pos => {
    pos.percentageOfTotalVariableRent =
      totalCommodityValue > 0 ? (pos.value / totalCommodityValue) * 100 : 0
  })

  // Ensure percentages add up to 100% with rounding adjustment
  if (sortedCommodityPositions.length > 0 && totalCommodityValue > 0) {
    let remainingPercentage = 100

    sortedCommodityPositions.forEach((pos, index) => {
      if (index === sortedCommodityPositions.length - 1) {
        pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
      } else {
        const roundedPercentage =
          Math.round(pos.percentageOfTotalVariableRent * 100) / 100
        pos.percentageOfTotalVariableRent = roundedPercentage
        remainingPercentage -= roundedPercentage
      }
    })
  }

  return sortedCommodityPositions
}

export const getRecentTransactions = (
  transactions: TransactionsResult | null,
  locale: string,
  defaultCurrency: string,
): Record<string, GroupedTransaction[]> => {
  if (!transactions || !transactions.transactions) return {}

  const groupedTxs: Record<string, GroupedTransaction[]> = {}

  transactions.transactions
    .map(tx => ({
      date: tx.date,
      description: tx.name,
      amount: tx.amount,
      currency: tx.currency,
      formattedAmount: formatCurrency(
        tx.net_amount ?? tx.amount,
        locale,
        defaultCurrency,
        tx.currency,
      ),
      type: tx.type,
      product_type: tx.product_type,
      displayType: getTransactionDisplayType(tx.type),
      entity: tx.entity.name,
    }))
    .forEach(tx => {
      const dateKey = formatDate(tx.date, locale)
      if (!groupedTxs[dateKey]) {
        groupedTxs[dateKey] = []
      }
      groupedTxs[dateKey].push(tx)
    })

  const sortedDates = Object.keys(groupedTxs).sort((a, b) => {
    const dateA = new Date(a.split("/").reverse().join("-"))
    const dateB = new Date(b.split("/").reverse().join("-"))
    return dateB.getTime() - dateA.getTime()
  })

  const sortedGroupedTxs: Record<string, GroupedTransaction[]> = {}
  sortedDates.forEach(date => {
    sortedGroupedTxs[date] = groupedTxs[date]
  })

  return sortedGroupedTxs
}

export const getDaysStatus = (dateString: string, t: any) => {
  const today = new Date()
  const maturityDate = new Date(dateString)
  const diffTime = maturityDate.getTime() - today.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays >= 0) {
    return {
      days: diffDays,
      isDelayed: false,
      statusText: `${diffDays}${t.dashboard.daysLeft}`,
    }
  } else {
    const absDiffDays = Math.abs(diffDays)
    return {
      days: absDiffDays,
      isDelayed: true,
      statusText: `${absDiffDays}${t.dashboard.daysDelay}`,
    }
  }
}

export const getTotalDisplayedAssets = (
  positionsData: EntitiesPosition | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates,
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let total = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    // Only include FUND, STOCK_ETF, CRYPTO, and COMMODITY
    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      const fundsMarketValue = fundsProduct.entries.reduce(
        (sum: number, fund: any) => {
          const marketValue = fund.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  fund.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      total += fundsMarketValue
    }

    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      const stocksMarketValue = stocksProduct.entries.reduce(
        (sum: number, stock: any) => {
          const marketValue = stock.market_value || 0
          const convertedValue =
            targetCurrency && exchangeRates
              ? convertCurrency(
                  marketValue,
                  stock.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : marketValue
          return sum + convertedValue
        },
        0,
      )
      total += stocksMarketValue
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          targetCurrency,
          exchangeRates,
        )
        total += walletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenValue = calculateCryptoValue(
              token.amount,
              token.symbol,
              targetCurrency,
              exchangeRates,
            )
            total += tokenValue
          })
        }
      })
    }

    const commodityProduct = entityPosition.products[ProductType.COMMODITY]
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        const commoditySymbol =
          COMMODITY_SYMBOLS[commodity.type as CommodityType]
        const commodityValue = calculateCommodityValue(
          commodity.amount,
          commoditySymbol,
          targetCurrency,
          exchangeRates,
          commodity.unit,
        )
        total += commodityValue
      })
    }
  })

  return total
}

export const calculateInvestmentDistribution = (
  positions: any[],
  groupBy: "entity" | "symbol" | "name" = "symbol", // Allow grouping by name as well
): { name: string; value: number; color: string; percentage: number }[] => {
  if (!positions || positions.length === 0) return []

  // Group positions by the specified field
  const grouped = positions.reduce(
    (acc, position) => {
      const key =
        groupBy === "entity"
          ? position.entity
          : groupBy === "name"
            ? position.name || position.symbol
            : position.symbol || position.name
      if (!acc[key]) {
        acc[key] = 0
      }
      acc[key] += position.currentValue || position.value || 0
      return acc
    },
    {} as Record<string, number>,
  )

  // Calculate total value
  const values = Object.values(grouped) as number[]
  const totalValue = values.reduce((sum, value) => sum + value, 0)

  // Convert to chart data format
  const entries = Object.entries(grouped) as [string, number][]
  const data = entries
    .map(([name, value]) => ({
      name,
      value,
      color: "",
      percentage: totalValue > 0 ? (value / totalValue) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value) // Sort by value descending

  // Assign colors
  const colors = [
    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#06b6d4",
    "#f97316",
    "#84cc16",
    "#ec4899",
    "#6366f1",
    "#14b8a6",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#06b6d4",
  ]
  data.forEach((item, index) => {
    item.color = colors[index]
  })

  return data
}

export const calculateInvestmentDistributionWithCurrency = (
  positions: any[],
  groupBy: "entity" | "symbol" | "name" = "symbol",
  userCurrency: string,
  exchangeRates: ExchangeRates | null,
): {
  name: string
  value: number
  color: string
  percentage: number
  currency?: string
  convertedValue?: number
  convertedCurrency?: string
}[] => {
  if (!positions || positions.length === 0) return []

  // Group positions by the specified field
  const grouped = positions.reduce(
    (acc, position) => {
      const key =
        groupBy === "entity"
          ? position.entity
          : groupBy === "name"
            ? position.name || position.symbol
            : position.symbol || position.name

      if (!acc[key]) {
        acc[key] = {
          value: 0,
          currency: position.currency,
          convertedValue: 0,
        }
      }

      const positionValue = position.currentValue || position.value || 0
      acc[key].value += positionValue

      // Convert to user currency for comparison
      const convertedValue = convertCurrency(
        positionValue,
        position.currency,
        userCurrency,
        exchangeRates,
      )
      acc[key].convertedValue += convertedValue

      return acc
    },
    {} as Record<
      string,
      { value: number; currency: string; convertedValue: number }
    >,
  )

  // Calculate total value in user currency
  const groupedValues = Object.values(grouped) as {
    value: number
    currency: string
    convertedValue: number
  }[]
  const values = groupedValues.map(item => item.convertedValue)
  const totalValue = values.reduce((sum, value) => sum + value, 0)

  // Convert to chart data format
  const entries = Object.entries(grouped) as [
    string,
    { value: number; currency: string; convertedValue: number },
  ][]
  const data = entries
    .map(([name, item]) => ({
      name,
      value: item.value,
      currency: item.currency,
      convertedValue: item.convertedValue,
      convertedCurrency: userCurrency,
      color: "",
      percentage: totalValue > 0 ? (item.convertedValue / totalValue) * 100 : 0,
    }))
    .sort((a, b) => b.convertedValue - a.convertedValue) // Sort by converted value descending

  // Assign colors
  const colors = [
    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#06b6d4",
    "#f97316",
    "#84cc16",
    "#ec4899",
    "#6366f1",
    "#14b8a6",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#06b6d4",
  ]
  data.forEach((item, index) => {
    item.color = colors[index % colors.length]
  })

  return data
}

/**
 * Convert snake_case or SCREAMING_SNAKE_CASE to human-readable format
 */
export const formatSnakeCaseToHuman = (text: string): string => {
  if (!text) return text

  return text
    .toLowerCase()
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

/**
 * Get all entity IDs that have positions for a specific product type
 */
export const getEntitiesWithProductType = (
  positionsData: any,
  productType: ProductType,
): string[] => {
  if (!positionsData?.positions) return []

  const entityIds = new Set<string>()

  // positionsData.positions is an object, not an array
  Object.values(positionsData.positions).forEach((entityPosition: any) => {
    if (entityPosition.products && entityPosition.products[productType]) {
      const product = entityPosition.products[productType]
      // Check if the product has entries and they're not empty
      if (
        product &&
        "entries" in product &&
        product.entries &&
        product.entries.length > 0
      ) {
        entityIds.add(entityPosition.entity.id)
      }
      // Also check for products with total value (like crowdlending)
      else if (
        product &&
        "total" in product &&
        product.total &&
        product.total > 0
      ) {
        entityIds.add(entityPosition.entity.id)
      }
    }
  })

  return Array.from(entityIds)
}

/**
 * Get all available investment types from positions data
 */
export const getAvailableInvestmentTypes = (
  positionsData: any,
): ProductType[] => {
  if (!positionsData?.positions) return []

  const availableTypes = new Set<ProductType>()

  Object.values(positionsData.positions).forEach((entityPosition: any) => {
    if (entityPosition.products) {
      // Check each investment product type
      const investmentTypes = [
        ProductType.STOCK_ETF,
        ProductType.FUND,
        ProductType.DEPOSIT,
        ProductType.FACTORING,
        ProductType.REAL_ESTATE_CF,
        ProductType.CRYPTO,
      ]

      investmentTypes.forEach(productType => {
        const product = entityPosition.products[productType]
        if (product) {
          // Check if the product has entries and they're not empty
          if (
            "entries" in product &&
            product.entries &&
            product.entries.length > 0
          ) {
            availableTypes.add(productType)
          }
          // Also check for products with total value (like crowdlending)
          else if ("total" in product && product.total && product.total > 0) {
            availableTypes.add(productType)
          }
        }
      })
    }
  })

  return Array.from(availableTypes)
}

export const calculatePendingEarningsTotal = (
  pendingFlows: PendingFlow[],
  targetCurrency: string,
  exchangeRates: ExchangeRates,
): number => {
  if (!pendingFlows || pendingFlows.length === 0) return 0

  const now = new Date()

  return pendingFlows
    .filter(flow => flow.enabled)
    .filter(flow => {
      // Only include future or current flows
      if (!flow.date) return true
      const flowDate = new Date(flow.date)
      return flowDate >= now
    })
    .reduce((total, flow) => {
      const amount = parseFloat(flow.amount) || 0
      const convertedAmount = convertCurrency(
        amount,
        flow.currency,
        targetCurrency,
        exchangeRates,
      )

      // Add earnings (positive), subtract expenses (negative)
      return flow.flow_type === "EARNING"
        ? total + convertedAmount
        : total - convertedAmount
    }, 0)
}
