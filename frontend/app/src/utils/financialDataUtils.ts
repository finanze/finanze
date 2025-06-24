import { EntitiesPosition } from "@/types/position"
import { TransactionsResult, TxType } from "@/types/transactions"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { ExchangeRates } from "@/types"

/**
 * Convert amount from one currency to another using exchange rates
 */
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
  entities: string[] // Changed from single entity to array of entities
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

/**
 * Calculate asset distribution by asset type
 */
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
    if (entityPosition.accounts && entityPosition.accounts.length > 0) {
      const accountsTotal = entityPosition.accounts.reduce((sum, account) => {
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
      }, 0)
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

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details &&
        entityPosition.investments.funds.details.length > 0
      ) {
        if (!assetTypes["FUND"]) {
          assetTypes["FUND"] = {
            type: "FUND",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const fundsMarketValue =
          entityPosition.investments.funds.details.reduce((sum, fund) => {
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
          }, 0)
        assetTypes["FUND"].value += fundsMarketValue
        totalValue += fundsMarketValue
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details &&
        entityPosition.investments.stocks.details.length > 0
      ) {
        if (!assetTypes["STOCK_ETF"]) {
          assetTypes["STOCK_ETF"] = {
            type: "STOCK_ETF",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const stocksMarketValue =
          entityPosition.investments.stocks.details.reduce((sum, stock) => {
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
          }, 0)
        assetTypes["STOCK_ETF"].value += stocksMarketValue
        totalValue += stocksMarketValue
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details &&
        entityPosition.investments.deposits.details.length > 0
      ) {
        if (!assetTypes["DEPOSIT"]) {
          assetTypes["DEPOSIT"] = {
            type: "DEPOSIT",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const depositsTotal =
          entityPosition.investments.deposits.details.reduce((sum, deposit) => {
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
          }, 0)
        assetTypes["DEPOSIT"].value += depositsTotal
        totalValue += depositsTotal
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details &&
        entityPosition.investments.real_state_cf.details.length > 0
      ) {
        if (!assetTypes["REAL_STATE_CF"]) {
          assetTypes["REAL_STATE_CF"] = {
            type: "REAL_STATE_CF",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const realStateCfTotal =
          entityPosition.investments.real_state_cf.details.reduce(
            (sum, project) => {
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

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details &&
        entityPosition.investments.factoring.details.length > 0
      ) {
        if (!assetTypes["FACTORING"]) {
          assetTypes["FACTORING"] = {
            type: "FACTORING",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const factoringTotal =
          entityPosition.investments.factoring.details.reduce(
            (sum, factoring) => {
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

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.total
      ) {
        if (!assetTypes["CROWDLENDING"]) {
          assetTypes["CROWDLENDING"] = {
            type: "CROWDLENDING",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        const crowdlendingTotal = entityPosition.investments.crowdlending.total
        const convertedCrowdlendingTotal =
          targetCurrency && exchangeRates
            ? convertCurrency(
                crowdlendingTotal,
                entityPosition.investments.crowdlending.currency,
                targetCurrency,
                exchangeRates,
              )
            : crowdlendingTotal
        assetTypes["CROWDLENDING"].value += convertedCrowdlendingTotal
        totalValue += convertedCrowdlendingTotal
      }

      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        if (!assetTypes["CRYPTO"]) {
          assetTypes["CRYPTO"] = {
            type: "CRYPTO",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }

        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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
    }
  })

  Object.values(assetTypes).forEach(asset => {
    asset.percentage =
      totalValue > 0 ? Math.round((asset.value / totalValue) * 100) : 0
  })

  return Object.values(assetTypes).sort((a, b) => b.value - a.value)
}

/**
 * Calculate asset distribution by entity
 */
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

    // Calculate cash from accounts
    if (entityPosition.accounts && entityPosition.accounts.length > 0) {
      const accountsTotal = entityPosition.accounts.reduce((sum, account) => {
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
      }, 0)
      entityTotal += accountsTotal
    }

    // Calculate investments
    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details &&
        entityPosition.investments.funds.details.length > 0
      ) {
        const fundsMarketValue =
          entityPosition.investments.funds.details.reduce((sum, fund) => {
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
          }, 0)
        entityTotal += fundsMarketValue
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details &&
        entityPosition.investments.stocks.details.length > 0
      ) {
        const stocksMarketValue =
          entityPosition.investments.stocks.details.reduce((sum, stock) => {
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
          }, 0)
        entityTotal += stocksMarketValue
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details &&
        entityPosition.investments.deposits.details.length > 0
      ) {
        const depositsTotal =
          entityPosition.investments.deposits.details.reduce((sum, deposit) => {
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
          }, 0)
        entityTotal += depositsTotal
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details &&
        entityPosition.investments.real_state_cf.details.length > 0
      ) {
        const realStateCfTotal =
          entityPosition.investments.real_state_cf.details.reduce(
            (sum, project) => {
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

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details &&
        entityPosition.investments.factoring.details.length > 0
      ) {
        const factoringTotal =
          entityPosition.investments.factoring.details.reduce(
            (sum, factoring) => {
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

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.total
      ) {
        const amount = entityPosition.investments.crowdlending.total
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                entityPosition.investments.crowdlending.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        entityTotal += convertedAmount
      }

      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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

  // Calculate percentages with proper rounding to ensure they sum to 100%
  if (totalValue > 0) {
    const entityList = Object.values(entities)
    let remainingPercentage = 100

    // Calculate exact percentages first
    const exactPercentages = entityList.map(entity => ({
      entity,
      exactPercentage: (entity.value / totalValue) * 100,
    }))

    // Sort by exact percentage descending to allocate largest percentages first
    exactPercentages.sort((a, b) => b.exactPercentage - a.exactPercentage)

    // Assign rounded percentages, keeping track of remainder
    exactPercentages.forEach((item, index) => {
      if (index === exactPercentages.length - 1) {
        // Last item gets the remaining percentage to ensure sum is 100%
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

/**
 * Calculate total assets value
 */
export const getTotalAssets = (
  positionsData: EntitiesPosition | null,
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let total = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.accounts) {
      entityPosition.accounts.forEach(account => {
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
        total += convertedTotal
      })
    }

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details &&
        entityPosition.investments.funds.details.length > 0
      ) {
        const fundsMarketValue =
          entityPosition.investments.funds.details.reduce((sum, fund) => {
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
          }, 0)
        total += fundsMarketValue
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details &&
        entityPosition.investments.stocks.details.length > 0
      ) {
        const stocksMarketValue =
          entityPosition.investments.stocks.details.reduce((sum, stock) => {
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
          }, 0)
        total += stocksMarketValue
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details &&
        entityPosition.investments.deposits.details.length > 0
      ) {
        const depositsTotal =
          entityPosition.investments.deposits.details.reduce((sum, deposit) => {
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
          }, 0)
        total += depositsTotal
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details &&
        entityPosition.investments.real_state_cf.details.length > 0
      ) {
        const realStateCfTotal =
          entityPosition.investments.real_state_cf.details.reduce(
            (sum, project) => {
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

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details &&
        entityPosition.investments.factoring.details.length > 0
      ) {
        const factoringTotal =
          entityPosition.investments.factoring.details.reduce(
            (sum, factoring) => {
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

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.total
      ) {
        const amount = entityPosition.investments.crowdlending.total
        const convertedAmount =
          targetCurrency && exchangeRates
            ? convertCurrency(
                amount,
                entityPosition.investments.crowdlending.currency,
                targetCurrency,
                exchangeRates,
              )
            : amount
        total += convertedAmount
      }

      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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
    }
  })

  return total
}

/**
 * Calculate total invested amount
 */
export const getTotalInvestedAmount = (
  positionsData: EntitiesPosition | null,
  targetCurrency?: string,
  exchangeRates?: ExchangeRates | null,
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let totalInvested = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.accounts) {
      entityPosition.accounts.forEach(account => {
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
        totalInvested += convertedTotal
      })
    }

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details
      ) {
        entityPosition.investments.funds.details.forEach(fund => {
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

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details
      ) {
        entityPosition.investments.stocks.details.forEach(stock => {
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

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details
      ) {
        entityPosition.investments.deposits.details.forEach(deposit => {
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

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details
      ) {
        entityPosition.investments.real_state_cf.details.forEach(project => {
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

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details
      ) {
        entityPosition.investments.factoring.details.forEach(factoring => {
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

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.details
      ) {
        entityPosition.investments.crowdlending.details.forEach(loan => {
          const amount = loan.amount || 0
          const convertedAmount =
            targetCurrency &&
            exchangeRates &&
            entityPosition.investments?.crowdlending?.currency
              ? convertCurrency(
                  amount,
                  entityPosition.investments.crowdlending.currency,
                  targetCurrency,
                  exchangeRates,
                )
              : amount
          totalInvested += convertedAmount
        })
      }

      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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
    }
  })

  return totalInvested
}

/**
 * Get ongoing projects (deposits, real estate, factoring with maturity dates)
 */
export const getOngoingProjects = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
): OngoingProject[] => {
  if (!positionsData || !positionsData.positions) return []

  const projects: OngoingProject[] = []

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.investments) {
      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details
      ) {
        entityPosition.investments.deposits.details.forEach(deposit => {
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

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details
      ) {
        entityPosition.investments.real_state_cf.details.forEach(project => {
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

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details
      ) {
        entityPosition.investments.factoring.details.forEach(factoring => {
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
    }
  })

  return projects
    .sort(
      (a, b) => new Date(a.maturity).getTime() - new Date(b.maturity).getTime(),
    )
    .slice(0, 12)
}

/**
 * Get stock and fund positions
 */
export const getStockAndFundPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates?: ExchangeRates | null,
): StockFundPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  const allPositionsRaw: any[] = []
  let totalVariableRentValue = 0

  // First pass: calculate total variable rent value (stocks + funds + crypto)
  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.investments) {
      // Add stocks value
      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details
      ) {
        entityPosition.investments.stocks.details.forEach(stock => {
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

      // Add funds value
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details
      ) {
        entityPosition.investments.funds.details.forEach(fund => {
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

      // Add crypto value
      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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
    }
  })

  // Second pass: collect stock and fund positions
  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.investments) {
      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details
      ) {
        entityPosition.investments.stocks.details.forEach(stock => {
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
            change:
              (value / (stock.initial_investment || value || 1) - 1) * 100,
            entity: entityPosition.entity?.name,
          })
        })
      }

      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details
      ) {
        entityPosition.investments.funds.details.forEach(fund => {
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

  // Ensure percentages sum to exactly the portion they represent
  const sortedPositions = enrichedPositions
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  // Adjust percentages to account for rounding and ensure consistency
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
          // Last item gets the remaining percentage
          pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
        } else {
          const exactPercentage =
            (convertedValue / totalVariableRentValue) * 100
          const roundedPercentage = Math.round(exactPercentage * 100) / 100 // Round to 2 decimal places
          pos.percentageOfTotalVariableRent = roundedPercentage
          remainingPercentage -= roundedPercentage
        }
      })
    }
  }

  return sortedPositions
}

/**
 * Get crypto positions with percentage calculated against total variable rent (stocks + funds + crypto)
 */
export const getCryptoPositions = (
  positionsData: EntitiesPosition | null,
  locale: string,
  defaultCurrency: string,
  exchangeRates?: ExchangeRates | null,
): CryptoPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  const cryptoAggregation: Record<string, any> = {}
  let totalVariableRentValue = 0

  // First pass: calculate total variable rent value (stocks + funds + crypto)
  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.investments) {
      // Add stocks value
      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details
      ) {
        entityPosition.investments.stocks.details.forEach(stock => {
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

      // Add funds value
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details
      ) {
        entityPosition.investments.funds.details.forEach(fund => {
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

      // Add crypto value
      if (
        entityPosition.investments.crypto_currencies &&
        entityPosition.investments.crypto_currencies.details
      ) {
        entityPosition.investments.crypto_currencies.details.forEach(wallet => {
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

          // Include tokens if they exist
          if (wallet.tokens) {
            wallet.tokens.forEach(token => {
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
    }
  })

  // Second pass: aggregate crypto positions
  Object.values(positionsData.positions).forEach(entityPosition => {
    if (
      entityPosition.investments &&
      entityPosition.investments.crypto_currencies &&
      entityPosition.investments.crypto_currencies.details
    ) {
      entityPosition.investments.crypto_currencies.details.forEach(wallet => {
        const entityName = entityPosition.entity?.name || "Unknown"

        // Process main wallet crypto - each entity gets separate entry
        if (wallet.market_value && wallet.market_value > 0) {
          const symbol = wallet.symbol || wallet.crypto || "Unknown"
          const key = `${symbol}-${entityName}` // Use symbol-entity for main cryptos

          // Convert wallet value to default currency
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
              currency: defaultCurrency, // Always use defaultCurrency for display
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

        // Process tokens - aggregate across entities
        if (wallet.tokens) {
          wallet.tokens.forEach(token => {
            if (token.market_value && token.market_value > 0) {
              const symbol = token.symbol || "Unknown"
              const key = symbol // Only use symbol as key for tokens

              // Convert token value to default currency
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
                  currency: defaultCurrency, // Always use defaultCurrency for display
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

  // Convert aggregated data to final format
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

      // For tokens: use token name and show entity badges
      // For main crypto: use entity name and no badges
      const displayName = isToken ? crypto.name : entitiesArray[0] // For main crypto, use the entity name

      return {
        symbol: crypto.symbol,
        name: displayName,
        address: Array.from(crypto.addresses).join(", "), // Join multiple addresses
        amount: crypto.amount,
        price: crypto.amount > 0 ? value / crypto.amount : 0,
        value: value,
        currency: defaultCurrency, // Always use defaultCurrency for crypto display
        formattedValue: formatCurrency(
          value,
          locale,
          defaultCurrency,
          defaultCurrency, // Force display in defaultCurrency
        ),
        type: crypto.type,
        change: change,
        entities: entitiesArray, // Array of entities where this crypto is held
        showEntityBadge: isToken, // Only show entity badges for tokens
        percentageOfTotalVariableRent:
          totalVariableRentValue > 0
            ? (value / totalVariableRentValue) * 100
            : 0,
        id: `crypto-${crypto.symbol}-${entitiesArray.join("-")}-${index}`,
      }
    },
  )

  const sortedCryptoPositions = allCryptoPositions
    .sort((a, b) => b.value - a.value)
    .slice(0, 10)

  // Ensure crypto percentages are accurate and consistent with the bar display
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
          // Last item gets the remaining percentage
          pos.percentageOfTotalVariableRent = Math.max(0, remainingPercentage)
        } else {
          const exactPercentage = (pos.value / totalVariableRentValue) * 100
          const roundedPercentage = Math.round(exactPercentage * 100) / 100 // Round to 2 decimal places
          pos.percentageOfTotalVariableRent = roundedPercentage
          remainingPercentage -= roundedPercentage
        }
      })
    }
  }

  return sortedCryptoPositions
}

/**
 * Get recent transactions grouped by date
 */
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
    .slice(0, 10)
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

/**
 * Get days status for maturity date
 */
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
