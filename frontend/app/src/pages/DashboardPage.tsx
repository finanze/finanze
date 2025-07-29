import { useEffect, useRef, useState, useMemo, useLayoutEffect } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { getTransactions } from "@/services/api"
import { TransactionsResult, TxType } from "@/types/transactions"
import { FlowType } from "@/types"
import { formatCurrency, formatPercentage, formatDate } from "@/lib/formatters"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
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
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ArrowLeftRight,
  BarChart3,
  ArrowRight,
  CalendarDays,
  CalendarSync,
  HandCoins,
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
import {
  getAssetDistribution,
  getEntityDistribution,
  getTotalAssets,
  getTotalInvestedAmount,
  convertCurrency,
  getOngoingProjects,
  getStockAndFundPositions,
  getCryptoPositions,
  getCommodityPositions,
  getRecentTransactions,
  getDaysStatus,
} from "@/utils/financialDataUtils"

export default function DashboardPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const {
    positionsData,
    periodicFlows,
    pendingFlows,
    isLoading: financialDataLoading,
    error: financialDataError,
    refreshData: refreshFinancialData,
  } = useFinancialData()
  const { settings, inactiveEntities, exchangeRates, refreshExchangeRates } =
    useAppContext()

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
        const excludedEntityIds = inactiveEntities.map(entity => entity.id)
        const result = await getTransactions({
          excluded_entities: excludedEntityIds,
          limit: 8,
        })
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

  const [assetDistributionCardSmall, setAssetDistributionCardSmall] = useState(
    () => {
      if (typeof window !== "undefined") {
        return window.innerWidth < 768
      }
      return false
    },
  )

  const [chartRenderKey, setChartRenderKey] = useState(0)

  const [hoveredItem, setHoveredItem] = useState<string | null>(null)
  const [clickedItem, setClickedItem] = useState<string | null>(null)

  const isPopoverOpen = (itemId: string) => {
    return hoveredItem === itemId || clickedItem === itemId
  }

  const handlePopoverClick = (itemId: string) => {
    setClickedItem(prev => {
      if (prev === itemId) {
        return null
      }
      return itemId
    })
  }

  const handleMouseEnter = (itemId: string) => {
    setHoveredItem(itemId)
    if (clickedItem && clickedItem !== itemId) {
      setClickedItem(null)
    }
  }

  const hasData =
    positionsData !== null &&
    positionsData.positions &&
    Object.keys(positionsData.positions).length > 0

  useLayoutEffect(() => {
    if (hasData) {
      const checkInitialSize = () => {
        const assetDistributionCardElement = assetDistributionCardRef.current
        if (assetDistributionCardElement) {
          const cardWidth = assetDistributionCardElement.clientWidth
          const shouldBeSmall = cardWidth < 500
          setAssetDistributionCardSmall(shouldBeSmall)
          if (shouldBeSmall) {
            setChartRenderKey(prev => prev + 1)
          }
        } else {
          requestAnimationFrame(checkInitialSize)
        }
      }

      checkInitialSize()
    }
  }, [hasData])

  useEffect(() => {
    const checkScreenSize = () => {
      const assetDistributionCardElement = assetDistributionCardRef.current
      if (assetDistributionCardElement) {
        const cardWidth = assetDistributionCardElement.clientWidth
        const shouldBeSmall = cardWidth < 500
        if (shouldBeSmall !== assetDistributionCardSmall) {
          setAssetDistributionCardSmall(shouldBeSmall)
          setChartRenderKey(prev => prev + 1)
        }
      }
    }

    const timeoutId = setTimeout(checkScreenSize, 0)

    const assetDistributionCardElement = assetDistributionCardRef.current
    if (assetDistributionCardElement) {
      const resizeObserver = new ResizeObserver(checkScreenSize)
      resizeObserver.observe(assetDistributionCardElement)

      return () => {
        clearTimeout(timeoutId)
        resizeObserver.unobserve(assetDistributionCardElement)
      }
    }

    return () => {
      clearTimeout(timeoutId)
    }
  }, [hasData, assetDistributionCardSmall])

  useEffect(() => {
    const handleWindowResize = () => {
      const assetDistributionCardElement = assetDistributionCardRef.current
      if (assetDistributionCardElement) {
        const cardWidth = assetDistributionCardElement.clientWidth
        const shouldBeSmall = cardWidth < 500
        if (shouldBeSmall !== assetDistributionCardSmall) {
          setAssetDistributionCardSmall(shouldBeSmall)
          setChartRenderKey(prev => prev + 1)
        }
      }
    }

    window.addEventListener("resize", handleWindowResize)
    return () => {
      window.removeEventListener("resize", handleWindowResize)
    }
  }, [assetDistributionCardSmall])

  useEffect(() => {
    fetchTransactionsData()
  }, [inactiveEntities, t])

  const targetCurrency = settings.general.defaultCurrency
  const assetDistribution = getAssetDistribution(
    positionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
  )
  const entityDistribution = getEntityDistribution(
    positionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
  )
  const { entities } = useAppContext()
  const adjustedEntityDistribution = useMemo(() => {
    const contextIds = new Set(entities.map(e => e.id))
    return entityDistribution.map(item => {
      if (contextIds.has(item.id)) {
        return item
      } else if (item.id === "pending-flows") {
        // Handle pending flows entity specifically
        return {
          ...item,
          name: (t.enums?.productType as any)?.PENDING_FLOWS,
        }
      } else {
        return {
          ...item,
          name: (t.enums?.productType as any)?.COMMODITY || item.name,
        }
      }
    })
  }, [entityDistribution, entities, t])
  const totalAssets = getTotalAssets(
    positionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
  )
  const ongoingProjects = getOngoingProjects(
    positionsData,
    locale,
    settings.general.defaultCurrency,
  )
  const stockAndFundPositions = getStockAndFundPositions(
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
  )
  const cryptoPositions = getCryptoPositions(
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
  )
  const commodityPositions = getCommodityPositions(
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
    settings,
  )
  const recentTransactions = getRecentTransactions(
    transactions,
    locale,
    settings.general.defaultCurrency,
  )
  const totalInvestedAmount = getTotalInvestedAmount(
    positionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
  )

  const fundItems = stockAndFundPositions
    .filter(p => p.type === "FUND")
    .map((p, index) => ({
      ...p,
      id: `fund-${p.name}-${p.entity}-${p.portfolioName || "default"}-${index}`,
    }))

  const stockItems = stockAndFundPositions
    .filter(p => p.type === "STOCK_ETF")
    .map((p, index) => ({
      ...p,
      id: `${p.symbol}-stock-${index}-${p.entity}`,
    }))

  const cryptoItems = cryptoPositions.map((p, index) => ({
    ...p,
    id: `crypto-${p.symbol}-${p.entities.join("-")}-${p.address}-${index}`,
  }))

  const commodityItems = commodityPositions.map((p, index) => ({
    ...p,
    id: `commodity-${p.symbol}-${p.entities.join("-")}-${index}`,
  }))

  // Check if there are any detailed assets to display
  const hasDetailedAssets = [
    fundItems,
    stockItems,
    cryptoItems,
    commodityItems,
  ].some(items => items.length > 0)

  const fundPortfolioColorMap = useMemo(() => {
    const uniqueNames = Array.from(
      new Set(
        fundItems
          .filter(item => item.portfolioName)
          .map(item => item.portfolioName as string),
      ),
    )
    const colors = [
      "bg-emerald-500",
      "bg-blue-500",
      "bg-amber-500",
      "bg-purple-500",
      "bg-cyan-500",
      "bg-orange-500",
      "bg-teal-500",
      "bg-pink-500",
      "bg-lime-500",
      "bg-violet-500",
      "bg-yellow-500",
      "bg-indigo-500",
      "bg-rose-500",
      "bg-sky-500",
      "bg-fuchsia-500",
      "bg-green-500",
    ]
    const mapping = new Map<string, string>()
    uniqueNames.forEach((name, i) => {
      mapping.set(name, colors[i % colors.length])
    })
    return mapping
  }, [fundItems])

  const ITEM_FUND_COLORS = [
    "bg-blue-500",
    "bg-cyan-500",
    "bg-teal-500",
    "bg-emerald-500",
    "bg-green-500",
    "bg-lime-500",
    "bg-blue-600",
    "bg-cyan-600",
    "bg-teal-600",
    "bg-emerald-600",
    "bg-green-600",
    "bg-lime-600",
    "bg-sky-500",
    "bg-sky-600",
    "bg-indigo-500",
    "bg-indigo-600",
    "bg-slate-500",
  ]
  const ITEM_STOCK_COLORS = [
    "bg-violet-500",
    "bg-purple-500",
    "bg-fuchsia-500",
    "bg-pink-500",
    "bg-rose-500",
    "bg-red-500",
    "bg-violet-600",
    "bg-purple-600",
    "bg-fuchsia-600",
    "bg-pink-600",
    "bg-rose-600",
    "bg-red-600",
    "bg-indigo-700",
    "bg-purple-700",
    "bg-fuchsia-700",
    "bg-pink-700",
    "bg-rose-700",
  ]

  const ITEM_CRYPTO_COLORS = [
    "bg-orange-500",
    "bg-amber-500",
    "bg-yellow-500",
    "bg-orange-600",
    "bg-amber-600",
    "bg-yellow-600",
    "bg-red-400",
    "bg-pink-400",
    "bg-purple-400",
    "bg-orange-400",
    "bg-amber-400",
    "bg-yellow-400",
    "bg-stone-500",
    "bg-neutral-500",
    "bg-gray-500",
    "bg-zinc-500",
    "bg-slate-600",
  ]

  const ITEM_COMMODITY_COLORS = [
    "bg-yellow-500",
    "bg-amber-500",
    "bg-orange-500",
    "bg-yellow-600",
    "bg-amber-600",
    "bg-orange-600",
    "bg-lime-500",
    "bg-green-500",
    "bg-emerald-500",
    "bg-teal-500",
    "bg-cyan-500",
    "bg-blue-500",
    "bg-indigo-500",
    "bg-purple-500",
    "bg-pink-500",
    "bg-rose-500",
    "bg-red-500",
  ]

  const ENTITY_COLORS = [
    "#8b5cf6",
    "#06b6d4",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#3b82f6",
    "#84cc16",
    "#f97316",
    "#ec4899",
    "#8b5cf6",
    "#14b8a6",
    "#a855f7",
  ]

  const entityColorMap = useMemo(() => {
    const mapping = new Map<string, string>()
    entityDistribution.forEach((entity, index) => {
      mapping.set(entity.id, ENTITY_COLORS[index % ENTITY_COLORS.length])
    })
    return mapping
  }, [entityDistribution])

  const shuffle = <T,>(arr: T[]): T[] =>
    arr
      .map(value => ({ value, sort: Math.random() }))
      .sort((a, b) => a.sort - b.sort)
      .map(({ value }) => value)

  const shuffledFundItemColors = useMemo(() => shuffle(ITEM_FUND_COLORS), [])
  const shuffledStockItemColors = useMemo(() => shuffle(ITEM_STOCK_COLORS), [])
  const shuffledCryptoItemColors = useMemo(
    () => shuffle(ITEM_CRYPTO_COLORS),
    [],
  )
  const shuffledCommodityItemColors = useMemo(
    () => shuffle(ITEM_COMMODITY_COLORS),
    [],
  )

  const getItemColorByIndex = (
    index: number,
    type: "FUND" | "STOCK_ETF" | "CRYPTO" | "CRYPTO_TOKEN" | "COMMODITY",
  ) => {
    const colors =
      type === "FUND"
        ? shuffledFundItemColors
        : type === "STOCK_ETF"
          ? shuffledStockItemColors
          : type === "CRYPTO" || type === "CRYPTO_TOKEN"
            ? shuffledCryptoItemColors
            : shuffledCommodityItemColors
    return colors[index % colors.length]
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

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
          <div className="flex items-center gap-2 mb-2">
            {getIconForAssetType(data.type)}
            <p className="font-medium text-sm text-popover-foreground">
              {t.enums &&
              t.enums.productType &&
              (t.enums.productType as any)[data.type]
                ? (t.enums.productType as any)[data.type]
                : data.type?.toLowerCase().replace(/_/g, " ")}
            </p>
          </div>
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>
              <span className="font-medium text-popover-foreground">
                {formatCurrency(
                  data.value,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </span>
            </p>
            <p>{data.percentage}%</p>
          </div>
        </div>
      )
    }
    return null
  }

  const CustomEntityTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entityColorMap.get(data.id) }}
            />
            <p className="font-medium text-sm text-popover-foreground">
              {data.name}
            </p>
          </div>
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>
              <span className="font-medium text-popover-foreground">
                {formatCurrency(
                  data.value,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </span>
            </p>
            <p>{data.percentage}%</p>
          </div>
        </div>
      )
    }
    return null
  }

  const CustomLegend = (props: any) => {
    const { payload } = props

    const getInvestmentRoute = (assetType: string) => {
      const routeMap: Record<string, string> = {
        STOCK_ETF: "/investments/stocks-etfs",
        FUND: "/investments/funds",
        DEPOSIT: "/investments/deposits",
        FACTORING: "/investments/factoring",
        REAL_ESTATE_CF: "/investments/real-estate",
        CRYPTO: "/investments/crypto",
        PENDING_FLOWS: "/management/pending",
        CASH: "/banking",
      }
      return routeMap[assetType] || null
    }

    const handleLegendClick = (assetType: string) => {
      const route = getInvestmentRoute(assetType)
      if (route) {
        navigate(route)
      }
    }

    return (
      <ul className="space-y-1.5 text-xs scrollbar-thin pr-0.5">
        {payload.map((entry: any, index: number) => {
          const assetType = entry.payload.payload.type
          const assetValue = entry.payload.payload.value
          const assetPercentage = entry.payload.payload.percentage
          const icon = getIconForAssetType(assetType)
          const hasRoute = getInvestmentRoute(assetType) !== null

          return (
            <li
              key={`legend-item-${index}`}
              className={`flex items-center space-x-2 p-1 rounded transition-colors ${
                hasRoute
                  ? "hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer"
                  : "cursor-default"
              }`}
              title={`${(t.enums.productType as any)[assetType] || assetType.toLowerCase().replace(/_/g, " ")}: ${formatCurrency(assetValue, locale, settings.general.defaultCurrency)} (${assetPercentage}%)${hasRoute ? " - Click to view details" : ""}`}
              onClick={() => hasRoute && handleLegendClick(assetType)}
            >
              <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
                {icon}
              </span>
              <span className="capitalize truncate flex-grow min-w-0">
                {(t.enums.productType as any)[assetType] ||
                  assetType.toLowerCase().replace(/_/g, " ")}
              </span>
              <div className="text-right flex space-x-1">
                <span className="block whitespace-nowrap text-[11px]">
                  {formatCurrency(
                    assetValue,
                    locale,
                    settings.general.defaultCurrency,
                  )}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    )
  }

  const CustomEntityLegend = (props: any) => {
    const { payload } = props
    return (
      <ul className="space-y-1.5 text-xs scrollbar-thin pr-0.5">
        {payload.map((entry: any, index: number) => {
          const entityName = entry.payload.payload.name
          const entityValue = entry.payload.payload.value
          const entityPercentage = entry.payload.payload.percentage
          const entityId = entry.payload.payload.id

          return (
            <li
              key={`entity-legend-item-${index}`}
              className="flex items-center space-x-2 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer"
              title={`${entityName}: ${formatCurrency(entityValue, locale, settings.general.defaultCurrency)} (${entityPercentage}%)`}
            >
              <span
                className="flex-shrink-0 w-4 h-4 rounded-full"
                style={{ backgroundColor: entityColorMap.get(entityId) }}
              />
              <span className="truncate flex-grow min-w-0">{entityName}</span>
              <div className="text-right flex space-x-1">
                <span className="block whitespace-nowrap text-[11px]">
                  {formatCurrency(
                    entityValue,
                    locale,
                    settings.general.defaultCurrency,
                  )}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    )
  }

  // Calculate upcoming flows data
  const upcomingFlowsData = useMemo(() => {
    const now = new Date()
    const allFlows = [...periodicFlows, ...pendingFlows]
      .filter(flow => flow.enabled)
      .map(flow => {
        let nextDate = null

        if ("next_date" in flow && flow.next_date) {
          nextDate = new Date(flow.next_date)
        } else if ("date" in flow && flow.date) {
          nextDate = new Date(flow.date)
        }

        if (!nextDate) return null

        const daysUntil = Math.ceil(
          (nextDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
        )

        return {
          ...flow,
          nextDate,
          daysUntil,
          convertedAmount: convertCurrency(
            parseFloat(flow.amount),
            flow.currency,
            targetCurrency,
            exchangeRates,
          ),
        }
      })
      .filter((flow): flow is NonNullable<typeof flow> => flow !== null)
      .filter(flow => flow.daysUntil >= 0) // Filter out outdated flows
      .sort((a, b) => a.nextDate.getTime() - b.nextDate.getTime())
      .slice(0, 5) // Show only next 5 flows

    return allFlows
  }, [periodicFlows, pendingFlows, targetCurrency, exchangeRates])

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
            refreshExchangeRates()
          }}
        >
          {t.common.retry}
        </Button>
      </div>
    )
  }

  // Don't render until exchange rates are available
  if (!exchangeRates) {
    return (
      <div className="flex justify-center items-center h-[70vh]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Utility function for date urgency (copied from PendingMoneyPage)
  const getDateUrgencyInfo = (dateString: string | undefined) => {
    if (!dateString) return null

    const targetDate = new Date(dateString)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    targetDate.setHours(0, 0, 0, 0)

    const diffTime = targetDate.getTime() - today.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return {
        show: true,
        urgencyLevel: "urgent" as const,
        timeText: t.management.today,
      }
    }

    if (diffDays === 1) {
      return {
        show: true,
        urgencyLevel: "urgent" as const,
        timeText: t.management.tomorrow,
      }
    }

    if (diffDays <= 7) {
      return {
        show: true,
        urgencyLevel: "soon" as const,
        timeText: `${t.management.inDays}`.replace(
          "{days}",
          diffDays.toString(),
        ),
      }
    }

    if (diffDays <= 30) {
      return {
        show: true,
        urgencyLevel: "normal" as const,
        timeText: `${t.management.inDays}`.replace(
          "{days}",
          diffDays.toString(),
        ),
      }
    }

    // format date
    return {
      show: true,
      urgencyLevel: "normal" as const,
      timeText: formatDate(dateString, locale),
    }
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.common.dashboard}</h1>
        <div className="flex gap-2">
          <EntityRefreshDropdown />
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
                <CardContent ref={assetDistributionCardRef} className="px-2">
                  <Tabs defaultValue="by-asset" className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                      <TabsTrigger value="by-asset">
                        {t.dashboard.assetDistributionByType}
                      </TabsTrigger>
                      <TabsTrigger value="by-entity">
                        {t.dashboard.assetDistributionByEntity}
                      </TabsTrigger>
                    </TabsList>

                    <TabsContent value="by-asset" className="mt-4">
                      {assetDistribution.length > 0 ? (
                        <div
                          className={
                            assetDistributionCardSmall
                              ? "h-[450px] px-2"
                              : "h-[300px] px-4"
                          }
                        >
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart
                              key={`pie-asset-${assetDistributionCardSmall ? "small" : "large"}-${chartRenderKey}`}
                              style={{ userSelect: "none" }}
                            >
                              <Pie
                                data={assetDistribution}
                                cx={assetDistributionCardSmall ? "50%" : "45%"}
                                cy={assetDistributionCardSmall ? "40%" : "50%"}
                                labelLine={false}
                                innerRadius={
                                  assetDistributionCardSmall ? 60 : 70
                                }
                                outerRadius={
                                  assetDistributionCardSmall ? 100 : 110
                                }
                                fill="#8884d8"
                                dataKey="value"
                                nameKey="type"
                                isAnimationActive={false}
                                stroke="hsl(var(--background))"
                                strokeWidth={2}
                                label={({
                                  cx,
                                  cy,
                                  midAngle,
                                  innerRadius,
                                  outerRadius,
                                  percentage,
                                }) => {
                                  if (percentage < 3) return null

                                  const RADIAN = Math.PI / 180

                                  const isLargeSegment = percentage >= 15
                                  const radius = isLargeSegment
                                    ? innerRadius +
                                      (outerRadius - innerRadius) * 0.45 // Inside
                                    : innerRadius +
                                      (outerRadius - innerRadius) * 1.25 // Outside

                                  const x =
                                    cx + radius * Math.cos(-midAngle * RADIAN)
                                  const y =
                                    cy + radius * Math.sin(-midAngle * RADIAN)

                                  return (
                                    <g>
                                      <text
                                        x={x}
                                        y={y}
                                        fill={
                                          isLargeSegment
                                            ? "white"
                                            : "hsl(var(--foreground))"
                                        }
                                        textAnchor="middle"
                                        dominantBaseline="central"
                                        fontSize={isLargeSegment ? "12" : "10"}
                                        fontWeight="600"
                                      >
                                        {percentage.toFixed(0)}%
                                      </text>
                                    </g>
                                  )
                                }}
                              >
                                {assetDistribution.map((entry, index) => (
                                  <Cell
                                    key={`cell-${index}`}
                                    fill={getPieSliceColorForAssetType(
                                      entry.type,
                                    )}
                                    style={{ outline: "none" }}
                                  />
                                ))}
                              </Pie>
                              <Tooltip content={<CustomTooltip />} />
                              <Legend
                                layout="vertical"
                                verticalAlign={
                                  assetDistributionCardSmall
                                    ? "bottom"
                                    : "middle"
                                }
                                align={
                                  assetDistributionCardSmall
                                    ? "center"
                                    : "right"
                                }
                                wrapperStyle={
                                  assetDistributionCardSmall
                                    ? {
                                        maxHeight: "200px",
                                        overflowY: "auto",
                                        width: "95%",
                                        margin: "0 auto",
                                      }
                                    : {
                                        paddingRight: "10px",
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
                    </TabsContent>

                    <TabsContent value="by-entity" className="mt-4">
                      {adjustedEntityDistribution.length > 0 ? (
                        <div
                          className={
                            assetDistributionCardSmall
                              ? "h-[450px] px-2"
                              : "h-[300px] px-4"
                          }
                        >
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart
                              key={`pie-entity-${assetDistributionCardSmall ? "small" : "large"}-${chartRenderKey}`}
                              style={{ userSelect: "none" }}
                            >
                              <Pie
                                data={adjustedEntityDistribution}
                                cx={assetDistributionCardSmall ? "50%" : "45%"}
                                cy={assetDistributionCardSmall ? "40%" : "50%"}
                                labelLine={false}
                                innerRadius={
                                  assetDistributionCardSmall ? 60 : 70
                                }
                                outerRadius={
                                  assetDistributionCardSmall ? 100 : 110
                                }
                                fill="#8884d8"
                                dataKey="value"
                                nameKey="name"
                                isAnimationActive={false}
                                stroke="hsl(var(--background))"
                                strokeWidth={2}
                                label={({
                                  cx,
                                  cy,
                                  midAngle,
                                  innerRadius,
                                  outerRadius,
                                  percentage,
                                }) => {
                                  if (percentage < 3) return null

                                  const RADIAN = Math.PI / 180

                                  const isLargeSegment = percentage >= 15
                                  const radius = isLargeSegment
                                    ? innerRadius +
                                      (outerRadius - innerRadius) * 0.45 // Inside
                                    : innerRadius +
                                      (outerRadius - innerRadius) * 1.25 // Outside

                                  const x =
                                    cx + radius * Math.cos(-midAngle * RADIAN)
                                  const y =
                                    cy + radius * Math.sin(-midAngle * RADIAN)

                                  return (
                                    <g>
                                      <text
                                        x={x}
                                        y={y}
                                        fill={
                                          isLargeSegment
                                            ? "white"
                                            : "hsl(var(--foreground))"
                                        }
                                        textAnchor="middle"
                                        dominantBaseline="central"
                                        fontSize={isLargeSegment ? "12" : "10"}
                                        fontWeight="600"
                                      >
                                        {percentage.toFixed(0)}%
                                      </text>
                                    </g>
                                  )
                                }}
                              >
                                {adjustedEntityDistribution.map(
                                  (entry, index) => (
                                    <Cell
                                      key={`entity-cell-${index}`}
                                      fill={entityColorMap.get(entry.id)}
                                      style={{ outline: "none" }}
                                    />
                                  ),
                                )}
                              </Pie>
                              <Tooltip content={<CustomEntityTooltip />} />
                              <Legend
                                layout="vertical"
                                verticalAlign={
                                  assetDistributionCardSmall
                                    ? "bottom"
                                    : "middle"
                                }
                                align={
                                  assetDistributionCardSmall
                                    ? "center"
                                    : "right"
                                }
                                wrapperStyle={
                                  assetDistributionCardSmall
                                    ? {
                                        maxHeight: "200px",
                                        overflowY: "auto",
                                        width: "95%",
                                        margin: "0 auto",
                                      }
                                    : {
                                        paddingRight: "10px",
                                        maxHeight: "260px",
                                        overflowY: "auto",
                                      }
                                }
                                content={<CustomEntityLegend />}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {t.common.noDataAvailable}
                        </p>
                      )}
                    </TabsContent>
                  </Tabs>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="md:col-span-5 space-y-6"
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
                        settings.general.defaultCurrency,
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
                      settings.general.defaultCurrency,
                    )}
                  </p>
                </CardContent>
              </Card>

              {/* Upcoming Flows Card */}
              {upcomingFlowsData.length > 0 && (
                <Card>
                  <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 gap-2">
                    <CardTitle className="text-lg font-bold flex items-center">
                      <CalendarDays className="h-5 w-5 mr-2 text-primary" />
                      {t.dashboard.upcomingFlows}
                    </CardTitle>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate("/management")}
                      className="text-xs px-2 py-1 h-auto min-h-0 self-start sm:self-auto"
                    >
                      <ArrowRight className="h-3 w-3 mr-1" />
                      {t.dashboard.manageFlows}
                    </Button>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="space-y-3">
                      {upcomingFlowsData.map((flow, index) => {
                        const isEarning = flow.flow_type === FlowType.EARNING
                        const isRecurring = "frequency" in flow
                        const urgencyInfo = getDateUrgencyInfo(
                          flow.nextDate.toISOString().split("T")[0],
                        )

                        return (
                          <div
                            key={`${flow.id}-${index}`}
                            className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 rounded-lg bg-muted/50"
                          >
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                              {isRecurring ? (
                                <CalendarSync
                                  className={`h-4 w-4 flex-shrink-0 ${isEarning ? "text-green-500" : "text-red-500"}`}
                                />
                              ) : (
                                <HandCoins
                                  className={`h-4 w-4 flex-shrink-0 ${isEarning ? "text-green-500" : "text-red-500"}`}
                                />
                              )}
                              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 min-w-0 flex-1">
                                <p className="font-medium text-sm truncate">
                                  {flow.name}
                                </p>
                                {urgencyInfo?.show && (
                                  <Badge
                                    variant={
                                      urgencyInfo.urgencyLevel === "urgent"
                                        ? "destructive"
                                        : urgencyInfo.urgencyLevel === "soon"
                                          ? "default"
                                          : "outline"
                                    }
                                    className="text-xs px-1 py-0 h-4 self-start sm:self-auto"
                                  >
                                    {urgencyInfo.timeText}
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <p
                              className={`font-mono text-sm font-semibold flex-shrink-0 text-center sm:text-right ${isEarning ? "text-green-600" : "text-red-600"}`}
                            >
                              {isEarning ? "+" : "-"}
                              {formatCurrency(
                                Math.abs(flow.convertedAmount),
                                locale,
                                settings.general.defaultCurrency,
                              )}
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}
            </motion.div>
          </div>

          {ongoingProjects.length > 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div>
                    <CardTitle className="text-lg font-bold flex items-center">
                      <TrendingUp className="h-5 w-5 mr-2 text-primary" />
                      {t.dashboard.ongoingProjects}
                    </CardTitle>
                  </div>
                  {ongoingProjects.length > 3 && (
                    <div className="flex space-x-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => scrollProjects("left")}
                        disabled={!showLeftScroll}
                        className={`h-7 w-7 p-0 ${
                          !showLeftScroll ? "opacity-50 cursor-not-allowed" : ""
                        }`}
                      >
                        <ChevronLeft className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => scrollProjects("right")}
                        disabled={!showRightScroll}
                        className={`h-7 w-7 p-0 ${
                          !showRightScroll
                            ? "opacity-50 cursor-not-allowed"
                            : ""
                        }`}
                      >
                        <ChevronRight className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent className="pt-0">
                  <div
                    ref={projectsContainerRef}
                    className="flex overflow-x-auto space-x-3 scrollbar-none"
                    onScroll={handleScroll}
                    style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
                  >
                    {ongoingProjects.map((project, index) => {
                      const status = getDaysStatus(project.maturity, t)
                      return (
                        <Card
                          key={index}
                          className="bg-gray-50 dark:bg-gray-900 border flex-shrink-0 w-[280px]"
                        >
                          <CardContent className="p-3 flex flex-col justify-between h-full">
                            <div>
                              <div className="flex justify-between items-start mb-2">
                                <div className="flex-grow mr-2 min-w-0">
                                  <h3
                                    className="font-medium text-sm truncate"
                                    title={project.name}
                                  >
                                    {project.name}
                                  </h3>
                                  <div className="flex items-center text-xs text-muted-foreground mt-0.5">
                                    <Badge
                                      variant="outline"
                                      className="mr-1.5 text-[10px] py-0 px-1"
                                    >
                                      {project.entity}
                                    </Badge>
                                    <div className="flex items-center">
                                      {getIconForProjectType(project.type)}
                                      <span className="ml-1 capitalize text-[10px]">
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
                                  className={`flex-shrink-0 h-auto px-1.5 py-0.5 text-center text-[10px] whitespace-nowrap ${
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
                              <div className="flex justify-between text-[10px] text-muted-foreground">
                                <span>{t.dashboard.maturity}</span>
                                <span>
                                  {formatDate(project.maturity, locale)}
                                </span>
                              </div>
                              <div className="flex justify-between items-start mb-2">
                                <p className="text-base font-semibold">
                                  {project.formattedValue}
                                </p>
                                <p className="text-base font-semibold text-green-600">
                                  {formatPercentage(project.roi, locale)}
                                </p>
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
                <CardContent className="flex-grow flex flex-col space-y-3 p-4 overflow-hidden min-h-[350px] max-h-[650px]">
                  {fundItems.length > 0 ||
                  stockItems.length > 0 ||
                  cryptoItems.length > 0 ||
                  commodityItems.length > 0 ? (
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
                                className="flex items-stretch space-x-2 py-3 border-b border-border last:border-b-0"
                              >
                                <div
                                  className={`flex-shrink-0 w-1 rounded-sm ${getItemColorByIndex(index, "FUND")}`}
                                ></div>
                                <div className="flex-grow min-w-0">
                                  <div className="flex justify-between items-center">
                                    <div className="flex items-center flex-1 min-w-0 mr-2">
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

                                  <div className="flex justify-between items-center text-muted-foreground text-xs mt-0.5">
                                    <Badge
                                      variant="outline"
                                      className="py-0.5 px-1.5 text-[10px] leading-tight"
                                    >
                                      {item.entity}
                                    </Badge>
                                    {item.change !== 0 && (
                                      <span
                                        className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                      >
                                        {formatPercentage(item.change, locale)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {stockItems.length > 0 ? (
                          <div className="pb-2">
                            <h3 className="text-sm font-semibold mb-1.5 text-muted-foreground sticky top-0 bg-card z-10 py-1">
                              {t.dashboard.stocksAndFunds.stocksEtfs}
                            </h3>
                            {stockItems.map((item, index) => (
                              <div
                                key={item.id}
                                className="flex items-stretch space-x-2 py-3 border-b border-border last:border-b-0"
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
                                  <div className="flex justify-between items-center text-muted-foreground text-xs mt-0.5">
                                    <Badge
                                      variant="outline"
                                      className="py-0.5 px-1.5 text-[10px] leading-tight"
                                    >
                                      {item.entity}
                                    </Badge>
                                    {item.change !== 0 && (
                                      <span
                                        className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                      >
                                        {formatPercentage(item.change, locale)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {cryptoItems.length > 0 ? (
                          <div className="pb-2">
                            <h3 className="text-sm font-semibold mb-1.5 text-muted-foreground sticky top-0 bg-card z-10 py-1">
                              {t.common.crypto}
                            </h3>
                            {cryptoItems.map((item, index) => (
                              <div
                                key={item.id}
                                className="flex items-stretch space-x-2 py-3 border-b border-border last:border-b-0"
                              >
                                <div
                                  className={`flex-shrink-0 w-1 rounded-sm ${getItemColorByIndex(index, item.type as "CRYPTO" | "CRYPTO_TOKEN")}`}
                                ></div>
                                <div className="flex-grow min-w-0">
                                  <div className="flex justify-between items-center">
                                    <span
                                      className="font-medium truncate flex-1 mr-2 text-base"
                                      title={item.name}
                                    >
                                      {item.name}
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                                        {item.amount?.toLocaleString(locale, {
                                          minimumFractionDigits:
                                            item.amount < 1 ? 6 : 2,
                                          maximumFractionDigits:
                                            item.amount < 1 ? 6 : 2,
                                        })}{" "}
                                        {item.symbol}
                                      </span>
                                      <span className="font-semibold whitespace-nowrap text-sm">
                                        {item.formattedValue}
                                      </span>
                                    </div>
                                  </div>
                                  <div className="flex justify-between items-center text-muted-foreground text-xs mt-0.5">
                                    {item.showEntityBadge &&
                                    item.entities &&
                                    item.entities.length > 0 ? (
                                      <div className="flex gap-1 flex-wrap">
                                        {item.entities.map(
                                          (entity, entityIndex) => (
                                            <Badge
                                              key={entityIndex}
                                              variant="outline"
                                              className="py-0.5 px-1.5 text-[10px] leading-tight"
                                            >
                                              {entity}
                                            </Badge>
                                          ),
                                        )}
                                      </div>
                                    ) : (
                                      <span>&nbsp;</span>
                                    )}
                                    {item.change !== 0 && (
                                      <span
                                        className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                      >
                                        {formatPercentage(item.change, locale)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}

                        {commodityItems.length > 0 ? (
                          <div className="pb-2">
                            <h3 className="text-sm font-semibold mb-1.5 text-muted-foreground sticky top-0 bg-card z-10 py-1">
                              {t.common.commodities}
                            </h3>
                            {commodityItems.map((item, index) => (
                              <div
                                key={item.id}
                                className="flex items-stretch space-x-2 py-3 border-b border-border last:border-b-0"
                              >
                                <div
                                  className={`flex-shrink-0 w-1 rounded-sm ${getItemColorByIndex(index, "COMMODITY")}`}
                                ></div>
                                <div className="flex-grow min-w-0">
                                  <div className="flex justify-between items-center">
                                    <span
                                      className="font-medium truncate flex-1 mr-2 text-base"
                                      title={
                                        t.enums.commodityType[
                                          item.type as keyof typeof t.enums.commodityType
                                        ]
                                      }
                                    >
                                      {
                                        t.enums.commodityType[
                                          item.type as keyof typeof t.enums.commodityType
                                        ]
                                      }
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                                        {item.amount?.toLocaleString(locale, {
                                          minimumFractionDigits: 0,
                                          maximumFractionDigits: 1,
                                        })}{" "}
                                        {
                                          t.enums.weightUnit[
                                            item.unit as keyof typeof t.enums.weightUnit
                                          ]
                                        }
                                      </span>
                                      <span className="font-semibold whitespace-nowrap text-sm">
                                        {item.formattedValue}
                                      </span>
                                    </div>
                                  </div>
                                  <div className="flex justify-between items-center text-muted-foreground text-xs mt-0.5">
                                    {item.showEntityBadge &&
                                    item.entities &&
                                    item.entities.length > 0 ? (
                                      <div className="flex gap-1 flex-wrap">
                                        {item.entities.map(
                                          (
                                            entity: string,
                                            entityIndex: number,
                                          ) => (
                                            <Badge
                                              key={entityIndex}
                                              variant="outline"
                                              className="py-0.5 px-1.5 text-[10px] leading-tight"
                                            >
                                              {entity}
                                            </Badge>
                                          ),
                                        )}
                                      </div>
                                    ) : (
                                      <span>&nbsp;</span>
                                    )}
                                    {item.change !== 0 && (
                                      <span
                                        className={`whitespace-nowrap ${item.change >= 0 ? "text-green-500" : "text-red-500"}`}
                                      >
                                        {formatPercentage(item.change, locale)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex-shrink-0 w-6 relative">
                        {hasDetailedAssets && (
                          <div className="h-full w-full flex flex-col rounded-sm overflow-hidden">
                            {fundItems.map(
                              (item, index) =>
                                item.percentageOfTotalPortfolio > 0 && (
                                  <Popover
                                    key={`bar-fund-${item.id}`}
                                    open={isPopoverOpen(`fund-${item.id}`)}
                                    onOpenChange={open => {
                                      if (!open) {
                                        setHoveredItem(null)
                                        setClickedItem(null)
                                      }
                                    }}
                                  >
                                    <PopoverTrigger asChild>
                                      <div
                                        className={`w-full ${getItemColorByIndex(index, "FUND")} cursor-pointer hover:opacity-80 transition-opacity`}
                                        style={{
                                          height: `${item.percentageOfTotalPortfolio}%`,
                                        }}
                                        onMouseEnter={() =>
                                          handleMouseEnter(`fund-${item.id}`)
                                        }
                                        onMouseLeave={() =>
                                          setHoveredItem(null)
                                        }
                                        onClick={() =>
                                          handlePopoverClick(`fund-${item.id}`)
                                        }
                                      ></div>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      className="w-80"
                                      side="left"
                                      onMouseEnter={() =>
                                        handleMouseEnter(`fund-${item.id}`)
                                      }
                                      onMouseLeave={() => setHoveredItem(null)}
                                    >
                                      <div className="space-y-2">
                                        <div className="flex items-center space-x-2">
                                          <div
                                            className={`w-4 h-4 rounded ${getItemColorByIndex(index, "FUND")}`}
                                          ></div>
                                          <h4 className="font-medium text-sm">
                                            {item.name}
                                          </h4>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                          <div>
                                            <span className="text-muted-foreground">
                                              {t.dashboard.value}:
                                            </span>
                                            <div className="font-semibold">
                                              {item.formattedValue}
                                            </div>
                                          </div>
                                          {item.percentageOfTotalVariableRent <
                                            100 && (
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.stakeInFunds}:
                                              </span>
                                              <div className="font-semibold">
                                                {formatPercentage(
                                                  item.percentageOfTotalVariableRent,
                                                  locale,
                                                )}
                                              </div>
                                            </div>
                                          )}
                                          <div className="col-span-2">
                                            <span className="text-muted-foreground">
                                              {t.dashboard.entity}:
                                            </span>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                              <Badge
                                                variant="outline"
                                                className="text-xs"
                                              >
                                                {item.entity}
                                              </Badge>
                                            </div>
                                          </div>
                                          {item.portfolioName && (
                                            <div className="col-span-2">
                                              <span className="text-muted-foreground">
                                                {t.dashboard.portfolio}:
                                              </span>
                                              <div className="font-semibold">
                                                {item.portfolioName}
                                              </div>
                                            </div>
                                          )}
                                          <div className="col-span-2">
                                            <span className="text-muted-foreground">
                                              {t.dashboard.change}:
                                            </span>
                                            <div
                                              className={`font-semibold ${
                                                item.change > 0
                                                  ? "text-green-500"
                                                  : item.change < 0
                                                    ? "text-red-500"
                                                    : "text-white"
                                              }`}
                                            >
                                              {item.change === 0
                                                ? "-"
                                                : (item.change > 0 ? "+" : "") +
                                                  formatPercentage(
                                                    item.change,
                                                    locale,
                                                  )}
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    </PopoverContent>
                                  </Popover>
                                ),
                            )}
                            {fundItems.length > 0 &&
                              stockItems.length > 0 &&
                              stockItems.some(
                                si => si.percentageOfTotalVariableRent > 0,
                              ) &&
                              fundItems.some(
                                fi => fi.percentageOfTotalVariableRent > 0,
                              ) && <div className="h-1 w-full my-0.5"></div>}
                            {stockItems.map(
                              (item, index) =>
                                item.percentageOfTotalPortfolio > 0 && (
                                  <Popover
                                    key={`bar-stock-${item.id}`}
                                    open={isPopoverOpen(`stock-${item.id}`)}
                                    onOpenChange={open => {
                                      if (!open) {
                                        setHoveredItem(null)
                                        setClickedItem(null)
                                      }
                                    }}
                                  >
                                    <PopoverTrigger asChild>
                                      <div
                                        className={`w-full ${getItemColorByIndex(index, "STOCK_ETF")} cursor-pointer hover:opacity-80 transition-opacity`}
                                        style={{
                                          height: `${item.percentageOfTotalPortfolio}%`,
                                        }}
                                        onMouseEnter={() =>
                                          handleMouseEnter(`stock-${item.id}`)
                                        }
                                        onMouseLeave={() =>
                                          setHoveredItem(null)
                                        }
                                        onClick={() =>
                                          handlePopoverClick(`stock-${item.id}`)
                                        }
                                      ></div>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      className="w-80"
                                      side="left"
                                      onMouseEnter={() =>
                                        handleMouseEnter(`stock-${item.id}`)
                                      }
                                      onMouseLeave={() => setHoveredItem(null)}
                                    >
                                      <div className="space-y-2">
                                        <div className="flex items-center space-x-2">
                                          <div
                                            className={`w-4 h-4 rounded ${getItemColorByIndex(index, "STOCK_ETF")}`}
                                          ></div>
                                          <h4 className="font-medium text-sm">
                                            {item.name}
                                          </h4>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                          <div>
                                            <span className="text-muted-foreground">
                                              {t.dashboard.value}:
                                            </span>
                                            <div className="font-semibold">
                                              {item.formattedValue}
                                            </div>
                                          </div>
                                          {item.percentageOfTotalVariableRent <
                                            100 && (
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.stakeInStocks}:
                                              </span>
                                              <div className="font-semibold">
                                                {formatPercentage(
                                                  item.percentageOfTotalVariableRent,
                                                  locale,
                                                )}
                                              </div>
                                            </div>
                                          )}
                                          {item.symbol && (
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.symbol}:
                                              </span>
                                              <div className="font-semibold">
                                                {item.symbol}
                                              </div>
                                            </div>
                                          )}
                                          <div
                                            className={
                                              item.symbol ? "" : "col-span-2"
                                            }
                                          >
                                            <span className="text-muted-foreground">
                                              {t.dashboard.entity}:
                                            </span>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                              <Badge
                                                variant="outline"
                                                className="text-xs"
                                              >
                                                {item.entity}
                                              </Badge>
                                            </div>
                                          </div>
                                          <div className="col-span-2">
                                            <span className="text-muted-foreground">
                                              {t.dashboard.change}:
                                            </span>
                                            <div
                                              className={`font-semibold ${
                                                item.change > 0
                                                  ? "text-green-500"
                                                  : item.change < 0
                                                    ? "text-red-500"
                                                    : "text-white"
                                              }`}
                                            >
                                              {item.change === 0
                                                ? "-"
                                                : (item.change > 0 ? "+" : "") +
                                                  formatPercentage(
                                                    item.change,
                                                    locale,
                                                  )}
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    </PopoverContent>
                                  </Popover>
                                ),
                            )}
                            {(fundItems.length > 0 || stockItems.length > 0) &&
                              cryptoItems.length > 0 &&
                              cryptoItems.some(
                                ci => ci.percentageOfTotalVariableRent > 0,
                              ) && <div className="h-1 w-full my-0.5"></div>}
                            {cryptoItems.map(
                              (item, index) =>
                                item.percentageOfTotalPortfolio > 0 && (
                                  <Popover
                                    key={`bar-crypto-${item.id}`}
                                    open={isPopoverOpen(`crypto-${item.id}`)}
                                    onOpenChange={open => {
                                      if (!open) {
                                        setHoveredItem(null)
                                        setClickedItem(null)
                                      }
                                    }}
                                  >
                                    <PopoverTrigger asChild>
                                      <div
                                        className={`w-full ${getItemColorByIndex(index, item.type as "CRYPTO" | "CRYPTO_TOKEN")} cursor-pointer hover:opacity-80 transition-opacity`}
                                        style={{
                                          height: `${item.percentageOfTotalPortfolio}%`,
                                        }}
                                        onMouseEnter={() =>
                                          handleMouseEnter(`crypto-${item.id}`)
                                        }
                                        onMouseLeave={() =>
                                          setHoveredItem(null)
                                        }
                                        onClick={() =>
                                          handlePopoverClick(
                                            `crypto-${item.id}`,
                                          )
                                        }
                                      ></div>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      className="w-80"
                                      side="left"
                                      onMouseEnter={() =>
                                        handleMouseEnter(`crypto-${item.id}`)
                                      }
                                      onMouseLeave={() => setHoveredItem(null)}
                                    >
                                      <div className="space-y-2">
                                        <div className="flex items-center space-x-2">
                                          <div
                                            className={`w-4 h-4 rounded ${getItemColorByIndex(index, item.type as "CRYPTO" | "CRYPTO_TOKEN")}`}
                                          ></div>
                                          <h4 className="font-medium text-sm">
                                            {item.name}
                                          </h4>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                          <div>
                                            <span className="text-muted-foreground">
                                              {t.dashboard.value}:
                                            </span>
                                            <div className="font-semibold">
                                              {item.formattedValue}
                                            </div>
                                          </div>
                                          {item.percentageOfTotalVariableRent <
                                            100 && (
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.stakeInCryptos}:
                                              </span>
                                              <div className="font-semibold">
                                                {formatPercentage(
                                                  item.percentageOfTotalVariableRent,
                                                  locale,
                                                )}
                                              </div>
                                            </div>
                                          )}
                                          <div>
                                            <span className="text-muted-foreground">
                                              Amount:
                                            </span>
                                            <div className="font-semibold">
                                              {item.amount?.toLocaleString(
                                                locale,
                                                {
                                                  minimumFractionDigits:
                                                    item.amount < 1 ? 6 : 2,
                                                  maximumFractionDigits:
                                                    item.amount < 1 ? 6 : 2,
                                                },
                                              )}{" "}
                                              {item.symbol}
                                            </div>
                                          </div>
                                          {item.symbol && (
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.symbol}:
                                              </span>
                                              <div className="font-semibold">
                                                {item.symbol}
                                              </div>
                                            </div>
                                          )}
                                          <div>
                                            <span className="text-muted-foreground">
                                              {t.dashboard.type}:
                                            </span>
                                            <div className="font-semibold capitalize">
                                              {item.type === "CRYPTO"
                                                ? t.dashboard.mainCrypto
                                                : t.dashboard.token}
                                            </div>
                                          </div>
                                          {item.showEntityBadge &&
                                            item.entities &&
                                            item.entities.length > 0 && (
                                              <div className="col-span-2">
                                                <span className="text-muted-foreground">
                                                  {t.dashboard.entities}:
                                                </span>
                                                <div className="flex flex-wrap gap-1 mt-1">
                                                  {item.entities.map(
                                                    (entity, entityIndex) => (
                                                      <Badge
                                                        key={entityIndex}
                                                        variant="outline"
                                                        className="text-xs"
                                                      >
                                                        {entity}
                                                      </Badge>
                                                    ),
                                                  )}
                                                </div>
                                              </div>
                                            )}
                                          {item.change !== 0 && (
                                            <div className="col-span-2">
                                              <span className="text-muted-foreground">
                                                {t.dashboard.change}:
                                              </span>
                                              <div
                                                className={`font-semibold ${
                                                  item.change > 0
                                                    ? "text-green-500"
                                                    : "text-red-500"
                                                }`}
                                              >
                                                {item.change >= 0 ? "+" : ""}
                                                {formatPercentage(
                                                  item.change,
                                                  locale,
                                                )}
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </PopoverContent>
                                  </Popover>
                                ),
                            )}
                            {(fundItems.length > 0 ||
                              stockItems.length > 0 ||
                              cryptoItems.length > 0) &&
                              commodityItems.length > 0 &&
                              commodityItems.some(
                                ci => ci.percentageOfTotalVariableRent > 0,
                              ) && <div className="h-1 w-full my-0.5"></div>}
                            {commodityItems.map(
                              (item, index) =>
                                item.percentageOfTotalPortfolio > 0 && (
                                  <Popover
                                    key={`bar-commodity-${item.id}`}
                                    open={isPopoverOpen(`commodity-${item.id}`)}
                                    onOpenChange={open => {
                                      if (!open) {
                                        setHoveredItem(null)
                                        setClickedItem(null)
                                      }
                                    }}
                                  >
                                    <PopoverTrigger asChild>
                                      <div
                                        className={`w-full ${getItemColorByIndex(index, "COMMODITY")} cursor-pointer hover:opacity-80 transition-opacity`}
                                        style={{
                                          height: `${item.percentageOfTotalPortfolio}%`,
                                        }}
                                        onClick={() =>
                                          handlePopoverClick(
                                            `commodity-${item.id}`,
                                          )
                                        }
                                        onMouseEnter={() =>
                                          handleMouseEnter(
                                            `commodity-${item.id}`,
                                          )
                                        }
                                        onMouseLeave={() =>
                                          setHoveredItem(null)
                                        }
                                      ></div>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-80">
                                      <div
                                        onMouseEnter={() =>
                                          handleMouseEnter(
                                            `commodity-${item.id}`,
                                          )
                                        }
                                        onMouseLeave={() =>
                                          setHoveredItem(null)
                                        }
                                      >
                                        <div className="space-y-2">
                                          <div className="flex items-center space-x-2">
                                            <div
                                              className={`w-4 h-4 rounded ${getItemColorByIndex(index, "COMMODITY")}`}
                                            ></div>
                                            <h4 className="font-medium text-sm">
                                              {
                                                t.enums.commodityType[
                                                  item.type as keyof typeof t.enums.commodityType
                                                ]
                                              }
                                            </h4>
                                          </div>
                                          <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.value}:
                                              </span>
                                              <div className="font-semibold">
                                                {item.formattedValue}
                                              </div>
                                            </div>
                                            {item.percentageOfTotalVariableRent <
                                              100 && (
                                              <div>
                                                <span className="text-muted-foreground">
                                                  {
                                                    t.dashboard
                                                      .stakeInCommodities
                                                  }
                                                  :
                                                </span>
                                                <div className="font-semibold">
                                                  {formatPercentage(
                                                    item.percentageOfTotalVariableRent,
                                                    locale,
                                                  )}
                                                </div>
                                              </div>
                                            )}
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.amount}:
                                              </span>
                                              <div className="font-semibold">
                                                {item.amount?.toLocaleString(
                                                  locale,
                                                  {
                                                    minimumFractionDigits: 0,
                                                    maximumFractionDigits: 1,
                                                  },
                                                )}{" "}
                                                {
                                                  t.enums.weightUnit[
                                                    item.unit as keyof typeof t.enums.weightUnit
                                                  ]
                                                }
                                              </div>
                                            </div>
                                            <div>
                                              <span className="text-muted-foreground">
                                                {t.dashboard.change}:
                                              </span>
                                              <div
                                                className={`font-semibold ${
                                                  item.change > 0
                                                    ? "text-green-500"
                                                    : item.change < 0
                                                      ? "text-red-500"
                                                      : "text-white"
                                                }`}
                                              >
                                                {item.change === 0
                                                  ? "-"
                                                  : (item.change > 0
                                                      ? "+"
                                                      : "") +
                                                    formatPercentage(
                                                      item.change,
                                                      locale,
                                                    )}
                                              </div>
                                            </div>
                                            {item.showEntityBadge &&
                                              item.entities &&
                                              item.entities.length > 0 && (
                                                <div className="col-span-2">
                                                  <span className="text-muted-foreground">
                                                    {t.dashboard.entities}:
                                                  </span>
                                                  <div className="flex flex-wrap gap-1 mt-1">
                                                    {item.entities.map(
                                                      (entity, entityIndex) => (
                                                        <Badge
                                                          key={entityIndex}
                                                          variant="outline"
                                                          className="text-xs"
                                                        >
                                                          {entity}
                                                        </Badge>
                                                      ),
                                                    )}
                                                  </div>
                                                </div>
                                              )}
                                          </div>
                                        </div>
                                      </div>
                                    </PopoverContent>
                                  </Popover>
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
                      <ArrowLeftRight className="h-5 w-5 mr-2 text-primary" />
                      {t.dashboard.recentTransactions}
                    </CardTitle>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate("/transactions")}
                      className="flex items-center gap-1"
                    >
                      {t.dashboard.viewAll}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
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
                                        {getIconForTxType(
                                          tx.type as TxType,
                                          "h-full w-full",
                                        )}
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
                                          tx.displayType === "in"
                                            ? "text-green-600 dark:text-green-400"
                                            : undefined
                                        }`}
                                      >
                                        {tx.displayType === "in" ? "+" : ""}
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
                      <ArrowLeftRight className="h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" />
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
