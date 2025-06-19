import { EntitiesPosition } from "@/types/position"
import { TransactionsResult, TxType } from "@/types/transactions"
import { formatCurrency, formatDate } from "@/lib/formatters"

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
): AssetDistributionItem[] => {
  if (!positionsData || !positionsData.positions) return []

  const assetTypes: Record<
    string,
    { type: string; value: number; percentage: number; change: number }
  > = {}
  let totalValue = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.accounts && entityPosition.accounts.length > 0) {
      const accountsTotal = entityPosition.accounts.reduce(
        (sum, account) => sum + (account.total || 0),
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

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.market_value
      ) {
        if (!assetTypes["FUND"]) {
          assetTypes["FUND"] = {
            type: "FUND",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["FUND"].value +=
          entityPosition.investments.funds.market_value
        totalValue += entityPosition.investments.funds.market_value
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.market_value
      ) {
        if (!assetTypes["STOCK_ETF"]) {
          assetTypes["STOCK_ETF"] = {
            type: "STOCK_ETF",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["STOCK_ETF"].value +=
          entityPosition.investments.stocks.market_value
        totalValue += entityPosition.investments.stocks.market_value
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.total
      ) {
        if (!assetTypes["DEPOSIT"]) {
          assetTypes["DEPOSIT"] = {
            type: "DEPOSIT",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["DEPOSIT"].value += entityPosition.investments.deposits.total
        totalValue += entityPosition.investments.deposits.total
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.total
      ) {
        if (!assetTypes["REAL_STATE_CF"]) {
          assetTypes["REAL_STATE_CF"] = {
            type: "REAL_STATE_CF",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["REAL_STATE_CF"].value +=
          entityPosition.investments.real_state_cf.total
        totalValue += entityPosition.investments.real_state_cf.total
      }

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.total
      ) {
        if (!assetTypes["FACTORING"]) {
          assetTypes["FACTORING"] = {
            type: "FACTORING",
            value: 0,
            percentage: 0,
            change: 0,
          }
        }
        assetTypes["FACTORING"].value +=
          entityPosition.investments.factoring.total
        totalValue += entityPosition.investments.factoring.total
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
        assetTypes["CROWDLENDING"].value +=
          entityPosition.investments.crowdlending.total
        totalValue += entityPosition.investments.crowdlending.total
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
      const accountsTotal = entityPosition.accounts.reduce(
        (sum, account) => sum + (account.total || 0),
        0,
      )
      entityTotal += accountsTotal
    }

    // Calculate investments
    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.market_value
      ) {
        entityTotal += entityPosition.investments.funds.market_value
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.market_value
      ) {
        entityTotal += entityPosition.investments.stocks.market_value
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.total
      ) {
        entityTotal += entityPosition.investments.deposits.total
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.total
      ) {
        entityTotal += entityPosition.investments.real_state_cf.total
      }

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.total
      ) {
        entityTotal += entityPosition.investments.factoring.total
      }

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.total
      ) {
        entityTotal += entityPosition.investments.crowdlending.total
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

  // Calculate percentages
  Object.values(entities).forEach(entity => {
    entity.percentage =
      totalValue > 0 ? Math.round((entity.value / totalValue) * 100) : 0
  })

  return Object.values(entities).sort((a, b) => b.value - a.value)
}

/**
 * Calculate total assets value
 */
export const getTotalAssets = (
  positionsData: EntitiesPosition | null,
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let total = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.accounts) {
      entityPosition.accounts.forEach(account => {
        total += account.total || 0
      })
    }

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.market_value
      ) {
        total += entityPosition.investments.funds.market_value
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.market_value
      ) {
        total += entityPosition.investments.stocks.market_value
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.total
      ) {
        total += entityPosition.investments.deposits.total
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.total
      ) {
        total += entityPosition.investments.real_state_cf.total
      }

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.total
      ) {
        total += entityPosition.investments.factoring.total
      }

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.total
      ) {
        total += entityPosition.investments.crowdlending.total
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
): number => {
  if (!positionsData || !positionsData.positions) return 0

  let totalInvested = 0

  Object.values(positionsData.positions).forEach(entityPosition => {
    if (entityPosition.accounts) {
      entityPosition.accounts.forEach(account => {
        totalInvested += account.total || 0
      })
    }

    if (entityPosition.investments) {
      if (
        entityPosition.investments.funds &&
        entityPosition.investments.funds.details
      ) {
        entityPosition.investments.funds.details.forEach(fund => {
          totalInvested += fund.initial_investment || fund.market_value || 0
        })
      }

      if (
        entityPosition.investments.stocks &&
        entityPosition.investments.stocks.details
      ) {
        entityPosition.investments.stocks.details.forEach(stock => {
          totalInvested +=
            stock.initial_investment ||
            (stock.shares && stock.average_buy_price
              ? stock.shares * stock.average_buy_price
              : stock.market_value || 0)
        })
      }

      if (
        entityPosition.investments.deposits &&
        entityPosition.investments.deposits.details
      ) {
        entityPosition.investments.deposits.details.forEach(deposit => {
          totalInvested += deposit.amount || 0
        })
      }

      if (
        entityPosition.investments.real_state_cf &&
        entityPosition.investments.real_state_cf.details
      ) {
        entityPosition.investments.real_state_cf.details.forEach(project => {
          totalInvested += project.amount || 0
        })
      }

      if (
        entityPosition.investments.factoring &&
        entityPosition.investments.factoring.details
      ) {
        entityPosition.investments.factoring.details.forEach(factoring => {
          totalInvested += factoring.amount || 0
        })
      }

      if (
        entityPosition.investments.crowdlending &&
        entityPosition.investments.crowdlending.details
      ) {
        entityPosition.investments.crowdlending.details.forEach(loan => {
          totalInvested += loan.amount || 0
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
  defaultCurrency?: string,
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
                defaultCurrency || "EUR",
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
                defaultCurrency || "EUR",
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
                defaultCurrency || "EUR",
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
  defaultCurrency?: string,
): StockFundPosition[] => {
  if (!positionsData || !positionsData.positions) return []

  const allPositionsRaw: any[] = []
  let totalVariableRentValue = 0

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
              defaultCurrency || "EUR",
              stock.currency,
            ),
            type: "STOCK_ETF",
            change:
              (value / (stock.initial_investment || value || 1) - 1) * 100,
            entity: entityPosition.entity?.name,
          })
          totalVariableRentValue += value
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
              defaultCurrency || "EUR",
              fund.currency,
            ),
            type: "FUND",
            change: (value / (fund.initial_investment || value || 1) - 1) * 100,
            entity: entityPosition.entity?.name,
          })
          totalVariableRentValue += value
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

  return enrichedPositions.sort((a, b) => b.value - a.value).slice(0, 10)
}

/**
 * Get recent transactions grouped by date
 */
export const getRecentTransactions = (
  transactions: TransactionsResult | null,
  locale: string,
  defaultCurrency?: string,
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
        defaultCurrency || "EUR",
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
