import { MoneyEventType, type ForecastResult } from "@/types"
import { ProductType } from "@/types/position"
import { getForecast, getMoneyEvents } from "@/services/api"
import { useEffect, useRef, useState, useMemo, useLayoutEffect } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"

let hasLoadedTransactionsThisSession = false
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { TxType } from "@/types/transactions"
import { formatCurrency, formatPercentage, formatDate } from "@/lib/formatters"
import { useSkipMountAnimation } from "@/lib/animations"
import { AnimatedContainer } from "@/components/ui/AnimatedContainer"
import { Button } from "@/components/ui/Button"
import { DatePicker } from "@/components/ui/DatePicker"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs"
import { Switch } from "@/components/ui/Switch"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
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
  CalendarPlus,
  HandCoins,
  CreditCard,
  Home,
  SlidersHorizontal,
  PiggyBank,
  TrendingUpDown,
} from "lucide-react"
import {
  getAssetDistribution,
  getEntityDistribution,
  convertCurrency,
  getOngoingProjects,
  getStockAndFundPositions,
  getCryptoPositions,
  getCommodityPositions,
  getRecentTransactions,
  getDaysStatus,
  computeAdjustedKpis,
  computeForecastKpis,
  filterRealEstateByOptions,
  getTotalCash,
} from "@/utils/financialDataUtils"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts"
import { EntityRefreshDropdown } from "@/components/EntityRefreshDropdown"

export default function DashboardPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const {
    positionsData,
    pendingFlows,
    isInitialLoading,
    error: financialDataError,
    refreshData: refreshFinancialData,
    realEstateList,
    cachedLastTransactions,
    fetchCachedTransactions,
    invalidateTransactionsCache,
  } = useFinancialData()
  const { settings, exchangeRates, refreshExchangeRates } = useAppContext()

  const skipAnimations = useSkipMountAnimation(!isInitialLoading)

  const stablecoinSymbols = settings.assets?.crypto?.stablecoins ?? []
  const stablecoinSymbolsSet = useMemo(() => {
    const normalized = stablecoinSymbols
      .map(symbol => symbol.trim().toUpperCase())
      .filter(Boolean)
    return new Set(normalized)
  }, [stablecoinSymbols])

  // Forecast state
  const [forecastOpen, setForecastOpen] = useState(false)
  const [forecastTargetDate, setForecastTargetDate] = useState<string>("")
  const [forecastAnnualIncrease, setForecastAnnualIncrease] =
    useState<string>("") // market percentage as string input
  const [forecastAnnualCryptoIncrease, setForecastAnnualCryptoIncrease] =
    useState<string>("")
  const [forecastAnnualCommodityIncrease, setForecastAnnualCommodityIncrease] =
    useState<string>("")
  const [forecastLoading, setForecastLoading] = useState(false)
  const [forecastResult, setForecastResult] = useState<ForecastResult | null>(
    null,
  )
  const forecastMode = !!forecastResult

  const [transactionsLoading, setTransactionsLoading] = useState(false)
  const [transactionsError, setTransactionsError] = useState<string | null>(
    null,
  )

  const [upcomingEventsRaw, setUpcomingEventsRaw] = useState<
    Array<{
      kind: "flow" | "contribution" | "maturity"
      id: string
      name: string
      direction: "in" | "out"
      recurring: boolean
      nextDate: Date
      daysUntil: number
      amount: number
      currency: string
      productType?: ProductType
    }>
  >([])
  const [upcomingEventsLoading, setUpcomingEventsLoading] = useState(false)

  const transactions = cachedLastTransactions

  type DashboardOptions = {
    includePending: boolean
    includeCardExpenses: boolean
    includeRealEstate: boolean
    includeResidences: boolean
  }
  const [dashboardOptions, setDashboardOptions] = useState<DashboardOptions>(
    () => {
      if (typeof window !== "undefined") {
        try {
          const raw = localStorage.getItem("dashboardOptions")
          if (raw) return JSON.parse(raw)
        } catch {
          // ignore
        }
      }
      return {
        includePending: true,
        includeCardExpenses: false,
        includeRealEstate: true,
        includeResidences: false,
      }
    },
  )
  useEffect(() => {
    try {
      localStorage.setItem("dashboardOptions", JSON.stringify(dashboardOptions))
    } catch {
      // ignore
    }
  }, [dashboardOptions])

  const fetchTransactionsData = async () => {
    if (cachedLastTransactions) {
      return
    }

    // Only show loading spinner on very first load of the session
    // Not on cache invalidation or return visits to dashboard
    const isFirstLoadEver = !hasLoadedTransactionsThisSession
    if (isFirstLoadEver) {
      setTransactionsLoading(true)
    }
    setTransactionsError(null)
    try {
      await fetchCachedTransactions()
      hasLoadedTransactionsThisSession = true
    } catch (err) {
      console.error("Error fetching transactions:", err)
      setTransactionsError(t.common.unexpectedError)
    } finally {
      if (isFirstLoadEver) {
        setTransactionsLoading(false)
      }
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

  const hasData = useMemo(
    () =>
      positionsData !== null &&
      positionsData.positions &&
      Object.keys(positionsData.positions).length > 0,
    [positionsData],
  )

  // Build derived forecast positions + adjustments (cash delta & remove change data)
  const forecastAdjustedPositionsData = useMemo(() => {
    if (!forecastResult) return null
    // Deep clone positions (shallow is fine for our use) and zero out change-related fields if any
    const cloned: any = {
      positions: { ...forecastResult.positions.positions },
    }
    // Add synthetic cash delta entity if provided
    if (forecastResult.cash_delta && forecastResult.cash_delta.length > 0) {
      const accountEntries = forecastResult.cash_delta.map(cd => ({
        id: `cash-delta-${cd.currency}`,
        total: cd.amount,
        currency: cd.currency,
        type: "CHECKING",
        name: t.forecast.cashDeltaLabel,
      }))
      cloned.positions["forecast-cash-delta"] = {
        id: "forecast-cash-delta",
        entity: {
          id: "forecast-cash-delta",
          name: t.forecast.cashDeltaEntity,
          is_real: true,
        },
        date: forecastResult.target_date,
        is_real: true,
        products: {
          ACCOUNT: { entries: accountEntries },
        },
      }
    }
    return cloned
  }, [forecastResult, t.forecast.cashDeltaEntity, t.forecast.cashDeltaLabel])

  // Decide which positions data to use for computations
  const effectivePositionsData = useMemo(
    () =>
      forecastMode
        ? (forecastAdjustedPositionsData as any) || positionsData
        : positionsData,
    [forecastMode, forecastAdjustedPositionsData, positionsData],
  )

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
  }, [cachedLastTransactions, t])

  const targetCurrency = settings.general.defaultCurrency

  const upcomingEventsData = useMemo(() => {
    return upcomingEventsRaw.map(event => ({
      ...event,
      convertedAmount: convertCurrency(
        event.amount,
        event.currency,
        targetCurrency,
        exchangeRates,
      ),
    }))
  }, [upcomingEventsRaw, targetCurrency, exchangeRates])

  // In forecast mode we never apply current pending flows separately because they're implicitly reflected in the forecast snapshot by date.
  const appliedPendingFlows = useMemo(
    () =>
      forecastMode ? [] : dashboardOptions.includePending ? pendingFlows : [],
    [forecastMode, dashboardOptions.includePending, pendingFlows],
  )
  const appliedRealEstateList = useMemo(
    () => filterRealEstateByOptions(realEstateList, dashboardOptions),
    [realEstateList, dashboardOptions],
  )
  const assetDistributionBase = useMemo(
    () =>
      getAssetDistribution(
        effectivePositionsData,
        targetCurrency,
        exchangeRates,
        appliedPendingFlows,
        appliedRealEstateList,
      ),
    [
      effectivePositionsData,
      targetCurrency,
      exchangeRates,
      appliedPendingFlows,
      appliedRealEstateList,
    ],
  )
  const assetDistribution = useMemo(() => {
    if (!forecastMode || !forecastResult) {
      // Round percentages to 1 decimal also in non-forecast mode
      return assetDistributionBase.map(i => ({
        ...i,
        percentage:
          i.percentage != null
            ? Math.round((i.percentage + Number.EPSILON) * 10) / 10
            : i.percentage,
      }))
    }
    // Sum real estate equity at target (respect dashboard options)
    const includeRE = dashboardOptions.includeRealEstate
    // If residences excluded, remove their equity from forecast aggregation
    const excludedResidenceIds =
      includeRE && !dashboardOptions.includeResidences
        ? new Set(
            (realEstateList || [])
              .filter(re => re.basic_info?.is_residence)
              .map(re => re.id),
          )
        : null
    const totalEquity = includeRE
      ? (forecastResult.real_estate || []).reduce((acc, re) => {
          if (excludedResidenceIds && excludedResidenceIds.has(re.id))
            return acc
          return acc + (re.equity_at_target || 0)
        }, 0)
      : 0
    let items = [...assetDistributionBase]
    // Apply crypto & commodity appreciation percentage on top of base snapshot
    const cryptoFactor = 1 + (forecastResult.crypto_appreciation || 0)
    const commodityFactor = 1 + (forecastResult.commodity_appreciation || 0)
    items = items.map(i => {
      if (i.type === "CRYPTO") {
        return { ...i, value: i.value * cryptoFactor }
      }
      if (i.type === "COMMODITY") {
        return { ...i, value: i.value * commodityFactor }
      }
      return i
    })
    if (totalEquity > 0) {
      // Replace existing REAL_ESTATE if present
      const idx = items.findIndex(i => i.type === "REAL_ESTATE")
      if (idx >= 0) items.splice(idx, 1)
      items.push({
        type: "REAL_ESTATE",
        value: totalEquity,
        percentage: 0, // will recompute below
        change: 0,
      })
    }
    const totalValue = items.reduce((acc, i) => acc + i.value, 0)
    items = items.map(i => ({
      ...i,
      percentage:
        totalValue > 0
          ? Math.round(((i.value / totalValue) * 100 + Number.EPSILON) * 10) /
            10
          : 0,
    }))
    return items.sort((a, b) => b.value - a.value)
  }, [
    assetDistributionBase,
    forecastMode,
    forecastResult,
    dashboardOptions.includeRealEstate,
    dashboardOptions.includeResidences,
    realEstateList,
  ])
  const entityDistributionBase = useMemo(
    () =>
      getEntityDistribution(
        effectivePositionsData,
        targetCurrency,
        exchangeRates,
        appliedPendingFlows,
        appliedRealEstateList,
      ),
    [
      effectivePositionsData,
      targetCurrency,
      exchangeRates,
      appliedPendingFlows,
      appliedRealEstateList,
    ],
  )
  const entityDistribution = useMemo(() => {
    if (!forecastMode || !forecastResult) return entityDistributionBase
    const cryptoFactor = 1 + (forecastResult.crypto_appreciation || 0)
    const commodityFactor = 1 + (forecastResult.commodity_appreciation || 0)
    if (cryptoFactor === 1 && commodityFactor === 1)
      return entityDistributionBase
    // Build per-entity base crypto & commodity values from raw positions
    const perEntityDeltas: Record<string, number> = {}
    const pos = effectivePositionsData?.positions || {}
    Object.entries(pos).forEach(([entityId, gp]: any) => {
      let cryptoBase = 0
      let commodityBase = 0
      const cryptoProduct = gp.products?.CRYPTO
      if (cryptoProduct?.entries?.length) {
        cryptoProduct.entries.forEach((w: any) => {
          const mv = typeof w.market_value === "number" ? w.market_value : 0
          const cur = w.currency || targetCurrency
          cryptoBase += convertCurrency(mv, cur, targetCurrency, exchangeRates)
        })
      }
      const commodityProduct = gp.products?.COMMODITY
      if (commodityProduct?.entries?.length) {
        commodityProduct.entries.forEach((c: any) => {
          const mv = typeof c.market_value === "number" ? c.market_value : 0
          const cur = c.currency || targetCurrency
          commodityBase += convertCurrency(
            mv,
            cur,
            targetCurrency,
            exchangeRates,
          )
        })
      }
      const delta =
        cryptoBase * (cryptoFactor - 1) + commodityBase * (commodityFactor - 1)
      if (delta !== 0) perEntityDeltas[entityId] = delta
    })
    // Apply deltas to distribution values
    const adjusted = entityDistributionBase.map(item => ({
      ...item,
      value:
        item.id in perEntityDeltas
          ? item.value + perEntityDeltas[item.id]
          : item.value,
    }))
    const total = adjusted.reduce((s, i) => s + i.value, 0)
    return adjusted
      .map(i => ({
        ...i,
        percentage: total > 0 ? (i.value / total) * 100 : 0,
      }))
      .sort((a, b) => b.value - a.value)
  }, [
    entityDistributionBase,
    forecastMode,
    forecastResult,
    effectivePositionsData,
    targetCurrency,
    exchangeRates,
  ])
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
      } else if (item.id === "real-estate") {
        return {
          ...item,
          name: (t.enums?.productType as any)?.REAL_ESTATE,
        }
      } else if (item.id === "forecast-cash-delta") {
        return {
          ...item,
          name: t.forecast.cashDeltaEntity,
        }
      } else {
        return {
          ...item,
          name: (t.enums?.productType as any)?.COMMODITY,
        }
      }
    })
  }, [entityDistribution, entities, t])
  const { adjustedTotalAssets, adjustedInvestedAmount } = useMemo(() => {
    if (!forecastMode) {
      const currentSnapshot = computeAdjustedKpis(
        positionsData,
        targetCurrency,
        exchangeRates,
        pendingFlows,
        realEstateList,
        dashboardOptions,
      )
      return {
        adjustedTotalAssets: currentSnapshot.adjustedTotalAssets,
        adjustedInvestedAmount: currentSnapshot.adjustedInvestedAmount,
      }
    }
    const forecastKpis = computeForecastKpis(
      positionsData,
      effectivePositionsData as any,
      targetCurrency,
      exchangeRates,
      [],
      realEstateList,
      forecastResult?.real_estate?.map(re => ({
        id: re.id,
        equity_at_target: re.equity_at_target || 0,
      })),
      { ...dashboardOptions, includePending: false },
    )
    // Appreciation deltas (crypto & commodities) not embedded in forecast positions snapshot
    let projectedTotalAssets = forecastKpis.projectedTotalAssets
    if (forecastResult) {
      const cryptoFactor = 1 + (forecastResult.crypto_appreciation || 0)
      const commodityFactor = 1 + (forecastResult.commodity_appreciation || 0)
      if (cryptoFactor !== 1) {
        const baseCrypto = getCryptoPositions(
          positionsData,
          locale,
          settings.general.defaultCurrency,
          exchangeRates,
        ).reduce((s, c) => s + c.value, 0)
        const appreciatedCrypto = baseCrypto * cryptoFactor
        projectedTotalAssets += appreciatedCrypto - baseCrypto
      }
      if (commodityFactor !== 1) {
        const baseCommodity = getCommodityPositions(
          positionsData,
          locale,
          settings.general.defaultCurrency,
          exchangeRates,
          settings,
        ).reduce((s, c) => s + c.value, 0)
        const appreciatedCommodity = baseCommodity * commodityFactor
        projectedTotalAssets += appreciatedCommodity - baseCommodity
      }
    }
    return {
      adjustedTotalAssets: projectedTotalAssets,
      adjustedInvestedAmount: forecastKpis.projectedInvestedAmount,
    }
  }, [
    forecastMode,
    positionsData,
    effectivePositionsData,
    targetCurrency,
    exchangeRates,
    pendingFlows,
    realEstateList,
    dashboardOptions,
    forecastResult,
    locale,
    settings,
  ])

  const forecastCashDeltaTotal = useMemo(() => {
    if (
      !forecastMode ||
      !forecastResult ||
      !Array.isArray(forecastResult.cash_delta)
    )
      return 0
    return forecastResult.cash_delta.reduce<number>(
      (acc, cd) =>
        acc +
        convertCurrency(cd.amount, cd.currency, targetCurrency, exchangeRates),
      0,
    )
  }, [forecastMode, forecastResult, targetCurrency, exchangeRates])
  // Base ongoing projects (unfiltered)
  const ongoingProjectsBase = useMemo(
    () =>
      getOngoingProjects(
        positionsData,
        locale,
        settings.general.defaultCurrency,
      ),
    [positionsData, locale, settings.general.defaultCurrency],
  )
  // When forecasting, only show projects whose maturity is after the forecast target date
  const ongoingProjects = useMemo(() => {
    if (!forecastMode || !forecastResult) return ongoingProjectsBase
    try {
      const target = new Date(forecastResult.target_date)
      return ongoingProjectsBase.filter(p => {
        const maturity = new Date(p.maturity)
        const extended = p.extendedMaturity
          ? new Date(p.extendedMaturity)
          : null
        const hasValidExtended = !!extended && !Number.isNaN(extended.getTime())
        const hasValidMaturity = !Number.isNaN(maturity.getTime())
        if (!hasValidMaturity && !hasValidExtended) return false

        const effectiveMaturity =
          hasValidExtended && (!hasValidMaturity || extended! > maturity)
            ? extended!
            : maturity

        return effectiveMaturity >= target
      })
    } catch {
      return ongoingProjectsBase
    }
  }, [forecastMode, forecastResult, ongoingProjectsBase])
  const stockAndFundPositions = useMemo(
    () =>
      getStockAndFundPositions(
        effectivePositionsData,
        locale,
        settings.general.defaultCurrency,
        exchangeRates,
      ),
    [
      effectivePositionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    ],
  )
  const cryptoPositions = useMemo(
    () =>
      getCryptoPositions(
        effectivePositionsData,
        locale,
        settings.general.defaultCurrency,
        exchangeRates,
      ),
    [
      effectivePositionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    ],
  )
  const commodityPositions = useMemo(
    () =>
      getCommodityPositions(
        effectivePositionsData,
        locale,
        settings.general.defaultCurrency,
        exchangeRates,
        settings,
      ),
    [
      effectivePositionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
      settings,
    ],
  )
  // Asset presence flags for conditional forecast inputs
  const hasMarketAssets = useMemo(
    () =>
      stockAndFundPositions.some(
        p => p.type === "FUND" || p.type === "STOCK_ETF",
      ),
    [stockAndFundPositions],
  )
  const hasCryptoAssets = cryptoPositions.length > 0
  const hasCommodityAssets = commodityPositions.length > 0
  const recentTransactions = useMemo(
    () =>
      getRecentTransactions(
        transactions,
        locale,
        settings.general.defaultCurrency,
      ),
    [transactions, locale, settings.general.defaultCurrency],
  )

  const fundItems = useMemo(
    () =>
      stockAndFundPositions
        .filter(p => p.type === "FUND")
        .map((p, index) => ({
          ...p,
          id: `fund-${p.name}-${p.entity}-${p.portfolioName || "default"}-${index}`,
        })),
    [stockAndFundPositions],
  )

  const stockItems = useMemo(
    () =>
      stockAndFundPositions
        .filter(p => p.type === "STOCK_ETF")
        .map((p, index) => ({
          ...p,
          id: `${p.symbol}-stock-${index}-${p.entity}`,
        })),
    [stockAndFundPositions],
  )

  // Apply appreciation in forecast mode for crypto & commodities (excluding stablecoins)
  const cryptoItems = useMemo(() => {
    const factor =
      forecastMode && forecastResult
        ? 1 + (forecastResult.crypto_appreciation || 0)
        : 1
    // Base total for later percentage recompute
    const baseOthersTotal = [...fundItems, ...stockItems].reduce(
      (s, i) => s + i.value,
      0,
    )
    const mapped = cryptoPositions.map((p, index) => {
      const baseValue = p.value
      const normalizedSymbol = (p.symbol || "").toUpperCase()
      const shouldApplyAppreciation =
        factor !== 1 && !stablecoinSymbolsSet.has(normalizedSymbol)
      const value = shouldApplyAppreciation ? baseValue * factor : baseValue
      const tokens = p.tokens?.map(tk => {
        const tokenSymbol = (tk.symbol || "").toUpperCase()
        const shouldApplyTokenAppreciation =
          factor !== 1 && !stablecoinSymbolsSet.has(tokenSymbol)
        const tVal = shouldApplyTokenAppreciation ? tk.value * factor : tk.value
        return {
          ...tk,
          value: tVal,
          formattedValue: formatCurrency(
            tVal,
            locale,
            settings.general.defaultCurrency,
          ),
        }
      })
      let change = p.change
      if (shouldApplyAppreciation && p.initialInvestment > 0) {
        change = ((value - p.initialInvestment) / p.initialInvestment) * 100
      }
      return {
        ...p,
        value,
        change,
        formattedValue: formatCurrency(
          value,
          locale,
          settings.general.defaultCurrency,
        ),
        tokens,
        id: `crypto-${p.symbol}-${p.entities.join("-")}-${p.address}-${index}`,
      }
    })
    // Recompute percentageOfTotalPortfolio after scaling
    const total =
      baseOthersTotal +
      mapped.reduce((s, i) => s + i.value, 0) +
      commodityPositions.reduce((s, i) => s + i.value, 0)
    return mapped.map(m => ({
      ...m,
      percentageOfTotalPortfolio: total > 0 ? (m.value / total) * 100 : 0,
    }))
  }, [
    cryptoPositions,
    forecastMode,
    forecastResult,
    locale,
    settings.general.defaultCurrency,
    fundItems,
    stockItems,
    commodityPositions,
    stablecoinSymbolsSet,
  ])

  const commodityItems = useMemo(() => {
    const factor =
      forecastMode && forecastResult
        ? 1 + (forecastResult.commodity_appreciation || 0)
        : 1
    const baseOthersTotal = [...fundItems, ...stockItems].reduce(
      (s, i) => s + i.value,
      0,
    )
    const baseCryptoTotal = cryptoItems.reduce((s, i) => s + i.value, 0)
    const mapped = commodityPositions.map((p, index) => {
      const baseValue = p.value
      const value = factor !== 1 ? baseValue * factor : baseValue
      let change = p.change
      if (factor !== 1 && p.initialInvestment > 0) {
        change = ((value - p.initialInvestment) / p.initialInvestment) * 100
      }
      return {
        ...p,
        value,
        change,
        formattedValue: formatCurrency(
          value,
          locale,
          settings.general.defaultCurrency,
        ),
        id: `commodity-${p.symbol}-${p.entities.join("-")}-${index}`,
      }
    })
    const total =
      baseOthersTotal +
      baseCryptoTotal +
      mapped.reduce((s, i) => s + i.value, 0)
    return mapped.map(m => ({
      ...m,
      percentageOfTotalPortfolio: total > 0 ? (m.value / total) * 100 : 0,
    }))
  }, [
    commodityPositions,
    forecastMode,
    forecastResult,
    locale,
    settings.general.defaultCurrency,
    fundItems,
    stockItems,
    cryptoItems,
  ])

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

  // Projected / current cash for warning (separate from fundPortfolioColorMap memo)
  const projectedCash = useMemo(() => {
    if (forecastMode) {
      return getTotalCash(effectivePositionsData, targetCurrency, exchangeRates)
    }
    return getTotalCash(positionsData, targetCurrency, exchangeRates)
  }, [
    forecastMode,
    effectivePositionsData,
    positionsData,
    targetCurrency,
    exchangeRates,
  ])

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
      // In forecast mode, ensure no change/profit related info leaks
      if (forecastMode) {
        data.change = 0
      }
      return (
        <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
          <div className="flex items-center gap-2 mb-2">
            {getIconForAssetType(data.type)}
            <p className="font-medium text-sm text-popover-foreground">
              {(t.enums?.productType as any)?.[data.type] ?? data.type}
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
        REAL_ESTATE_CF: "/investments/real-estate-cf",
        CRYPTO: "/investments/crypto",
        COMMODITY: "/investments/commodities",
        PENDING_FLOWS: "/management/pending",
        CASH: "/banking",
        REAL_ESTATE: "/real-estate",
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
              title={`${(t.enums?.productType as any)?.[assetType] ?? assetType}: ${formatCurrency(assetValue, locale, settings.general.defaultCurrency)} (${assetPercentage}%)${hasRoute ? " - Click to view details" : ""}`}
              onClick={() => hasRoute && handleLegendClick(assetType)}
            >
              <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center">
                {icon}
              </span>
              <span className="capitalize truncate flex-grow min-w-0">
                {(t.enums?.productType as any)?.[assetType] ?? assetType}
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
        {forecastMode && forecastCashDeltaTotal < 0 && (
          <li
            className="flex items-center space-x-2 p-1 rounded bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40"
            title={(t as any).forecast.pendingPaymentsLegend.replace(
              "{amount}",
              formatCurrency(
                Math.abs(forecastCashDeltaTotal),
                locale,
                settings.general.defaultCurrency,
              ),
            )}
          >
            <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4" />
            </span>
            <span className="truncate flex-grow min-w-0 text-red-700 dark:text-red-300">
              {(t as any).forecast.pendingPaymentsLegendLabel}
            </span>
            <div className="text-right flex space-x-1 text-red-700 dark:text-red-300">
              <span className="block whitespace-nowrap text-[11px]">
                {formatCurrency(
                  Math.abs(forecastCashDeltaTotal),
                  locale,
                  settings.general.defaultCurrency,
                )}
              </span>
            </div>
          </li>
        )}
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
        {forecastMode && forecastCashDeltaTotal < 0 && (
          <li
            className="flex items-center space-x-2 p-1 rounded bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40"
            title={(t as any).forecast.pendingPaymentsLegend.replace(
              "{amount}",
              formatCurrency(
                Math.abs(forecastCashDeltaTotal),
                locale,
                settings.general.defaultCurrency,
              ),
            )}
          >
            <span className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4" />
            </span>
            <span className="truncate flex-grow min-w-0 text-red-700 dark:text-red-300">
              {(t as any).forecast.pendingPaymentsLegendLabel}
            </span>
            <div className="text-right flex space-x-1 text-red-700 dark:text-red-300">
              <span className="block whitespace-nowrap text-[11px]">
                {formatCurrency(
                  Math.abs(forecastCashDeltaTotal),
                  locale,
                  settings.general.defaultCurrency,
                )}
              </span>
            </div>
          </li>
        )}
      </ul>
    )
  }

  // Fetch upcoming events from API
  useEffect(() => {
    if (forecastMode) {
      setUpcomingEventsRaw([])
      return
    }

    const fetchUpcomingEvents = async () => {
      setUpcomingEventsLoading(true)
      try {
        const tomorrow = new Date()
        tomorrow.setDate(tomorrow.getDate() + 1)
        const nextMonth = new Date()
        nextMonth.setMonth(nextMonth.getMonth() + 1)

        const fromDate = tomorrow.toISOString().split("T")[0]
        const toDate = nextMonth.toISOString().split("T")[0]

        const response = await getMoneyEvents({
          from_date: fromDate,
          to_date: toDate,
        })

        const mappedEvents = response.events
          .map(event => {
            const nextDate = new Date(event.date)
            const today = new Date()
            today.setHours(0, 0, 0, 0)
            const daysUntil = Math.ceil(
              (nextDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
            )

            let kind: "flow" | "contribution" | "maturity"
            let recurring = false

            if (event.type === MoneyEventType.CONTRIBUTION) {
              kind = "contribution"
              recurring = true
            } else if (event.type === MoneyEventType.PERIODIC_FLOW) {
              kind = "flow"
              recurring = true
            } else if (event.type === MoneyEventType.MATURITY) {
              kind = "maturity"
              recurring = false
            } else {
              kind = "flow"
              recurring = false
            }

            const isEarning = event.amount > 0

            return {
              kind,
              id: event.id || `event-${event.name}-${event.date}`,
              name: event.name,
              direction: isEarning ? ("in" as const) : ("out" as const),
              recurring,
              nextDate,
              daysUntil,
              amount: Math.abs(event.amount),
              currency: event.currency,
              productType: event.product_type ?? undefined,
            }
          })
          .filter(e => e.daysUntil >= 0)
          .sort((a, b) => a.nextDate.getTime() - b.nextDate.getTime())
          .slice(0, 5)

        setUpcomingEventsRaw(mappedEvents)
      } catch (error) {
        console.error("Failed to fetch upcoming events:", error)
        setUpcomingEventsRaw([])
      } finally {
        setUpcomingEventsLoading(false)
      }
    }

    fetchUpcomingEvents()
  }, [forecastMode])

  const isLoading = isInitialLoading || transactionsLoading
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
            invalidateTransactionsCache()
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

  if (!exchangeRates) {
    return (
      <div className="flex justify-center items-center h-[70vh]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const renderUpcomingCard = () => (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 gap-2">
        <CardTitle className="text-lg font-bold flex items-center">
          <CalendarDays className="h-5 w-5 mr-2 text-primary" />
          {t.dashboard.upcomingFlows}
        </CardTitle>
        {!forecastMode && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/management")}
            className="text-xs px-2 py-1 h-auto min-h-0 self-start sm:self-auto"
          >
            <ArrowRight className="h-3 w-3 mr-1" />
            {t.dashboard.manageFlows}
          </Button>
        )}
      </CardHeader>
      <CardContent className="pt-0">
        {forecastMode && (
          <div className="flex flex-col items-center justify-center py-6 text-center text-sm text-muted-foreground">
            <TrendingUpDown className="h-8 w-8 mb-2 opacity-60" />
            <p>{t.forecast.notShowing}</p>
          </div>
        )}
        {!forecastMode && upcomingEventsLoading && (
          <div className="flex justify-center items-center py-6">
            <LoadingSpinner size="sm" />
          </div>
        )}
        {!forecastMode &&
          !upcomingEventsLoading &&
          upcomingEventsData.length === 0 && (
            <div className="flex flex-col items-center justify-center py-6 text-center text-sm text-muted-foreground">
              <CalendarDays className="h-8 w-8 mb-2 opacity-60" />
              <p>{t.dashboard.noUpcomingFlows}</p>
            </div>
          )}
        {!forecastMode &&
          !upcomingEventsLoading &&
          upcomingEventsData.length > 0 && (
            <div className="space-y-3">
              {upcomingEventsData.map((item, index) => {
                const isEarning = item.direction === "in"
                const urgencyInfo = getDateUrgencyInfo(
                  item.nextDate.toISOString().split("T")[0],
                )
                const fullName = item.name || ""
                const displayName = fullName
                const amountColorClass =
                  item.kind === "contribution"
                    ? "text-foreground"
                    : item.kind === "maturity" || isEarning
                      ? "text-green-600"
                      : "text-red-600"
                const amountPrefix =
                  item.kind === "contribution"
                    ? ""
                    : item.kind === "maturity" || isEarning
                      ? "+"
                      : "-"
                return (
                  <div
                    key={`${item.kind}-${item.id}-${index}`}
                    className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 p-3 rounded-lg bg-muted/50"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      {item.kind === "contribution" ? (
                        <PiggyBank className="h-4 w-4 flex-shrink-0 text-blue-500" />
                      ) : item.kind === "maturity" && item.productType ? (
                        <span className="flex-shrink-0">
                          {getIconForAssetType(
                            item.productType,
                            "h-4 w-4",
                            null,
                          )}
                        </span>
                      ) : item.recurring ? (
                        <CalendarSync
                          className={`h-4 w-4 flex-shrink-0 ${isEarning ? "text-green-500" : "text-red-500"}`}
                        />
                      ) : (
                        <HandCoins
                          className={`h-4 w-4 flex-shrink-0 ${isEarning ? "text-green-500" : "text-red-500"}`}
                        />
                      )}
                      <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 min-w-0 flex-1">
                        <p
                          className="font-medium text-sm truncate"
                          title={fullName}
                        >
                          {displayName}
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
                            className="text-[10px] leading-tight px-2 py-0 h-4 self-start sm:self-auto whitespace-nowrap min-w-[65px] inline-flex items-center justify-center"
                          >
                            {urgencyInfo.timeText}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <p
                      className={`font-mono text-sm font-semibold md:flex-shrink-0 text-left md:text-right ${amountColorClass}`}
                    >
                      {amountPrefix}
                      {formatCurrency(
                        Math.abs(item.convertedAmount),
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
      </CardContent>
    </Card>
  )

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
    return {
      show: true,
      urgencyLevel: "normal" as const,
      timeText: formatDate(dateString, locale),
    }
  }

  const getInvestmentRouteForProject = (assetType: string) => {
    const routeMap: Record<string, string> = {
      FACTORING: "/investments/factoring",
      DEPOSIT: "/investments/deposits",
      REAL_ESTATE_CF: "/investments/real-estate-cf",
      CROWDLENDING: "/investments/crowdlending",
    }
    return routeMap[assetType] || null
  }

  return (
    <div className="space-y-6 pb-8">
      {forecastLoading ? (
        <div className="flex justify-center items-center h-[70vh]">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-6"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center">
            <h1 className="text-3xl font-bold flex-shrink-0">
              {t.common.dashboard}
            </h1>
            <div className="flex flex-wrap gap-2 items-center justify-end">
              {/* Forecast active indicator / trigger */}
              <Popover open={forecastOpen} onOpenChange={setForecastOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant={forecastMode ? "default" : "outline"}
                    className="flex items-center h-9 px-3 text-sm"
                  >
                    <TrendingUpDown className="h-4 w-4 mr-1 flex-shrink-0" />
                    <span className="whitespace-nowrap">
                      {forecastMode && forecastResult
                        ? formatDate(forecastResult.target_date, locale)
                        : t.forecast.title}
                    </span>
                    {forecastMode && (
                      <span
                        onClick={e => {
                          e.stopPropagation()
                          setForecastResult(null)
                          setForecastTargetDate("")
                          setForecastAnnualIncrease("")
                          setForecastAnnualCryptoIncrease("")
                          setForecastAnnualCommodityIncrease("")
                        }}
                        className="ml-2 text-xs font-semibold opacity-80 hover:opacity-100 cursor-pointer"
                        aria-label={t.forecast.close}
                      >
                        ×
                      </span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80 z-[50]" align="end">
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-xs font-medium">
                        {t.forecast.targetDate}
                      </label>
                      <DatePicker
                        value={forecastTargetDate}
                        onChange={setForecastTargetDate}
                        placeholder={t.forecast.targetDate}
                      />
                    </div>
                    {hasMarketAssets && (
                      <div className="space-y-1">
                        <label className="text-xs font-medium flex items-center justify-between">
                          <span>{t.forecast.avgAnnualIncrease}</span>
                          <span className="text-[10px] text-muted-foreground">
                            %
                          </span>
                        </label>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={forecastAnnualIncrease}
                          onChange={e =>
                            setForecastAnnualIncrease(e.target.value)
                          }
                          className="w-full h-9 px-2 rounded-md border bg-background text-sm"
                          placeholder="0.0"
                        />
                      </div>
                    )}
                    {hasCryptoAssets && (
                      <div className="space-y-1">
                        <label className="text-xs font-medium flex items-center justify-between">
                          <span>{t.forecast.avgAnnualCryptoIncrease}</span>
                          <span className="text-[10px] text-muted-foreground">
                            %
                          </span>
                        </label>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={forecastAnnualCryptoIncrease}
                          onChange={e =>
                            setForecastAnnualCryptoIncrease(e.target.value)
                          }
                          className="w-full h-9 px-2 rounded-md border bg-background text-sm"
                          placeholder="0.0"
                        />
                      </div>
                    )}
                    {hasCommodityAssets && (
                      <div className="space-y-1">
                        <label className="text-xs font-medium flex items-center justify-between">
                          <span>{t.forecast.avgAnnualCommodityIncrease}</span>
                          <span className="text-[10px] text-muted-foreground">
                            %
                          </span>
                        </label>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={forecastAnnualCommodityIncrease}
                          onChange={e =>
                            setForecastAnnualCommodityIncrease(e.target.value)
                          }
                          className="w-full h-9 px-2 rounded-md border bg-background text-sm"
                          placeholder="0.0"
                        />
                      </div>
                    )}
                    <div className="flex justify-end gap-2">
                      {forecastMode && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setForecastResult(null)
                            setForecastTargetDate("")
                            setForecastAnnualIncrease("")
                            setForecastAnnualCryptoIncrease("")
                            setForecastAnnualCommodityIncrease("")
                          }}
                          className="text-xs"
                        >
                          {t.forecast.reset}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        disabled={
                          !forecastTargetDate ||
                          forecastLoading ||
                          (!!forecastTargetDate &&
                            new Date(forecastTargetDate) <= new Date())
                        }
                        onClick={async () => {
                          try {
                            setForecastLoading(true)
                            const result = await getForecast({
                              target_date: forecastTargetDate,
                              avg_annual_market_increase: forecastAnnualIncrease
                                ? parseFloat(forecastAnnualIncrease) / 100
                                : null,
                              avg_annual_crypto_increase:
                                forecastAnnualCryptoIncrease
                                  ? parseFloat(forecastAnnualCryptoIncrease) /
                                    100
                                  : null,
                              avg_annual_commodity_increase:
                                forecastAnnualCommodityIncrease
                                  ? parseFloat(
                                      forecastAnnualCommodityIncrease,
                                    ) / 100
                                  : null,
                            })
                            setForecastResult(result)
                            setForecastOpen(false)
                          } catch (err) {
                            console.error("Forecast error", err)
                          } finally {
                            setForecastLoading(false)
                          }
                        }}
                        className="text-xs"
                      >
                        {forecastLoading ? t.common.loading : t.forecast.run}
                      </Button>
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      {t.forecast.disclaimer}
                    </p>
                  </div>
                </PopoverContent>
              </Popover>
              {/* Dashboard Options */}
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="flex items-center h-9 px-3"
                  >
                    <SlidersHorizontal className="h-4 w-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80" align="end">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm flex items-center gap-2">
                        <HandCoins className="h-4 w-4 text-muted-foreground" />
                        {t.dashboard.includePendingMoney}
                      </div>
                      <Switch
                        disabled={forecastMode}
                        checked={
                          forecastMode ? false : dashboardOptions.includePending
                        }
                        onCheckedChange={val =>
                          setDashboardOptions(prev => ({
                            ...prev,
                            includePending: Boolean(val),
                          }))
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-sm flex items-center gap-2">
                        <CreditCard className="h-4 w-4 text-muted-foreground" />
                        {t.dashboard.includeCardExpenses}
                      </div>
                      <Switch
                        checked={dashboardOptions.includeCardExpenses}
                        onCheckedChange={val =>
                          setDashboardOptions(prev => ({
                            ...prev,
                            includeCardExpenses: Boolean(val),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="text-sm flex items-center gap-2">
                          <Home className="h-4 w-4 text-muted-foreground" />
                          {t.dashboard.includeRealEstateEquity}
                        </div>
                        <Switch
                          checked={dashboardOptions.includeRealEstate}
                          onCheckedChange={val =>
                            setDashboardOptions(prev => ({
                              ...prev,
                              includeRealEstate: Boolean(val),
                            }))
                          }
                        />
                      </div>
                      <div className="flex items-center justify-between pl-6">
                        <div className="text-sm text-muted-foreground">
                          {t.dashboard.includeResidences}
                        </div>
                        <Switch
                          checked={dashboardOptions.includeResidences}
                          onCheckedChange={val =>
                            setDashboardOptions(prev => ({
                              ...prev,
                              includeResidences: Boolean(val),
                            }))
                          }
                          disabled={!dashboardOptions.includeRealEstate}
                        />
                      </div>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
              <EntityRefreshDropdown />
            </div>
          </div>

          {!hasData ? (
            <AnimatedContainer
              skipAnimation={skipAnimations}
              delay={0.2}
              className="flex flex-col items-center justify-center h-[70vh] text-center"
            >
              <BarChart3 className="h-16 w-16 text-gray-400 mb-6" />
              <h2 className="text-2xl font-bold mb-3">
                {t.dashboard.noDataTitle}
              </h2>
              <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md">
                {t.dashboard.noDataSubtitle}
              </p>
              <Button onClick={() => navigate("/entities")}>
                {t.dashboard.connectEntitiesButton}
              </Button>
            </AnimatedContainer>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <AnimatedContainer
                  skipAnimation={skipAnimations}
                  delay={0.1}
                  className="order-2 lg:order-1 lg:col-span-7"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg font-bold flex items-center">
                        <PieChartIcon className="h-5 w-5 mr-2 text-primary" />
                        {t.dashboard.assetDistribution}
                      </CardTitle>
                    </CardHeader>
                    <CardContent
                      ref={assetDistributionCardRef}
                      className="px-2"
                    >
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
                                    cx={
                                      assetDistributionCardSmall ? "50%" : "45%"
                                    }
                                    cy={
                                      assetDistributionCardSmall ? "40%" : "50%"
                                    }
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
                                        cx +
                                        radius * Math.cos(-midAngle * RADIAN)
                                      const y =
                                        cy +
                                        radius * Math.sin(-midAngle * RADIAN)

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
                                            fontSize={
                                              isLargeSegment ? "12" : "10"
                                            }
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
                                    cx={
                                      assetDistributionCardSmall ? "50%" : "45%"
                                    }
                                    cy={
                                      assetDistributionCardSmall ? "40%" : "50%"
                                    }
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
                                        cx +
                                        radius * Math.cos(-midAngle * RADIAN)
                                      const y =
                                        cy +
                                        radius * Math.sin(-midAngle * RADIAN)

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
                                            fontSize={
                                              isLargeSegment ? "12" : "10"
                                            }
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
                </AnimatedContainer>

                <AnimatedContainer
                  skipAnimation={skipAnimations}
                  delay={0.25}
                  className="order-3 lg:hidden"
                >
                  {renderUpcomingCard()}
                </AnimatedContainer>

                <AnimatedContainer
                  skipAnimation={skipAnimations}
                  delay={0.2}
                  className="order-1 lg:order-2 lg:col-span-5 lg:col-start-8 space-y-6"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg font-bold flex items-center">
                        <Wallet className="h-5 w-5 mr-2 text-primary" />
                        {t.dashboard.netWorth}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-y-1">
                        <p className="text-4xl font-bold">
                          {formatCurrency(
                            adjustedTotalAssets,
                            locale,
                            settings.general.defaultCurrency,
                          )}
                        </p>
                        {adjustedInvestedAmount > 0 &&
                          (() => {
                            const percentageValue =
                              ((adjustedTotalAssets - adjustedInvestedAmount) /
                                adjustedInvestedAmount) *
                              100
                            const sign = percentageValue >= 0 ? "+" : "-"
                            return (
                              <p
                                className={`text-xl font-medium sm:text-right sm:self-end ${percentageValue === 0 ? "text-gray-500 dark:text-gray-400" : percentageValue > 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
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
                          adjustedInvestedAmount,
                          locale,
                          settings.general.defaultCurrency,
                        )}
                      </p>
                      {forecastMode && projectedCash < 0 && (
                        <div className="mt-3 flex items-start gap-3 rounded-md border border-amber-400/60 bg-amber-100/70 dark:bg-amber-900/40 px-3 py-2.5 text-sm">
                          <div className="shrink-0 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-300 p-1.5 ring-1 ring-amber-500/30">
                            <AlertCircle className="h-5 w-5" />
                          </div>
                          <div className="space-y-0.5">
                            <p className="font-semibold text-amber-800 dark:text-amber-200 tracking-tight">
                              {t.forecast.negativeCashWarningTitle}
                            </p>
                            <p className="text-amber-800/90 dark:text-amber-100/80 leading-snug">
                              {t.forecast.negativeCashWarning.replace(
                                "{amount}",
                                formatCurrency(
                                  projectedCash,
                                  locale,
                                  settings.general.defaultCurrency,
                                ),
                              )}
                            </p>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                  <div className="hidden lg:block">{renderUpcomingCard()}</div>
                </AnimatedContainer>
              </div>

              {ongoingProjects.length > 0 ? (
                <AnimatedContainer skipAnimation={skipAnimations} delay={0.3}>
                  {/* Ongoing investments (full-width, no card background) */}
                  <div className="relative w-full">
                    <div className="flex flex-row items-center justify-between pb-3">
                      <div>
                        <h2 className="text-lg font-bold flex items-center">
                          <TrendingUp className="h-5 w-5 mr-2 text-primary" />
                          {t.dashboard.ongoingProjects}
                        </h2>
                      </div>
                      {ongoingProjects.length > 3 && (
                        <div className="flex space-x-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => scrollProjects("left")}
                            disabled={!showLeftScroll}
                            className={`h-7 w-7 p-0 ${
                              !showLeftScroll
                                ? "opacity-50 cursor-not-allowed"
                                : ""
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
                    </div>
                    {/* Full-bleed horizontal scroller */}
                    <div className="-mx-4 sm:-mx-6">
                      <div
                        ref={projectsContainerRef}
                        className="flex overflow-x-auto overflow-y-visible space-x-3 scrollbar-none px-4 sm:px-6 pb-4"
                        onScroll={handleScroll}
                        style={{
                          scrollbarWidth: "none",
                          msOverflowStyle: "none",
                        }}
                      >
                        {ongoingProjects.map((project, index) => {
                          const status = getDaysStatus(
                            project.maturity,
                            t,
                            project.extendedMaturity,
                          )
                          const route = getInvestmentRouteForProject(
                            project.type,
                          )
                          return (
                            <Card
                              key={index}
                              className={`flex-shrink-0 w-[280px] ${route ? "cursor-pointer hover:border-primary/40 transition-colors" : ""}`}
                              onClick={() => route && navigate(route)}
                              role={route ? "button" : undefined}
                              tabIndex={route ? 0 : -1}
                              onKeyDown={e => {
                                if (
                                  route &&
                                  (e.key === "Enter" || e.key === " ")
                                ) {
                                  e.preventDefault()
                                  navigate(route)
                                }
                              }}
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
                                          {getIconForAssetType(project.type)}
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
                                      <span className="font-semibold inline-flex items-center gap-1">
                                        {status.usedExtendedMaturity && (
                                          <CalendarPlus className="h-3 w-3" />
                                        )}
                                        {status.statusText}
                                      </span>
                                    </Badge>
                                  </div>
                                </div>
                                <div className="space-y-1 mt-auto">
                                  <div className="flex justify-between text-[10px] text-muted-foreground">
                                    <span>{t.dashboard.maturity}</span>
                                    <span>
                                      {formatDate(
                                        status.usedExtendedMaturity &&
                                          project.extendedMaturity
                                          ? project.extendedMaturity
                                          : project.maturity,
                                        locale,
                                      )}
                                    </span>
                                  </div>
                                  <div className="flex justify-between items-start mb-2">
                                    <p className="text-base font-semibold">
                                      {project.formattedValue}
                                    </p>
                                    {(() => {
                                      const isLate =
                                        status.isDelayed &&
                                        project.type === "FACTORING" &&
                                        project.lateInterestRate != null &&
                                        project.lateInterestRate > 0
                                      if (isLate) {
                                        return (
                                          <div className="flex items-center gap-1">
                                            <p className="text-[9px] text-muted-foreground">
                                              {formatPercentage(
                                                project.roi,
                                                locale,
                                              )}
                                            </p>
                                            <p className="text-base font-semibold text-green-600">
                                              {formatPercentage(
                                                project.lateInterestRate!,
                                                locale,
                                              )}
                                            </p>
                                          </div>
                                        )
                                      }
                                      return (
                                        <p className="text-base font-semibold text-green-600">
                                          {formatPercentage(
                                            project.roi,
                                            locale,
                                          )}
                                        </p>
                                      )
                                    })()}
                                  </div>
                                </div>
                              </CardContent>
                            </Card>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </AnimatedContainer>
              ) : null}

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <AnimatedContainer
                  skipAnimation={skipAnimations}
                  delay={0.4}
                  className="lg:col-span-7"
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
                                            {formatPercentage(
                                              item.change,
                                              locale,
                                            )}
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
                                            {formatPercentage(
                                              item.change,
                                              locale,
                                            )}
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
                                            {formatPercentage(
                                              item.change,
                                              locale,
                                            )}
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
                                            {formatPercentage(
                                              item.change,
                                              locale,
                                            )}
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
                                              handleMouseEnter(
                                                `fund-${item.id}`,
                                              )
                                            }
                                            onMouseLeave={() =>
                                              setHoveredItem(null)
                                            }
                                            onClick={() =>
                                              handlePopoverClick(
                                                `fund-${item.id}`,
                                              )
                                            }
                                          ></div>
                                        </PopoverTrigger>
                                        <PopoverContent
                                          className="w-80"
                                          side="left"
                                          onMouseEnter={() =>
                                            handleMouseEnter(`fund-${item.id}`)
                                          }
                                          onMouseLeave={() =>
                                            setHoveredItem(null)
                                          }
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
                                                    : (item.change > 0
                                                        ? "+"
                                                        : "") +
                                                      formatPercentage(
                                                        item.change,
                                                        locale,
                                                      )}
                                                </div>
                                              </div>
                                              <div className="col-span-2">
                                                <span className="text-muted-foreground">
                                                  {t.dashboard.investedAmount}:
                                                </span>
                                                <div className="font-semibold">
                                                  {(item as any)
                                                    .formattedInitialInvestment ||
                                                    (item as any)
                                                      .formattedOriginalValue ||
                                                    item.formattedValue}
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
                                  ) && (
                                    <div className="h-1 w-full my-0.5"></div>
                                  )}
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
                                              handleMouseEnter(
                                                `stock-${item.id}`,
                                              )
                                            }
                                            onMouseLeave={() =>
                                              setHoveredItem(null)
                                            }
                                            onClick={() =>
                                              handlePopoverClick(
                                                `stock-${item.id}`,
                                              )
                                            }
                                          ></div>
                                        </PopoverTrigger>
                                        <PopoverContent
                                          className="w-80"
                                          side="left"
                                          onMouseEnter={() =>
                                            handleMouseEnter(`stock-${item.id}`)
                                          }
                                          onMouseLeave={() =>
                                            setHoveredItem(null)
                                          }
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
                                                  item.symbol
                                                    ? ""
                                                    : "col-span-2"
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
                                                    : (item.change > 0
                                                        ? "+"
                                                        : "") +
                                                      formatPercentage(
                                                        item.change,
                                                        locale,
                                                      )}
                                                </div>
                                              </div>
                                              <div className="col-span-2">
                                                <span className="text-muted-foreground">
                                                  {t.dashboard.investedAmount}:
                                                </span>
                                                <div className="font-semibold">
                                                  {(item as any)
                                                    .formattedInitialInvestment ||
                                                    (item as any)
                                                      .formattedOriginalValue ||
                                                    item.formattedValue}
                                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        </PopoverContent>
                                      </Popover>
                                    ),
                                )}
                                {(fundItems.length > 0 ||
                                  stockItems.length > 0) &&
                                  cryptoItems.length > 0 &&
                                  cryptoItems.some(
                                    ci => ci.percentageOfTotalVariableRent > 0,
                                  ) && (
                                    <div className="h-1 w-full my-0.5"></div>
                                  )}
                                {cryptoItems.map(
                                  (item, index) =>
                                    item.percentageOfTotalPortfolio > 0 && (
                                      <Popover
                                        key={`bar-crypto-${item.id}`}
                                        open={isPopoverOpen(
                                          `crypto-${item.id}`,
                                        )}
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
                                              handleMouseEnter(
                                                `crypto-${item.id}`,
                                              )
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
                                            handleMouseEnter(
                                              `crypto-${item.id}`,
                                            )
                                          }
                                          onMouseLeave={() =>
                                            setHoveredItem(null)
                                          }
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
                                                  {(item as any)
                                                    .formattedInitialInvestment ||
                                                    item.formattedValue}
                                                </div>
                                              </div>
                                              {item.percentageOfTotalVariableRent <
                                                100 && (
                                                <div>
                                                  <span className="text-muted-foreground">
                                                    {t.dashboard.stakeInCryptos}
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
                                                        (
                                                          entity,
                                                          entityIndex,
                                                        ) => (
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
                                                    {item.change >= 0
                                                      ? "+"
                                                      : ""}
                                                    {formatPercentage(
                                                      item.change,
                                                      locale,
                                                    )}
                                                  </div>
                                                </div>
                                              )}
                                              <div className="col-span-2">
                                                <span className="text-muted-foreground">
                                                  {t.dashboard.investedAmount}:
                                                </span>
                                                <div className="font-semibold">
                                                  {item.formattedValue}
                                                </div>
                                              </div>
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
                                  ) && (
                                    <div className="h-1 w-full my-0.5"></div>
                                  )}
                                {commodityItems.map(
                                  (item, index) =>
                                    item.percentageOfTotalPortfolio > 0 && (
                                      <Popover
                                        key={`bar-commodity-${item.id}`}
                                        open={isPopoverOpen(
                                          `commodity-${item.id}`,
                                        )}
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
                                                    {(item as any)
                                                      .formattedInitialInvestment ||
                                                      item.formattedValue}
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
                                                <div className="col-span-2">
                                                  <span className="text-muted-foreground">
                                                    {t.dashboard.investedAmount}
                                                    :
                                                  </span>
                                                  <div className="font-semibold">
                                                    {item.formattedValue}
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
                                                          (
                                                            entity,
                                                            entityIndex,
                                                          ) => (
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
                </AnimatedContainer>

                <AnimatedContainer
                  skipAnimation={skipAnimations}
                  delay={0.5}
                  className="lg:col-span-5"
                >
                  <Card className="h-full flex flex-col">
                    <CardHeader>
                      <div className="flex justify-between items-center">
                        <CardTitle className="text-lg font-bold flex items-center">
                          <ArrowLeftRight className="h-5 w-5 mr-2 text-primary" />
                          {t.dashboard.recentTransactions}
                        </CardTitle>
                        {!forecastMode && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate("/transactions")}
                            className="flex items-center gap-1"
                          >
                            {t.dashboard.viewAll}
                            <ArrowRight className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="flex-grow overflow-y-auto scrollbar-thin min-h-[350px] max-h-[650px]">
                      {forecastMode ? (
                        <div className="flex-grow flex flex-col items-center justify-center h-full text-center">
                          <TrendingUpDown className="h-12 w-12 text-gray-400 dark:text-gray-500 mb-4" />
                          <p className="text-sm text-muted-foreground mb-1">
                            {t.forecast.notShowing}
                          </p>
                        </div>
                      ) : Object.keys(recentTransactions).length > 0 ? (
                        <ul className="space-y-0">
                          {Object.entries(recentTransactions).map(
                            ([date, txsOnDate]) => (
                              <li key={date} className="py-2">
                                <h4 className="text-sm font-semibold text-muted-foreground mb-2 sticky top-0 bg-card z-5 py-1 px-4 -mx-4 border-b border-t">
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
                                                    ? (
                                                        t.enums
                                                          .productType as any
                                                      )[tx.product_type]
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
                                                : tx.type === TxType.FEE
                                                  ? "text-red-600 dark:text-red-400"
                                                  : undefined
                                            }`}
                                          >
                                            {tx.displayType === "in"
                                              ? "+"
                                              : tx.type === TxType.FEE
                                                ? "-"
                                                : ""}
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
                </AnimatedContainer>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
