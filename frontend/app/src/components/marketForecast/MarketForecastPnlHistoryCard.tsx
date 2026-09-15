import { useCallback, useMemo, useState } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "framer-motion"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  LineChart as LineChartIcon,
  Maximize2,
  Minimize2,
  X,
} from "lucide-react"

import { Card, CardContent, CardHeader } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { DatePicker } from "@/components/ui/DatePicker"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Sensitive } from "@/components/ui/Sensitive"
import { useAppContext } from "@/context/AppContext"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { DataDisplayMode } from "@/types"
import { useI18n } from "@/i18n"
import {
  formatCompactCurrency,
  formatDate,
  formatGainLoss,
} from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"

export type MarketForecastPnlRange = "1w" | "1m" | "6m" | "1y" | "ytd" | "all"

export interface MarketForecastPnlHistoryPoint {
  timestamp: number
  value: number
}

interface MarketForecastPnlHistoryCardProps {
  points: MarketForecastPnlHistoryPoint[]
  isLoading: boolean
  error?: string | null
  onExpandedChange?: (expanded: boolean) => void
}

const RANGE_KEYS: MarketForecastPnlRange[] = [
  "1w",
  "1m",
  "6m",
  "1y",
  "ytd",
  "all",
]

function getRangeStartTimestamp(
  range: MarketForecastPnlRange,
  latestTimestamp: number,
): number | null {
  switch (range) {
    case "1w":
      return latestTimestamp - 7 * 24 * 60 * 60
    case "1m":
      return latestTimestamp - 30 * 24 * 60 * 60
    case "6m":
      return latestTimestamp - 180 * 24 * 60 * 60
    case "1y":
      return latestTimestamp - 365 * 24 * 60 * 60
    case "ytd": {
      const date = new Date(latestTimestamp * 1000)
      return new Date(date.getFullYear(), 0, 1).getTime() / 1000
    }
    case "all":
      return null
  }
}

function getDateStartTimestamp(dateString: string): number | null {
  if (!dateString) return null
  const timestamp = new Date(`${dateString}T00:00:00Z`).getTime()
  return Number.isFinite(timestamp) ? timestamp / 1000 : null
}

function getDateKey(timestamp: number): string {
  return new Date(timestamp * 1000).toISOString().slice(0, 10)
}

function niceGridTicks(min: number, max: number, target: number): number[] {
  const range = max - min
  if (!(range > 0)) return []
  const rawStep = range / target
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const normalized = rawStep / magnitude
  const step =
    (normalized <= 1
      ? 1
      : normalized <= 2
        ? 2
        : normalized <= 2.5
          ? 2.5
          : normalized <= 5
            ? 5
            : 10) * magnitude
  const ticks: number[] = []
  const start = Math.ceil(min / step) * step
  for (let value = start; value <= max; value += step) {
    ticks.push(value)
  }
  return ticks
}

function getSelectionValue(
  allPoints: MarketForecastPnlHistoryPoint[],
  selectedPoints: MarketForecastPnlHistoryPoint[],
  range: MarketForecastPnlRange,
  customFrom: string,
): number {
  if (selectedPoints.length === 0) return 0

  const latestValue = selectedPoints[selectedPoints.length - 1].value
  const selectionStart = customFrom
    ? getDateStartTimestamp(customFrom)
    : getRangeStartTimestamp(range, allPoints[allPoints.length - 1].timestamp)

  if (selectionStart == null) return latestValue

  let baseline: MarketForecastPnlHistoryPoint | null = null
  for (const point of allPoints) {
    if (point.timestamp <= selectionStart) {
      baseline = point
      continue
    }
    break
  }

  if (baseline) return latestValue - baseline.value
  return latestValue - selectedPoints[0].value
}

function getRangeLabel(
  range: MarketForecastPnlRange,
  t: ReturnType<typeof useI18n>["t"],
): string {
  switch (range) {
    case "1w":
      return t.netWorthTimeline.ranges["1W"]
    case "1m":
      return t.netWorthTimeline.ranges["1M"]
    case "6m":
      return t.netWorthTimeline.ranges["6M"]
    case "1y":
      return t.netWorthTimeline.ranges["1Y"]
    case "ytd":
      return t.netWorthTimeline.ranges.YTD
    case "all":
      return t.netWorthTimeline.ranges.ALL
  }
}

export default function MarketForecastPnlHistoryCard({
  points,
  isLoading,
  error,
  onExpandedChange,
}: MarketForecastPnlHistoryCardProps) {
  const { t, locale } = useI18n()
  const { settings } = useAppContext()
  const { mode } = useDataDisplayMode()
  const isPrivate = mode === DataDisplayMode.PRIVATE
  const currency = settings.general.defaultCurrency

  const [range, setRange] = useState<MarketForecastPnlRange>("all")
  const [customFrom, setCustomFrom] = useState("")
  const [customTo, setCustomTo] = useState("")
  const [dragStart, setDragStart] = useState<string | null>(null)
  const [dragEnd, setDragEnd] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useModalBackHandler(expanded, () => setExpanded(false))

  const sortedPoints = useMemo(
    () => [...points].sort((a, b) => a.timestamp - b.timestamp),
    [points],
  )

  const filteredPoints = useMemo(() => {
    if (sortedPoints.length === 0) return []

    if (customFrom || customTo) {
      return sortedPoints.filter(point => {
        const date = getDateKey(point.timestamp)
        return (
          (!customFrom || date >= customFrom) && (!customTo || date <= customTo)
        )
      })
    }

    const latestTimestamp = sortedPoints[sortedPoints.length - 1].timestamp
    const cutoff = getRangeStartTimestamp(range, latestTimestamp)
    if (cutoff == null) return sortedPoints
    return sortedPoints.filter(point => point.timestamp >= cutoff)
  }, [customFrom, customTo, range, sortedPoints])

  const latestValue =
    sortedPoints.length > 0 ? sortedPoints[sortedPoints.length - 1].value : 0
  const selectedValue = useMemo(
    () => getSelectionValue(sortedPoints, filteredPoints, range, customFrom),
    [customFrom, customTo, filteredPoints, range, sortedPoints],
  )

  const chartData = useMemo(
    () =>
      filteredPoints.map(point => ({
        date: new Date(point.timestamp * 1000).toISOString(),
        timestamp: point.timestamp,
        value: point.value,
      })),
    [filteredPoints],
  )

  const spansMultipleYears = useMemo(
    () =>
      new Set(
        chartData.map(point => new Date(point.timestamp * 1000).getFullYear()),
      ).size > 1,
    [chartData],
  )

  const yAxisDomain = useMemo(() => {
    if (chartData.length === 0) return [0, 1] as [number, number]
    const values = chartData.map(point => point.value)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const spread = max - min
    const padding = spread > 0 ? spread * 0.1 : Math.max(Math.abs(max), 1) * 0.1
    return [Math.min(0, min - padding), Math.max(0, max + padding)] as [
      number,
      number,
    ]
  }, [chartData])

  const formatAxisDate = useCallback(
    (value: string) => {
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      return new Intl.DateTimeFormat(locale, {
        month: "short",
        day: "numeric",
        ...(spansMultipleYears ? { year: "2-digit" } : {}),
      }).format(date)
    },
    [locale, spansMultipleYears],
  )

  const handleDragStart = useCallback(
    (event: { activeLabel?: string } | null) => {
      if (event?.activeLabel) {
        setDragStart(event.activeLabel)
        setDragEnd(event.activeLabel)
      }
    },
    [],
  )

  const handleDragMove = useCallback(
    (event: { activeLabel?: string } | null) => {
      if (dragStart && event?.activeLabel) {
        setDragEnd(event.activeLabel)
      }
    },
    [dragStart],
  )

  const handleDragEnd = useCallback(() => {
    if (dragStart && dragEnd && dragStart !== dragEnd) {
      const [from, to] = [dragStart.slice(0, 10), dragEnd.slice(0, 10)].sort()
      setCustomFrom(from)
      setCustomTo(to)
    }
    setDragStart(null)
    setDragEnd(null)
  }, [dragEnd, dragStart])

  const selectRange = useCallback((nextRange: MarketForecastPnlRange) => {
    setRange(nextRange)
    setCustomFrom("")
    setCustomTo("")
  }, [])

  const makeGridLabel = (text: string) => {
    const GridLabel = (props: { viewBox?: { x?: number; y?: number } }) => (
      <text
        x={(props.viewBox?.x ?? 0) + 6}
        y={(props.viewBox?.y ?? 0) - 3}
        textAnchor="start"
        fontSize={9}
        className="fill-muted-foreground"
        opacity={0.55}
      >
        {text}
      </text>
    )
    GridLabel.displayName = "GridLabel"
    return GridLabel
  }

  const renderChart = (height: number | string, isExpanded: boolean) => {
    const gridTicks = niceGridTicks(
      yAxisDomain[0],
      yAxisDomain[1],
      isExpanded ? 7 : 4,
    )

    return (
      <div className="relative" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 10, right: 0, left: 0, bottom: 0 }}
            onMouseDown={handleDragStart}
            onMouseMove={handleDragMove}
            onMouseUp={handleDragEnd}
            onMouseLeave={handleDragEnd}
            style={{ cursor: dragStart ? "col-resize" : "crosshair" }}
          >
            <defs>
              <linearGradient
                id="market-forecast-pnl-gradient"
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor="hsl(var(--chart-1))"
                  stopOpacity={0.45}
                />
                <stop
                  offset="100%"
                  stopColor="hsl(var(--chart-1))"
                  stopOpacity={0.08}
                />
              </linearGradient>
            </defs>
            {isExpanded && (
              <CartesianGrid
                horizontal={false}
                vertical
                strokeDasharray="3 3"
                stroke="hsl(var(--foreground))"
                strokeOpacity={0.12}
              />
            )}
            {gridTicks.map(tick => (
              <ReferenceLine
                key={tick}
                y={tick}
                stroke="hsl(var(--foreground))"
                strokeOpacity={0.07}
                label={
                  isPrivate
                    ? undefined
                    : makeGridLabel(
                        formatCompactCurrency(tick, locale, currency),
                      )
                }
              />
            ))}
            <ReferenceLine
              y={0}
              stroke="hsl(var(--muted-foreground))"
              strokeOpacity={0.45}
            />
            <XAxis
              dataKey="date"
              height={28}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))", strokeWidth: 1 }}
              tickMargin={8}
              minTickGap={isExpanded ? 24 : 64}
              tickFormatter={formatAxisDate}
            />
            <YAxis
              mirror
              width={0}
              domain={yAxisDomain}
              tick={false}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={!dragStart}
              content={({ active, payload, label }) => {
                if (dragStart || !active || !payload?.length) return null
                const row = payload[0].payload as {
                  date: string
                  value: number
                }
                return (
                  <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                    <p className="mb-1 font-semibold">
                      {formatDate(String(label), locale)}
                    </p>
                    <Sensitive>
                      <span
                        className={cn(
                          "font-bold",
                          row.value >= 0
                            ? "text-green-600 dark:text-green-400"
                            : "text-red-600 dark:text-red-400",
                        )}
                      >
                        {formatGainLoss(row.value, locale, currency)}
                      </span>
                    </Sensitive>
                  </div>
                )
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="hsl(var(--chart-1))"
              fill="url(#market-forecast-pnl-gradient)"
              strokeWidth={2}
              dot={false}
              baseValue={0}
              isAnimationActive
              animationBegin={0}
              animationDuration={600}
              animationEasing="ease-out"
            />
            {dragStart && dragEnd && dragStart !== dragEnd && (
              <ReferenceArea
                x1={dragStart}
                x2={dragEnd}
                fill="hsl(var(--primary))"
                fillOpacity={0.12}
                stroke="hsl(var(--primary))"
                strokeOpacity={0.4}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    )
  }

  const renderRangeButtons = () => (
    <div className="inline-flex h-7 items-center overflow-hidden rounded-md border border-input">
      {RANGE_KEYS.map((key, index) => {
        const active = !customFrom && !customTo && range === key
        return (
          <button
            key={key}
            type="button"
            onClick={() => selectRange(key)}
            className={cn(
              "h-full px-2.5 text-xs font-medium transition-colors",
              index > 0 && "border-l border-input",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {getRangeLabel(key, t)}
          </button>
        )
      })}
    </div>
  )

  const renderDateRange = () => (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant={customFrom || customTo ? "default" : "outline"}
          size="sm"
          className="h-7 px-2 text-xs"
        >
          <CalendarDays className="h-3.5 w-3.5 sm:mr-1" />
          <span className="hidden sm:inline">
            {t.netWorthTimeline.dateRange}
          </span>
          {(customFrom || customTo) && (
            <span
              onClick={event => {
                event.stopPropagation()
                setCustomFrom("")
                setCustomTo("")
              }}
              className="ml-1.5 cursor-pointer text-xs font-semibold opacity-80 hover:opacity-100"
              aria-label={t.netWorthTimeline.clear}
            >
              <X className="h-3.5 w-3.5" />
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="z-[18050] w-72" align="end">
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t.netWorthTimeline.from}
            </label>
            <DatePicker
              value={customFrom}
              onChange={setCustomFrom}
              placeholder={t.netWorthTimeline.from}
              contentClassName="z-[18100]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t.netWorthTimeline.to}
            </label>
            <DatePicker
              value={customTo}
              onChange={setCustomTo}
              placeholder={t.netWorthTimeline.to}
              contentClassName="z-[18100]"
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs"
            onClick={() => {
              setCustomFrom("")
              setCustomTo("")
            }}
          >
            {t.netWorthTimeline.clear}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )

  const renderControls = () => (
    <div className="flex w-max flex-nowrap items-center justify-end gap-2">
      {renderRangeButtons()}
      {renderDateRange()}
    </div>
  )

  const renderBody = (chartHeight: number | string, isExpanded: boolean) => {
    if (isLoading && sortedPoints.length === 0) {
      return (
        <div className="flex h-[260px] items-center justify-center">
          <LoadingSpinner size="md" />
        </div>
      )
    }
    if (error) {
      return (
        <div className="flex h-[260px] flex-col items-center justify-center px-6 text-center text-sm text-muted-foreground">
          <LineChartIcon className="mb-3 h-10 w-10 text-primary/60" />
          <p>{error}</p>
        </div>
      )
    }
    if (sortedPoints.length === 0) {
      return (
        <div className="flex h-[260px] flex-col items-center justify-center px-6 text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <LineChartIcon className="h-6 w-6" />
          </div>
          <p className="font-semibold">{t.marketForecast.empty.pnlTitle}</p>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            {t.marketForecast.empty.pnlDescription}
          </p>
        </div>
      )
    }
    if (filteredPoints.length === 0) {
      return (
        <div className="flex h-[260px] flex-col items-center justify-center px-6 text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <LineChartIcon className="h-6 w-6" />
          </div>
          <p className="font-semibold">{t.netWorthTimeline.noData}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {t.netWorthTimeline.dateRange}
          </p>
        </div>
      )
    }
    return renderChart(chartHeight, isExpanded)
  }

  const hasSelectedRange = Boolean(customFrom || customTo || range !== "all")

  const handleToggle = () => {
    const nextOpen = !isOpen
    onExpandedChange?.(nextOpen)
    setIsOpen(nextOpen)
  }

  return (
    <>
      <Card className="-mx-6 select-none rounded-none border-0 bg-transparent shadow-none">
        <div
          className={cn(
            "border-t border-border bg-card",
            !isOpen && "border-b",
          )}
        >
          <CardHeader className="flex flex-row flex-wrap items-center gap-3 px-4 pb-3 pt-3 sm:px-6">
            <button
              type="button"
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
              onClick={handleToggle}
              aria-expanded={isOpen}
              aria-controls="market-forecast-pnl-chart"
            >
              <LineChartIcon className="h-5 w-5 shrink-0 text-primary" />
              <span className="text-lg font-bold">
                {t.marketForecast.summary.pnlHistory}
              </span>
              {isOpen && sortedPoints.length > 0 && (
                <Sensitive>
                  <span
                    className={cn(
                      "min-w-0 truncate text-lg font-semibold tracking-tight tabular-nums",
                      (hasSelectedRange ? selectedValue : latestValue) >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400",
                    )}
                  >
                    {formatGainLoss(
                      hasSelectedRange ? selectedValue : latestValue,
                      locale,
                      currency,
                    )}
                  </span>
                </Sensitive>
              )}
              {isLoading && isOpen && <LoadingSpinner size="sm" />}
              {isOpen ? (
                <ChevronUp className="ml-auto h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronDown className="ml-auto h-4 w-4 shrink-0 text-muted-foreground" />
              )}
            </button>
            {isOpen && (
              <>
                <div className="order-3 basis-full overflow-x-auto md:order-none md:ml-auto md:min-w-0 md:basis-auto">
                  <div className="flex w-max items-center gap-2">
                    {renderControls()}
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 w-7 shrink-0 p-0"
                      onClick={() => setExpanded(true)}
                      aria-label={t.netWorthTimeline.expand}
                    >
                      <Maximize2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardHeader>
          <AnimatePresence initial={false}>
            {isOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 272, opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{
                  height: { duration: 0.25, ease: "easeInOut" },
                  opacity: { duration: 0.18 },
                }}
                className="overflow-visible"
              >
                <CardContent
                  id="market-forecast-pnl-chart"
                  className="overflow-visible p-0"
                >
                  <div className="-mb-7">{renderBody(300, false)}</div>
                </CardContent>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        {isOpen && <div className="h-7" aria-hidden="true" />}
      </Card>

      {expanded &&
        createPortal(
          <div className="fixed inset-0 z-[18000] flex flex-col bg-background px-4 pb-4 pt-[max(1rem,var(--safe-area-inset-top,0px))] md:px-6 md:pb-6 md:pt-[max(1.5rem,var(--safe-area-inset-top,0px))]">
            <div className="mb-4 flex flex-row items-center justify-between gap-2">
              <h2 className="flex items-center text-xl font-bold">
                <LineChartIcon className="mr-2 h-5 w-5 text-primary" />
                {t.marketForecast.summary.pnlHistory}
              </h2>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setExpanded(false)}
                aria-label={t.netWorthTimeline.collapse}
              >
                <Minimize2 className="h-4 w-4" />
              </Button>
            </div>
            <div className="mb-4">{renderControls()}</div>
            <div className="flex min-h-0 flex-1 flex-col">
              {isLoading || error || sortedPoints.length === 0 ? (
                renderBody(400, true)
              ) : (
                <div className="min-h-0 flex-1">{renderBody("100%", true)}</div>
              )}
            </div>
            <button
              type="button"
              className="absolute right-4 top-4 hidden"
              onClick={() => setExpanded(false)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>,
          document.body,
        )}
    </>
  )
}
