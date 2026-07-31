import React, { useEffect, useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  History,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { InvestmentFilters } from "@/components/InvestmentFilters"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import type { MultiSelectOption } from "@/components/ui/MultiSelect"
import { EntityBadge } from "@/components/ui/EntityBadge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { Sensitive } from "@/components/ui/Sensitive"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useTheme } from "@/context/ThemeContext"
import { useI18n } from "@/i18n"
import {
  formatCompactCurrency,
  formatCurrency,
  formatDate,
  formatGainLoss,
  formatNumber,
  formatPercentage,
} from "@/lib/formatters"
import { cn } from "@/lib/utils"
import {
  getMarketForecastClosedPositions,
  getMarketForecastPnl,
} from "@/services/api"
import type {
  MarketForecastAccountSummary,
  MarketForecastClosedPositionsResponse,
  MarketForecastPosition,
  MarketForecastPnlPoint,
  MarketForecastPnlResponse,
} from "@/types/marketForecast"
import { ProductType, type MarketForecastDetail } from "@/types/position"
import { getIconForProductType } from "@/utils/dashboardUtils"
import { convertCurrency } from "@/utils/financialDataUtils"

type PnlRange = "1d" | "1w" | "1m" | "1y" | "ytd" | "all"

const PNL_INTERVALS: PnlRange[] = ["1d", "1w", "1m", "1y", "ytd", "all"]

function normalizeSlug(value?: string | null): string | null {
  if (!value) return null
  return value.trim() || null
}

function getPolymarketUrl(position: {
  slug?: string | null
  event_slug?: string | null
  market_slug?: string | null
}): string | null {
  const slug =
    normalizeSlug(position.slug) ?? normalizeSlug(position.market_slug) ?? null
  const eventSlug = normalizeSlug(position.event_slug)

  if (eventSlug && slug && eventSlug !== slug) {
    return `https://polymarket.com/event/${eventSlug}/${slug}`
  }

  const finalSlug = slug || eventSlug
  return finalSlug ? `https://polymarket.com/event/${finalSlug}` : null
}

function toFiniteNumber(value: unknown): number | null {
  const num = typeof value === "number" ? value : Number(value)
  return Number.isFinite(num) ? num : null
}

function abbreviateAddress(address?: string | null): string | null {
  if (!address) return null
  const normalized = address.trim()
  if (!normalized) return null
  if (normalized.length <= 12) return normalized
  return `${normalized.slice(0, 6)}...${normalized.slice(-4)}`
}

function getProfileDisplayName(
  profile?: Record<string, unknown> | null,
): string | null {
  if (!profile) return null

  const candidates = [
    profile.name,
    profile.username,
    profile.handle,
    profile.alias,
    profile.pseudonym,
  ]

  for (const candidate of candidates) {
    if (typeof candidate === "string") {
      const trimmed = candidate.trim()
      if (trimmed) {
        return trimmed
      }
    }
  }

  return null
}

function getDayKey(timestampSeconds: number): string {
  return new Date(timestampSeconds * 1000).toISOString().slice(0, 10)
}

function getStartOfYearTimestamp(timestampSeconds: number): number {
  const date = new Date(timestampSeconds * 1000)
  return new Date(date.getFullYear(), 0, 1).getTime() / 1000
}

function getPnlRangeStartTimestamp(
  range: PnlRange,
  latestTimestamp: number,
): number | null {
  switch (range) {
    case "1d":
      return latestTimestamp - 24 * 60 * 60
    case "1w":
      return latestTimestamp - 7 * 24 * 60 * 60
    case "1m":
      return latestTimestamp - 30 * 24 * 60 * 60
    case "1y":
      return latestTimestamp - 365 * 24 * 60 * 60
    case "ytd":
      return getStartOfYearTimestamp(latestTimestamp)
    case "all":
    default:
      return null
  }
}

function getPnlValueForRange(
  points: MarketForecastPnlPoint[],
  range: PnlRange,
): number {
  if (points.length === 0) {
    return 0
  }

  const latestPoint = points[points.length - 1]
  const latestValue = toFiniteNumber(latestPoint.value) ?? 0
  if (range === "all") {
    return latestValue
  }

  const minTimestamp = getPnlRangeStartTimestamp(range, latestPoint.timestamp)
  if (minTimestamp == null) {
    return latestValue
  }

  let baselinePoint: MarketForecastPnlPoint | null = null
  for (const point of points) {
    if (point.timestamp <= minTimestamp) {
      baselinePoint = point
      continue
    }
    break
  }

  if (baselinePoint) {
    return latestValue - (toFiniteNumber(baselinePoint.value) ?? 0)
  }

  const firstPointInRange = points.find(
    point => point.timestamp >= minTimestamp,
  )
  if (firstPointInRange) {
    return latestValue - (toFiniteNumber(firstPointInRange.value) ?? 0)
  }

  return latestValue
}

function getPolymarketAccountLabel(args: {
  customName?: string | null
  accountName?: string | null
  profile?: Record<string, unknown> | null
  walletAddress?: string | null
}): string {
  const customName = args.customName?.trim()
  if (customName) return customName

  const accountName = args.accountName?.trim()
  if (accountName) return accountName

  const profileName = getProfileDisplayName(args.profile)
  if (profileName) return profileName

  return abbreviateAddress(args.walletAddress) || "Polymarket"
}

function getPositionValue(
  position: MarketForecastPosition,
  fallback = 0,
): number {
  return (
    toFiniteNumber(position.current_value) ??
    toFiniteNumber(position.cash_pnl) ??
    fallback
  )
}

function getMarketForecastCardBorderColor(
  pnl: number,
  status: "open" | "closed",
): string {
  if (pnl > 0) return "hsl(var(--chart-2))"
  if (pnl < 0) return "hsl(var(--destructive))"
  return status === "open" ? "hsl(var(--chart-4))" : "hsl(var(--chart-3))"
}

function getMarketForecastPositionKey(
  position: MarketForecastPosition,
  status: "open" | "closed",
): string {
  return [
    status,
    position.entity_account_id ?? position.wallet_address ?? "unknown-account",
    position.condition_id ??
      position.slug ??
      position.asset ??
      position.title ??
      "unknown-market",
    position.outcome ?? "unknown-outcome",
  ].join(":")
}

function getMarketForecastPositionRecencyTimestamp(
  position: MarketForecastPosition,
  status: "open" | "closed",
): number {
  const candidates =
    status === "closed"
      ? [
          position.closed_at,
          position.updated_at,
          position.created_at,
          position.end_date,
        ]
      : [position.updated_at, position.created_at, position.end_date]

  for (const candidate of candidates) {
    if (!candidate) continue
    const timestamp = new Date(candidate).getTime()
    if (Number.isFinite(timestamp)) {
      return timestamp
    }
  }

  return 0
}

function normalizeOpenMarketForecastPosition(
  position: MarketForecastDetail,
  entityAccountId?: string | null,
): MarketForecastPosition {
  const initialValue = toFiniteNumber(position.initial_investment)
  const cashPnl = toFiniteNumber(position.unrealized_pnl)

  return {
    entity_account_id: entityAccountId,
    title: position.name,
    slug: position.market_slug,
    event_slug: position.event_slug,
    outcome: position.outcome,
    condition_id: position.condition_id,
    asset: position.token_id,
    size: position.size,
    avg_price: position.entry_price,
    price: position.mark_price,
    current_value: position.market_value,
    initial_value: position.initial_investment,
    cash_pnl: position.unrealized_pnl,
    percent_pnl:
      initialValue && cashPnl != null ? (cashPnl / initialValue) * 100 : null,
    cur_price: position.mark_price,
    end_date: position.expiry,
  }
}

function getPolymarketEmbedMarketSlug(
  position: MarketForecastPosition,
): string | null {
  return (
    normalizeSlug(position.slug) ?? normalizeSlug(position.event_slug) ?? null
  )
}

interface MarketForecastDetailProps {
  position: MarketForecastPosition
  status: "open" | "closed"
  locale: string
  defaultCurrency: string
  isDarkMode: boolean
  positionUrl: string | null
}

function MarketForecastDetail({
  position,
  status,
  locale,
  defaultCurrency,
  isDarkMode,
  positionUrl,
}: MarketForecastDetailProps) {
  const { t } = useI18n()
  const embedMarketSlug = getPolymarketEmbedMarketSlug(position)
  const iframeSrc = embedMarketSlug
    ? `https://embed.polymarket.com/market?market=${encodeURIComponent(embedMarketSlug)}&theme=${isDarkMode ? "dark" : "light"}&fit=true`
    : null
  const shares = toFiniteNumber(position.size)
  const averagePrice = toFiniteNumber(position.avg_price)
  const markPrice =
    toFiniteNumber(position.cur_price) ?? toFiniteNumber(position.price)
  const resolvedAt = position.end_date || position.updated_at || null
  const closedAt = position.closed_at || position.updated_at || null

  return (
    <div className="px-4 pb-4">
      <div className="border-t border-border/50 pt-3">
        <div className="mb-4 grid grid-cols-2 gap-3 sm:hidden">
          {shares != null && (
            <div className="rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.shares}
              </div>
              <div className="mt-1 text-sm font-medium">
                {formatNumber(shares, locale)}
              </div>
            </div>
          )}

          {averagePrice != null && (
            <div className="rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.entry}
              </div>
              <div className="mt-1 text-sm font-medium">
                {formatCurrency(averagePrice, locale, defaultCurrency)}
              </div>
            </div>
          )}

          {status === "open" && markPrice != null && (
            <div className="rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.mark}
              </div>
              <div className="mt-1 text-sm font-medium">
                {formatCurrency(markPrice, locale, defaultCurrency)}
              </div>
            </div>
          )}

          {status === "open" && resolvedAt && (
            <div className="rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.resolves}
              </div>
              <div className="mt-1 text-sm font-medium">
                {formatDate(resolvedAt, locale)}
              </div>
            </div>
          )}

          {status === "closed" && closedAt && (
            <div className="rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.closed}
              </div>
              <div className="mt-1 text-sm font-medium">
                {formatDate(closedAt, locale)}
              </div>
            </div>
          )}

          {positionUrl && (
            <div className="col-span-2 rounded-lg border border-border/60 bg-background/60 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.marketForecast.labels.viewMarket}
              </div>
              <a
                href={positionUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                {t.marketForecast.labels.viewMarket}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          )}
        </div>

        {iframeSrc ? (
          <iframe
            title="polymarket-market-iframe"
            src={iframeSrc}
            width="100%"
            height="100%"
          />
        ) : (
          <div className="flex min-h-[320px] items-center justify-center rounded-xl border border-dashed bg-background px-4 text-center text-sm text-muted-foreground">
            {t.marketForecast.chartPreviewUnavailable}
          </div>
        )}
      </div>
    </div>
  )
}

interface MarketForecastPositionCardProps {
  position: MarketForecastPosition
  status: "open" | "closed"
  locale: string
  defaultCurrency: string
  entityName?: string
  isExpanded: boolean
  onToggleDetails: () => void
  isDarkMode: boolean
}

function MarketForecastPositionCard({
  position,
  status,
  locale,
  defaultCurrency,
  entityName,
  isExpanded,
  onToggleDetails,
  isDarkMode,
}: MarketForecastPositionCardProps) {
  const { t } = useI18n()
  const positionUrl = getPolymarketUrl(position)
  const pnl =
    status === "open"
      ? (toFiniteNumber(position.current_value) ?? 0)
      : (toFiniteNumber(position.realized_pnl) ?? 0)
  const pct =
    status === "open"
      ? (toFiniteNumber(position.percent_pnl) ??
        (toFiniteNumber(position.initial_value)
          ? (pnl / (toFiniteNumber(position.initial_value) || 1)) * 100
          : null))
      : null
  const title =
    position.title ||
    position.slug ||
    position.condition_id ||
    t.marketForecast.untitledMarket
  const subtitle =
    position.slug || position.condition_id || position.asset || null
  const shares = toFiniteNumber(position.size)
  const averagePrice = toFiniteNumber(position.avg_price)
  const markPrice =
    toFiniteNumber(position.cur_price) ?? toFiniteNumber(position.price)
  const resolvedAt = position.end_date || position.updated_at || null
  const closedAt = position.closed_at || position.updated_at || null
  const totalBought = toFiniteNumber(position.total_bought)

  return (
    <Card
      className="overflow-hidden border-l-4 transition-all hover:shadow-sm"
      style={{ borderLeftColor: getMarketForecastCardBorderColor(pnl, status) }}
    >
      <CardContent className="p-0">
        <div
          className="flex flex-col gap-3 p-4 transition-colors hover:bg-accent/40 sm:gap-4 md:flex-row md:items-start md:justify-between"
          onClick={e => {
            if ((e.target as HTMLElement).closest("[data-no-expand]")) return
            onToggleDetails()
          }}
          onKeyDown={e => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault()
              onToggleDetails()
            }
          }}
          role="button"
          tabIndex={0}
          aria-expanded={isExpanded}
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-3">
              {position.icon ? (
                <img
                  src={position.icon}
                  alt=""
                  className="h-12 w-12 shrink-0 rounded-xl border bg-muted object-cover"
                />
              ) : (
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border bg-muted/50 text-primary">
                  {getIconForProductType(
                    ProductType.MARKET_FORECAST,
                    "h-5 w-5",
                  )}
                </div>
              )}
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold leading-tight sm:text-lg">
                    {title}
                  </h3>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant="secondary"
                    className="rounded-full px-2.5 py-1"
                  >
                    {status === "open"
                      ? t.marketForecast.status.open
                      : t.marketForecast.status.closed}
                  </Badge>
                  {position.outcome && (
                    <Badge
                      variant="outline"
                      className="rounded-full px-2.5 py-1"
                    >
                      {position.outcome}
                    </Badge>
                  )}
                  {entityName && (
                    <EntityBadge
                      name={entityName}
                      className="text-xs"
                      title={entityName}
                      showVirtualTag={false}
                      data-no-expand
                    />
                  )}
                </div>

                {subtitle && (
                  <div className="hidden break-words text-sm text-muted-foreground sm:block">
                    {subtitle}
                  </div>
                )}

                <div className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm text-muted-foreground min-[460px]:grid-cols-2 sm:flex sm:flex-wrap sm:items-center">
                  {shares != null && (
                    <span>
                      {formatNumber(shares, locale)}{" "}
                      {t.marketForecast.labels.shares.toLowerCase()}
                    </span>
                  )}
                  {averagePrice != null && (
                    <span>
                      {t.marketForecast.labels.entry}{" "}
                      {formatCurrency(averagePrice, locale, defaultCurrency)}
                    </span>
                  )}
                  {status === "open" && markPrice != null && (
                    <span className="hidden sm:inline">
                      {t.marketForecast.labels.mark}{" "}
                      {formatCurrency(markPrice, locale, defaultCurrency)}
                    </span>
                  )}
                  {status === "open" && resolvedAt && (
                    <span className="hidden sm:inline">
                      {t.marketForecast.labels.resolves}{" "}
                      {formatDate(resolvedAt, locale)}
                    </span>
                  )}
                  {status === "closed" && closedAt && (
                    <span className="hidden sm:inline">
                      {t.marketForecast.labels.closed}{" "}
                      {formatDate(closedAt, locale)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex w-full items-start justify-between gap-3 border-t border-border/50 pt-3 md:w-auto md:shrink-0 md:items-center md:justify-end md:border-t-0 md:pt-0">
            <div className="grid min-w-0 flex-1 gap-1.5 text-sm md:min-w-[220px] md:text-right">
              <Sensitive>
                <div className="text-base font-semibold">
                  {status === "open"
                    ? t.marketForecast.labels.value
                    : t.marketForecast.labels.bought}
                  :{" "}
                  {formatCurrency(
                    status === "open"
                      ? (toFiniteNumber(position.current_value) ?? 0)
                      : (totalBought ?? 0),
                    locale,
                    defaultCurrency,
                  )}
                </div>
              </Sensitive>

              <div
                className={cn(
                  "inline-flex items-center gap-1 md:justify-end",
                  pnl >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400",
                )}
              >
                {pnl >= 0 ? (
                  <TrendingUp className="h-4 w-4" />
                ) : (
                  <TrendingDown className="h-4 w-4" />
                )}
                <span>
                  {formatGainLoss(pnl, locale, defaultCurrency)}
                  {pct != null ? ` (${formatPercentage(pct, locale)})` : ""}
                </span>
              </div>

              {status === "closed" &&
                totalBought != null &&
                position.total_sold != null && (
                  <div className="text-xs text-muted-foreground">
                    {formatNumber(totalBought, locale)}{" "}
                    {t.marketForecast.labels.bought.toLowerCase()} ·{" "}
                    {formatNumber(
                      toFiniteNumber(position.total_sold) ?? 0,
                      locale,
                    )}{" "}
                    {t.marketForecast.labels.sold.toLowerCase()}
                  </div>
                )}

              {positionUrl && (
                <div className="hidden sm:block md:text-right">
                  <a
                    href={positionUrl}
                    target="_blank"
                    rel="noreferrer"
                    data-no-expand
                    className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                  >
                    {t.marketForecast.labels.viewMarket}{" "}
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              )}
            </div>

            <ChevronDown
              className={cn(
                "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 md:mt-0",
                isExpanded && "rotate-180",
              )}
            />
          </div>
        </div>

        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              key="expanded"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
              className="overflow-hidden"
            >
              <MarketForecastDetail
                position={position}
                status={status}
                locale={locale}
                defaultCurrency={defaultCurrency}
                isDarkMode={isDarkMode}
                positionUrl={positionUrl}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

export default function MarketForecastInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { isLoading: financialLoading, positionsData } = useFinancialData()
  const { entities, settings, exchangeRates } = useAppContext()
  const { resolvedTheme } = useTheme()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
  const [selectedInterval, setSelectedInterval] = useState<PnlRange>("all")
  const [isClosedVisible, setIsClosedVisible] = useState(false)
  const [expandedPositionKey, setExpandedPositionKey] = useState<string | null>(
    null,
  )
  const [marketForecastPnlData, setMarketForecastPnlData] =
    useState<MarketForecastPnlResponse | null>(null)
  const [
    marketForecastClosedPositionsData,
    setMarketForecastClosedPositionsData,
  ] = useState<MarketForecastClosedPositionsResponse | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [isPnlLoading, setIsPnlLoading] = useState(false)
  const [isClosedLoading, setIsClosedLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const defaultCurrency = settings.general.defaultCurrency
  const isDarkMode = resolvedTheme === "dark"

  const polymarketEntities = useMemo(
    () => entities.filter(entity => entity.name === "Polymarket"),
    [entities],
  )

  const polymarketEntityIds = useMemo(
    () => polymarketEntities.map(entity => entity.id),
    [polymarketEntities],
  )

  const accountToEntityMap = useMemo(() => {
    const map = new Map<string, string>()
    polymarketEntities.forEach(entity => {
      ;(entity.accounts ?? []).forEach(account => {
        map.set(account.id, entity.id)
      })
    })
    return map
  }, [polymarketEntities])

  const accountEntityNames = useMemo(() => {
    const map = new Map<string, string>()
    polymarketEntities.forEach(entity => {
      ;(entity.accounts ?? []).forEach(account => {
        map.set(account.id, entity.name)
      })
    })
    return map
  }, [polymarketEntities])

  const allMarketForecastAccounts = useMemo(() => {
    const map = new Map<string, MarketForecastAccountSummary>()

    marketForecastPnlData?.accounts.forEach(account => {
      map.set(account.entity_account_id, account)
    })

    marketForecastClosedPositionsData?.accounts.forEach(account => {
      if (!map.has(account.entity_account_id)) {
        map.set(account.entity_account_id, account)
      }
    })

    return [...map.values()]
  }, [marketForecastClosedPositionsData, marketForecastPnlData])

  const marketForecastAccountMap = useMemo(() => {
    const map = new Map<string, MarketForecastAccountSummary>()
    allMarketForecastAccounts.forEach(account => {
      map.set(account.entity_account_id, account)
    })
    return map
  }, [allMarketForecastAccounts])

  const accountOptions = useMemo<MultiSelectOption[]>(() => {
    const seen = new Set<string>()
    const options: MultiSelectOption[] = []

    polymarketEntities.forEach(entity => {
      ;(entity.accounts ?? []).forEach(account => {
        if (!account.id || seen.has(account.id)) return
        if (
          selectedEntities.length > 0 &&
          !selectedEntities.includes(entity.id)
        ) {
          return
        }

        const accountData = marketForecastAccountMap.get(account.id)
        const label = getPolymarketAccountLabel({
          customName: account.name,
          accountName: accountData?.account_name,
          profile: accountData?.profile,
          walletAddress: accountData?.wallet_address,
        })

        seen.add(account.id)
        options.push({
          value: account.id,
          label,
        })
      })
    })

    return options.sort((a, b) => a.label.localeCompare(b.label, locale))
  }, [marketForecastAccountMap, polymarketEntities, selectedEntities, locale])

  useEffect(() => {
    if (accountOptions.length === 0) {
      if (selectedAccounts.length > 0) {
        setSelectedAccounts([])
      }
      return
    }

    const allowed = new Set(accountOptions.map(option => option.value))
    setSelectedAccounts(prev => {
      const next = prev.filter(id => allowed.has(id))
      return next.length === prev.length ? prev : next
    })
  }, [accountOptions, selectedAccounts.length])

  const openMarketForecastPositions = useMemo(() => {
    if (!positionsData?.positions) {
      return []
    }

    return Object.values(positionsData.positions)
      .flat()
      .filter(entityPosition => {
        const entityId = entityPosition.entity?.id
        return entityId ? polymarketEntityIds.includes(entityId) : false
      })
      .flatMap(entityPosition => {
        const marketForecastProduct =
          entityPosition.products[ProductType.MARKET_FORECAST]

        if (
          !marketForecastProduct ||
          !("entries" in marketForecastProduct) ||
          !Array.isArray(marketForecastProduct.entries)
        ) {
          return []
        }

        return (marketForecastProduct.entries as MarketForecastDetail[]).map(
          position =>
            normalizeOpenMarketForecastPosition(
              position,
              entityPosition.entity_account_id,
            ),
        )
      })
  }, [polymarketEntityIds, positionsData])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setIsInitialLoading(true)
      setIsPnlLoading(true)
      setIsClosedLoading(true)
      setError(null)

      const accountIds = polymarketEntities.flatMap(entity =>
        (entity.accounts ?? []).map(account => account.id),
      )

      const [pnlResult, closedPositionsResult] = await Promise.allSettled([
        getMarketForecastPnl(accountIds, "all"),
        getMarketForecastClosedPositions(accountIds),
      ])

      if (cancelled) {
        return
      }

      if (pnlResult.status === "fulfilled") {
        setMarketForecastPnlData(pnlResult.value)
      } else {
        console.error(
          "Error loading market forecast pnl data",
          pnlResult.reason,
        )
        setMarketForecastPnlData(null)
      }

      if (closedPositionsResult.status === "fulfilled") {
        setMarketForecastClosedPositionsData(closedPositionsResult.value)
      } else {
        console.error(
          "Error loading market forecast closed positions",
          closedPositionsResult.reason,
        )
        setMarketForecastClosedPositionsData(null)
      }

      if (
        pnlResult.status === "rejected" &&
        closedPositionsResult.status === "rejected"
      ) {
        setError(t.common.unexpectedError)
      }

      setIsInitialLoading(false)
      setIsPnlLoading(false)
      setIsClosedLoading(false)
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [polymarketEntities, t.common.unexpectedError])

  useEffect(() => {
    if (
      !isClosedVisible ||
      marketForecastClosedPositionsData ||
      isClosedLoading
    ) {
      return
    }

    let cancelled = false

    const loadClosedPositions = async () => {
      setIsClosedLoading(true)
      setError(null)
      try {
        const accountIds = polymarketEntities.flatMap(entity =>
          (entity.accounts ?? []).map(account => account.id),
        )
        const response = await getMarketForecastClosedPositions(accountIds)
        if (!cancelled) {
          setMarketForecastClosedPositionsData(response)
        }
      } catch (err) {
        console.error("Error loading market forecast closed positions", err)
        if (!cancelled) {
          setError(t.common.unexpectedError)
        }
      } finally {
        if (!cancelled) {
          setIsClosedLoading(false)
        }
      }
    }

    void loadClosedPositions()
    return () => {
      cancelled = true
    }
  }, [
    isClosedVisible,
    isClosedLoading,
    marketForecastClosedPositionsData,
    polymarketEntities,
    t.common.unexpectedError,
  ])

  const filteredAccountIds = useMemo(() => {
    if (!selectedEntities.length && !selectedAccounts.length) {
      return null
    }

    const ids = new Set<string>()
    allMarketForecastAccounts.forEach(account => {
      const entityId = accountToEntityMap.get(account.entity_account_id)
      const matchesEntity =
        !selectedEntities.length ||
        (entityId ? selectedEntities.includes(entityId) : false)
      const matchesAccount =
        !selectedAccounts.length ||
        selectedAccounts.includes(account.entity_account_id)

      if (matchesEntity && matchesAccount) {
        ids.add(account.entity_account_id)
      }
    })

    openMarketForecastPositions.forEach(position => {
      const accountId = position.entity_account_id
      if (!accountId) return
      const entityId = accountToEntityMap.get(accountId)
      const matchesEntity =
        !selectedEntities.length ||
        (entityId ? selectedEntities.includes(entityId) : false)
      const matchesAccount =
        !selectedAccounts.length || selectedAccounts.includes(accountId)

      if (matchesEntity && matchesAccount) {
        ids.add(accountId)
      }
    })

    return ids
  }, [
    selectedEntities,
    selectedAccounts,
    allMarketForecastAccounts,
    accountToEntityMap,
    openMarketForecastPositions,
  ])

  const filteredOpenPositions = useMemo(() => {
    return openMarketForecastPositions
      .filter(position => {
        if (!filteredAccountIds) return true
        return position.entity_account_id
          ? filteredAccountIds.has(position.entity_account_id)
          : false
      })
      .sort(
        (a, b) =>
          getMarketForecastPositionRecencyTimestamp(b, "open") -
          getMarketForecastPositionRecencyTimestamp(a, "open"),
      )
  }, [openMarketForecastPositions, filteredAccountIds])

  const filteredClosedPositions = useMemo(() => {
    const closedPositions =
      marketForecastClosedPositionsData?.closed_positions ?? []
    return closedPositions
      .filter(position => {
        if (!filteredAccountIds) return true
        return position.entity_account_id
          ? filteredAccountIds.has(position.entity_account_id)
          : false
      })
      .sort(
        (a, b) =>
          getMarketForecastPositionRecencyTimestamp(b, "closed") -
          getMarketForecastPositionRecencyTimestamp(a, "closed"),
      )
  }, [marketForecastClosedPositionsData, filteredAccountIds])

  const aggregatedPnlHistory = useMemo(() => {
    const history = marketForecastPnlData?.pnl_history ?? []
    const latestPointByAccountDay = new Map<
      string,
      { dayKey: string; timestamp: number; value: number }
    >()

    history.forEach(point => {
      if (
        filteredAccountIds &&
        point.entity_account_id &&
        !filteredAccountIds.has(point.entity_account_id)
      ) {
        return
      }

      const accountKey =
        point.entity_account_id ?? point.wallet_address ?? "unknown"
      const dayKey = getDayKey(point.timestamp)
      const compositeKey = `${accountKey}:${dayKey}`
      const existing = latestPointByAccountDay.get(compositeKey)

      if (!existing || point.timestamp > existing.timestamp) {
        latestPointByAccountDay.set(compositeKey, {
          dayKey,
          timestamp: point.timestamp,
          value: toFiniteNumber(point.value) ?? 0,
        })
      }
    })

    const totalsByDay = new Map<string, { timestamp: number; value: number }>()
    latestPointByAccountDay.forEach(({ dayKey, timestamp, value }) => {
      const existing = totalsByDay.get(dayKey)
      if (existing) {
        totalsByDay.set(dayKey, {
          timestamp: Math.max(existing.timestamp, timestamp),
          value: existing.value + value,
        })
      } else {
        totalsByDay.set(dayKey, { timestamp, value })
      }
    })

    return [...totalsByDay.values()]
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(({ timestamp, value }) => ({ timestamp, value }))
  }, [marketForecastPnlData, filteredAccountIds])

  const filteredPnlHistory = useMemo(() => {
    if (aggregatedPnlHistory.length === 0) {
      return aggregatedPnlHistory
    }

    const latestTimestamp =
      aggregatedPnlHistory[aggregatedPnlHistory.length - 1].timestamp
    const minTimestamp = getPnlRangeStartTimestamp(
      selectedInterval,
      latestTimestamp,
    )

    if (minTimestamp == null) {
      return aggregatedPnlHistory
    }

    return aggregatedPnlHistory.filter(point => point.timestamp >= minTimestamp)
  }, [aggregatedPnlHistory, selectedInterval])

  const pnlChartData = useMemo(
    () =>
      filteredPnlHistory.map(point => ({
        timestamp: point.timestamp,
        date: new Date(point.timestamp * 1000).toISOString(),
        value: toFiniteNumber(point.value) ?? 0,
      })),
    [filteredPnlHistory],
  )

  const formatPnlAxisDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    if (Number.isNaN(date.getTime())) return ""

    const spansMultipleYears =
      new Set(
        pnlChartData.map(point =>
          new Date(point.timestamp * 1000).getFullYear(),
        ),
      ).size > 1

    const options: Intl.DateTimeFormatOptions =
      selectedInterval === "1d"
        ? { hour: "2-digit", minute: "2-digit" }
        : selectedInterval === "all"
          ? spansMultipleYears
            ? { year: "2-digit", month: "short", day: "numeric" }
            : { month: "short", day: "numeric" }
          : { month: "short", day: "numeric" }

    return new Intl.DateTimeFormat(locale, options).format(date)
  }

  const getPnlIntervalLabel = (interval: PnlRange) => {
    switch (interval) {
      case "1d":
        return "1D"
      case "1w":
        return t.netWorthTimeline.ranges["1W"]
      case "1m":
        return t.netWorthTimeline.ranges["1M"]
      case "1y":
        return t.netWorthTimeline.ranges["1Y"]
      case "ytd":
        return t.netWorthTimeline.ranges.YTD
      case "all":
      default:
        return t.netWorthTimeline.ranges.ALL
    }
  }

  const summary = useMemo(() => {
    const openValue = filteredOpenPositions.reduce((sum, position) => {
      const value = getPositionValue(position)
      return (
        sum +
        convertCurrency(value, defaultCurrency, defaultCurrency, exchangeRates)
      )
    }, 0)

    const openInvestment = filteredOpenPositions.reduce((sum, position) => {
      const value =
        toFiniteNumber(position.initial_value) ??
        toFiniteNumber(position.current_value) ??
        0
      return (
        sum +
        convertCurrency(value, defaultCurrency, defaultCurrency, exchangeRates)
      )
    }, 0)

    const closedPnl = filteredClosedPositions.reduce((sum, position) => {
      return sum + (toFiniteNumber(position.realized_pnl) ?? 0)
    }, 0)

    const pnlForSelectedRange = getPnlValueForRange(
      aggregatedPnlHistory,
      selectedInterval,
    )

    return {
      openValue,
      openInvestment,
      closedPnl,
      pnlForSelectedRange,
    }
  }, [
    aggregatedPnlHistory,
    filteredClosedPositions,
    filteredOpenPositions,
    selectedInterval,
    defaultCurrency,
    exchangeRates,
  ])

  if (financialLoading || isInitialLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-1"
              onClick={() => navigate(-1)}
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{t.common.marketForecast}</h1>
              <PinAssetButton
                assetId="market-forecast"
                className="hidden md:inline-flex"
              />
            </div>
          </div>
        </div>
      </div>

      <InvestmentFilters
        filteredEntities={polymarketEntities}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
        walletOptions={accountOptions}
        selectedWallets={selectedAccounts}
        onWalletsChange={setSelectedAccounts}
        walletPlaceholder={t.transactions.selectAccounts}
      />

      {error && (
        <Card>
          <CardContent className="pt-6 text-sm text-red-600 dark:text-red-400">
            {error}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">
              {t.marketForecast.summary.openExposure}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Sensitive>
              <div>
                {formatCurrency(summary.openValue, locale, defaultCurrency)}
              </div>
            </Sensitive>
            <div className="mt-1 text-xs text-muted-foreground">
              {t.marketForecast.summary.costBasis}{" "}
              {formatCurrency(summary.openInvestment, locale, defaultCurrency)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">
              {t.marketForecast.summary.openPositions}
            </CardTitle>
          </CardHeader>
          <CardContent>{filteredOpenPositions.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">
              {t.marketForecast.summary.closedPositions}
            </CardTitle>
          </CardHeader>
          <CardContent>{filteredClosedPositions.length}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">
              {t.marketForecast.summary.realizedPnl}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Sensitive>
              <span
                className={
                  summary.closedPnl >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }
              >
                {formatGainLoss(summary.closedPnl, locale, defaultCurrency)}
              </span>
            </Sensitive>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle>{t.marketForecast.summary.pnlHistory}</CardTitle>
              {isPnlLoading && <LoadingSpinner size="sm" />}
            </div>
            <div className="mt-2 text-sm text-muted-foreground">
              {selectedInterval === "all"
                ? t.marketForecast.summary.latestCumulativePnl
                : t.marketForecast.summary.selectedRangePnl}
              :{" "}
              <span
                className={
                  summary.pnlForSelectedRange >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }
              >
                {formatGainLoss(
                  summary.pnlForSelectedRange,
                  locale,
                  defaultCurrency,
                )}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {PNL_INTERVALS.map(interval => (
              <Button
                key={interval}
                type="button"
                size="sm"
                variant={selectedInterval === interval ? "default" : "outline"}
                onClick={() => setSelectedInterval(interval)}
                disabled={isPnlLoading}
              >
                {getPnlIntervalLabel(interval)}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {pnlChartData.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              {t.common.noDataAvailable}
            </div>
          ) : (
            <div className="relative h-80 w-full">
              {isPnlLoading && (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-md bg-background/60 backdrop-blur-[1px]">
                  <LoadingSpinner size="sm" />
                </div>
              )}
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={pnlChartData}
                  margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
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
                        stopOpacity={0.4}
                      />
                      <stop
                        offset="100%"
                        stopColor="hsl(var(--chart-1))"
                        stopOpacity={0.05}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="hsl(var(--border))"
                  />
                  <ReferenceLine
                    y={0}
                    stroke="hsl(var(--muted-foreground))"
                    strokeOpacity={0.5}
                  />
                  <XAxis
                    dataKey="timestamp"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={24}
                    tickFormatter={formatPnlAxisDate}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={72}
                    tick={{ fontSize: 11 }}
                    tickFormatter={value =>
                      formatCompactCurrency(
                        Number(value),
                        locale,
                        defaultCurrency,
                      )
                    }
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const row = payload[0].payload as {
                        date: string
                        value: number
                      }
                      return (
                        <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                          <div className="font-semibold">
                            {formatDate(row.date, locale)}
                          </div>
                          <Sensitive className="mt-1 block">
                            <span
                              className={
                                row.value >= 0
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-red-600 dark:text-red-400"
                              }
                            >
                              {formatGainLoss(
                                row.value,
                                locale,
                                defaultCurrency,
                              )}
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
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-bold">
              {t.marketForecast.sections.openTitle}
            </h2>
            <div className="text-sm text-muted-foreground">
              {t.marketForecast.sections.openDescription}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="w-fit rounded-full px-3 py-1">
              {filteredOpenPositions.length}{" "}
              {t.marketForecast.sections.positions}
            </Badge>
            <Button
              variant={isClosedVisible ? "default" : "outline"}
              size="sm"
              className="flex items-center gap-2"
              onClick={() => setIsClosedVisible(prev => !prev)}
            >
              <History className="h-4 w-4" />
              <span>
                {isClosedVisible
                  ? t.investments.historicSection.toggleShort.hide
                  : t.investments.historicSection.toggleShort.show}
              </span>
              {isClosedLoading && <LoadingSpinner size="sm" />}
            </Button>
          </div>
        </div>

        {filteredOpenPositions.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            {t.common.noDataAvailable}
          </div>
        ) : (
          filteredOpenPositions.map(position => {
            const positionKey = getMarketForecastPositionKey(position, "open")

            return (
              <MarketForecastPositionCard
                key={positionKey}
                position={position}
                status="open"
                locale={locale}
                defaultCurrency={defaultCurrency}
                entityName={
                  position.entity_account_id
                    ? accountEntityNames.get(position.entity_account_id)
                    : undefined
                }
                isExpanded={expandedPositionKey === positionKey}
                onToggleDetails={() =>
                  setExpandedPositionKey(prev =>
                    prev === positionKey ? null : positionKey,
                  )
                }
                isDarkMode={isDarkMode}
              />
            )
          })
        )}
      </section>

      {isClosedVisible && (
        <Card>
          <CardHeader className="gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle>{t.marketForecast.sections.closedTitle}</CardTitle>
                {isClosedLoading && <LoadingSpinner size="sm" />}
              </div>
              <div className="text-sm text-muted-foreground">
                {t.marketForecast.sections.closedDescription}
              </div>
            </div>
            <Badge variant="outline" className="w-fit rounded-full px-3 py-1">
              {filteredClosedPositions.length}{" "}
              {t.marketForecast.sections.positions}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-3">
            {filteredClosedPositions.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                {t.common.noDataAvailable}
              </div>
            ) : (
              filteredClosedPositions.map(position => {
                const positionKey = getMarketForecastPositionKey(
                  position,
                  "closed",
                )

                return (
                  <MarketForecastPositionCard
                    key={positionKey}
                    position={position}
                    status="closed"
                    locale={locale}
                    defaultCurrency={defaultCurrency}
                    entityName={
                      position.entity_account_id
                        ? accountEntityNames.get(position.entity_account_id)
                        : undefined
                    }
                    isExpanded={expandedPositionKey === positionKey}
                    onToggleDetails={() =>
                      setExpandedPositionKey(prev =>
                        prev === positionKey ? null : positionKey,
                      )
                    }
                    isDarkMode={isDarkMode}
                  />
                )
              })
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
