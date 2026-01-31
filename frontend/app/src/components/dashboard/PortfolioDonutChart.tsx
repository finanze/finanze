import { useState, useMemo, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useI18n } from "@/i18n"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import { cn, getCurrencySymbol } from "@/lib/utils"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Button } from "@/components/ui/Button"
import {
  getPieSliceColorForAssetType,
  getIconForAssetType,
} from "@/utils/dashboardUtils"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"
import {
  Info,
  ChevronUp,
  SlidersHorizontal,
  HandCoins,
  CreditCard,
  Home,
} from "lucide-react"
import { Switch } from "@/components/ui/Switch"
import { getImageUrl } from "@/services/api"
import { EntityOrigin } from "@/types"

const formatCompactCurrency = (
  value: number,
  locale: string,
  currency: string,
): string => {
  const absValue = Math.abs(value)
  let suffix = ""
  let displayValue = absValue

  if (absValue >= 1_000_000) {
    displayValue = absValue / 1_000_000
    suffix = "M"
  } else if (absValue >= 1_000) {
    displayValue = absValue / 1_000
    suffix = "k"
  }

  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: suffix ? 1 : 0,
    maximumFractionDigits: suffix ? 1 : 0,
  }).format(displayValue)

  const symbol = getCurrencySymbol(currency)
  const sign = value < 0 ? "-" : ""
  return `${sign}${formatted}${suffix} ${symbol}`
}

type DistributionItem = {
  type: string
  value: number
  percentage: number
}

type EntityDistributionItem = {
  id: string
  name: string
  value: number
  percentage: number
}

type EntityInfo = {
  id: string
  name: string
  origin: EntityOrigin
  icon_url?: string | null
}

type DashboardOptions = {
  includePending: boolean
  includeCardExpenses: boolean
  includeRealEstate: boolean
  includeResidences: boolean
}

interface PortfolioDonutChartProps {
  totalValue: number
  investedAmount: number
  gainPercentage: number
  currency: string
  assetDistribution: DistributionItem[]
  entityDistribution: EntityDistributionItem[]
  entityColorMap: Map<string, string>
  entities: EntityInfo[]
  distributionView: "by-asset" | "by-entity"
  setDistributionView: (view: "by-asset" | "by-entity") => void
  forecastMode?: boolean
  dashboardOptions: DashboardOptions
  setDashboardOptions: React.Dispatch<React.SetStateAction<DashboardOptions>>
}

const VISIBLE_ITEMS = 6

export function PortfolioDonutChart({
  totalValue,
  investedAmount,
  gainPercentage,
  currency,
  assetDistribution,
  entityDistribution,
  entityColorMap,
  entities,
  distributionView,
  setDistributionView,
  forecastMode = false,
  dashboardOptions,
  setDashboardOptions,
}: PortfolioDonutChartProps) {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const [legendExpanded, setLegendExpanded] = useState(false)
  const [entityImages, setEntityImages] = useState<Record<string, string>>({})
  const [isDarkMode, setIsDarkMode] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches,
  )

  const specialEntityIds = new Set([
    "pending-flows",
    "real-estate",
    "forecast-cash-delta",
    "commodity",
  ])

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    const handleChange = (e: MediaQueryListEvent) => setIsDarkMode(e.matches)
    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [])

  useEffect(() => {
    const loadImages = async () => {
      const images: Record<string, string> = {}
      for (const entity of entities) {
        try {
          if (entity.icon_url) {
            images[entity.id] = entity.icon_url
          } else if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            images[entity.id] = await getImageUrl(
              `/static/entities/logos/${entity.id}.png`,
            )
          } else if (entity.origin === EntityOrigin.NATIVE) {
            images[entity.id] = `entities/${entity.id}.png`
          } else {
            images[entity.id] = ""
          }
        } catch {
          images[entity.id] = ""
        }
      }
      setEntityImages(images)
    }
    loadImages()
  }, [entities])

  const currentDistribution =
    distributionView === "by-asset" ? assetDistribution : entityDistribution

  const visibleItems = useMemo(() => {
    if (legendExpanded || currentDistribution.length <= VISIBLE_ITEMS) {
      return currentDistribution
    }
    return currentDistribution.slice(0, VISIBLE_ITEMS - 1)
  }, [currentDistribution, legendExpanded])

  const overflowItems = useMemo(() => {
    if (legendExpanded || currentDistribution.length <= VISIBLE_ITEMS) {
      return []
    }
    return currentDistribution.slice(VISIBLE_ITEMS - 1)
  }, [currentDistribution, legendExpanded])

  const overflowTotal = useMemo(() => {
    return overflowItems.reduce((sum, item) => sum + item.value, 0)
  }, [overflowItems])

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

  const handleLegendItemClick = (
    item: DistributionItem | EntityDistributionItem,
  ) => {
    if (distributionView === "by-asset") {
      const route = getInvestmentRoute((item as DistributionItem).type)
      if (route) navigate(route)
    }
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      const isEntity = "name" in data && "id" in data
      return (
        <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
          <div className="flex items-center gap-2 mb-2">
            {isEntity ? (
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entityColorMap.get(data.id) }}
              />
            ) : (
              getIconForAssetType(data.type)
            )}
            <p className="font-medium text-sm text-popover-foreground">
              {isEntity
                ? data.name
                : ((t.enums?.productType as any)?.[data.type] ?? data.type)}
            </p>
          </div>
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>
              <span className="font-medium text-popover-foreground">
                {formatCurrency(data.value, locale, currency)}
              </span>
            </p>
            <p>{data.percentage}%</p>
          </div>
        </div>
      )
    }
    return null
  }

  const getEntityIcon = (
    entityId: string,
  ):
    | { type: "asset"; assetType: string }
    | { type: "image"; url: string }
    | { type: "dot" } => {
    if (specialEntityIds.has(entityId)) {
      const typeMap: Record<string, string> = {
        "pending-flows": "PENDING_FLOWS",
        "real-estate": "REAL_ESTATE",
        "forecast-cash-delta": "CASH",
        commodity: "COMMODITY",
      }
      return { type: "asset", assetType: typeMap[entityId] || "CASH" }
    }
    const image = entityImages[entityId]
    if (image && image.length > 0) {
      return { type: "image", url: image }
    }
    return { type: "dot" }
  }

  const renderLegendItem = (
    item: DistributionItem | EntityDistributionItem,
    index: number,
  ) => {
    const isEntity = "name" in item && "id" in item
    const assetType = isEntity ? null : (item as DistributionItem).type
    const hasRoute = assetType ? getInvestmentRoute(assetType) !== null : false
    const color = isEntity
      ? entityColorMap.get((item as EntityDistributionItem).id)
      : getPieSliceColorForAssetType((item as DistributionItem).type)
    const label = isEntity
      ? (item as EntityDistributionItem).name
      : ((t.enums?.productType as any)?.[assetType!] ?? assetType)

    const entityId = isEntity ? (item as EntityDistributionItem).id : null
    const entityIcon = entityId ? getEntityIcon(entityId) : null

    const isLongLabel = label && label.length > 8
    const iconSize = isLongLabel ? "w-3.5 h-3.5" : "w-4 h-4"
    const iconClass = isLongLabel ? "h-3.5 w-3.5" : "h-4 w-4"

    const renderEntityIcon = () => {
      if (!entityIcon) return null
      if (entityIcon.type === "asset") {
        return (
          <span className={`flex-shrink-0 ${iconSize}`}>
            {getIconForAssetType(
              entityIcon.assetType,
              iconClass,
              color ?? null,
            )}
          </span>
        )
      }
      if (entityIcon.type === "image") {
        return (
          <div
            className={`${isLongLabel ? "w-4 h-4" : "w-5 h-5"} flex-shrink-0 overflow-hidden rounded`}
          >
            <img
              src={entityIcon.url}
              alt={label}
              className="w-full h-full object-contain"
              onError={e => (e.currentTarget.style.display = "none")}
            />
          </div>
        )
      }
      return (
        <div
          className={`${iconSize} rounded-full flex-shrink-0`}
          style={{ backgroundColor: color }}
        />
      )
    }

    return (
      <button
        key={`legend-${index}`}
        onClick={() => handleLegendItemClick(item)}
        disabled={!hasRoute && !isEntity}
        className={cn(
          "relative flex flex-col items-center justify-center p-2 rounded-lg bg-muted/50 min-w-0 transition-colors overflow-hidden",
          (hasRoute || isEntity) && "hover:bg-muted cursor-pointer",
        )}
      >
        {isEntity && (
          <div
            className="absolute bottom-0 left-1/2 -translate-x-1/2 h-0.5 w-1/2 rounded-t-sm"
            style={{ backgroundColor: color }}
          />
        )}
        <div className="flex items-center gap-1.5 mb-1">
          {isEntity ? (
            renderEntityIcon()
          ) : (
            <span className={`flex-shrink-0 ${iconSize}`}>
              {getIconForAssetType(assetType!, iconClass)}
            </span>
          )}
          <span
            className={cn(
              "font-medium max-w-[90px] whitespace-normal break-words leading-tight",
              isLongLabel ? "text-[10px]" : "text-xs",
            )}
          >
            {label}
          </span>
        </div>
        <span className="text-xs font-semibold">
          {formatCompactCurrency(item.value, locale, currency)}
        </span>
      </button>
    )
  }

  const renderOverflowBox = () => {
    if (overflowItems.length === 0) return null

    const displayIcons = overflowItems.slice(0, 3)

    const renderOverflowIcon = (
      item: DistributionItem | EntityDistributionItem,
      idx: number,
    ) => {
      const isEntity = "name" in item && "id" in item
      const entityId = isEntity ? (item as EntityDistributionItem).id : null
      const color = isEntity
        ? entityColorMap.get((item as EntityDistributionItem).id)
        : getPieSliceColorForAssetType((item as DistributionItem).type)
      const marginStyle = {
        marginLeft: idx > 0 ? "-2.5px" : 0,
        zIndex: 4 - idx,
        ...(isDarkMode && { filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.4))" }),
      }

      if (isEntity && entityId) {
        const entityIcon = getEntityIcon(entityId)
        if (entityIcon.type === "asset") {
          return (
            <span
              key={idx}
              className="relative flex-shrink-0 w-5 h-5 flex items-center justify-center"
              style={marginStyle}
            >
              {getIconForAssetType(
                entityIcon.assetType,
                "h-4 w-4",
                color ?? null,
              )}
            </span>
          )
        }
        if (entityIcon.type === "image") {
          return (
            <div
              key={idx}
              className="relative w-5 h-5 flex-shrink-0 overflow-hidden rounded"
              style={marginStyle}
            >
              <img
                src={entityIcon.url}
                alt=""
                className="w-full h-full object-contain"
                onError={e => (e.currentTarget.style.display = "none")}
              />
            </div>
          )
        }
        return (
          <div
            key={idx}
            className="relative w-4 h-4 rounded-full flex-shrink-0"
            style={{ backgroundColor: color, ...marginStyle }}
          />
        )
      }
      return (
        <span
          key={idx}
          className="relative flex-shrink-0 w-5 h-5 flex items-center justify-center"
          style={marginStyle}
        >
          {getIconForAssetType((item as DistributionItem).type, "h-4 w-4")}
        </span>
      )
    }

    return (
      <button
        onClick={() => setLegendExpanded(true)}
        className="flex flex-col items-center justify-center p-2 rounded-lg bg-muted/50 min-w-0 hover:bg-muted cursor-pointer transition-colors"
      >
        <div className="flex items-center mb-1">
          {displayIcons.map((item, idx) => renderOverflowIcon(item, idx))}
          {overflowItems.length > 3 && (
            <span
              className="relative text-[10px] text-muted-foreground bg-muted rounded-full w-5 h-5 flex items-center justify-center"
              style={{
                marginLeft: "-1px",
                zIndex: 0,
                ...(isDarkMode && {
                  filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.4))",
                }),
              }}
            >
              +{overflowItems.length - 3}
            </span>
          )}
        </div>
        <span className="text-xs font-semibold">
          {formatCompactCurrency(overflowTotal, locale, currency)}
        </span>
      </button>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div
          className="inline-flex items-center rounded-full border border-border bg-muted/30 p-0.5"
          role="tablist"
        >
          <button
            type="button"
            role="tab"
            aria-selected={distributionView === "by-asset"}
            onClick={() => setDistributionView("by-asset")}
            className={cn(
              "h-7 rounded-full px-2.5 text-xs font-medium transition-colors",
              distributionView === "by-asset"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.dashboard.assetDistributionByType}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={distributionView === "by-entity"}
            onClick={() => setDistributionView("by-entity")}
            className={cn(
              "h-7 rounded-full px-2.5 text-xs font-medium transition-colors",
              distributionView === "by-entity"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.dashboard.assetDistributionByEntity}
          </button>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
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
      </div>

      <div className="flex flex-col xl:flex-row xl:items-start items-center">
        <div className="relative w-full max-w-[280px] xl:max-w-[240px] 2xl:max-w-[280px] aspect-square flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={currentDistribution}
                cx="50%"
                cy="50%"
                innerRadius="68%"
                outerRadius="95%"
                fill="#8884d8"
                dataKey="value"
                nameKey={distributionView === "by-asset" ? "type" : "name"}
                isAnimationActive={false}
                stroke="hsl(var(--background))"
                strokeWidth={1}
                paddingAngle={1}
              >
                {currentDistribution.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      distributionView === "by-asset"
                        ? getPieSliceColorForAssetType(
                            (entry as DistributionItem).type,
                          )
                        : entityColorMap.get(
                            (entry as EntityDistributionItem).id,
                          )
                    }
                    style={{ outline: "none" }}
                  />
                ))}
              </Pie>
              <Tooltip
                content={<CustomTooltip />}
                wrapperStyle={{ zIndex: 50 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
            <span className="text-xs text-muted-foreground mb-0.5">
              {t.dashboard.totalValue}
            </span>
            <span className="text-2xl font-bold">
              {formatCompactCurrency(totalValue, locale, currency)}
            </span>
            {gainPercentage !== 0 && (
              <div className="flex items-center gap-1">
                <span
                  className={cn(
                    "text-sm font-medium",
                    gainPercentage > 0
                      ? "text-green-500"
                      : gainPercentage < 0
                        ? "text-red-500"
                        : "text-muted-foreground",
                  )}
                >
                  {gainPercentage > 0 ? "+" : ""}
                  {formatPercentage(gainPercentage, locale)}
                </span>
                {investedAmount > 0 && (
                  <Popover>
                    <PopoverTrigger asChild>
                      <button className="text-muted-foreground hover:text-foreground transition-colors pointer-events-auto">
                        <Info className="h-3.5 w-3.5" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-3" align="center">
                      <div className="text-sm">
                        <span className="text-muted-foreground">
                          {t.dashboard.investedAmount}:{" "}
                        </span>
                        <span className="font-semibold">
                          {formatCurrency(investedAmount, locale, currency)}
                        </span>
                      </div>
                    </PopoverContent>
                  </Popover>
                )}
              </div>
            )}
            {gainPercentage === 0 && investedAmount > 0 && (
              <Popover>
                <PopoverTrigger asChild>
                  <button className="text-muted-foreground hover:text-foreground transition-colors pointer-events-auto">
                    <Info className="h-3.5 w-3.5" />
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-3" align="center">
                  <div className="text-sm">
                    <span className="text-muted-foreground">
                      {t.dashboard.investedAmount}:{" "}
                    </span>
                    <span className="font-semibold">
                      {formatCurrency(investedAmount, locale, currency)}
                    </span>
                  </div>
                </PopoverContent>
              </Popover>
            )}
          </div>
        </div>

        <div className="w-full mt-4 xl:mt-0 xl:w-auto xl:flex-1 xl:pl-6 xl:max-w-[520px] xl:self-center xl:ml-auto">
          <div className="grid grid-cols-3 min-[500px]:grid-cols-4 xl:grid-cols-2 2xl:grid-cols-3 gap-2 xl:justify-end">
            {visibleItems.map((item, index) => renderLegendItem(item, index))}
            {!legendExpanded && renderOverflowBox()}
          </div>
          {legendExpanded && currentDistribution.length > VISIBLE_ITEMS && (
            <button
              onClick={() => setLegendExpanded(false)}
              className="flex items-center justify-center gap-1 w-full mt-2 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronUp className="h-3.5 w-3.5" />
              {t.common.showLess}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
