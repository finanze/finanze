import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  CalendarDays,
  Check,
  LineChart as LineChartIcon,
  Maximize2,
  Minimize2,
  SlidersHorizontal,
  X,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { DatePicker } from "@/components/ui/DatePicker"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Sensitive } from "@/components/ui/Sensitive"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  formatCompactCurrency,
  formatCurrency,
  formatDate,
} from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import {
  ASSET_TYPE_TO_COLOR_MAP,
  getIconForAssetType,
} from "@/utils/dashboardUtils"
import { getNetworthTimeline } from "@/services/api"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { DataDisplayMode } from "@/types"
import type { NetworthTimelinePoint } from "@/types/networthTimeline"

type RangeKey = "ALL" | "1Y" | "6M" | "3M" | "1M" | "1W"

const RANGE_KEYS: RangeKey[] = ["ALL", "1Y", "6M", "3M", "1M", "1W"]

const TYPE_ORDER = [
  "ACCOUNT",
  "DEPOSIT",
  "FUND",
  "STOCK_ETF",
  "CRYPTO",
  "COMMODITY",
  "FACTORING",
  "REAL_ESTATE_CF",
  "CROWDLENDING",
  "DERIVATIVE",
  "REAL_ESTATE",
  "REAL_ESTATE_RESIDENCE",
  "CARD",
  "CREDIT",
  "LOAN",
]

const FALLBACK_COLORS = [
  "#6366f1",
  "#0ea5e9",
  "#22c55e",
  "#a855f7",
  "#f43f5e",
  "#64748b",
]

function colorForType(type: string, index: number): string {
  const sharedKey = type === "ACCOUNT" ? "CASH" : type
  return (
    ASSET_TYPE_TO_COLOR_MAP[sharedKey] ??
    FALLBACK_COLORS[index % FALLBACK_COLORS.length]
  )
}

function orderTypes(types: string[]): string[] {
  return [...types].sort((a, b) => {
    const ia = TYPE_ORDER.indexOf(a)
    const ib = TYPE_ORDER.indexOf(b)
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
  })
}

function seededShuffle<T>(items: T[], seed: number): T[] {
  const result = [...items]
  let state = (seed + result.length * 2654435761) & 0x7fffffff
  const next = () => {
    state = (state * 1103515245 + 12345) & 0x7fffffff
    return state / 0x7fffffff
  }
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

function niceGridTicks(max: number, target: number): number[] {
  if (!(max > 0)) return []
  const rawStep = max / target
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const norm = rawStep / mag
  let step: number
  if (norm <= 1) step = 1
  else if (norm <= 2) step = 2
  else if (norm <= 2.5) step = 2.5
  else if (norm <= 5) step = 5
  else step = 10
  step *= mag
  const ticks: number[] = []
  for (let v = step; v < max; v += step) ticks.push(v)
  return ticks
}

function rangeCutoff(range: RangeKey): string | null {
  if (range === "ALL") return null
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  switch (range) {
    case "1Y":
      d.setFullYear(d.getFullYear() - 1)
      break
    case "6M":
      d.setMonth(d.getMonth() - 6)
      break
    case "3M":
      d.setMonth(d.getMonth() - 3)
      break
    case "1M":
      d.setMonth(d.getMonth() - 1)
      break
    case "1W":
      d.setDate(d.getDate() - 7)
      break
  }
  return d.toISOString().split("T")[0]
}

const INITIAL_RANGE: RangeKey = "1Y"

// Lower bound of the data a given selection needs. `null` means "from the very
// beginning" (e.g. the ALL range, or a custom range with only an upper bound).
function neededCutoff(
  range: RangeKey,
  customFrom: string,
  customTo: string,
): string | null {
  if (customFrom) return customFrom
  if (customTo) return null
  return rangeCutoff(range)
}

let hasLoadedTimelineThisSession = false

interface NetWorthTimelineCardProps {
  todayPoint?: NetworthTimelinePoint | null
  defaultHiddenTypes?: string[]
}

export default function NetWorthTimelineCard({
  todayPoint,
  defaultHiddenTypes,
}: NetWorthTimelineCardProps) {
  const { t, locale } = useI18n()
  const { settings } = useAppContext()
  const { mode } = useDataDisplayMode()
  const isPrivate = mode === DataDisplayMode.PRIVATE
  const defaultCurrency = settings.general.defaultCurrency

  const [backendPoints, setBackendPoints] = useState<NetworthTimelinePoint[]>(
    [],
  )
  const [currency, setCurrency] = useState<string>(defaultCurrency)
  const [loading, setLoading] = useState(!hasLoadedTimelineThisSession)
  const [rangeLoading, setRangeLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [range, setRange] = useState<RangeKey>(INITIAL_RANGE)
  const [customFrom, setCustomFrom] = useState<string>("")
  const [customTo, setCustomTo] = useState<string>("")
  // Lower bound currently loaded into `backendPoints`. `null` means everything
  // (down to the very first point) is loaded, so no further fetch is needed.
  const [coveredFrom, setCoveredFrom] = useState<string | null>(
    rangeCutoff(INITIAL_RANGE),
  )
  const [chartType, setChartType] = useState<"stacked" | "lines">("stacked")
  const [showTotal, setShowTotal] = useState(true)
  const [dragStart, setDragStart] = useState<string | null>(null)
  const [dragEnd, setDragEnd] = useState<string | null>(null)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(
    () => new Set(defaultHiddenTypes ?? []),
  )
  const [expanded, setExpanded] = useState(false)

  useModalBackHandler(expanded, () => setExpanded(false))

  const loadedRef = useRef(false)
  const fetchSeqRef = useRef(0)

  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    let cancelled = false

    const apply = (points: NetworthTimelinePoint[], cur: string) => {
      if (cancelled) return
      setBackendPoints(points)
      setCurrency(cur || defaultCurrency)
    }

    const initialCutoff = rangeCutoff(INITIAL_RANGE)

    const load = async () => {
      try {
        const fast = await getNetworthTimeline({
          no_calculation: true,
          from_date: initialCutoff ?? undefined,
        })
        apply(fast.points, fast.currency)
      } catch {
        // ignore, the full load below will surface errors
      } finally {
        if (!cancelled) setLoading(false)
      }

      try {
        const full = await getNetworthTimeline({
          from_date: initialCutoff ?? undefined,
        })
        apply(full.points, full.currency)
        if (!cancelled) setCoveredFrom(initialCutoff)
        hasLoadedTimelineThisSession = true
      } catch (err) {
        console.error("Error loading net worth timeline:", err)
        if (!cancelled && !hasLoadedTimelineThisSession) {
          setError(t.common.unexpectedError)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [defaultCurrency, t])

  // Widen the loaded window on demand when the user selects a range/custom range
  // that needs older data than what is currently cached. Narrower selections are
  // served from memory; we only ever fetch (and cache) a wider window.
  useEffect(() => {
    if (!loadedRef.current) return
    if (coveredFrom === null) return // everything is already loaded

    const needed = neededCutoff(range, customFrom, customTo)
    const needsWider = needed === null || needed < coveredFrom
    if (!needsWider) return

    let cancelled = false
    const seq = ++fetchSeqRef.current
    setRangeLoading(true)

    const widen = async () => {
      try {
        const res = await getNetworthTimeline({
          no_calculation: true,
          from_date: needed ?? undefined,
        })
        if (cancelled || seq !== fetchSeqRef.current) return
        setBackendPoints(res.points)
        setCurrency(res.currency || defaultCurrency)
        setCoveredFrom(needed)
      } catch (err) {
        console.error("Error widening net worth timeline:", err)
      } finally {
        if (!cancelled && seq === fetchSeqRef.current) setRangeLoading(false)
      }
    }

    widen()
    return () => {
      cancelled = true
    }
  }, [range, customFrom, customTo, coveredFrom, defaultCurrency])

  const allPoints = useMemo(() => {
    if (!todayPoint) return backendPoints
    if (
      backendPoints.length &&
      backendPoints[backendPoints.length - 1].date >= todayPoint.date
    ) {
      return backendPoints
    }
    return [...backendPoints, todayPoint]
  }, [backendPoints, todayPoint])

  const allTypes = useMemo(() => {
    const present = new Set<string>()
    for (const point of allPoints) {
      for (const key of Object.keys(point.breakdown)) {
        present.add(key)
      }
    }
    return orderTypes([...present])
  }, [allPoints])

  const visibleTypes = useMemo(
    () => allTypes.filter(type => !hiddenTypes.has(type)),
    [allTypes, hiddenTypes],
  )

  const privateColorMap = useMemo(() => {
    if (!isPrivate) return null
    const palette = allTypes.map((type, index) => colorForType(type, index))
    const shuffled = seededShuffle(palette, allTypes.length + 11)
    const map: Record<string, string> = {}
    allTypes.forEach((type, index) => {
      map[type] = shuffled[index]
    })
    return map
  }, [isPrivate, allTypes])

  const colorOf = useCallback(
    (type: string, index: number) =>
      privateColorMap?.[type] ?? colorForType(type, index),
    [privateColorMap],
  )

  const displayTypes = useMemo(
    () =>
      isPrivate
        ? seededShuffle(visibleTypes, visibleTypes.length + 5)
        : visibleTypes,
    [isPrivate, visibleTypes],
  )

  const filteredPoints = useMemo(() => {
    if (customFrom || customTo) {
      return allPoints.filter(
        p =>
          (!customFrom || p.date >= customFrom) &&
          (!customTo || p.date <= customTo),
      )
    }
    const cutoff = rangeCutoff(range)
    if (!cutoff) return allPoints
    return allPoints.filter(p => p.date >= cutoff)
  }, [allPoints, range, customFrom, customTo])

  const chartData = useMemo(() => {
    return filteredPoints.map(point => {
      const row: Record<string, number | string> = { date: point.date }
      let total = 0
      for (const type of visibleTypes) {
        const value = point.breakdown[type] ?? 0
        row[type] = value
        total += value
      }
      row.__total = total
      return row
    })
  }, [filteredPoints, visibleTypes])

  const toggleType = useCallback((type: string) => {
    setHiddenTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }, [])

  const selectRange = useCallback((next: RangeKey) => {
    setRange(next)
    setCustomFrom("")
    setCustomTo("")
  }, [])

  const handleDragStart = useCallback((e: { activeLabel?: string } | null) => {
    if (e?.activeLabel) {
      setDragStart(e.activeLabel)
      setDragEnd(e.activeLabel)
    }
  }, [])

  const handleDragMove = useCallback(
    (e: { activeLabel?: string } | null) => {
      if (dragStart && e?.activeLabel) {
        setDragEnd(e.activeLabel)
      }
    },
    [dragStart],
  )

  const handleDragEnd = useCallback(() => {
    if (dragStart && dragEnd && dragStart !== dragEnd) {
      const [from, to] = [dragStart, dragEnd].sort()
      setCustomFrom(from)
      setCustomTo(to)
    }
    setDragStart(null)
    setDragEnd(null)
  }, [dragStart, dragEnd])

  const typeLabel = useCallback(
    (type: string) => {
      const labels = (t.enums?.productType ?? {}) as Record<string, string>
      return labels[type] ?? type
    },
    [t],
  )

  const formatYAxis = useCallback(
    (value: number) =>
      isPrivate ? "" : formatCompactCurrency(value, locale, currency),
    [locale, currency, isPrivate],
  )

  const maxTotal = useMemo(() => {
    let m = 0
    for (const row of chartData) {
      const v = typeof row.__total === "number" ? row.__total : 0
      if (v > m) m = v
    }
    return m
  }, [chartData])

  const makeGridLabel = (text: string) => {
    const GridLabel = (props: {
      viewBox?: { x?: number; y?: number; width?: number }
    }) => {
      const x = (props.viewBox?.x ?? 0) + 6
      const y = (props.viewBox?.y ?? 0) - 3
      return (
        <text
          x={x}
          y={y}
          textAnchor="start"
          fontSize={9}
          className="fill-muted-foreground"
          opacity={0.55}
        >
          {text}
        </text>
      )
    }
    GridLabel.displayName = "GridLabel"
    return GridLabel
  }

  const formatAxisDate = useCallback(
    (value: string) => {
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      const sameYear = date.getFullYear() === new Date().getFullYear()
      return new Intl.DateTimeFormat(locale, {
        month: "short",
        day: "numeric",
        ...(sameYear ? {} : { year: "2-digit" }),
      }).format(date)
    },
    [locale],
  )

  const hasData = allPoints.length > 0

  const renderChart = (height: number | string, isExpanded: boolean) => {
    const gridTicks = niceGridTicks(maxTotal, isExpanded ? 7 : 4)
    return (
      <div className="relative" style={{ height }}>
        {rangeLoading && (
          <div className="absolute right-2 top-2 z-10">
            <LoadingSpinner size="sm" />
          </div>
        )}
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
            {chartType === "stacked" && (
              <defs>
                {displayTypes.map((type, index) => {
                  const c = colorOf(type, index)
                  return (
                    <linearGradient
                      id={`nwt-grad-${index}`}
                      key={`${type}-${index}`}
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="0%" stopColor={c} stopOpacity={0.62} />
                      <stop offset="100%" stopColor={c} stopOpacity={0.12} />
                    </linearGradient>
                  )
                })}
              </defs>
            )}
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
              domain={[0, (dataMax: number) => dataMax * 1.1]}
              tick={false}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatYAxis}
            />
            <Tooltip
              cursor={!dragStart}
              content={({ active, payload, label }) => {
                if (dragStart) return null
                if (!active || !payload || payload.length === 0) return null
                const row = payload[0].payload as Record<string, number>
                return (
                  <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                    <p className="font-semibold mb-1">
                      {formatDate(String(label), locale)}
                    </p>
                    <p className="mb-1 flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">
                        {t.netWorthTimeline.showTotal}
                      </span>
                      <Sensitive className="font-bold text-foreground">
                        {formatCurrency(row.__total ?? 0, locale, currency)}
                      </Sensitive>
                    </p>
                    {displayTypes.map(type => (
                      <p
                        key={type}
                        className="flex items-center justify-between gap-4"
                      >
                        <span className="flex items-center gap-1.5">
                          <span
                            className="inline-block h-2 w-2 rounded-full"
                            style={{ backgroundColor: colorOf(type, 0) }}
                          />
                          {typeLabel(type)}
                        </span>
                        <Sensitive>
                          {formatCurrency(row[type] ?? 0, locale, currency)}
                        </Sensitive>
                      </p>
                    ))}
                  </div>
                )
              }}
            />
            {chartType === "stacked"
              ? displayTypes.map((type, index) => (
                  <Area
                    key={type}
                    type="monotone"
                    dataKey={type}
                    name={typeLabel(type)}
                    stackId="networth"
                    stroke="none"
                    fill={`url(#nwt-grad-${index})`}
                    fillOpacity={1}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))
              : displayTypes.map((type, index) => (
                  <Line
                    key={type}
                    type="monotone"
                    dataKey={type}
                    name={typeLabel(type)}
                    stroke={colorOf(type, index)}
                    strokeWidth={1.5}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
            <Line
              type="monotone"
              dataKey="__total"
              name={t.netWorthTimeline.showTotal}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              hide={!showTotal}
              isAnimationActive={false}
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
            {t.netWorthTimeline.ranges[key]}
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
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 z-[18050]" align="end">
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t.netWorthTimeline.from}
            </label>
            <DatePicker
              value={customFrom}
              onChange={setCustomFrom}
              placeholder={t.netWorthTimeline.from}
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

  const renderTypeFilter = () => {
    if (allTypes.length === 0) return null
    const hiddenCount = allTypes.filter(type => hiddenTypes.has(type)).length
    const active = hiddenCount > 0
    return (
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant={active ? "default" : "outline"}
            size="sm"
            className="h-7 px-2 text-xs"
          >
            <SlidersHorizontal className="h-3.5 w-3.5 sm:mr-1" />
            <span className="hidden sm:inline">
              {t.netWorthTimeline.options}
            </span>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-60 z-[18050] p-1" align="end">
          <div className="px-1 pt-1 space-y-1">
            <div className="inline-flex h-7 w-full overflow-hidden rounded-md border border-input">
              {(["stacked", "lines"] as const).map((kind, index) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => setChartType(kind)}
                  className={cn(
                    "flex-1 text-xs font-medium transition-colors",
                    index > 0 && "border-l border-input",
                    chartType === kind
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  {t.netWorthTimeline[kind]}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setShowTotal(prev => !prev)}
              className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent hover:text-accent-foreground"
            >
              <span>{t.netWorthTimeline.showTotal}</span>
              {showTotal && <Check className="h-3.5 w-3.5 text-primary" />}
            </button>
          </div>
          <div className="my-1 border-t border-border" />
          <div className="flex items-center justify-between px-2 py-1">
            <button
              type="button"
              className="text-[11px] text-muted-foreground hover:text-foreground"
              onClick={() => setHiddenTypes(new Set())}
            >
              {t.netWorthTimeline.selectAll}
            </button>
            <button
              type="button"
              className="text-[11px] text-muted-foreground hover:text-foreground"
              onClick={() => setHiddenTypes(new Set(allTypes))}
            >
              {t.netWorthTimeline.clearAll}
            </button>
          </div>
          <div className="max-h-72 overflow-auto">
            {allTypes.map(type => {
              const hidden = hiddenTypes.has(type)
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => toggleType(type)}
                  className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent hover:text-accent-foreground"
                >
                  <span
                    className={`flex items-center gap-2 ${
                      hidden ? "opacity-40" : "opacity-100"
                    }`}
                  >
                    {getIconForAssetType(type, "h-4 w-4", colorOf(type, 0))}
                    {typeLabel(type)}
                  </span>
                  {!hidden && <Check className="h-3.5 w-3.5 text-primary" />}
                </button>
              )
            })}
          </div>
        </PopoverContent>
      </Popover>
    )
  }

  const renderBody = (chartHeight: number, isExpanded: boolean) => {
    if (loading) {
      return (
        <div className="flex justify-center items-center h-[260px]">
          <LoadingSpinner size="md" />
        </div>
      )
    }
    if (error) {
      return (
        <div className="flex flex-col items-center justify-center h-[260px] text-center text-sm text-muted-foreground">
          <p>{error}</p>
        </div>
      )
    }
    if (!hasData) {
      return (
        <div className="flex flex-col items-center justify-center h-[260px] text-center text-sm text-muted-foreground">
          <LineChartIcon className="h-10 w-10 mb-3 opacity-50" />
          <p>{t.netWorthTimeline.noData}</p>
        </div>
      )
    }
    return renderChart(chartHeight, isExpanded)
  }

  const renderControls = () => (
    <div className="flex flex-wrap items-center gap-2 justify-end">
      {renderRangeButtons()}
      {renderTypeFilter()}
      {renderDateRange()}
    </div>
  )

  return (
    <>
      <Card className="-mx-6 rounded-none border-0 bg-transparent shadow-none select-none">
        <div className="bg-card border-t border-b border-border">
          <CardHeader className="flex flex-col gap-3 pb-3">
            <div className="flex flex-row items-center justify-between gap-2">
              <CardTitle className="text-lg font-bold flex items-center shrink-0">
                <LineChartIcon className="h-5 w-5 mr-2 text-primary" />
                {t.netWorthTimeline.title}
              </CardTitle>
              <div className="flex items-center gap-2">
                <div className="hidden lg:block">{renderControls()}</div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0 flex-shrink-0"
                  onClick={() => setExpanded(true)}
                  aria-label={t.netWorthTimeline.expand}
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            <div className="lg:hidden">{renderControls()}</div>
          </CardHeader>
          <CardContent className="p-0 overflow-visible">
            <div className="-mb-7">{renderBody(300, false)}</div>
          </CardContent>
        </div>
        <div className="h-7" aria-hidden="true" />
      </Card>

      {expanded &&
        createPortal(
          <div className="fixed inset-0 z-[18000] bg-background flex flex-col p-4 md:p-6 select-none">
            <div className="flex flex-row items-center justify-between gap-2 mb-4">
              <h2 className="text-xl font-bold flex items-center">
                <LineChartIcon className="h-5 w-5 mr-2 text-primary" />
                {t.netWorthTimeline.title}
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
            <div className="flex-1 min-h-0 flex flex-col">
              {loading || error || !hasData ? (
                renderBody(400, true)
              ) : (
                <div className="flex-1 min-h-0">
                  {renderChart("100%", true)}
                </div>
              )}
            </div>
            <button
              type="button"
              className="absolute top-4 right-4 hidden"
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
