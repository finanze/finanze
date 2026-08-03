import React, { useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  BarChart3,
  CalendarDays,
  ChevronDown,
  ExternalLink,
  History,
  Link2,
  TrendingDown,
  TrendingUp,
  Vote,
} from "lucide-react"

import { InvestmentFilters } from "@/components/InvestmentFilters"
import { EntityRefreshDropdown } from "@/components/EntityRefreshDropdown"
import MarketForecastPnlHistoryCard from "@/components/marketForecast/MarketForecastPnlHistoryCard"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent } from "@/components/ui/Card"
import type { MultiSelectOption } from "@/components/ui/MultiSelect"
import { EntityBadge } from "@/components/ui/EntityBadge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { Sensitive } from "@/components/ui/Sensitive"
import { useAppContext } from "@/context/AppContext"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
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
  MarketForecastPnlResponse,
} from "@/types/marketForecast"
import { EntityStatus, EntityType, type ExchangeRates } from "@/types"
import { ProductType, type MarketForecastDetail } from "@/types/position"
import { getIconForProductType } from "@/utils/dashboardUtils"
import {
  getCurrencyDisplayValue,
  tryConvertCurrency,
} from "@/utils/financialDataUtils"

function toFiniteNumber(value: unknown): number | null {
  const num = typeof value === "number" ? value : Number(value)
  return Number.isFinite(num) ? num : null
}

function sumMarketForecastValues(
  positions: MarketForecastPosition[],
  getValue: (position: MarketForecastPosition) => number | null,
  targetCurrency: string,
  exchangeRates: ExchangeRates | null | undefined,
): number | null {
  let total = 0

  for (const position of positions) {
    const value = getValue(position)
    if (value == null) continue

    const convertedValue = tryConvertCurrency(
      value,
      position.currency,
      targetCurrency,
      exchangeRates,
    )
    if (convertedValue == null) {
      return null
    }
    total += convertedValue
  }

  return total
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

function hasDifferentCurrency(
  sourceCurrency: string | null | undefined,
  targetCurrency: string,
): boolean {
  return Boolean(
    sourceCurrency?.trim() &&
    sourceCurrency.trim().toUpperCase() !== targetCurrency.trim().toUpperCase(),
  )
}

function getMarketForecastPositionKey(
  position: MarketForecastPosition,
  status: "open" | "closed",
): string {
  return [
    status,
    position.entity_account_id ?? position.wallet_address ?? "unknown-account",
    position.market_key ??
      position.event_key ??
      position.outcome_key ??
      position.name ??
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

function getMarketForecastInitialInvestment(
  position: MarketForecastPosition,
): number | null {
  const reportedValue = toFiniteNumber(position.initial_value)
  const boughtShares =
    toFiniteNumber(position.total_bought) ?? toFiniteNumber(position.size)
  const entryPrice = toFiniteNumber(position.avg_price)

  if (
    (reportedValue == null || reportedValue <= 0) &&
    boughtShares != null &&
    boughtShares > 0 &&
    entryPrice != null &&
    entryPrice >= 0
  ) {
    return boughtShares * entryPrice
  }

  return reportedValue
}

function normalizeOpenMarketForecastPosition(
  position: MarketForecastDetail,
  entityAccountId?: string | null,
): MarketForecastPosition {
  const initialValue = toFiniteNumber(position.initial_investment)
  const cashPnl = toFiniteNumber(position.unrealized_pnl)

  return {
    currency: position.currency,
    entity_account_id: entityAccountId,
    name: position.name,
    market_key: position.market_key,
    event_key: position.event_key,
    outcome_key: position.outcome_key,
    market_url: position.market_url,
    outcome: position.outcome,
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
    icon_url: position.icon_url,
  }
}

function MarketForecastDateBadge({
  value,
  locale,
  className,
}: {
  value: string
  locale: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-primary/25 bg-primary/5 px-2 py-1 text-xs",
        className,
      )}
    >
      <CalendarDays className="h-3.5 w-3.5 shrink-0 text-primary" />
      <span className="font-semibold text-foreground">
        {formatDate(value, locale)}
      </span>
    </span>
  )
}

function getMarketForecastEmbedKey(
  position: MarketForecastPosition,
): string | null {
  const marketUrl = position.market_url?.trim()
  if (marketUrl && URL.canParse(marketUrl)) {
    const pathSegments = new URL(marketUrl).pathname.split("/").filter(Boolean)
    const marketSlug = pathSegments.at(-1)
    if (marketSlug) return marketSlug
  }

  return position.event_key?.trim() || position.market_key?.trim() || null
}

interface MarketForecastDetailProps {
  position: MarketForecastPosition
  status: "open" | "closed"
  locale: string
  defaultCurrency: string
  exchangeRates: ExchangeRates | null | undefined
  isDarkMode: boolean
}

function MarketForecastDetail({
  position,
  status,
  locale,
  defaultCurrency,
  exchangeRates,
  isDarkMode,
}: MarketForecastDetailProps) {
  const { t } = useI18n()
  const embedMarketKey = getMarketForecastEmbedKey(position)
  const iframeSrc = embedMarketKey
    ? `https://embed.polymarket.com/market?market=${encodeURIComponent(embedMarketKey)}&theme=${isDarkMode ? "dark" : "light"}&fit=true&showBorder=false`
    : null
  const averagePrice = toFiniteNumber(position.avg_price)
  const initialValue = getMarketForecastInitialInvestment(position)
  const currentValue = toFiniteNumber(position.current_value)
  const pnl =
    status === "open"
      ? (toFiniteNumber(position.cash_pnl) ??
        (currentValue != null && initialValue != null
          ? currentValue - initialValue
          : null))
      : toFiniteNumber(position.realized_pnl)
  const totalBought = toFiniteNumber(position.total_bought)
  const totalSold = toFiniteNumber(position.total_sold)
  const hasSoldShares = totalSold != null && totalSold > 0
  const sourceCurrency = position.currency?.trim()
  const sourceCurrencyDiffers = hasDifferentCurrency(
    sourceCurrency,
    defaultCurrency,
  )
  const displayAveragePrice =
    averagePrice == null
      ? null
      : getCurrencyDisplayValue(
          averagePrice,
          position.currency,
          defaultCurrency,
          exchangeRates,
        )
  const displayInitialValue =
    initialValue == null
      ? null
      : getCurrencyDisplayValue(
          initialValue,
          position.currency,
          defaultCurrency,
          exchangeRates,
        )
  const displayOpenPnl =
    pnl == null
      ? null
      : getCurrencyDisplayValue(
          pnl,
          position.currency,
          defaultCurrency,
          exchangeRates,
        )
  const formattedOriginalAveragePrice =
    averagePrice != null &&
    sourceCurrencyDiffers &&
    sourceCurrency &&
    displayAveragePrice?.currency.toUpperCase() ===
      defaultCurrency.toUpperCase()
      ? formatCurrency(averagePrice, locale, defaultCurrency, sourceCurrency)
      : null
  const formattedOriginalInitialValue =
    initialValue != null &&
    sourceCurrencyDiffers &&
    sourceCurrency &&
    displayInitialValue?.currency.toUpperCase() ===
      defaultCurrency.toUpperCase()
      ? formatCurrency(initialValue, locale, defaultCurrency, sourceCurrency)
      : null
  const formattedOriginalOpenPnl =
    pnl != null &&
    sourceCurrencyDiffers &&
    sourceCurrency &&
    displayOpenPnl?.currency.toUpperCase() === defaultCurrency.toUpperCase()
      ? formatGainLoss(pnl, locale, sourceCurrency)
      : null

  return (
    <div className="px-4 pb-0">
      <div className="border-t border-border/50 pt-3">
        {(averagePrice != null ||
          initialValue != null ||
          pnl != null ||
          (status === "closed" && (totalBought != null || hasSoldShares))) && (
          <div
            className={cn(
              "mb-4 grid gap-y-3 text-sm",
              status === "open"
                ? "grid-cols-3 gap-x-3"
                : "grid-cols-1 gap-x-6 sm:grid-cols-3",
            )}
          >
            {averagePrice != null && (
              <div>
                <div className="text-xs font-medium text-muted-foreground">
                  {t.marketForecast.labels.entry}
                </div>
                <div className="mt-0.5 font-medium text-foreground">
                  <Sensitive>
                    {displayAveragePrice
                      ? formatCurrency(
                          displayAveragePrice.value,
                          locale,
                          defaultCurrency,
                          displayAveragePrice.currency,
                        )
                      : "-"}
                  </Sensitive>
                </div>
                {formattedOriginalAveragePrice && (
                  <div className="text-xs font-normal text-muted-foreground">
                    <Sensitive>{formattedOriginalAveragePrice}</Sensitive>
                  </div>
                )}
                {status === "closed" &&
                  (totalBought != null || hasSoldShares) && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {totalBought != null && (
                        <>
                          <Sensitive>
                            {formatNumber(totalBought, locale)}
                          </Sensitive>{" "}
                          {t.marketForecast.labels.bought.toLowerCase()}
                        </>
                      )}
                      {totalBought != null && hasSoldShares && " · "}
                      {hasSoldShares && (
                        <>
                          <Sensitive>
                            {formatNumber(totalSold, locale)}
                          </Sensitive>{" "}
                          {t.marketForecast.labels.sold.toLowerCase()}
                        </>
                      )}
                    </div>
                  )}
              </div>
            )}

            {initialValue != null && (
              <div>
                <div className="text-xs font-medium text-muted-foreground">
                  {t.marketForecast.labels.initialInvestment}
                </div>
                <div className="mt-0.5 font-medium text-foreground">
                  <Sensitive>
                    {displayInitialValue
                      ? formatCurrency(
                          displayInitialValue.value,
                          locale,
                          defaultCurrency,
                          displayInitialValue.currency,
                        )
                      : "-"}
                  </Sensitive>
                </div>
                {formattedOriginalInitialValue && (
                  <div className="text-xs font-normal text-muted-foreground">
                    <Sensitive>{formattedOriginalInitialValue}</Sensitive>
                  </div>
                )}
              </div>
            )}

            {pnl != null && (
              <div>
                <div className="text-xs font-medium text-muted-foreground">
                  {status === "open"
                    ? t.marketForecast.summary.unrealizedPnl
                    : t.marketForecast.labels.realizedPnl}
                </div>
                <div
                  className={cn(
                    "mt-0.5 font-medium",
                    pnl >= 0
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400",
                  )}
                >
                  <Sensitive>
                    {displayOpenPnl
                      ? formatGainLoss(
                          displayOpenPnl.value,
                          locale,
                          displayOpenPnl.currency,
                        )
                      : "-"}
                  </Sensitive>
                </div>
                {formattedOriginalOpenPnl && (
                  <div className="text-xs font-normal text-muted-foreground">
                    <Sensitive>{formattedOriginalOpenPnl}</Sensitive>
                  </div>
                )}
              </div>
            )}

            {averagePrice == null &&
              status === "closed" &&
              (totalBought != null || hasSoldShares) && (
                <div>
                  <div className="text-xs font-medium text-muted-foreground">
                    {t.marketForecast.labels.tradingActivity}
                  </div>
                  <div className="mt-0.5 text-foreground">
                    {totalBought != null && (
                      <>
                        <Sensitive>
                          {formatNumber(totalBought, locale)}
                        </Sensitive>{" "}
                        {t.marketForecast.labels.bought.toLowerCase()}
                      </>
                    )}
                    {totalBought != null && hasSoldShares && " · "}
                    {hasSoldShares && (
                      <>
                        <Sensitive>{formatNumber(totalSold, locale)}</Sensitive>{" "}
                        {t.marketForecast.labels.sold.toLowerCase()}
                      </>
                    )}
                  </div>
                </div>
              )}
          </div>
        )}

        {iframeSrc ? (
          <div className="-mx-4 overflow-hidden border-t border-border/40 bg-transparent">
            <iframe
              title="polymarket-market-iframe"
              src={iframeSrc}
              loading="lazy"
              className="block h-[360px] w-full rounded-none border-0 bg-transparent md:h-[420px]"
            />
          </div>
        ) : (
          <div className="flex min-h-[320px] items-center justify-center border border-dashed bg-background px-4 text-center text-sm text-muted-foreground">
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
  exchangeRates: ExchangeRates | null | undefined
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
  exchangeRates,
  entityName,
  isExpanded,
  onToggleDetails,
  isDarkMode,
}: MarketForecastPositionCardProps) {
  const { t } = useI18n()
  const [iconLoadFailed, setIconLoadFailed] = useState(false)
  const positionUrl = position.market_url?.trim() || null
  const iconUrl = position.icon_url?.trim() || null
  const currentValue = toFiniteNumber(position.current_value)
  const initialInvestment = getMarketForecastInitialInvestment(position)
  const calculatedPnl =
    status === "open"
      ? (toFiniteNumber(position.cash_pnl) ??
        (currentValue != null && initialInvestment != null
          ? currentValue - initialInvestment
          : null))
      : toFiniteNumber(position.realized_pnl)
  const pnl = calculatedPnl ?? 0
  const pct =
    status === "closed"
      ? calculatedPnl != null &&
        initialInvestment != null &&
        initialInvestment > 0
        ? (calculatedPnl / initialInvestment) * 100
        : null
      : (toFiniteNumber(position.percent_pnl) ??
        (calculatedPnl != null &&
        initialInvestment != null &&
        initialInvestment > 0
          ? (calculatedPnl / initialInvestment) * 100
          : null))
  const title = position.name || t.marketForecast.untitledMarket
  const shares = toFiniteNumber(position.size)
  const markPrice =
    toFiniteNumber(position.cur_price) ?? toFiniteNumber(position.price)
  const resolvedAt = position.end_date || position.updated_at || null
  const closedAt = position.closed_at || position.updated_at || null
  const positionValue =
    status === "closed" && initialInvestment != null
      ? initialInvestment + pnl
      : currentValue
  const sourceCurrency = position.currency?.trim()
  const sourceCurrencyDiffers = hasDifferentCurrency(
    sourceCurrency,
    defaultCurrency,
  )
  const displayValue =
    positionValue == null
      ? null
      : getCurrencyDisplayValue(
          positionValue,
          position.currency,
          defaultCurrency,
          exchangeRates,
        )
  const formattedOriginalValue =
    positionValue != null && sourceCurrency
      ? formatCurrency(positionValue, locale, defaultCurrency, sourceCurrency)
      : null
  const formattedConvertedValue =
    sourceCurrencyDiffers &&
    displayValue?.currency.toUpperCase() === defaultCurrency.toUpperCase()
      ? formatCurrency(displayValue.value, locale, defaultCurrency)
      : null
  const formattedShares =
    shares != null && shares > 0 ? formatNumber(shares, locale) : null
  const formattedMarkPrice =
    status === "open" && markPrice != null && sourceCurrency
      ? formatCurrency(markPrice, locale, defaultCurrency, sourceCurrency)
      : null

  useEffect(() => {
    setIconLoadFailed(false)
  }, [iconUrl])

  return (
    <Card
      className={cn(
        "overflow-hidden border-l-4 transition-all hover:shadow-sm",
        pnl < 0 && "border-l-red-600 dark:border-l-red-400",
      )}
      style={
        pnl < 0
          ? undefined
          : {
              borderLeftColor: getMarketForecastCardBorderColor(pnl, status),
            }
      }
    >
      <CardContent className="p-0">
        <div
          className="flex flex-col gap-3 p-4 transition-colors hover:bg-accent/40 sm:gap-4 lg:flex-row lg:items-start lg:justify-between"
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
              {iconUrl && !iconLoadFailed ? (
                <img
                  src={iconUrl}
                  alt=""
                  className="h-12 w-12 shrink-0 self-center rounded-xl border bg-muted object-cover"
                  onError={() => setIconLoadFailed(true)}
                />
              ) : (
                <div className="flex h-12 w-12 shrink-0 self-center items-center justify-center rounded-xl border bg-muted/50 text-primary">
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
                  {position.outcome && (
                    <Badge
                      variant="outline"
                      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1"
                    >
                      <Vote className="h-3.5 w-3.5" />
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

                <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs text-muted-foreground">
                  {(formattedShares || formattedMarkPrice) && (
                    <span className="inline-flex items-center gap-1">
                      {formattedShares && (
                        <Sensitive>{formattedShares}</Sensitive>
                      )}
                      {formattedShares && formattedMarkPrice && <span>×</span>}
                      {formattedMarkPrice && <span>{formattedMarkPrice}</span>}
                    </span>
                  )}
                  {status === "open" && resolvedAt && (
                    <MarketForecastDateBadge
                      value={resolvedAt}
                      locale={locale}
                      className="ml-2"
                    />
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

          <div className="flex w-full items-start justify-between gap-3 border-t border-border/50 pt-3 lg:w-fit lg:shrink-0 lg:items-center lg:justify-start lg:border-t-0 lg:pt-0">
            <div className="flex min-w-0 flex-1 items-center justify-between gap-3 text-sm lg:flex-none lg:grid lg:w-[220px] lg:min-w-0 lg:gap-1.5 lg:justify-normal lg:justify-items-end lg:text-right">
              {formattedOriginalValue && (
                <Sensitive>
                  <div className="text-base font-semibold">
                    <div>{formattedOriginalValue}</div>
                    {formattedConvertedValue && (
                      <div className="text-xs font-normal text-muted-foreground">
                        {formattedConvertedValue}
                      </div>
                    )}
                  </div>
                </Sensitive>
              )}

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
                <span>{pct != null ? formatPercentage(pct, locale) : "-"}</span>
              </div>

              {positionUrl && (
                <div className="hidden w-full lg:block lg:w-auto lg:text-right">
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
                exchangeRates={exchangeRates}
                isDarkMode={isDarkMode}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

function MarketForecastInvestmentContent() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { isLoading: financialLoading, positionsData } = useFinancialData()
  const { scrape, fetchingEntityState } = useEntityWorkflow()
  const { entities, settings, exchangeRates } = useAppContext()
  const { resolvedTheme } = useTheme()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
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
  const [isPnlLoading, setIsPnlLoading] = useState(false)
  const [isPnlExpanded, setIsPnlExpanded] = useState(false)
  const [loadedPnlAccountKey, setLoadedPnlAccountKey] = useState<string | null>(
    null,
  )
  const [isClosedLoading, setIsClosedLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initialFetchAttemptedIds = useRef(new Set<string>())

  const defaultCurrency = settings.general.defaultCurrency
  const isDarkMode = resolvedTheme === "dark"

  const polymarketEntities = useMemo(
    () =>
      entities.filter(
        entity =>
          entity.type === EntityType.MARKET_FORECAST_PLATFORM &&
          entity.status === EntityStatus.CONNECTED,
      ),
    [entities],
  )

  const polymarketEntityIds = useMemo(
    () => polymarketEntities.map(entity => entity.id),
    [polymarketEntities],
  )

  useEffect(() => {
    if (!__CONNECTIONS__ || financialLoading) return

    const fetchingEntityIds = new Set(fetchingEntityState.fetchingEntityIds)
    const entitiesToFetch = polymarketEntities.filter(
      entity =>
        entity.features.includes("POSITION") &&
        !entity.last_fetch?.POSITION?.trim() &&
        !initialFetchAttemptedIds.current.has(entity.id) &&
        !fetchingEntityIds.has(entity.id),
    )

    if (entitiesToFetch.length === 0) return

    entitiesToFetch.forEach(entity => {
      initialFetchAttemptedIds.current.add(entity.id)
    })

    void Promise.all(
      entitiesToFetch.map(entity =>
        scrape(entity, entity.features, {
          silent: true,
          avoidNewLogin: true,
        }),
      ),
    )
  }, [
    financialLoading,
    fetchingEntityState.fetchingEntityIds,
    polymarketEntities,
    scrape,
  ])

  const marketForecastAccountKey = useMemo(
    () =>
      polymarketEntities
        .flatMap(entity => (entity.accounts ?? []).map(account => account.id))
        .sort()
        .join("|"),
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

  const showEntityFilter = polymarketEntities.length > 1
  const showAccountFilter = accountToEntityMap.size > 1

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
    if (!isPnlExpanded || loadedPnlAccountKey === marketForecastAccountKey) {
      return
    }

    let cancelled = false

    const load = async () => {
      setIsPnlLoading(true)
      setMarketForecastPnlData(null)
      setError(null)

      const accountIds = polymarketEntities.flatMap(entity =>
        (entity.accounts ?? []).map(account => account.id),
      )

      try {
        const response = await getMarketForecastPnl(accountIds, "all")
        if (!cancelled) {
          setMarketForecastPnlData(response)
          setLoadedPnlAccountKey(marketForecastAccountKey)
        }
      } catch (err) {
        console.error("Error loading market forecast pnl data", err)
        if (!cancelled) {
          setMarketForecastPnlData(null)
          setError(t.common.unexpectedError)
        }
      } finally {
        if (!cancelled) {
          setIsPnlLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [
    isPnlExpanded,
    loadedPnlAccountKey,
    marketForecastAccountKey,
    polymarketEntities,
    t.common.unexpectedError,
  ])

  useEffect(() => {
    if (!isClosedVisible || marketForecastClosedPositionsData) {
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
      const value = toFiniteNumber(point.value)
      const convertedValue =
        value == null
          ? null
          : tryConvertCurrency(
              value,
              point.currency,
              defaultCurrency,
              exchangeRates,
            )

      if (convertedValue == null) return

      if (!existing || point.timestamp > existing.timestamp) {
        latestPointByAccountDay.set(compositeKey, {
          dayKey,
          timestamp: point.timestamp,
          value: convertedValue,
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
  }, [
    defaultCurrency,
    exchangeRates,
    filteredAccountIds,
    marketForecastPnlData,
  ])

  const summary = useMemo(() => {
    const openValue = sumMarketForecastValues(
      filteredOpenPositions,
      getPositionValue,
      defaultCurrency,
      exchangeRates,
    )
    const openInvestment = sumMarketForecastValues(
      filteredOpenPositions,
      position =>
        toFiniteNumber(position.initial_value) ??
        toFiniteNumber(position.current_value) ??
        0,
      defaultCurrency,
      exchangeRates,
    )
    const closedPnl = sumMarketForecastValues(
      filteredClosedPositions,
      position => toFiniteNumber(position.realized_pnl) ?? 0,
      defaultCurrency,
      exchangeRates,
    )
    const openPnl =
      openValue != null && openInvestment != null
        ? openValue - openInvestment
        : null

    return {
      openValue,
      openInvestment,
      openPnl,
      openPnlPercentage:
        openPnl != null && openInvestment != null && openInvestment > 0
          ? (openPnl / openInvestment) * 100
          : null,
      averageOpenValue:
        openValue != null && filteredOpenPositions.length > 0
          ? openValue / filteredOpenPositions.length
          : openValue === 0
            ? 0
            : null,
      closedPnl,
    }
  }, [
    filteredClosedPositions,
    filteredOpenPositions,
    defaultCurrency,
    exchangeRates,
  ])

  if (financialLoading) {
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
          {__CONNECTIONS__ && (
            <EntityRefreshDropdown
              entityType={EntityType.MARKET_FORECAST_PLATFORM}
            />
          )}
        </div>
      </div>

      {(showEntityFilter || showAccountFilter) && (
        <InvestmentFilters
          filteredEntities={polymarketEntities}
          selectedEntities={selectedEntities}
          onEntitiesChange={setSelectedEntities}
          walletOptions={accountOptions}
          selectedWallets={selectedAccounts}
          onWalletsChange={setSelectedAccounts}
          walletPlaceholder={t.transactions.selectAccounts}
          showEntityFilter={showEntityFilter}
          showWalletFilter={showAccountFilter}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="overflow-hidden">
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-muted-foreground">
                  {t.marketForecast.summary.openExposure}
                </p>
                <Sensitive>
                  <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums">
                    {summary.openValue != null
                      ? formatCompactCurrency(
                          summary.openValue,
                          locale,
                          defaultCurrency,
                        )
                      : "-"}
                  </div>
                </Sensitive>
              </div>
              <div className="rounded-full bg-primary/10 p-2 text-primary">
                <TrendingUp className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-5 space-y-2 border-t border-border/60 pt-3 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">
                  {t.marketForecast.summary.costBasis}
                </span>
                <Sensitive>
                  <span className="font-medium tabular-nums">
                    {summary.openInvestment != null
                      ? formatCurrency(
                          summary.openInvestment,
                          locale,
                          defaultCurrency,
                        )
                      : "-"}
                  </span>
                </Sensitive>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">
                  {t.marketForecast.summary.unrealizedPnl}
                </span>
                <Sensitive>
                  <span
                    className={cn(
                      "font-medium tabular-nums",
                      summary.openPnl == null
                        ? "text-muted-foreground"
                        : summary.openPnl >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400",
                    )}
                  >
                    {summary.openPnl != null
                      ? formatGainLoss(summary.openPnl, locale, defaultCurrency)
                      : "-"}
                    {summary.openPnlPercentage != null &&
                      ` (${formatPercentage(summary.openPnlPercentage, locale)})`}
                  </span>
                </Sensitive>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  {t.marketForecast.summary.openPositions}
                </p>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-4xl font-semibold leading-none tracking-tight tabular-nums">
                    {formatNumber(filteredOpenPositions.length, locale)}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {t.marketForecast.sections.positions}
                  </span>
                </div>
              </div>
              <div className="rounded-full bg-primary/10 p-2 text-primary">
                <BarChart3 className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border/60 pt-3 text-xs">
              <div>
                <div className="text-muted-foreground">
                  {t.marketForecast.summary.openExposure}
                </div>
                <Sensitive>
                  <div className="mt-1 font-medium tabular-nums">
                    {summary.openValue != null
                      ? formatCompactCurrency(
                          summary.openValue,
                          locale,
                          defaultCurrency,
                        )
                      : "-"}
                  </div>
                </Sensitive>
              </div>
              <div>
                <div className="text-muted-foreground">
                  {t.marketForecast.summary.averageExposure}
                </div>
                <Sensitive>
                  <div className="mt-1 font-medium tabular-nums">
                    {summary.averageOpenValue != null
                      ? formatCompactCurrency(
                          summary.averageOpenValue,
                          locale,
                          defaultCurrency,
                        )
                      : "-"}
                  </div>
                </Sensitive>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <MarketForecastPnlHistoryCard
        points={aggregatedPnlHistory}
        isLoading={isPnlLoading}
        error={marketForecastPnlData ? null : error}
        onExpandedChange={setIsPnlExpanded}
      />

      <section className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-lg font-bold">
              {t.marketForecast.sections.openTitle}
            </h2>
            <div className="text-sm text-muted-foreground">
              {t.marketForecast.sections.openDescription}
            </div>
          </div>
          <Button
            variant={isClosedVisible ? "default" : "outline"}
            size="sm"
            className="h-8 shrink-0 gap-1 px-2 text-xs sm:gap-2 sm:px-3 sm:text-sm"
            onClick={() => setIsClosedVisible(prev => !prev)}
          >
            <History className="h-4 w-4" />
            <span>
              {isClosedVisible
                ? t.investments.historicSection.toggleShort.hide
                : t.investments.historicSection.toggleShort.show}
            </span>
            {isClosedLoading && <LoadingSpinner size="sm" color="invert" />}
          </Button>
        </div>

        {filteredOpenPositions.length === 0 ? (
          <div className="flex flex-col items-center rounded-lg border border-dashed border-border bg-muted/20 px-6 py-10 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <TrendingUp className="h-6 w-6" />
            </div>
            <h3 className="font-semibold">
              {t.marketForecast.empty.openTitle}
            </h3>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              {t.marketForecast.empty.openDescription}
            </p>
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
                exchangeRates={exchangeRates}
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
        <section className="space-y-3">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">
                  {t.marketForecast.sections.closedTitle}
                </h2>
                {isClosedLoading && <LoadingSpinner size="sm" />}
              </div>
              <div className="text-sm text-muted-foreground">
                {t.marketForecast.sections.closedDescription}
              </div>
            </div>
            <div className="flex flex-wrap items-baseline gap-x-5 gap-y-2 border-t border-border/60 pt-3 sm:border-t-0 sm:pt-0">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold tracking-tight tabular-nums">
                  {marketForecastClosedPositionsData
                    ? formatNumber(filteredClosedPositions.length, locale)
                    : "-"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {t.marketForecast.summary.closedPositions}
                </span>
              </div>
              <div
                className="hidden h-6 w-px bg-border/70 sm:block"
                aria-hidden="true"
              />
              <div className="flex items-baseline gap-2">
                <Sensitive>
                  <span
                    className={cn(
                      "text-2xl font-semibold tracking-tight tabular-nums",
                      !marketForecastClosedPositionsData ||
                        summary.closedPnl == null
                        ? "text-muted-foreground"
                        : summary.closedPnl >= 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-red-600 dark:text-red-400",
                    )}
                  >
                    {marketForecastClosedPositionsData &&
                    summary.closedPnl != null
                      ? formatGainLoss(
                          summary.closedPnl,
                          locale,
                          defaultCurrency,
                        )
                      : "-"}
                  </span>
                </Sensitive>
                <span className="text-xs text-muted-foreground">
                  {t.marketForecast.summary.realizedPnl}
                </span>
              </div>
            </div>
          </div>
          {isClosedLoading ? (
            <div className="flex min-h-32 items-center justify-center border border-dashed border-border bg-muted/20">
              <LoadingSpinner size="md" />
            </div>
          ) : filteredClosedPositions.length === 0 ? (
            <div className="flex min-h-32 flex-col items-center justify-center border border-dashed border-border bg-muted/20 px-6 text-center">
              <History className="mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {t.common.noDataAvailable}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredClosedPositions.map(position => {
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
                    exchangeRates={exchangeRates}
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
              })}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function MarketForecastConnectionState() {
  const { t } = useI18n()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-[55vh] items-center justify-center px-6">
      <div className="flex max-w-md flex-col items-center text-center">
        <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          <TrendingUp className="h-7 w-7" />
        </div>
        <h1 className="text-2xl font-bold">
          {t.marketForecast.empty.connectionTitle}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {t.marketForecast.empty.connectionDescription}
        </p>
        <Button className="mt-6" onClick={() => navigate("/entities")}>
          <Link2 className="mr-2 h-4 w-4" />
          {t.entities.connect}
        </Button>
      </div>
    </div>
  )
}

export default function MarketForecastInvestmentPage() {
  const { entities, entitiesLoaded, isLoadingEntities } = useAppContext()

  if (!entitiesLoaded || isLoadingEntities) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const hasConnectedMarketForecastEntity = entities.some(
    entity =>
      entity.type === EntityType.MARKET_FORECAST_PLATFORM &&
      entity.status === EntityStatus.CONNECTED,
  )

  if (!hasConnectedMarketForecastEntity) {
    return <MarketForecastConnectionState />
  }

  return <MarketForecastInvestmentContent />
}
