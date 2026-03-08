import React, { useEffect, useMemo, useRef, useState } from "react"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Sector,
} from "recharts"
import { Card } from "@/components/ui/Card"
import {
  formatCurrency,
  formatCompactCurrency,
  formatPercentage,
} from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"
import { PieChart as PieChartIcon, Info } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"

interface ChartDataItem {
  name: string
  value: number
  color: string
  percentage: number
  currency?: string
  convertedValue?: number
  convertedCurrency?: string
  id?: string
}

interface DonutBadge {
  icon: React.ReactNode
  value: string
}

interface DonutCenterConfig {
  count?: number
  countLabel?: string
  countLabelSingular?: string
  rawValue: number
  gainPercentage?: number
  badgeText?: string
  infoRows?: {
    label: string
    value: string
    valueClassName?: string
  }[]
}

interface DonutToggleConfig {
  activeView: string
  onViewChange: (view: string) => void
  options: { value: string; label: string }[]
}

interface InvestmentDistributionChartProps {
  data: ChartDataItem[]
  title: string
  locale?: string
  currency?: string
  showOriginalCurrency?: boolean
  hideLegend?: boolean
  containerClassName?: string
  titleIcon?: React.ReactNode
  onSliceClick?: (item: ChartDataItem) => void
  variant?: "default" | "bare"
  innerData?: {
    name: string
    value: number
    color: string
    percentage: number
    isGap?: boolean
  }[]
  onInnerSliceClick?: (item: any) => void
  maxOuterRadius?: number
  centerContent?: DonutCenterConfig
  toggleConfig?: DonutToggleConfig
  badges?: DonutBadge[]
}

const RADIAN = Math.PI / 180
const renderCustomizedLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: any) => {
  if (percent < 0.03) return null
  const percentage = percent * 100
  const isLargeSegment = percentage >= 15
  const radius = isLargeSegment
    ? innerRadius + (outerRadius - innerRadius) * 0.35
    : innerRadius + (outerRadius - innerRadius) * 1.25
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text
      x={x}
      y={y}
      fill={isLargeSegment ? "white" : "currentColor"}
      textAnchor={x > cx ? "start" : "end"}
      dominantBaseline="central"
      className={`text-xs font-medium ${isLargeSegment ? "" : "text-gray-700 dark:text-gray-300"}`}
    >
      {`${percentage.toFixed(0)}%`}
    </text>
  )
}

const CustomTooltip = ({
  active,
  payload,
  locale,
  currency,
  showOriginalCurrency = false,
}: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    return (
      <div className="bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs">
        <p className="font-medium">{data.name}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {data.percentage.toFixed(2)}% •{" "}
          {showOriginalCurrency && data.currency && data.currency !== currency
            ? `${formatCurrency(data.value, locale, data.currency)} (${formatCurrency(data.convertedValue || data.value, locale, currency)})`
            : formatCurrency(data.value, locale, data.currency || currency)}
        </p>
      </div>
    )
  }
  return null
}

function InfoPopover({
  rows,
}: {
  rows: { label: string; value: string; valueClassName?: string }[]
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="text-muted-foreground hover:text-foreground transition-colors pointer-events-auto">
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-3" align="center">
        <div className="space-y-1 text-sm">
          {rows.map((row, i) => (
            <div key={i}>
              <span className="text-muted-foreground">{row.label}: </span>
              <span className={cn("font-semibold", row.valueClassName)}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export const InvestmentDistributionChart: React.FC<
  InvestmentDistributionChartProps
> = ({
  data,
  title,
  locale = "en",
  currency = "USD",
  showOriginalCurrency = false,
  hideLegend = false,
  containerClassName = "",
  titleIcon,
  onSliceClick,
  variant = "default",
  innerData,
  onInnerSliceClick,
  maxOuterRadius: maxOuterRadiusProp = 170,
  centerContent,
  toggleConfig,
  badges,
}) => {
  const { t } = useI18n()
  const [activeInnerIndex, setActiveInnerIndex] = useState<number>(-1)
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const chartAreaRef = useRef<HTMLDivElement | null>(null)
  const [size, setSize] = useState({ width: 0 })
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 })
  const hasData = Array.isArray(data) && data.length > 0

  const compactNumbers = useMemo(() => {
    if (typeof window === "undefined") return true
    try {
      const raw = localStorage.getItem("dashboardOptions")
      if (raw) {
        const parsed = JSON.parse(raw)
        return parsed.compactNumbers !== false
      }
    } catch {
      /* ignore */
    }
    return true
  }, [])

  const formattedCenterValue = centerContent
    ? compactNumbers
      ? formatCompactCurrency(centerContent.rawValue, locale, currency)
      : formatCurrency(centerContent.rawValue, locale, currency)
    : ""

  const maxOuterRadius = centerContent ? 200 : maxOuterRadiusProp

  useEffect(() => {
    if (variant !== "bare" || !hasData) return
    if (typeof ResizeObserver === "undefined") return
    const element = wrapperRef.current
    if (!element) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        if (entry.contentRect.width) {
          setSize({ width: entry.contentRect.width })
        }
      }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [variant, hasData])

  useEffect(() => {
    if (variant !== "bare" || !hasData) return
    if (typeof ResizeObserver === "undefined") return
    const element = chartAreaRef.current
    if (!element) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width || height) {
          setChartSize({ width, height })
        }
      }
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [variant, hasData])

  if (variant === "bare") {
    if (!hasData) {
      return (
        <div className={`flex flex-col justify-center ${containerClassName}`}>
          <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
            {t.common.noDataAvailable}
          </div>
        </div>
      )
    }
    const effectiveWidth = size.width || 600
    const effectiveHeight = chartSize.height || (centerContent ? 380 : 420)
    const limitingSide = Math.min(effectiveWidth, effectiveHeight)
    const computed = limitingSide / 2 - (centerContent ? 30 : 42)
    const outerRadius = Math.max(
      Math.min(computed, maxOuterRadius),
      centerContent ? 110 : 100,
    )
    const innerRadius = centerContent
      ? Math.round(outerRadius * 0.8)
      : Math.round(outerRadius * 0.62)
    return (
      <div
        ref={wrapperRef}
        className={`relative flex justify-center ${containerClassName}`}
      >
        <div className="w-full flex flex-col max-w-[640px] mx-auto">
          {toggleConfig ? (
            <div
              className="inline-flex items-center gap-3 px-4 pt-2"
              role="tablist"
            >
              <PieChartIcon size={18} className="text-primary" />
              {toggleConfig.options.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  role="tab"
                  aria-selected={toggleConfig.activeView === opt.value}
                  onClick={() => toggleConfig.onViewChange(opt.value)}
                  className={cn(
                    "text-base font-medium transition-colors",
                    toggleConfig.activeView === opt.value
                      ? "text-foreground font-extrabold"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          ) : !centerContent ? (
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-1 px-4 pt-2">
              {titleIcon || <PieChartIcon size={18} className="text-primary" />}{" "}
              {title}
            </h3>
          ) : null}
          <div
            ref={chartAreaRef}
            className={cn(
              "flex-1 flex items-center justify-center p-0 overflow-visible relative",
              centerContent
                ? "min-h-[320px] h-[380px]"
                : "min-h-[360px] h-[420px]",
            )}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart style={{ userSelect: "none" }}>
                {innerData &&
                  innerData.length > 0 &&
                  (() => {
                    const ringOuter = centerContent
                      ? innerRadius - 6
                      : innerRadius - 15
                    const ringThickness = centerContent ? 4 : 5
                    const ringInner = ringOuter - ringThickness
                    const activeOuter = ringOuter + 3
                    const activeInner = ringInner - 2
                    const activeShape = (props: any) => (
                      <Sector
                        {...props}
                        innerRadius={activeInner}
                        outerRadius={activeOuter}
                      />
                    )
                    return (
                      <Pie
                        data={innerData}
                        cx="50%"
                        cy="50%"
                        isAnimationActive={false}
                        dataKey="value"
                        outerRadius={ringOuter}
                        innerRadius={ringInner}
                        stroke="hsl(var(--background))"
                        strokeWidth={centerContent ? 1 : 2}
                        paddingAngle={5}
                        activeIndex={activeInnerIndex}
                        activeShape={activeShape}
                      >
                        {innerData.map((entry, index) => (
                          <Cell
                            key={`inner-cell-${index}`}
                            fill={entry.isGap ? "transparent" : entry.color}
                            stroke={entry.isGap ? "none" : undefined}
                            style={{
                              outline: "none",
                              cursor: entry.isGap
                                ? "default"
                                : onInnerSliceClick
                                  ? "pointer"
                                  : "default",
                              pointerEvents: entry.isGap ? "none" : "auto",
                            }}
                            onClick={() =>
                              !entry.isGap && onInnerSliceClick?.(entry)
                            }
                            onMouseEnter={() =>
                              !entry.isGap && setActiveInnerIndex(index)
                            }
                            onMouseLeave={() => setActiveInnerIndex(-1)}
                          />
                        ))}
                      </Pie>
                    )
                  })()}
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  isAnimationActive={false}
                  labelLine={false}
                  label={centerContent ? false : renderCustomizedLabel}
                  outerRadius={outerRadius}
                  innerRadius={innerRadius}
                  fill="#8884d8"
                  dataKey="value"
                  stroke="hsl(var(--background))"
                  strokeWidth={centerContent ? 1 : 2}
                  paddingAngle={centerContent ? 1 : undefined}
                >
                  {data.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.color}
                      style={{
                        outline: "none",
                        cursor: onSliceClick ? "pointer" : "default",
                      }}
                      onClick={() => onSliceClick?.(entry)}
                    />
                  ))}
                </Pie>
                <Tooltip
                  content={
                    <CustomTooltip
                      locale={locale}
                      currency={currency}
                      showOriginalCurrency={showOriginalCurrency}
                    />
                  }
                  wrapperStyle={{ zIndex: 50 }}
                />
              </PieChart>
            </ResponsiveContainer>
            {centerContent && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
                {centerContent.count != null && centerContent.countLabel && (
                  <span className="text-xs text-muted-foreground mb-0.5">
                    <span className="font-bold text-foreground">
                      {centerContent.count}
                    </span>{" "}
                    {centerContent.count === 1
                      ? centerContent.countLabelSingular
                      : centerContent.countLabel}
                  </span>
                )}
                <span
                  className={cn(
                    "font-light",
                    compactNumbers ? "text-3xl" : "text-[1.7rem]",
                  )}
                >
                  {formattedCenterValue}
                </span>
                {centerContent.badgeText && (
                  <span className="text-sm font-semibold text-muted-foreground mt-0.5">
                    {centerContent.badgeText}
                  </span>
                )}
                {centerContent.gainPercentage != null &&
                  centerContent.gainPercentage !== 0 && (
                    <div className="flex items-center gap-1">
                      <span
                        className={cn(
                          "text-sm font-medium",
                          centerContent.gainPercentage > 0
                            ? "text-green-500"
                            : centerContent.gainPercentage < 0
                              ? "text-red-500"
                              : "text-muted-foreground",
                        )}
                      >
                        {centerContent.gainPercentage > 0 ? "+" : ""}
                        {formatPercentage(centerContent.gainPercentage, locale)}
                      </span>
                      {centerContent.infoRows &&
                        centerContent.infoRows.length > 0 && (
                          <InfoPopover rows={centerContent.infoRows} />
                        )}
                    </div>
                  )}
                {(centerContent.gainPercentage == null ||
                  centerContent.gainPercentage === 0) &&
                  centerContent.infoRows &&
                  centerContent.infoRows.length > 0 && (
                    <InfoPopover rows={centerContent.infoRows} />
                  )}
              </div>
            )}
            {badges && badges.length > 0 && (
              <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-2 pointer-events-none z-10">
                {badges.map((badge, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 rounded-full bg-muted/80 backdrop-blur-sm border border-border/50 px-2.5 py-1 text-xs font-medium text-muted-foreground shadow-sm"
                  >
                    {badge.icon}
                    {badge.value}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card className={`p-6 ${containerClassName}`}>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          {titleIcon || <PieChartIcon size={18} className="text-primary" />}{" "}
          {title}
        </h3>
        <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
          {t.common.noDataAvailable}
        </div>
      </Card>
    )
  }

  return (
    <Card className={`p-6 ${containerClassName}`}>
      <div className="mb-4 flex items-center gap-2">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          {titleIcon || <PieChartIcon size={18} className="text-primary" />}{" "}
          {title}
        </h3>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart style={{ userSelect: "none" }}>
            {innerData &&
              innerData.length > 0 &&
              (() => {
                const mainOuterInnerRadius = innerData.length > 0 ? 75 : 70
                const ringOuter = mainOuterInnerRadius - 18
                const ringThickness = 5
                const ringInner = ringOuter - ringThickness
                const activeOuter = ringOuter + 3
                const activeInner = ringInner - 2
                const activeShape = (props: any) => (
                  <Sector
                    {...props}
                    innerRadius={activeInner}
                    outerRadius={activeOuter}
                  />
                )
                return (
                  <Pie
                    data={innerData}
                    cx="50%"
                    cy="50%"
                    isAnimationActive={false}
                    dataKey="value"
                    outerRadius={ringOuter}
                    innerRadius={ringInner}
                    stroke="hsl(var(--background))"
                    strokeWidth={2}
                    activeIndex={activeInnerIndex}
                    activeShape={activeShape}
                  >
                    {innerData.map((entry, index) => (
                      <Cell
                        key={`inner-cell-${index}`}
                        fill={entry.isGap ? "transparent" : entry.color}
                        stroke={entry.isGap ? "none" : undefined}
                        style={{
                          outline: "none",
                          cursor: entry.isGap
                            ? "default"
                            : onInnerSliceClick
                              ? "pointer"
                              : "default",
                          pointerEvents: entry.isGap ? "none" : "auto",
                        }}
                        onClick={() =>
                          !entry.isGap && onInnerSliceClick?.(entry)
                        }
                        onMouseEnter={() =>
                          !entry.isGap && setActiveInnerIndex(index)
                        }
                        onMouseLeave={() => setActiveInnerIndex(-1)}
                      />
                    ))}
                  </Pie>
                )
              })()}
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              isAnimationActive={false}
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius={110}
              innerRadius={innerData && innerData.length > 0 ? 75 : 70}
              fill="#8884d8"
              dataKey="value"
              stroke="hsl(var(--background))"
              strokeWidth={2}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  style={{
                    outline: "none",
                    cursor: onSliceClick ? "pointer" : "default",
                  }}
                  onClick={() => onSliceClick?.(entry)}
                />
              ))}
            </Pie>
            <Tooltip
              content={
                <CustomTooltip
                  locale={locale}
                  currency={currency}
                  showOriginalCurrency={showOriginalCurrency}
                />
              }
              wrapperStyle={{ zIndex: 50 }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {!hideLegend && (
        <div className="mt-4 space-y-2">
          {data.map((item, index) => (
            <div
              key={index}
              className="flex items-center justify-between text-sm"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span
                  className="text-gray-700 dark:text-gray-300 truncate"
                  title={item.name}
                >
                  {item.name}
                </span>
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <div className="font-medium text-gray-900 dark:text-gray-100">
                  {showOriginalCurrency &&
                  item.currency &&
                  item.currency !== currency
                    ? formatCurrency(item.value, locale, item.currency)
                    : formatCurrency(item.value, locale, currency)}
                </div>
                {showOriginalCurrency &&
                  item.currency &&
                  item.currency !== currency &&
                  item.convertedValue && (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {formatCurrency(item.convertedValue, locale, currency)}
                    </div>
                  )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

interface LegendProps {
  data: ChartDataItem[]
  locale?: string
  currency?: string
  showOriginalCurrency?: boolean
}

export const InvestmentDistributionLegend: React.FC<LegendProps> = ({
  data,
  locale = "en",
  currency = "USD",
  showOriginalCurrency = false,
}) => {
  const { t } = useI18n()
  if (!data || data.length === 0) {
    return (
      <Card className="p-6 h-full flex items-center justify-center text-gray-500 dark:text-gray-400">
        {t.common.noDataAvailable}
      </Card>
    )
  }
  return (
    <Card className="p-6">
      <div className="space-y-2">
        {data.map((item, index) => (
          <div
            key={index}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <span
                className="text-gray-700 dark:text-gray-300 truncate"
                title={item.name}
              >
                {item.name}
              </span>
            </div>
            <div className="text-right flex-shrink-0 ml-2">
              <div className="font-medium text-gray-900 dark:text-gray-100">
                {showOriginalCurrency &&
                item.currency &&
                item.currency !== currency
                  ? formatCurrency(item.value, locale, item.currency)
                  : formatCurrency(item.value, locale, currency)}
              </div>
              {showOriginalCurrency &&
                item.currency &&
                item.currency !== currency &&
                item.convertedValue && (
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {formatCurrency(item.convertedValue, locale, currency)}
                  </div>
                )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
