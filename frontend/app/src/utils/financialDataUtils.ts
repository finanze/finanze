import { EntitiesPosition } from "@/types/position"
import { TransactionsResult, TxType } from "@/types/transactions"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { ExchangeRates } from "@/types"

import { ProductType } from "@/types/position"

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
  currency: string
  formattedValue: string
  type: string
  change: number
  entity: string
  percentageOfTotalVariableRent: number
  id: string
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
  id: string
  tokens?: {
    symbol: string
    name: string
    amount: number
    value: number
    formattedValue: string
  }[]
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
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
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

    const realStateCfProduct =
      entityPosition.products[ProductType.REAL_STATE_CF]
    if (
      realStateCfProduct &&
      "entries" in realStateCfProduct &&
      realStateCfProduct.entries.length > 0
    ) {
      if (!assetTypes["REAL_STATE_CF"]) {
        assetTypes["REAL_STATE_CF"] = {
          type: "REAL_STATE_CF",
          value: 0,
          percentage: 0,
          change: 0,
        }
      }
      const realStateCfTotal = realStateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.amount || 0
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
      assetTypes["REAL_STATE_CF"].value += realStateCfTotal
      totalValue += realStateCfTotal
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
        if (wallet.market_value) {
          const convertedValue =
            targetCurrency && exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.market_value,
                  wallet.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : wallet.market_value
          assetTypes["CRYPTO"].value += convertedValue
          totalValue += convertedValue
        }

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value) {
              const convertedTokenValue =
                targetCurrency && exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      targetCurrency,
                      exchangeRates,
                    )
                  : token.market_value
              assetTypes["CRYPTO"].value += convertedTokenValue
              totalValue += convertedTokenValue
            }
          })
        }
      })
    }
  })

  Object.values(assetTypes).forEach(asset => {
    asset.percentage =
      totalValue > 0 ? Math.round((asset.value / totalValue) * 100) : 0
  })

  return Object.values(assetTypes).sort((a, b) => b.value - a.value)
}

export const getEntityDistribution = (
  positionsData: EntitiesPosition | null,
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
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

    const realStateCfProduct =
      entityPosition.products[ProductType.REAL_STATE_CF]
    if (
      realStateCfProduct &&
      "entries" in realStateCfProduct &&
      realStateCfProduct.entries.length > 0
    ) {
      const realStateCfTotal = realStateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.amount || 0
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
      entityTotal += realStateCfTotal
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
        if (wallet.market_value) {
          const convertedValue =
            targetCurrency && exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.market_value,
                  wallet.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : wallet.market_value
          entityTotal += convertedValue
        }

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value) {
              const convertedTokenValue =
                targetCurrency && exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      targetCurrency,
                      exchangeRates,
                    )
                  : token.market_value
              entityTotal += convertedTokenValue
            }
          })
        }
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
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
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

    const realStateCfProduct =
      entityPosition.products[ProductType.REAL_STATE_CF]
    if (
      realStateCfProduct &&
      "entries" in realStateCfProduct &&
      realStateCfProduct.entries.length > 0
    ) {
      const realStateCfTotal = realStateCfProduct.entries.reduce(
        (sum: number, project: any) => {
          const amount = project.amount || 0
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
      total += realStateCfTotal
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
        if (wallet.market_value) {
          const convertedValue =
            targetCurrency && exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.market_value,
                  wallet.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : wallet.market_value
          total += convertedValue
        }

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value) {
              const convertedTokenValue =
                targetCurrency && exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      targetCurrency,
                      exchangeRates,
                    )
                  : token.market_value
              total += convertedTokenValue
            }
          })
        }
      })
    }
  })

  return total
}

export const getTotalInvestedAmount = (
  positionsData: EntitiesPosition | null,
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
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

    const realStateCfProduct =
      entityPosition.products[ProductType.REAL_STATE_CF]
    if (
      realStateCfProduct &&
      "entries" in realStateCfProduct &&
      realStateCfProduct.entries.length > 0
    ) {
      realStateCfProduct.entries.forEach((project: any) => {
        const amount = project.amount || 0
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
          wallet.initial_investment || wallet.market_value || 0
        const convertedWalletAmount =
          targetCurrency && exchangeRates && wallet.currency
            ? convertCurrency(
                walletAmount,
                wallet.currency,
                targetCurrency,
                exchangeRates,
              )
            : walletAmount
        totalInvested += convertedWalletAmount

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            const tokenAmount =
              token.initial_investment || token.market_value || 0
            const convertedTokenAmount =
              targetCurrency && exchangeRates && token.currency
                ? convertCurrency(
                    tokenAmount,
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
  })

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

    const realStateCfProduct =
      entityPosition.products[ProductType.REAL_STATE_CF]
    if (
      realStateCfProduct &&
      "entries" in realStateCfProduct &&
      realStateCfProduct.entries.length > 0
    ) {
      realStateCfProduct.entries.forEach((project: any) => {
        if (project.maturity) {
          projects.push({
            name: project.name,
            type: "REAL_STATE_CF",
            value: project.amount,
            currency: project.currency,
            formattedValue: formatCurrency(
              project.amount,
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

  const allPositionsRaw: any[] = []
  let totalVariableRentValue = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      stocksProduct.entries.forEach((stock: any) => {
        const stockValue = stock.market_value || 0
        const convertedStockValue = exchangeRates
          ? convertCurrency(
              stockValue,
              stock.currency,
              defaultCurrency,
              exchangeRates,
            )
          : stockValue
        totalVariableRentValue += convertedStockValue
      })
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      fundsProduct.entries.forEach((fund: any) => {
        const fundValue = fund.market_value || 0
        const convertedFundValue = exchangeRates
          ? convertCurrency(
              fundValue,
              fund.currency,
              defaultCurrency,
              exchangeRates,
            )
          : fundValue
        totalVariableRentValue += convertedFundValue
      })
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = wallet.market_value || 0
        const convertedWalletValue =
          exchangeRates && wallet.currency
            ? convertCurrency(
                walletValue,
                wallet.currency,
                defaultCurrency,
                exchangeRates,
              )
            : walletValue
        totalVariableRentValue += convertedWalletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value && token.market_value > 0) {
              const convertedTokenValue =
                exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      defaultCurrency,
                      exchangeRates,
                    )
                  : token.market_value
              totalVariableRentValue += convertedTokenValue
            }
          })
        }
      })
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
        const value = stock.market_value || 0
        allPositionsRaw.push({
          symbol: stock.ticker || "",
          name: stock.name,
          shares: stock.shares || 0,
          price: stock.average_buy_price || 0,
          value: value,
          currency: stock.currency,
          formattedValue: formatCurrency(
            value,
            locale,
            defaultCurrency,
            stock.currency,
          ),
          type: "STOCK_ETF",
          change: (value / (stock.initial_investment || value || 1) - 1) * 100,
          entity: entityPosition.entity?.name,
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
        const value = fund.market_value || 0
        allPositionsRaw.push({
          symbol: "",
          name: fund.name,
          portfolioName: fund.portfolio?.name || null,
          shares: fund.shares || 0,
          price: fund.average_buy_price || 0,
          value: value,
          currency: fund.currency,
          formattedValue: formatCurrency(
            value,
            locale,
            defaultCurrency,
            fund.currency,
          ),
          type: "FUND",
          change: (value / (fund.initial_investment || value || 1) - 1) * 100,
          entity: entityPosition.entity?.name,
        })
      })
    }
  })

  const enrichedPositions = allPositionsRaw.map((pos, index) => ({
    ...pos,
    percentageOfTotalVariableRent:
      totalVariableRentValue > 0
        ? (pos.value / totalVariableRentValue) * 100
        : 0,
    id:
      pos.type === "FUND"
        ? `fund-${pos.name}-${pos.entity}-${pos.portfolioName || "default"}-${index}`
        : `${pos.symbol}-stock-${index}-${pos.entity}`,
  }))

  const sortedPositions = enrichedPositions.sort((a, b) => b.value - a.value)

  if (sortedPositions.length > 0) {
    const totalStockFundValue = sortedPositions.reduce((sum, pos) => {
      const convertedValue = exchangeRates
        ? convertCurrency(
            pos.value,
            pos.currency,
            defaultCurrency,
            exchangeRates,
          )
        : pos.value
      return sum + convertedValue
    }, 0)

    if (totalStockFundValue > 0 && totalVariableRentValue > 0) {
      let remainingPercentage =
        (totalStockFundValue / totalVariableRentValue) * 100

      sortedPositions.forEach((pos, index) => {
        const convertedValue = exchangeRates
          ? convertCurrency(
              pos.value,
              pos.currency,
              defaultCurrency,
              exchangeRates,
            )
          : pos.value

        if (index === sortedPositions.length - 1) {
          pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
        } else {
          const exactPercentage =
            (convertedValue / totalVariableRentValue) * 100
          const roundedPercentage = Math.round(exactPercentage * 100) / 100
          pos.percentageOfTotalVariableRent = roundedPercentage
          remainingPercentage -= roundedPercentage
        }
      })
    }
  }

  return sortedPositions
}

export const getCryptoPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates?: ExchangeRates | null,
): CryptoPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  const cryptoAggregation: Record<string, any> = {}
  let totalVariableRentValue = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    const stocksProduct = entityPosition.products[ProductType.STOCK_ETF]
    if (
      stocksProduct &&
      "entries" in stocksProduct &&
      stocksProduct.entries.length > 0
    ) {
      stocksProduct.entries.forEach((stock: any) => {
        const stockValue = stock.market_value || 0
        const convertedStockValue = exchangeRates
          ? convertCurrency(
              stockValue,
              stock.currency,
              defaultCurrency,
              exchangeRates,
            )
          : stockValue
        totalVariableRentValue += convertedStockValue
      })
    }

    const fundsProduct = entityPosition.products[ProductType.FUND]
    if (
      fundsProduct &&
      "entries" in fundsProduct &&
      fundsProduct.entries.length > 0
    ) {
      fundsProduct.entries.forEach((fund: any) => {
        const fundValue = fund.market_value || 0
        const convertedFundValue = exchangeRates
          ? convertCurrency(
              fundValue,
              fund.currency,
              defaultCurrency,
              exchangeRates,
            )
          : fundValue
        totalVariableRentValue += convertedFundValue
      })
    }

    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const walletValue = wallet.market_value || 0
        const convertedWalletValue =
          exchangeRates && wallet.currency
            ? convertCurrency(
                walletValue,
                wallet.currency,
                defaultCurrency,
                exchangeRates,
              )
            : walletValue
        totalVariableRentValue += convertedWalletValue

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value && token.market_value > 0) {
              const convertedTokenValue =
                exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      defaultCurrency,
                      exchangeRates,
                    )
                  : token.market_value
              totalVariableRentValue += convertedTokenValue
            }
          })
        }
      })
    }
  })

  Object.values(positionsData.positions).forEach(entityPosition => {
    const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
    if (
      cryptoProduct &&
      "entries" in cryptoProduct &&
      cryptoProduct.entries.length > 0
    ) {
      cryptoProduct.entries.forEach((wallet: any) => {
        const entityName = entityPosition.entity?.name || "Unknown"

        if (wallet.market_value && wallet.market_value > 0) {
          const symbol = wallet.symbol || wallet.crypto || "Unknown"
          const key = `${symbol}-${entityName}`

          const convertedValue =
            exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.market_value,
                  wallet.currency,
                  defaultCurrency,
                  exchangeRates,
                )
              : wallet.market_value

          const convertedInitialInvestment =
            wallet.initial_investment && exchangeRates && wallet.currency
              ? convertCurrency(
                  wallet.initial_investment,
                  wallet.currency,
                  defaultCurrency,
                  exchangeRates,
                )
              : wallet.initial_investment || convertedValue

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
          cryptoAggregation[key].value += convertedValue
          cryptoAggregation[key].initialInvestment += convertedInitialInvestment
          cryptoAggregation[key].addresses.add(wallet.address)
        }

        if (wallet.tokens) {
          wallet.tokens.forEach((token: any) => {
            if (token.market_value && token.market_value > 0) {
              const symbol = token.symbol || "Unknown"
              const key = symbol

              const convertedValue =
                exchangeRates && token.currency
                  ? convertCurrency(
                      token.market_value,
                      token.currency,
                      defaultCurrency,
                      exchangeRates,
                    )
                  : token.market_value

              const convertedInitialInvestment =
                token.initial_investment && exchangeRates && token.currency
                  ? convertCurrency(
                      token.initial_investment,
                      token.currency,
                      defaultCurrency,
                      exchangeRates,
                    )
                  : token.initial_investment || convertedValue

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
              cryptoAggregation[key].value += convertedValue
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
        percentageOfTotalVariableRent:
          totalVariableRentValue > 0
            ? (value / totalVariableRentValue) * 100
            : 0,
        id: `crypto-${crypto.symbol}-${entitiesArray.join("-")}-${index}`,
      }
    },
  )

  const sortedCryptoPositions = allCryptoPositions.sort(
    (a, b) => b.value - a.value,
  )

  if (sortedCryptoPositions.length > 0) {
    const totalCryptoValue = sortedCryptoPositions.reduce(
      (sum, pos) => sum + pos.value,
      0,
    )

    if (totalCryptoValue > 0 && totalVariableRentValue > 0) {
      let remainingPercentage =
        (totalCryptoValue / totalVariableRentValue) * 100

      sortedCryptoPositions.forEach((pos, index) => {
        if (index === sortedCryptoPositions.length - 1) {
          pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
        } else {
          const exactPercentage = (pos.value / totalVariableRentValue) * 100
          const roundedPercentage = Math.round(exactPercentage * 100) / 100
          pos.percentageOfTotalVariableRent = roundedPercentage
          remainingPercentage -= roundedPercentage
        }
      })
    }
  }

  return sortedCryptoPositions
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
      displayType: [
        TxType.BUY,
        TxType.INVESTMENT,
        TxType.SUBSCRIPTION,
        TxType.SWAP_FROM,
        TxType.SWAP_TO,
      ].includes(tx.type)
        ? ("out" as const)
        : ("in" as const),
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
