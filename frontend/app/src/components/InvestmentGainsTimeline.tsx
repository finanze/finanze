import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import {
  ChevronDown,
  ChevronUp,
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
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
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
import type { GainsTimeline, GainsTimelineQuery } from "@/types/gainsTimeline"

const DESKTOP_MEDIA_QUERY = "(min-width: 1024px)"
type RangeKey = "ALL" | "1Y" | "YTD" | "1M"

const RANGE_KEYS: RangeKey[] = ["ALL", "1Y", "YTD", "1M"]
const INITIAL_RANGE: RangeKey = "1Y"

interface InvestmentGainsTimelineProps {
  query: GainsTimelineQuery
  currency: string
  className?: string
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
): GainsTimelineQuery {
  const rangeFromDate = getRangeFromDate(range)
  const fromDate =
    query.from_date && rangeFromDate
      ? query.from_date > rangeFromDate
        ? query.from_date
        : rangeFromDate
      : (query.from_date ?? rangeFromDate)

  return { ...query, from_date: fromDate }
}

function GainsPeriodSelector({
  range,
  onRangeChange,
}: {
  range: RangeKey
  onRangeChange: (range: RangeKey) => void
}) {
  const { t } = useI18n()

  return (
    <div
      className="inline-flex items-center gap-3"
      role="group"
      aria-label={t.gainsTimeline.period}
      data-testid="gains-timeline-periods"
    >
      {RANGE_KEYS.map(rangeKey => {
        const isSelected = range === rangeKey
        return (
          <button
            key={rangeKey}
            type="button"
            className={cn(
              "p-0 text-[11px] font-medium uppercase leading-none text-muted-foreground transition-colors hover:text-foreground",
              isSelected && "font-semibold text-foreground",
            )}
            aria-pressed={isSelected}
            data-testid={`gains-timeline-period-${rangeKey}`}
            onClick={() => onRangeChange(rangeKey)}
          >
            {t.gainsTimeline.ranges[rangeKey]}
          </button>
        )
      })}
    </div>
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

function GainsChart({
  queryKey,
  currency,
}: {
  queryKey: string
  currency: string
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
        className="flex h-56 items-center justify-center gap-3 text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="gains-timeline-loading"
      >
        <LoadingSpinner size="sm" />
        <span>{t.gainsTimeline.loading}</span>
      </div>
    )
  }

  if (hasError) {
    return (
      <div
        className="flex h-56 flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="gains-timeline-error"
      >
        <span>{t.gainsTimeline.error}</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRetryVersion(version => version + 1)}
        >
          {t.gainsTimeline.retry}
        </Button>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div
        className="flex h-56 items-center justify-center text-center text-sm text-muted-foreground sm:h-64 lg:h-[360px]"
        data-testid="gains-timeline-empty"
      >
        {t.gainsTimeline.noData}
      </div>
    )
  }

  return (
    <div
      className="h-56 sm:h-64 lg:h-[360px]"
      data-testid="gains-timeline-chart"
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
          <ReferenceLine
            yAxisId="gain"
            y={0}
            stroke="hsl(var(--muted-foreground))"
            strokeOpacity={0.45}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null
              const point = payload[0].payload as {
                value: number
                gain: number
              }
              return (
                <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                  <p className="mb-1 font-semibold">
                    {formatDate(String(label), locale)}
                  </p>
                  <p className="flex items-center justify-between gap-4">
                    <span className="text-muted-foreground">
                      {t.gainsTimeline.value}
                    </span>
                    <Sensitive className="font-medium">
                      {formatCurrency(point.value, locale, chartCurrency)}
                    </Sensitive>
                  </p>
                  <p className="flex items-center justify-between gap-4">
                    <span className="text-muted-foreground">
                      {t.gainsTimeline.gain}
                    </span>
                    <Sensitive
                      className={cn(
                        "font-medium",
                        point.gain >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400",
                      )}
                    >
                      {formatCurrency(point.gain, locale, chartCurrency)}
                    </Sensitive>
                  </p>
                </div>
              )
            }}
          />
          <Line
            yAxisId="value"
            type="monotone"
            dataKey="value"
            name={t.gainsTimeline.value}
            stroke="hsl(var(--chart-1))"
            strokeWidth={2}
            dot={false}
            isAnimationActive
            animationDuration={400}
          />
          <Line
            yAxisId="gain"
            type="monotone"
            dataKey="gain"
            name={t.gainsTimeline.gain}
            stroke="hsl(var(--chart-2))"
            strokeWidth={2}
            dot={false}
            isAnimationActive
            animationDuration={400}
          />
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

export function InvestmentGainsTimeline({
  query,
  currency,
  className,
}: InvestmentGainsTimelineProps) {
  const { t } = useI18n()
  const isDesktop = useIsDesktop()
  const [isExpanded, setIsExpanded] = useState(false)
  const [range, setRange] = useState<RangeKey>(INITIAL_RANGE)
  const queryKey = getQueryKey(getRangedQuery(query, range))
  const shouldRenderChart = isDesktop || isExpanded

  return (
    <section
      className={cn("min-w-0 -mx-6 lg:mx-0 lg:border-l lg:pl-6", className)}
      data-testid="gains-timeline"
    >
      {!isDesktop && (
        <>
          <div className="flex items-center justify-between gap-3 px-6">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <LineChartIcon className="h-4 w-4 text-primary" />
              {t.gainsTimeline.title}
            </h3>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 px-2 text-xs"
              aria-expanded={isExpanded}
              aria-label={
                isExpanded ? t.gainsTimeline.hide : t.gainsTimeline.show
              }
              data-testid="gains-timeline-toggle"
              onClick={() => setIsExpanded(expanded => !expanded)}
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
              <span>
                {isExpanded ? t.gainsTimeline.hide : t.gainsTimeline.show}
              </span>
            </Button>
          </div>
        </>
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
            <div className="mb-3 mt-4 flex items-center gap-3 px-6 lg:mt-0 lg:px-0">
              {isDesktop && (
                <>
                  <h3 className="flex items-center gap-2 text-lg font-semibold">
                    <LineChartIcon className="h-[18px] w-[18px] text-primary" />
                    {t.gainsTimeline.title}
                  </h3>
                </>
              )}
              <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[hsl(var(--chart-1))]" />
                  {t.gainsTimeline.value}
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[hsl(var(--chart-2))]" />
                  {t.gainsTimeline.gain}
                </span>
              </div>
              {isDesktop && (
                <GainsPeriodSelector range={range} onRangeChange={setRange} />
              )}
              {!isDesktop && (
                <GainsPeriodSelector range={range} onRangeChange={setRange} />
              )}
            </div>
            <GainsChart queryKey={queryKey} currency={currency} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
