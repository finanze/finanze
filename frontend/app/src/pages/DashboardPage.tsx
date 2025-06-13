import { useEffect, useRef, useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { getTransactions } from "@/services/api"
import { TransactionsResult, TxType } from "@/types/transactions"
import { formatCurrency, formatPercentage, formatDate } from "@/lib/formatters"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  getIconForProjectType,
  getPieSliceColorForAssetType,
  getIconForAssetType,
  getIconForTxType,
} from "@/utils/dashboardUtils"
import {
  PieChart as PieChartIcon,
  Wallet,
  TrendingUp,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Receipt,
  BarChart3,
} from "lucide-react"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { EntityRefreshDropdown } from "@/components/EntityRefreshDropdown"

export default function DashboardPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const {
    positionsData,
    isLoading: financialDataLoading,
    error: financialDataError,
    refreshData: refreshFinancialData,
  } = useFinancialData()
  const { settings, inactiveEntities } = useAppContext()

  const [transactions, setTransactions] = useState<TransactionsResult | null>(
    null,
  )
  const [transactionsLoading, setTransactionsLoading] = useState(true)
  const [transactionsError, setTransactionsError] = useState<string | null>(
    null,
  )

  const fetchTransactionsData = async () => {
    if (inactiveEntities && inactiveEntities.length > 0) {
      setTransactionsLoading(true)
      setTransactionsError(null)
      try {
        const entityIds = inactiveEntities.map(entity => entity.id)
        const result = await getTransactions({ entities: entityIds, limit: 8 })
        setTransactions(result)
      } catch (err) {
        console.error("Error fetching transactions:", err)
        setTransactionsError(t.errors.UNEXPECTED_ERROR)
      } finally {
        setTransactionsLoading(false)
      }
    } else {
      setTransactions(null)
      setTransactionsLoading(false)
    }
  }

  const projectsContainerRef = useRef<HTMLDivElement>(null)
  const assetDistributionCardRef = useRef<HTMLDivElement>(null)

  const [showLeftScroll, setShowLeftScroll] = useState(false)
  const [showRightScroll, setShowRightScroll] = useState(true)

  const [assetDistributionCardSmall, setAssetDistributionCardSmall] =
    useState(false)

  const hasData =
    positionsData !== null &&
    positionsData.positions &&
    Object.keys(positionsData.positions).length > 0

  useEffect(() => {
    const assetDistributionCardElement = assetDistributionCardRef.current

    const checkScreenSize = () => {
      if (assetDistributionCardElement) {
        setAssetDistributionCardSmall(
          assetDistributionCardElement.clientWidth < 600,
        )
      }
    }

    if (assetDistributionCardElement) {
      checkScreenSize()
      const resizeObserver = new ResizeObserver(checkScreenSize)
      resizeObserver.observe(assetDistributionCardElement)

      return () => {
        resizeObserver.unobserve(assetDistributionCardElement)
      }
    }
  }, [hasData, assetDistributionCardRef.current])

  useEffect(() => {
    fetchTransactionsData()
  }, [inactiveEntities, t]) // Add t to dependency array if it's not already there and used in fetchTransactionsData

  const getDaysStatus = (dateString: string) => {
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

  const getAssetDistribution = () => {
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
          assetTypes["DEPOSIT"].value +=
            entityPosition.investments.deposits.total
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

  const getTotalAssets = (): number => {
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

  const getTotalInvestedAmount = (): number => {
    if (!positionsData || !positionsData.positions) return 0

    let totalInvested = 0

    Object.values(positionsData.positions).forEach(entityPosition => {
      // Accounts are considered as cash, their invested amount is their current value
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

  const getOngoingProjects = () => {
    if (!positionsData || !positionsData.positions) return []

    const projects: any[] = []

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
                  settings?.mainCurrency,
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
                  settings?.mainCurrency,
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
                  settings?.mainCurrency,
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
        (a, b) =>
          new Date(a.maturity).getTime() - new Date(b.maturity).getTime(),
      )
      .slice(0, 12)
  }

  const getStockAndFundPositions = () => {
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
              symbol: stock.ticker || "", // Changed: Use ticker or empty string, remove ISIN fallback
              name: stock.name,
              shares: stock.shares || 0,
              price: stock.average_buy_price || 0,
              value: value,
              currency: stock.currency,
              formattedValue: formatCurrency(
                value,
                locale,
                settings?.mainCurrency,
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
              symbol: "", // Changed: Set symbol to empty string for funds
              name: fund.name,
              portfolioName: fund.portfolio?.name || null, // Added portfolioName
              shares: fund.shares || 0,
              price: fund.average_buy_price || 0,
              value: value,
              currency: fund.currency,
              formattedValue: formatCurrency(
                value,
                locale,
                settings?.mainCurrency,
                fund.currency,
              ),
              type: "FUND",
              change:
                (value / (fund.initial_investment || value || 1) - 1) * 100,
              entity: entityPosition.entity?.name,
            })
            totalVariableRentValue += value
          })
        }
      }
    })

    const enrichedPositions = allPositionsRaw.map(pos => ({
      ...pos,
      percentageOfTotalVariableRent:
        totalVariableRentValue > 0
          ? (pos.value / totalVariableRentValue) * 100
          : 0,
    }))

    return enrichedPositions.sort((a, b) => b.value - a.value).slice(0, 10) // Keep top 10 for display
  }

  const getRecentTransactions = () => {
    if (!transactions || !transactions.transactions) return {} // Return an object for grouped transactions

    const groupedTxs: Record<string, any[]> = {}

    transactions.transactions
      .map(tx => ({
        date: tx.date,
        description: tx.name,
        amount: tx.amount,
        currency: tx.currency,
        formattedAmount: formatCurrency(
          tx.amount,
          locale,
          settings?.mainCurrency,
          tx.currency,
        ),
        type: tx.type,
        product_type: tx.product_type,
        displayType: ["SELL", "REPAYMENT"].includes(tx.type)
          ? "expense"
          : "income",
        entity: tx.entity.name,
      }))
      .slice(0, 10) // Keep overall limit for recent transactions
      .forEach(tx => {
        const dateKey = formatDate(tx.date, locale)
        if (!groupedTxs[dateKey]) {
          groupedTxs[dateKey] = []
        }
        groupedTxs[dateKey].push(tx)
      })

    // Sort dates in descending order
    const sortedDates = Object.keys(groupedTxs).sort((a, b) => {
      // Assuming dateKey is in a format that can be converted to Date
      // Adjust parsing if formatDate produces a different format
      const dateA = new Date(a.split("/").reverse().join("-")) // Example: dd/mm/yyyy to yyyy-mm-dd
      const dateB = new Date(b.split("/").reverse().join("-"))
      return dateB.getTime() - dateA.getTime()
    })

    const sortedGroupedTxs: Record<string, any[]> = {}
    sortedDates.forEach(date => {
      sortedGroupedTxs[date] = groupedTxs[date]
    })

    return sortedGroupedTxs
  }

  const handleScroll = () => {
    if (projectsContainerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } =
        projectsContainerRef.current
      setShowLeftScroll(scrollLeft > 0)
      setShowRightScroll(scrollLeft < scrollWidth - clientWidth - 10)
    }
  }

  const scrollProjects = (direction: "left" | "right") => {
    if (projectsContainerRef.current) {
      const scrollAmount = 300
      const newScrollLeft =
        direction === "left"
          ? projectsContainerRef.current.scrollLeft - scrollAmount
          : projectsContainerRef.current.scrollLeft + scrollAmount

      projectsContainerRef.current.scrollTo({
        left: newScrollLeft,
        behavior: "smooth",
      })
    }
  }

  const assetDistribution = getAssetDistribution()
  const totalAssets = getTotalAssets()
  const ongoingProjects = getOngoingProjects()
  const stockAndFundPositions = getStockAndFundPositions()
  const recentTransactions = getRecentTransactions()
  const totalInvestedAmount = getTotalInvestedAmount()

  const fundItems = stockAndFundPositions
    .filter(p => p.type === "FUND")
    .map((p, index) => ({
      ...p,
      id: `fund-${p.name}-${p.entity}-${p.portfolioName || "default"}-${index}`, // Enhanced ID
    }))

  const stockItems = stockAndFundPositions
    .filter(p => p.type === "STOCK_ETF")
    .map((p, index) => ({
      ...p,
      id: `${p.symbol}-stock-${index}-${p.entity}`,
    }))

  // Generate a stable color map for fund portfolios
  const fundPortfolioColorMap = useMemo(() => {
    const uniqueNames = Array.from(
      new Set(
        fundItems
          .filter(item => item.portfolioName)
          .map(item => item.portfolioName as string),
      ),
    )
    const colors = [
      "bg-sky-500",
      "bg-blue-500",
      "bg-indigo-500",
      "bg-violet-500",
      "bg-purple-500",
      "bg-fuchsia-500",
      "bg-pink-500",
      "bg-rose-500",
      "bg-cyan-500",
      "bg-teal-500",
      "bg-emerald-500",
      "bg-green-500",
      "bg-lime-500",
      "bg-yellow-500",
      "bg-amber-500",
      "bg-orange-500",
    ]
    const mapping = new Map<string, string>()
    uniqueNames.forEach((name, i) => {
      mapping.set(name, colors[i % colors.length])
    })
    return mapping
  }, [fundItems])

  // Define base color lists for items
  const ITEM_FUND_COLORS = [
    "bg-sky-500",
    "bg-sky-400",
    "bg-sky-300",
    "bg-sky-600",
    "bg-sky-700",
    "bg-cyan-500",
    "bg-cyan-400",
    "bg-green-500",
    "bg-green-400",
    "bg-teal-500",
    "bg-teal-400",
    "bg-emerald-500",
    "bg-emerald-400",
    "bg-lime-500",
    "bg-lime-400",
    "bg-yellow-500",
    "bg-yellow-400",
  ]
  const ITEM_STOCK_COLORS = [
    "bg-violet-500",
    "bg-violet-400",
    "bg-violet-300",
    "bg-violet-600",
    "bg-violet-700",
    "bg-purple-500",
    "bg-purple-400",
    "bg-pink-500",
    "bg-pink-400",
    "bg-rose-500",
    "bg-rose-400",
    "bg-red-500",
    "bg-red-400",
    "bg-orange-500",
    "bg-orange-400",
    "bg-amber-500",
    "bg-amber-400",
  ]

  // Helper function to shuffle an array
  const shuffle = <T,>(arr: T[]): T[] =>
    arr
      .map(value => ({ value, sort: Math.random() }))
      .sort((a, b) => a.sort - b.sort)
      .map(({ value }) => value)

  // Memoize the shuffled color lists to ensure they are generated only once
  const shuffledFundItemColors = useMemo(() => shuffle(ITEM_FUND_COLORS), [])
  const shuffledStockItemColors = useMemo(() => shuffle(ITEM_STOCK_COLORS), [])

  const getItemColorByIndex = (index: number, type: "FUND" | "STOCK_ETF") => {
    const colors =
      type === "FUND" ? shuffledFundItemColors : shuffledStockItemColors
    return colors[index % colors.length]
  }

  const CustomLegend = (props: any) => {
    const { payload } = props
    return (
      <ul className="space-y-1.5 text-xs scrollbar-thin pr-0.5">
        {" "}
        {/* Removed max-h and overflow-y */}
        {payload.map((entry: any, index: number) => {
          const assetType = entry.payload.payload.type
          const assetValue = entry.payload.payload.value
          const assetPercentage = entry.payload.payload.percentage
          const icon = getIconForAssetType(assetType)

          return (
            <li
              key={`legend-item-${index}`}
              className="flex items-center space-x-2 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer"
              title={`${(t.enums.productType as any)[assetType] || assetType.toLowerCase().replace(/_/g, " ")}: ${formatCurrency(assetValue, locale, settings?.mainCurrency)} (${assetPercentage}%)`}
            >
              <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
                {icon}
              </span>
              <span className="capitalize truncate flex-grow min-w-0">
                {(t.enums.productType as any)[assetType] ||
                  assetType.toLowerCase().replace(/_/g, " ")}
              </span>
              <div className="text-right flex space-x-1">
                <span className="font-bold block whitespace-nowrap">
                  {formatCurrency(assetValue, locale, settings?.mainCurrency)}
                </span>
                <span className="text-muted-foreground block whitespace-nowrap text-[10px]">
                  ({assetPercentage}%)
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    )
  }

  const isLoading = financialDataLoading || transactionsLoading

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-[70vh]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const error = financialDataError || transactionsError

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[70vh] text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-2xl font-bold mb-4">{t.common.error}</h2>
        <p className="text-gray-500 dark:text-gray-400 mb-8 max-w-md">
          {error}
        </p>
        <Button
          onClick={() => {
            refreshFinancialData()
            fetchTransactionsData()
          }}
        >
          {t.common.retry}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.common.dashboard}</h1>
        <div className="flex gap-2">
          <EntityRefreshDropdown />
          <Button
            variant="outline"
            size="icon"
            onClick={() => {
              refreshFinancialData()
              fetchTransactionsData()
            }}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </div>

      {!hasData ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="flex flex-col items-center justify-center h-[70vh] text-center"
        >
          <BarChart3 className="h-16 w-16 text-gray-400 mb-6" />
          <h2 className="text-2xl font-bold mb-3">{t.dashboard.noDataTitle}</h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md">
            {t.dashboard.noDataSubtitle}
          </p>
          <Button onClick={() => navigate("/entities")}>
            {t.dashboard.connectEntitiesButton}
          </Button>
        </motion.div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="md:col-span-7"
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-bold flex items-center">
                    <PieChartIcon className="h-5 w-5 mr-2 text-primary" />
                    {t.dashboard.assetDistribution}
                  </CardTitle>
                </CardHeader>
                <CardContent ref={assetDistributionCardRef}>
                  {assetDistribution.length > 0 ? (
                    <div
                      className={
                        assetDistributionCardSmall ? "h-[450px]" : "h-[300px]"
                      }
                    >
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={assetDistribution}
                            cx={assetDistributionCardSmall ? "50%" : "40%"}
                            cy={assetDistributionCardSmall ? "40%" : "50%"}
                            labelLine={false}
                            outerRadius={assetDistributionCardSmall ? 100 : 120}
                            fill="#8884d8"
                            dataKey="value"
                            nameKey="type"
                          >
                            {assetDistribution.map((entry, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={getPieSliceColorForAssetType(entry.type)}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(
                              value: number,
                              name: string,
                              props: any,
                            ) => [
                              // eslint-disable-next-line react/prop-types -- props are not typed
                              `${formatCurrency(value, locale, settings?.mainCurrency)} (${props.payload.percentage}%)`,
                              t.enums &&
                              t.enums.productType &&
                              (t.enums.productType as any)[name]
                                ? (t.enums.productType as any)[name]
                                : name.toLowerCase().replace(/_/g, " "),
                            ]}
                          />
                          <Legend
                            layout="vertical"
                            verticalAlign={
                              assetDistributionCardSmall ? "bottom" : "middle"
                            }
                            align={
                              assetDistributionCardSmall ? "center" : "right"
                            }
                            wrapperStyle={
                              assetDistributionCardSmall
                                ? {
                                    maxHeight: "200px",
                                    overflowY: "auto",
                                    paddingTop: "25px",
                                    width: "95%",
                                    margin: "0 auto",
                                  }
                                : {
                                    paddingRight: "20px",
                                    maxHeight: "260px",
                                    overflowY: "auto",
                                  }
                            }
                            content={<CustomLegend />}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {t.common.noDataAvailable}
                    </p>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="md:col-span-5"
            >
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-bold flex items-center">
                    <Wallet className="h-5 w-5 mr-2 text-primary" />
                    {t.dashboard.totalAssets}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between items-baseline">
                    <p className="text-4xl font-bold">
                      {formatCurrency(
                        totalAssets,
                        locale,
                        settings?.mainCurrency,
                      )}
                    </p>
                    {totalInvestedAmount > 0 &&
                      (() => {
                        const percentageValue =
                          ((totalAssets - totalInvestedAmount) /
                            totalInvestedAmount) *
                          100
                        const sign = percentageValue >= 0 ? "+" : "-"
                        return (
                          <p
                            className={`text-xl font-medium ${percentageValue === 0 ? "text-gray-500 dark:text-gray-400" : percentageValue > 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                          >
                            {sign}
                            {formatPercentage(
                              Math.abs(percentageValue),
                              locale,
                            )}
                          </p>
                        )
                      })()}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {t.dashboard.investedAmount}{" "}
                    {formatCurrency(
                      totalInvestedAmount,
                      locale,
                      settings?.mainCurrency,
                    )}
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {ongoingProjects.length > 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-lg font-bold flex items-center">
                      <TrendingUp className="h-5 w-5 mr-2 text-primary" />
                      {t.dashboard.ongoingProjects}
                    </CardTitle>
                  </div>
                  {ongoingProjects.length > 3 && (
                    <div className="flex space-x-2">
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => scrollProjects("left")}
                        disabled={!showLeftScroll}
                        className={
                          !showLeftScroll ? "opacity-50 cursor-not-allowed" : ""
                        }
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => scrollProjects("right")}
                        disabled={!showRightScroll}
                        className={
                          !showRightScroll
                            ? "opacity-50 cursor-not-allowed"
                            : ""
                        }
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  <div
                    ref={projectsContainerRef}
                    className="flex overflow-x-auto pb-4 space-x-4 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600"
                    onScroll={handleScroll}
                  >
                    {ongoingProjects.map((project, index) => {
                      const status = getDaysStatus(project.maturity)
                      return (
                        <Card
                          key={index}
                          className="bg-gray-50 dark:bg-gray-900 border flex-shrink-0 w-[320px]"
                        >
                          <CardContent className="p-4 flex flex-col justify-between h-full">
                            <div>
                              <div className="flex justify-between items-start mb-3">
                                <div className="flex-grow mr-2 min-w-0">
                                  <h3
                                    className="font-medium text-sm truncate"
                                    title={project.name}
                                  >
                                    {project.name}
                                  </h3>
                                  <div className="flex items-center text-xs text-muted-foreground mt-1">
                                    <Badge
                                      variant="outline"
                                      className="mr-2 text-xs py-0.5 px-1.5"
                                    >
                                      {project.entity}
                                    </Badge>
                                    <div className="flex items-center">
                                      {getIconForProjectType(project.type)}
                                      <span className="ml-1 capitalize">
                                        {t.enums &&
                                        t.enums.productType &&
                                        (t.enums.productType as any)[
                                          project.type
                                        ]
                                          ? (t.enums.productType as any)[
                                              project.type
                                            ]
                                          : project.type
                                              .toLowerCase()
                                              .replace(/_/g, " ")}
                                      </span>
                                    </div>
                                  </div>
                                </div>
                                <Badge
                                  variant="outline"
                                  className={`flex-shrink-0 h-auto px-2 py-1 text-center text-xs whitespace-nowrap ${
                                    status.isDelayed
                                      ? "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300"
                                      : status.days < 30
                                        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300"
                                        : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
                                  }`}
                                >
                                  <span className="font-semibold">
                                    {status.statusText}
                                  </span>
                                </Badge>
                              </div>
                            </div>
                            <div className="space-y-1 mt-auto">
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">
                                  {t.dashboard.value}
                                </span>
                                <span className="text-xs font-medium">
                                  {project.formattedValue}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">
                                  {t.dashboard.roi}
                                </span>
                                <span className="text-xs font-medium text-green-600">
                                  {formatPercentage(project.roi, locale)}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-xs text-muted-foreground">
                                  {t.dashboard.maturity}
                                </span>
                                <span className="text-xs">
                                  {formatDate(project.maturity, locale)}
                                </span>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ) : null}

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="md:col-span-7"
            >
              <Card className="h-full flex flex-col">
                <CardHeader>
                  <CardTitle className="text-lg font-bold flex items-center">
                    <BarChart3 className="h-5 w-5 mr-2 text-primary" />
                    {t.dashboard.stocksAndFunds.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-grow flex flex-col space-x-3 p-4 overflow-hidden min-h-[350px] max-h-[650px]">
                  {fundItems.length > 0 || stockItems.length > 0 ? (
                    <div className="flex flex-grow space-x-3 overflow-hidden">
                      <div className="flex-grow space-y-2 overflow-y-auto scrollbar-thin pr-2">
                        {fundItems.length > 0 ? (
                          <div className="pb-2">
                            <h3 className="text-sm font-semibold mb-1.5 text-muted-foreground sticky top-0 bg-card z-10 py-1">
                              {t.dashboard.stocksAndFunds.funds}
                            </h3>
                            {fundItems.map((item, index) => (
                              <div
                                key={item.id}
                                className="flex items-stretch space-x-2 py-1.5 border-b border-border last:border-b-0"
                              >
                                <div
                                  className={`flex-shrink-0 w-1 rounded-sm ${getItemColorByIndex(index, "FUND")}`}
                                ></div>
                                <div className="flex-grow min-w-0">
                                  {/* Line 1: Name, Portfolio Badge, Value */}
                                  <div className="flex justify-between items-center">
                                    <div className="flex items-center flex-grow min-w-0 mr-2">
                                      <span
                                        className="font-medium truncate text-base"
                                        title={item.name}
                                      >
                                        {item.name}
                                      </span>
                                      {item.portfolioName && (
                                        <Badge
                                          className={`ml-2 py-0.5 px-1.5 text-[10px] leading-tight rounded-md ${fundPortfolioColorMap.get(item.portfolioName as string) || "bg-gray-400"} ${(fundPortfolioColorMap.get(item.portfolioName as string) || "bg-gray-400").replace("bg-", "hover:bg-")} text-white`}
                                          title={item.portfolioName}
                                        >
                                          <span className="truncate max-w-[120px]">
                                            {item.portfolioName}
                                          </span>
                                        </Badge>
                                      )}
                                    </div>
                                    <span className="font-semibold whitespace-nowrap text-sm">
                                      {item.formattedValue}
                                    </span>
                                  </div>

                                  {/* Line 2: Change % */}
                                  <div className="flex justify-end items-center text-muted-foreground text-xs mt-0.5">
                                    <span
                                      className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                    >
                                      {formatPercentage(item.change, locale)}
                                    </span>
                                  </div>

                                  {/* Line 3: Entity and % of Portfolio Share */}
                                  <div className="flex justify-between items-center text-muted-foreground text-xs mt-0.5">
                                    <Badge
                                      variant="outline"
                                      className="py-0.5 px-1.5 text-[10px] leading-tight"
                                    >
                                      {item.entity}
                                    </Badge>
                                    <span className="text-[10px] whitespace-nowrap">
                                      {formatPercentage(
                                        item.percentageOfTotalVariableRent,
                                        locale,
                                      )}{" "}
                                      {t.dashboard.ofPortfolioShareShort}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {stockItems.length > 0 ? (
                          <div>
                            <h3 className="text-sm font-semibold mb-1.5 text-muted-foreground sticky top-0 bg-card z-10 py-1">
                              {t.dashboard.stocksAndFunds.stocksEtfs}
                            </h3>
                            {stockItems.map((item, index) => (
                              <div
                                key={item.id}
                                className="flex items-stretch space-x-2 py-1.5 border-b border-border last:border-b-0"
                              >
                                <div
                                  className={`flex-shrink-0 w-1 rounded-sm ${getItemColorByIndex(index, "STOCK_ETF")}`}
                                ></div>
                                <div className="flex-grow min-w-0">
                                  <div className="flex justify-between items-center">
                                    <span
                                      className="font-medium truncate flex-1 mr-2 text-base"
                                      title={item.name}
                                    >
                                      {item.name}
                                    </span>
                                    <span className="font-semibold whitespace-nowrap text-sm">
                                      {item.formattedValue}
                                    </span>
                                  </div>
                                  <div className="flex justify-between items-center text-muted-foreground text-xs">
                                    {item.symbol ? (
                                      <span
                                        className="truncate"
                                        title={item.symbol}
                                      >
                                        {item.symbol}
                                      </span>
                                    ) : (
                                      <span>&nbsp;</span>
                                    )}
                                    <span
                                      className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                    >
                                      {formatPercentage(item.change, locale)}
                                    </span>
                                  </div>
                                  <div className="flex justify-between items-center text-muted-foreground mt-0.5">
                                    <Badge
                                      variant="outline"
                                      className="py-0.5 px-1.5 text-[10px] leading-tight"
                                    >
                                      {item.entity}
                                    </Badge>
                                    <span className="text-[10px] whitespace-nowrap">
                                      {formatPercentage(
                                        item.percentageOfTotalVariableRent,
                                        locale,
                                      )}{" "}
                                      {t.dashboard.ofPortfolioShareShort}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex-shrink-0 w-6 relative">
                        {(fundItems.length > 0 || stockItems.length > 0) && (
                          <div className="h-full w-full flex flex-col rounded-sm overflow-hidden">
                            {fundItems.map(
                              (item, index) =>
                                item.percentageOfTotalVariableRent > 0 && (
                                  <div
                                    key={`bar-fund-${item.id}`}
                                    title={`${item.name}: ${formatPercentage(item.percentageOfTotalVariableRent, locale)}`}
                                    className={`w-full ${getItemColorByIndex(index, "FUND")}`}
                                    style={{
                                      height: `${Math.max(item.percentageOfTotalVariableRent, 1)}%`,
                                    }}
                                  ></div>
                                ),
                            )}
                            {fundItems.length > 0 &&
                              stockItems.length > 0 &&
                              stockItems.some(
                                si => si.percentageOfTotalVariableRent > 0,
                              ) &&
                              fundItems.some(
                                fi => fi.percentageOfTotalVariableRent > 0,
                              ) && (
                                <div className="h-0.5 w-full bg-background my-0.5"></div>
                              )}
                            {stockItems.map(
                              (item, index) =>
                                item.percentageOfTotalVariableRent > 0 && (
                                  <div
                                    key={`bar-stock-${item.id}`}
                                    title={`${item.name}: ${formatPercentage(item.percentageOfTotalVariableRent, locale)}`}
                                    className={`w-full ${getItemColorByIndex(index, "STOCK_ETF")}`}
                                    style={{
                                      height: `${Math.max(item.percentageOfTotalVariableRent, 1)}%`,
                                    }}
                                  ></div>
                                ),
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex-grow flex flex-col items-center justify-center text-center">
                      <BarChart3 className="h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" />
                      <p className="text-sm text-muted-foreground">
                        {t.dashboard.noInvestments}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="md:col-span-5"
            >
              <Card className="h-full flex flex-col">
                <CardHeader>
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-lg font-bold flex items-center">
                      <Receipt className="h-5 w-5 mr-2 text-primary" />
                      {t.dashboard.recentTransactions}
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="flex-grow overflow-y-auto scrollbar-thin min-h-[350px] max-h-[650px]">
                  {Object.keys(recentTransactions).length > 0 ? (
                    <ul className="space-y-0">
                      {Object.entries(recentTransactions).map(
                        ([date, txsOnDate]) => (
                          <li key={date} className="py-2">
                            <h4 className="text-sm font-semibold text-muted-foreground mb-2 sticky top-0 bg-card z-10 py-1 px-4 -mx-4 border-b border-t">
                              {date}
                            </h4>
                            <ul className="space-y-0 pr-4">
                              {(txsOnDate as any[]).map(
                                (tx: any, index: number) => (
                                  <li
                                    key={`${tx.date}-${tx.description}-${index}`}
                                    className="flex items-center justify-between py-3 border-b border-border last:border-b-0"
                                  >
                                    <div className="flex items-center flex-grow min-w-0">
                                      <div className="flex-shrink-0 w-4 h-4 flex items-center justify-center mr-4 text-muted-foreground">
                                        {getIconForTxType(tx.type as TxType)}
                                      </div>
                                      <div className="flex-grow min-w-0">
                                        <p
                                          className="text-sm font-medium truncate"
                                          title={tx.description}
                                        >
                                          {tx.description}
                                        </p>
                                        <div className="flex items-center space-x-1.5 text-xs text-muted-foreground mt-0.5">
                                          <Badge
                                            variant="outline"
                                            className="py-0.5 px-1.5 text-[10px] leading-tight"
                                          >
                                            {tx.entity}
                                          </Badge>
                                          {tx.product_type && (
                                            <Badge
                                              variant="secondary"
                                              className="py-0.5 px-1.5 text-[10px] leading-tight"
                                            >
                                              {t.enums &&
                                              t.enums.productType &&
                                              (t.enums.productType as any)[
                                                tx.product_type
                                              ]
                                                ? (t.enums.productType as any)[
                                                    tx.product_type
                                                  ]
                                                : tx.product_type
                                                    .toLowerCase()
                                                    .replace(/_/g, " ")}
                                            </Badge>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                    <div className="text-right flex-shrink-0 pl-2">
                                      <p
                                        className={`text-sm font-semibold ${
                                          tx.displayType === "income"
                                            ? "text-green-600 dark:text-green-400"
                                            : "text-red-600 dark:text-red-400"
                                        }`}
                                      >
                                        {tx.displayType === "income"
                                          ? "+"
                                          : "-"}
                                        {tx.formattedAmount}
                                      </p>
                                    </div>
                                  </li>
                                ),
                              )}
                            </ul>
                          </li>
                        ),
                      )}
                    </ul>
                  ) : (
                    <div className="flex-grow flex flex-col items-center justify-center h-full text-center">
                      <Receipt className="h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" />
                      <p className="text-sm text-muted-foreground">
                        {t.dashboard.noTransactions}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>
      )}
    </div>
  )
}
