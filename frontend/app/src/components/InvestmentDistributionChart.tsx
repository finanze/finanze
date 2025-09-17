import React, { useEffect, useRef, useState } from "react"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Sector,
} from "recharts"
import { Card } from "@/components/ui/Card"
import { formatCurrency } from "@/lib/formatters"
import { useI18n } from "@/i18n"
import { PieChart as PieChartIcon } from "lucide-react"

interface ChartDataItem {
  name: string
  value: number
  color: string
  percentage: number
  currency?: string
  convertedValue?: number
  convertedCurrency?: string
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
  // Optional inner donut (e.g., by asset type) - values should add up to total of outer data
  innerData?: {
    name: string
    value: number
    color: string
    percentage: number
    isGap?: boolean
  }[]
  onInnerSliceClick?: (item: any) => void
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
  if (percent < 0.03) return null // Don't show labels for slices smaller than 3%

  const percentage = percent * 100
  const isLargeSegment = percentage >= 15
  const radius = isLargeSegment
    ? innerRadius + (outerRadius - innerRadius) * 0.35 // More inner
    : innerRadius + (outerRadius - innerRadius) * 1.25 // Outside

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
}) => {
  const { t } = useI18n()
  const [activeInnerIndex, setActiveInnerIndex] = useState<number>(-1)
  // Bare variant (no card) dynamic sizing branch
  if (variant === "bare") {
    if (!data || data.length === 0) {
      return (
        <div className={`flex flex-col justify-center ${containerClassName}`}>
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 px-2">
            {titleIcon || <PieChartIcon size={18} className="text-primary" />}{" "}
            {title}
          </h3>
          <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
            {t.common.noDataAvailable}
          </div>
        </div>
      )
    }
    const wrapperRef = useRef<HTMLDivElement | null>(null)
    const [size, setSize] = useState({ width: 0, height: 0 })
    useEffect(() => {
      if (!wrapperRef.current) return
      const obs = new ResizeObserver(entries => {
        for (const entry of entries) {
          const { width, height } = entry.contentRect
          if (width || height) setSize({ width, height })
        }
      })
      obs.observe(wrapperRef.current)
      return () => obs.disconnect()
    }, [])
    const chartSide = Math.min(size.width, size.height || 480)
    // Subtract extra space so the donut never gets visually clipped (top/bottom) and leave room for stroke + labels
    // Leave a bit more vertical room for outside percentage labels
    const outerRadius = Math.max(Math.min(chartSide / 2 - 52, 250), 90)
    const innerRadius = Math.round(outerRadius * 0.62)
    return (
      <div
        className={`relative flex justify-center ${containerClassName}`}
        ref={wrapperRef}
      >
        <div className="w-full flex flex-col">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-1 px-4 pt-2">
            {titleIcon || <PieChartIcon size={18} className="text-primary" />}{" "}
            {title}
          </h3>
          <div className="flex-1 min-h-[360px] h-[400px] sm:h-[460px] xl:h-[520px] 2xl:h-[600px] flex items-center justify-center p-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart style={{ userSelect: "none" }}>
                {innerData &&
                  innerData.length > 0 &&
                  (() => {
                    const ringOuter = innerRadius - 15
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
                  label={renderCustomizedLabel}
                  outerRadius={outerRadius}
                  innerRadius={innerRadius}
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
                />
              </PieChart>
            </ResponsiveContainer>
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
                const mainOuterInnerRadius =
                  innerData && innerData.length > 0 ? 75 : 70
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
