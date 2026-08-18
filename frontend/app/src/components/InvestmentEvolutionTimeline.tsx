import { useEffect, useRef, useState, type ReactNode } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Info,
  LineChart as LineChartIcon,
} from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Button } from "@/components/ui/Button"
import { DatePicker } from "@/components/ui/DatePicker"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Sensitive } from "@/components/ui/Sensitive"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { useI18n } from "@/i18n"
import {
  formatCompactCurrency,
  formatCurrency,
  formatDate,
} from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { getGainsTimeline } from "@/services/api"
import { DataDisplayMode } from "@/types"
import type {
  GainsTimeline,
  GainsTimelinePoint,
  GainsTimelineQuery,
} from "@/types/gainsTimeline"

const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)"
type RangeKey = "ALL" | "1Y" | "YTD" | "1M"

const RANGE_KEYS: RangeKey[] = ["ALL", "1Y", "YTD", "1M"]
const INITIAL_RANGE: RangeKey = "1Y"

interface InvestmentEvolutionTimelineProps {
  query: GainsTimelineQuery
  currency: string
  className?: string
  /** Products without a meaningful cost basis (crypto, commodities) chart value only. */
  supportsGains?: boolean
}

function formatDateValue(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${date.getFullYear()}-${month}-${day}`
}

function getRangeFromDate(range: RangeKey): string | undefined {
  if (range === "ALL") return undefined

  const date = new Date()
  date.setHours(0, 0, 0, 0)

  if (range === "1Y") {
    date.setFullYear(date.getFullYear() - 1)
  } else if (range === "YTD") {
    date.setMonth(0, 1)
  } else {
    date.setMonth(date.getMonth() - 1)
  }

  return formatDateValue(date)
}

function getRangedQuery(
  query: GainsTimelineQuery,
  range: RangeKey,
  customFrom: string,
  customTo: string,
): GainsTimelineQuery {
  const hasCustomRange = Boolean(customFrom || customTo)
  const lowerBound = hasCustomRange
    ? customFrom || undefined
    : getRangeFromDate(range)
  const upperBound = hasCustomRange ? customTo || undefined : undefined

  // the caller's own bounds always win, a selection can only narrow them
  const fromDate =
    query.from_date && lowerBound
      ? query.from_date > lowerBound
        ? query.from_date
        : lowerBound
      : (query.from_date ?? lowerBound)
  const toDate =
    query.to_date && upperBound
      ? query.to_date < upperBound
        ? query.to_date
        : upperBound
      : (query.to_date ?? upperBound)

  return { ...query, from_date: fromDate, to_date: toDate }
}

/**
 * Time-weighted return since the start of the selected range. The backend ships a
 * base-100 index rebased to the first point of the range, so the percentage starts
 * at 0 and moves with performance, unaffected by contributions or withdrawals.
 * It deliberately does not match the gain in currency, which is money-weighted.
 */
export function getReturnPercentage(point: {
  index: number | null
}): number | null {
  if (point.index == null) return null
  return point.index - 100
}

function TrendBadge({
  positive,
  testId,
  children,
}: {
  positive: boolean
  testId: string
  children: ReactNode
}) {
  const Icon = positive ? ChevronUp : ChevronDown

  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-medium",
        positive
          ? "text-green-600 dark:text-green-400"
          : "text-red-600 dark:text-red-400",
      )}
      data-testid={testId}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {children}
    </span>
  )
}

function BetaNotice() {
  const { t } = useI18n()

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex shrink-0 items-center text-orange-500 transition-colors hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
          aria-label={t.evolutionChart.beta}
          data-testid="evolution-timeline-beta"
        >
          <Info className="h-3 w-3" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <div className="flex items-start gap-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-orange-500 dark:text-orange-400" />
          <div className="space-y-1">
            <h4 className="text-sm font-medium">{t.evolutionChart.beta}</h4>
            <p className="text-xs text-muted-foreground">
              {t.evolutionChart.betaNotice}
            </p>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

function EvolutionPeriodSelector({
  range,
  hasCustomRange,
  onRangeChange,
}: {
  range: RangeKey
  hasCustomRange: boolean
  onRangeChange: (range: RangeKey) => void
}) {
  const { t } = useI18n()

  return (
    <div
      className="inline-flex items-center gap-3"
      role="group"
      aria-label={t.evolutionChart.period}
      data-testid="evolution-timeline-periods"
    >
      {RANGE_KEYS.map(rangeKey => {
        const isSelected = !hasCustomRange && range === rangeKey
        return (
          <button
            key={rangeKey}
            type="button"
            className={cn(
              "p-0 text-[11px] font-medium uppercase leading-none text-muted-foreground transition-colors hover:text-foreground",
              isSelected && "font-semibold text-foreground",
            )}
            aria-pressed={isSelected}
            data-testid={`evolution-timeline-period-${rangeKey}`}
            onClick={() => onRangeChange(rangeKey)}
          >
            {t.evolutionChart.ranges[rangeKey]}
          </button>
        )
      })}
    </div>
  )
}

function EvolutionDateRange({
  customFrom,
  customTo,
  onFromChange,
  onToChange,
  onClear,
}: {
  customFrom: string
  customTo: string
  onFromChange: (value: string) => void
  onToChange: (value: string) => void
  onClear: () => void
}) {
  const { t } = useI18n()
  const hasCustomRange = Boolean(customFrom || customTo)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant={hasCustomRange ? "default" : "ghost"}
          size="sm"
          className="h-7 gap-1 px-1.5 text-[11px]"
          aria-label={t.evolutionChart.dateRange}
          data-testid="evolution-timeline-date-range"
        >
          <CalendarDays className="h-3.5 w-3.5" />
          {hasCustomRange && (
            <span
              role="button"
              tabIndex={0}
              className="text-xs font-semibold opacity-80 hover:opacity-100"
              aria-label={t.evolutionChart.clear}
              data-testid="evolution-timeline-date-range-clear"
              onClick={event => {
                event.stopPropagation()
                onClear()
              }}
              onKeyDown={event => {
                if (event.key !== "Enter" && event.key !== " ") return
                event.preventDefault()
                event.stopPropagation()
                onClear()
              }}
            >
              ×
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="end">
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">
              {t.evolutionChart.from}
            </label>
            <DatePicker
              value={customFrom}
              onChange={onFromChange}
              placeholder={t.evolutionChart.from}
              contentClassName="z-[100000]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium">{t.evolutionChart.to}</label>
            <DatePicker
              value={customTo}
              onChange={onToChange}
              placeholder={t.evolutionChart.to}
              contentClassName="z-[100000]"
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs"
            onClick={onClear}
          >
            {t.evolutionChart.clear}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}

function getQueryKey(query: GainsTimelineQuery): string {
  const normalizedAssets = query.assets
    .map(asset => ({
      product_type: asset.product_type,
      asset_keys: [...(asset.asset_keys || [])].sort(),
      portfolio_names: [...(asset.portfolio_names || [])].sort(),
      equity_types: [...(asset.equity_types || [])].sort(),
      wallet_ids: [...(asset.wallet_ids || [])].sort(),
    }))
    .sort((first, second) =>
      JSON.stringify(first).localeCompare(JSON.stringify(second)),
    )

  return JSON.stringify({
    assets: normalizedAssets,
    base_currency: query.base_currency,
    entities: [...(query.entities || [])].sort(),
    from_date: query.from_date,
    to_date: query.to_date,
    accrue_fixed_income: query.accrue_fixed_income,
    calculation_mode: query.calculation_mode,
  })
}

function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(
    () =>
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia(DESKTOP_MEDIA_QUERY).matches,
  )

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return

    const mediaQuery = window.matchMedia(DESKTOP_MEDIA_QUERY)
    const update = () => setIsDesktop(mediaQuery.matches)
    update()
    mediaQuery.addEventListener("change", update)

    return () => mediaQuery.removeEventListener("change", update)
  }, [])

  return isDesktop
}

function EvolutionChart({
  queryKey,
  currency,
  showGains,
  isFullRange,
}: {
  queryKey: string
  currency: string
  showGains: boolean
  isFullRange: boolean
}) {
  const { t, locale } = useI18n()
  const { mode } = useDataDisplayMode()
  const isPrivate = mode === DataDisplayMode.PRIVATE
  const requestSequence = useRef(0)
  const [timeline, setTimeline] = useState<GainsTimeline | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    const sequence = ++requestSequence.current

    setIsLoading(true)
    setHasError(false)
    setTimeline(null)

    void getGainsTimeline(JSON.parse(queryKey) as GainsTimelineQuery)
      .then(nextTimeline => {
        if (cancelled || sequence !== requestSequence.current) return
        setTimeline(nextTimeline)
      })
      .catch(() => {
        if (cancelled || sequence !== requestSequence.current) return
        setHasError(true)
      })
      .finally(() => {
        if (cancelled || sequence !== requestSequence.current) return
        setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [queryKey, retryVersion])

  const chartCurrency = timeline?.currency || currency
  const chartData = timeline?.points || []
  const formatAxisDate = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    const sameYear = date.getFullYear() === new Date().getFullYear()
    return new Intl.DateTimeFormat(locale, {
      month: "short",
      day: "numeric",
      ...(sameYear ? {} : { year: "2-digit" }),
    }).format(date)
  }

  if (isLoading) {
    return (
      <div
        className="flex h-56 flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="evolution-timeline-loading"
      >
        <span className="flex items-center gap-3">
          <LoadingSpinner size="sm" />
          {t.evolutionChart.loading}
        </span>
        {isFullRange && (
          <span className="text-xs" data-testid="evolution-timeline-slow-hint">
            {t.evolutionChart.fullRangeHint}
          </span>
        )}
      </div>
    )
  }

  if (hasError) {
    return (
      <div
        className="flex h-56 flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="evolution-timeline-error"
      >
        <span>{t.evolutionChart.error}</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRetryVersion(version => version + 1)}
        >
          {t.evolutionChart.retry}
        </Button>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div
        className="flex h-56 items-center justify-center text-center text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="evolution-timeline-empty"
      >
        {t.evolutionChart.noData}
      </div>
    )
  }

  return (
    <div
      className="h-56 sm:h-64 lg:h-[360px]"
      data-testid="evolution-timeline-chart"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{ top: 10, right: 4, left: 4, bottom: 0 }}
        >
          <CartesianGrid
            vertical={false}
            stroke="hsl(var(--foreground))"
            strokeDasharray="3 3"
            strokeOpacity={0.08}
          />
          <XAxis
            dataKey="date"
            height={28}
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))", strokeWidth: 1 }}
            tickMargin={8}
            minTickGap={48}
            tickFormatter={formatAxisDate}
          />
          <YAxis yAxisId="value" hide domain={["auto", "auto"]} />
          <YAxis yAxisId="gain" hide domain={["auto", "auto"]} />
          {showGains && (
            <ReferenceLine
              yAxisId="gain"
              y={0}
              stroke="hsl(var(--muted-foreground))"
              strokeOpacity={0.45}
            />
          )}
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const point = payload[0].payload as GainsTimelinePoint
              const returnPercentage = getReturnPercentage(point)
              return (
                <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                  <p className="mb-1 font-semibold">
                    {formatDate(String(label), locale)}
                  </p>
                  <p className="flex items-center justify-between gap-4">
                    <span className="text-muted-foreground">
                      {t.evolutionChart.value}
                    </span>
                    <Sensitive className="font-medium">
                      {formatCurrency(point.value, locale, chartCurrency)}
                    </Sensitive>
                  </p>
                  {showGains && point.gain != null && (
                    <p className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">
                        {t.evolutionChart.gain}
                      </span>
                      <TrendBadge
                        positive={point.gain >= 0}
                        testId="evolution-gain-badge"
                      >
                        <Sensitive>
                          {formatCurrency(point.gain, locale, chartCurrency)}
                        </Sensitive>
                      </TrendBadge>
                    </p>
                  )}
                  {showGains && returnPercentage !== null && (
                    <p className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">
                        {t.evolutionChart.twr}
                      </span>
                      <TrendBadge
                        positive={returnPercentage >= 0}
                        testId="evolution-return-badge"
                      >
                        {returnPercentage >= 0 ? "+" : ""}
                        {returnPercentage.toFixed(2)}%
                      </TrendBadge>
                    </p>
                  )}
                </div>
              )
            }}
          />
          <Line
            yAxisId="value"
            type="monotone"
            dataKey="value"
            name={t.evolutionChart.value}
            stroke="hsl(var(--chart-1))"
            strokeWidth={2}
            dot={false}
            isAnimationActive
            animationDuration={400}
          />
          {showGains && (
            <Line
              yAxisId="gain"
              type="monotone"
              dataKey="gain"
              name={t.evolutionChart.gain}
              stroke="hsl(var(--chart-2))"
              strokeWidth={2}
              dot={false}
              isAnimationActive
              animationDuration={400}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
      {!isPrivate && (
        <div className="sr-only">
          {formatCompactCurrency(
            chartData[chartData.length - 1].value,
            locale,
            chartCurrency,
          )}
        </div>
      )}
    </div>
  )
}

export function InvestmentEvolutionTimeline({
  query,
  currency,
  className,
  supportsGains = true,
}: InvestmentEvolutionTimelineProps) {
  const { t } = useI18n()
  const isDesktop = useIsDesktop()
  const [isExpanded, setIsExpanded] = useState(false)
  const [range, setRange] = useState<RangeKey>(INITIAL_RANGE)
  const [customFrom, setCustomFrom] = useState("")
  const [customTo, setCustomTo] = useState("")
  const hasCustomRange = Boolean(customFrom || customTo)
  const rangedQuery = getRangedQuery(query, range, customFrom, customTo)
  const queryKey = getQueryKey(rangedQuery)
  const shouldRenderChart = isDesktop || isExpanded

  const selectRange = (next: RangeKey) => {
    setRange(next)
    setCustomFrom("")
    setCustomTo("")
  }

  const clearCustomRange = () => {
    setCustomFrom("")
    setCustomTo("")
  }

  return (
    <section
      className={cn("min-w-0 -mx-6 lg:mx-0 lg:border-l lg:pl-6", className)}
      data-testid="evolution-timeline"
    >
      {!isDesktop && (
        <div className="flex items-center justify-between gap-3 px-6">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <LineChartIcon className="h-4 w-4 text-primary" />
            {t.evolutionChart.title}
            <BetaNotice />
          </h3>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-xs"
            aria-expanded={isExpanded}
            aria-label={
              isExpanded ? t.evolutionChart.hide : t.evolutionChart.show
            }
            data-testid="evolution-timeline-toggle"
            onClick={() => setIsExpanded(expanded => !expanded)}
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
            <span>
              {isExpanded ? t.evolutionChart.hide : t.evolutionChart.show}
            </span>
          </Button>
        </div>
      )}
      <AnimatePresence initial={false}>
        {shouldRenderChart && (
          <motion.div
            key={isDesktop ? "desktop" : "mobile"}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="mb-3 mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 px-6 lg:mt-0 lg:px-0">
              {isDesktop && (
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                  <LineChartIcon className="h-[18px] w-[18px] text-primary" />
                  {t.evolutionChart.title}
                  <BetaNotice />
                </h3>
              )}
              <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[hsl(var(--chart-1))]" />
                  {t.evolutionChart.value}
                </span>
                {supportsGains && (
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[hsl(var(--chart-2))]" />
                    {t.evolutionChart.gain}
                  </span>
                )}
              </div>
              <EvolutionPeriodSelector
                range={range}
                hasCustomRange={hasCustomRange}
                onRangeChange={selectRange}
              />
              <EvolutionDateRange
                customFrom={customFrom}
                customTo={customTo}
                onFromChange={setCustomFrom}
                onToChange={setCustomTo}
                onClear={clearCustomRange}
              />
            </div>
            <EvolutionChart
              queryKey={queryKey}
              currency={currency}
              showGains={supportsGains}
              isFullRange={!rangedQuery.from_date}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
