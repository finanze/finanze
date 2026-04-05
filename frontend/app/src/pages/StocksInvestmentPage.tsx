import React, { useEffect, useMemo, useState, useRef, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { DataSource, type ExchangeRates } from "@/types"
import { useI18n, type Locale, type Translations } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { getColorForName, cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatGainLoss } from "@/lib/formatters"
import {
  getStockAndFundPositions,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  convertCurrency,
  type StockFundPosition,
} from "@/utils/financialDataUtils"
import { ProductType, type StockDetail, EquityType } from "@/types/position"
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpDown,
  TrendingUp,
  TrendingDown,
  Pencil,
  Trash2,
  Layers,
  ChevronDown,
  ChartCandlestick,
  ExternalLink,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { getIssuerIconPath } from "@/utils/issuerIcons"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"
import {
  ManualPositionsManager,
  ManualPositionsControls,
  ManualPositionsUnsavedNotice,
  useManualPositions,
} from "@/components/manual/ManualPositionsManager"
import type { Entity } from "@/types"
import type { ManualPositionDraft } from "@/components/manual/manualPositionTypes"
import {
  mergeManualDisplayItems,
  type ManualDisplayItem,
} from "@/components/manual/manualDisplayUtils"
import { SourceBadge } from "@/components/ui/SourceBadge"

type StockPositionWithEntity = StockFundPosition & {
  entityId: string
  entryId?: string
  source?: DataSource | null
}

type StockDraft = ManualPositionDraft<StockDetail>
type DisplayStockItem = ManualDisplayItem<StockPositionWithEntity, StockDraft>

interface StocksViewContentProps {
  t: Translations
  locale: Locale
  navigateBack: () => void
  entityOptions: MultiSelectOption[]
  selectedEntities: string[]
  setSelectedEntities: React.Dispatch<React.SetStateAction<string[]>>
  positions: StockPositionWithEntity[]
  entities: Entity[]
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
}

function isMostlyWhiteLogo(image: HTMLImageElement): boolean {
  const sampleSize = 32
  const canvas = document.createElement("canvas")
  canvas.width = sampleSize
  canvas.height = sampleSize

  const context = canvas.getContext("2d", { willReadFrequently: true })
  if (!context) return false

  context.clearRect(0, 0, sampleSize, sampleSize)
  context.drawImage(image, 0, 0, sampleSize, sampleSize)

  const { data } = context.getImageData(0, 0, sampleSize, sampleSize)
  let opaquePixels = 0
  let whitePixels = 0

  for (let index = 0; index < data.length; index += 4) {
    const alpha = data[index + 3]
    if (alpha < 32) continue

    opaquePixels += 1

    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]
    const minChannel = Math.min(red, green, blue)
    const maxChannel = Math.max(red, green, blue)

    if (minChannel >= 235 && maxChannel - minChannel <= 15) {
      whitePixels += 1
    }
  }

  if (opaquePixels === 0) return false

  return whitePixels / opaquePixels >= 0.9
}

function StockPositionLogo({
  position,
  className: externalClassName,
  size = "md",
}: {
  position: StockPositionWithEntity
  className?: string
  size?: "sm" | "md"
}) {
  const sizeClasses = size === "sm" ? "h-5 w-5" : "h-9 w-9"
  const iconSize = size === "sm" ? "h-3 w-3" : "h-5 w-5"
  const tickerToken = position.symbol?.split(".")[0]?.trim()
  const issuerIcon = getIssuerIconPath(position.issuer)
  const sources =
    position.equityType === EquityType.ETF
      ? issuerIcon
        ? [issuerIcon]
        : []
      : [
          position.isin?.trim()
            ? `https://static.finanze.me/icons/ticker/${encodeURIComponent(position.isin.trim())}.png`
            : null,
          tickerToken
            ? `https://static.finanze.me/icons/ticker/${encodeURIComponent(tickerToken)}.png`
            : null,
        ].filter((value): value is string => Boolean(value))
  const [sourceIndex, setSourceIndex] = useState(0)
  const [shouldInvert, setShouldInvert] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const imageRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => {
    const root = document.documentElement
    const updateMode = () => {
      setIsDarkMode(root.classList.contains("dark"))
    }

    updateMode()

    const observer = new MutationObserver(updateMode)
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["class"],
    })

    return () => {
      observer.disconnect()
    }
  }, [])

  useEffect(() => {
    setSourceIndex(0)
    setShouldInvert(false)
    setLoaded(false)
  }, [sources.join("|")])

  const isStock = position.equityType === EquityType.STOCK
  const currentSrc = sources[sourceIndex]
  const fallback = (
    <div
      className={cn(
        sizeClasses,
        "bg-muted flex items-center justify-center shrink-0 self-center",
        "rounded-md",
        externalClassName,
      )}
    >
      <ChartCandlestick className={cn(iconSize, "text-muted-foreground")} />
    </div>
  )

  useEffect(() => {
    if (isDarkMode) {
      setShouldInvert(false)
      return
    }

    if (!isStock) {
      return
    }

    const image = imageRef.current
    if (!image || !image.complete || image.naturalWidth === 0) {
      return
    }

    try {
      setShouldInvert(isMostlyWhiteLogo(image))
    } catch {
      setShouldInvert(false)
    }
  }, [isDarkMode, isStock, currentSrc])

  if (!currentSrc) {
    return fallback
  }

  if (!loaded) {
    return (
      <>
        {fallback}
        <img
          src={currentSrc}
          alt=""
          crossOrigin={isStock ? "anonymous" : undefined}
          className="absolute h-0 w-0 opacity-0 pointer-events-none"
          onLoad={event => {
            const img = event.currentTarget
            if (img.naturalWidth <= 1 || img.naturalHeight <= 1) {
              setSourceIndex(prev => prev + 1)
              return
            }
            setLoaded(true)
            imageRef.current = img
            if (isStock && !isDarkMode) {
              try {
                setShouldInvert(isMostlyWhiteLogo(img))
              } catch {
                setShouldInvert(false)
              }
            }
          }}
          onError={() => {
            setSourceIndex(prev => prev + 1)
          }}
        />
      </>
    )
  }

  return (
    <img
      ref={imageRef}
      src={currentSrc}
      alt={
        position.equityType === EquityType.ETF
          ? position.issuer || position.name
          : position.isin || tickerToken || position.name
      }
      crossOrigin={isStock ? "anonymous" : undefined}
      className={cn(
        sizeClasses,
        "object-contain shrink-0 self-center",
        isStock
          ? cn("rounded-none", !isDarkMode && shouldInvert && "invert")
          : "rounded-md",
        externalClassName,
      )}
      onError={() => {
        setShouldInvert(false)
        setLoaded(false)
        setSourceIndex(prev => prev + 1)
      }}
    />
  )
}

export default function StocksInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  const allStockPositions = useMemo<StockPositionWithEntity[]>(() => {
    const allPositions = getStockAndFundPositions(
      positionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    )

    return allPositions
      .filter(position => position.type === "STOCK_ETF")
      .map(position => {
        const entityObj = entities?.find(e => e.name === position.entity)
        const entryId = (position as any).entryId ?? position.id
        const source = (position as any).source as DataSource | undefined
        return {
          ...(position as StockFundPosition),
          entityId: entityObj?.id || position.entity,
          entryId,
          source: source ?? DataSource.REAL,
        }
      }) as StockPositionWithEntity[]
  }, [
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
    entities,
  ])

  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithStocks = getEntitiesWithProductType(
      positionsData,
      ProductType.STOCK_ETF,
    )
    return (
      entities
        ?.filter(entity => entitiesWithStocks.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <ManualPositionsManager asset="stocks">
      <StocksViewContent
        t={t}
        locale={locale}
        navigateBack={() => navigate(-1)}
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        setSelectedEntities={setSelectedEntities}
        entities={entities ?? []}
        defaultCurrency={settings.general.defaultCurrency}
        positions={allStockPositions}
        exchangeRates={exchangeRates}
      />
    </ManualPositionsManager>
  )
}

function StocksViewContent({
  t,
  locale,
  navigateBack,
  entityOptions,
  selectedEntities,
  setSelectedEntities,
  positions,
  entities,
  defaultCurrency,
  exchangeRates,
}: StocksViewContentProps) {
  const {
    drafts,
    isEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    isEntryDeleted,
    translate: manualTranslate,
    isDraftDirty: manualIsDraftDirty,
    enterEditMode,
  } = useManualPositions()

  const stockDrafts = drafts as StockDraft[]

  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<
    "amount" | "relativeGain" | "absoluteGain"
  >("amount")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>(
    {},
  )
  const [equityTypeFilter, setEquityTypeFilter] = useState<
    "all" | "STOCK" | "ETF"
  >("all")

  const handleEquityTypeToggle = useCallback((type: "STOCK" | "ETF") => {
    setEquityTypeFilter(prev => (prev === type ? "all" : type))
  }, [])

  const toggleCardExpanded = useCallback((key: string) => {
    setExpandedCards(prev => ({ ...prev, [key]: !prev[key] }))
  }, [])

  const filteredStockPositions = useMemo(() => {
    let filtered = positions
    if (selectedEntities.length > 0) {
      filtered = filtered.filter(position =>
        selectedEntities.includes(position.entityId),
      )
    }
    if (equityTypeFilter !== "all") {
      filtered = filtered.filter(
        position => position.equityType === equityTypeFilter,
      )
    }
    return filtered
  }, [positions, selectedEntities, equityTypeFilter])

  const buildPositionFromDraft = useCallback(
    (draft: StockDraft): StockPositionWithEntity => {
      const shares = Number(draft.shares ?? 0)
      const resolvedAverageBuy =
        draft.average_buy_price != null
          ? draft.average_buy_price
          : shares > 0
            ? (draft.initial_investment ?? 0) / shares
            : 0
      const resolvedInitialInvestment =
        draft.initial_investment != null
          ? draft.initial_investment
          : resolvedAverageBuy * shares
      const resolvedMarketValue =
        draft.market_value != null
          ? draft.market_value
          : resolvedInitialInvestment

      const convertedValue =
        exchangeRates && draft.currency !== defaultCurrency
          ? convertCurrency(
              resolvedMarketValue,
              draft.currency,
              defaultCurrency,
              exchangeRates,
            )
          : resolvedMarketValue

      const gainLossAmount = resolvedMarketValue - resolvedInitialInvestment

      const convertedGainLoss =
        exchangeRates && draft.currency !== defaultCurrency
          ? convertCurrency(
              gainLossAmount,
              draft.currency,
              defaultCurrency,
              exchangeRates,
            )
          : gainLossAmount

      const entryId = draft.originalId ?? (draft.id || draft.localId)

      return {
        symbol: draft.ticker || draft.name,
        name: draft.name,
        portfolioName: null,
        assetType: null,
        shares,
        price: resolvedAverageBuy,
        value: convertedValue,
        originalValue: resolvedMarketValue,
        initialInvestment: resolvedInitialInvestment,
        currency: draft.currency,
        formattedValue: formatCurrency(convertedValue, locale, defaultCurrency),
        formattedOriginalValue: formatCurrency(
          resolvedMarketValue,
          locale,
          draft.currency,
        ),
        formattedInitialInvestment: formatCurrency(
          resolvedInitialInvestment,
          locale,
          draft.currency,
        ),
        type: "STOCK_ETF",
        change:
          resolvedInitialInvestment === 0 && resolvedMarketValue === 0
            ? 0
            : (resolvedMarketValue /
                (resolvedInitialInvestment || resolvedMarketValue || 1) -
                1) *
              100,
        entity: draft.entityName,
        percentageOfTotalVariableRent: 0,
        percentageOfTotalPortfolio: 0,
        id: entryId,
        isin: draft.isin || undefined,
        gainLossAmount: convertedGainLoss,
        formattedGainLossAmount:
          resolvedInitialInvestment > 0 && gainLossAmount !== 0
            ? formatGainLoss(convertedGainLoss, locale, defaultCurrency)
            : undefined,
        source: DataSource.MANUAL,
        entryId,
        entityId: draft.entityId,
        equityType: draft.type || null,
      }
    },
    [exchangeRates, defaultCurrency, locale],
  )

  const displayItems = useMemo<DisplayStockItem[]>(
    () =>
      mergeManualDisplayItems({
        positions: filteredStockPositions,
        manualDrafts: stockDrafts,
        getPositionOriginalId: position => position.entryId ?? position.id,
        getDraftOriginalId: draft => draft.originalId,
        getDraftLocalId: draft => draft.localId,
        buildPositionFromDraft,
        isManualPosition: position =>
          (position.source as DataSource | undefined) === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: draft =>
          selectedEntities.length === 0 ||
          selectedEntities.includes(draft.entityId),
        getPositionKey: position => position.entryId ?? position.id,
        mergeDraftMetadata: (position, draft) => {
          const needsEntityUpdate =
            draft.entityId && draft.entityId !== position.entityId
          const nextName = draft.name || position.name
          const nextSymbol = draft.ticker || draft.name || position.symbol
          if (
            !needsEntityUpdate &&
            nextName === position.name &&
            nextSymbol === position.symbol
          ) {
            return position
          }
          return {
            ...position,
            entityId: needsEntityUpdate ? draft.entityId : position.entityId,
            entity: needsEntityUpdate ? draft.entityName : position.entity,
            name: nextName,
            symbol: nextSymbol,
          }
        },
      }),
    [
      filteredStockPositions,
      stockDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
    ],
  )

  const displayPositions = useMemo(
    () => displayItems.map(item => item.position),
    [displayItems],
  )

  const chartData = useMemo<
    ReturnType<typeof calculateInvestmentDistribution>
  >(() => {
    const mappedPositions = displayPositions.map(position => ({
      ...position,
      symbol: position.name || position.symbol,
      currentValue: position.value,
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [displayPositions])

  const totalValue = useMemo(
    () =>
      displayPositions.reduce(
        (sum, position) => sum + (position.value || 0),
        0,
      ),
    [displayPositions],
  )

  const totalInitialInvestment = useMemo(() => {
    return displayPositions.reduce((sum, position) => {
      const initialBase =
        position.initialInvestment ??
        (position.shares || 0) * (position.price || 0)
      const converted =
        exchangeRates && position.currency !== defaultCurrency
          ? convertCurrency(
              initialBase,
              position.currency,
              defaultCurrency,
              exchangeRates,
            )
          : initialBase
      return sum + converted
    }, 0)
  }, [displayPositions, exchangeRates, defaultCurrency])

  const sortedDisplayItems = useMemo(
    () =>
      [...displayItems].sort((a, b) => {
        let aVal: number
        let bVal: number
        switch (sortBy) {
          case "relativeGain":
            aVal = a.position.change ?? 0
            bVal = b.position.change ?? 0
            break
          case "absoluteGain":
            aVal = a.position.gainLossAmount ?? 0
            bVal = b.position.gainLossAmount ?? 0
            break
          default:
            aVal = a.position.value || 0
            bVal = b.position.value || 0
        }
        return sortOrder === "desc" ? bVal - aVal : aVal - bVal
      }),
    [displayItems, sortBy, sortOrder],
  )

  const handleSliceClick = useCallback((slice: { name: string }) => {
    const ref = itemRefs.current[slice.name]
    if (ref) {
      ref.scrollIntoView({ behavior: "smooth", block: "center" })
      setHighlighted(slice.name)
      setTimeout(() => {
        setHighlighted(prev => (prev === slice.name ? null : prev))
      }, 1500)
    }
  }, [])

  return (
    <motion.div
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeListItem} className="space-y-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              className="p-1 h-8 w-8"
              onClick={navigateBack}
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{t.common.stocksEtfs}</h1>
              <PinAssetButton
                assetId="stocks-etfs"
                className="hidden md:inline-flex"
              />
            </div>
          </div>
          <ManualPositionsControls className="justify-center sm:justify-end" />
        </div>
        <ManualPositionsUnsavedNotice />
      </motion.div>

      <motion.div variants={fadeListItem}>
        <InvestmentFilters
          entityOptions={entityOptions}
          selectedEntities={selectedEntities}
          onEntitiesChange={setSelectedEntities}
          extraFilters={
            <>
              {(
                [
                  { value: "STOCK" as const, label: t.enums.equityType.STOCK },
                  { value: "ETF" as const, label: t.enums.equityType.ETF },
                ] as const
              ).map(option => {
                const isActive = equityTypeFilter === option.value
                return (
                  <button
                    key={option.value}
                    onClick={() => handleEquityTypeToggle(option.value)}
                    className={cn(
                      "px-2.5 py-1 text-xs font-semibold rounded-full border transition-all",
                      isActive
                        ? "bg-foreground text-background border-foreground"
                        : "bg-transparent text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground",
                    )}
                  >
                    {option.label}
                  </button>
                )
              })}
            </>
          }
        />
      </motion.div>

      <motion.div variants={fadeListItem}>
        {sortedDisplayItems.length === 0 ? (
          <Card className="p-14 text-center flex flex-col items-center gap-4">
            {getIconForAssetType(
              ProductType.STOCK_ETF,
              "h-16 w-16",
              "text-gray-400 dark:text-gray-600",
            )}
            <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
              {selectedEntities.length > 0
                ? t.investments.noPositionsFound.replace(
                    "{type}",
                    t.common.stocksEtfs.toLowerCase(),
                  )
                : t.investments.noPositionsAvailable.replace(
                    "{type}",
                    t.common.stocksEtfs.toLowerCase(),
                  )}
            </div>
          </Card>
        ) : (
          <div className="space-y-6">
            <Card className="-mx-6 rounded-none border-x-0">
              <CardContent className="pt-6">
                <InvestmentDistributionChart
                  data={chartData}
                  title={t.common.distribution}
                  locale={locale}
                  currency={defaultCurrency}
                  hideLegend
                  containerClassName="overflow-visible w-full"
                  variant="bare"
                  onSliceClick={handleSliceClick}
                  toggleConfig={{
                    activeView: "asset",
                    onViewChange: () => {},
                    options: [{ value: "asset", label: t.investments.byAsset }],
                  }}
                  badges={[
                    {
                      icon: <Layers className="h-3 w-3" />,
                      value: `${sortedDisplayItems.length} ${sortedDisplayItems.length === 1 ? t.investments.asset : t.investments.assets}`,
                    },
                  ]}
                  centerContent={{
                    rawValue: totalValue,
                    gainPercentage:
                      totalInitialInvestment > 0
                        ? ((totalValue - totalInitialInvestment) /
                            totalInitialInvestment) *
                          100
                        : undefined,
                    infoRows: [
                      {
                        label: t.dashboard.totalValue,
                        value: formatCurrency(
                          totalValue,
                          locale,
                          defaultCurrency,
                        ),
                      },
                      ...(totalInitialInvestment > 0
                        ? [
                            {
                              label: t.dashboard.investedAmount,
                              value: formatCurrency(
                                totalInitialInvestment,
                                locale,
                                defaultCurrency,
                              ),
                            },
                            {
                              label: t.investments.sortAbsoluteGain,
                              value: `${totalValue - totalInitialInvestment >= 0 ? "+" : ""}${formatCurrency(
                                totalValue - totalInitialInvestment,
                                locale,
                                defaultCurrency,
                              )}`,
                              valueClassName:
                                totalValue - totalInitialInvestment >= 0
                                  ? "text-green-500"
                                  : "text-red-500",
                            },
                          ]
                        : []),
                    ],
                  }}
                />
              </CardContent>
            </Card>

            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <ArrowUpDown size={14} />
                {t.investments.sortBy}
              </span>
              <div className="flex items-center bg-muted rounded-lg p-1">
                {(
                  [
                    { value: "amount", label: t.investments.sortAmount },
                    {
                      value: "relativeGain",
                      label: t.investments.sortRelativeGain,
                    },
                    {
                      value: "absoluteGain",
                      label: t.investments.sortAbsoluteGain,
                    },
                  ] as const
                ).map(option => (
                  <button
                    key={option.value}
                    onClick={() => setSortBy(option.value)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                      sortBy === option.value
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button
                onClick={() =>
                  setSortOrder(sortOrder === "asc" ? "desc" : "asc")
                }
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
                aria-label={
                  sortOrder === "asc" ? "Sort descending" : "Sort ascending"
                }
              >
                {sortOrder === "asc" ? (
                  <ArrowRight size={16} className="rotate-[-90deg]" />
                ) : (
                  <ArrowRight size={16} className="rotate-90" />
                )}
              </button>
            </div>

            <div className="space-y-4">
              {sortedDisplayItems.map(item => {
                const { position, manualDraft, isManual, isDirty } = item
                if (item.originalId && isEntryDeleted(item.originalId)) {
                  return null
                }

                const identifier = position.name || position.symbol || item.key

                const percentageOfStocks =
                  totalValue > 0
                    ? ((position.value || 0) / totalValue) * 100
                    : 0

                const distributionEntry = chartData.find(
                  entry => entry.name === (position.name || position.symbol),
                )
                const borderColor = distributionEntry?.color || "transparent"
                const isCardHighlighted = highlighted === identifier

                const highlightClass = isDirty
                  ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                  : isCardHighlighted
                    ? "ring-2 ring-offset-0 ring-primary"
                    : ""

                const showActions = isEditMode && isManual

                const isExpanded = expandedCards[item.key] ?? false

                const rawShares = position.shares
                const numericShares =
                  rawShares !== undefined && rawShares !== null
                    ? Number(rawShares)
                    : null
                const formattedShares =
                  numericShares !== null && !Number.isNaN(numericShares)
                    ? numericShares.toLocaleString(locale)
                    : null
                const sharesLabelSource = t.investments.shares || ""
                const sharesLabel = sharesLabelSource
                  ? sharesLabelSource.toLocaleLowerCase(locale)
                  : ""

                const rawPrice = position.price
                const formattedAvgBuyPrice =
                  rawPrice !== undefined && rawPrice !== null
                    ? formatCurrency(rawPrice, locale, position.currency)
                    : null

                const marketPricePerShare =
                  numericShares != null &&
                  numericShares > 0 &&
                  position.originalValue
                    ? Math.round(
                        (position.originalValue / numericShares) * 10000,
                      ) / 10000
                    : null
                const formattedMarketPrice =
                  marketPricePerShare != null
                    ? formatCurrency(
                        marketPricePerShare,
                        locale,
                        position.currency,
                      )
                    : null

                const eachLabelSource = t.common.each || ""
                const eachLabel = eachLabelSource
                  ? eachLabelSource.toLocaleLowerCase(locale)
                  : ""

                const infoSheetUrl =
                  position.equityType === EquityType.ETF
                    ? position.infoSheetUrl?.trim() || null
                    : null

                return (
                  <Card
                    key={item.key}
                    ref={el => {
                      if (identifier) {
                        itemRefs.current[identifier] = el
                      }
                    }}
                    className={cn(
                      "border-l-4 transition-all overflow-hidden",
                      highlightClass,
                    )}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div
                      className="relative flex items-start justify-between gap-3 p-4 cursor-pointer transition-colors hover:bg-accent/40"
                      onClick={e => {
                        if (
                          (e.target as HTMLElement).closest("[data-no-expand]")
                        )
                          return
                        toggleCardExpanded(item.key)
                      }}
                      onKeyDown={e => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          toggleCardExpanded(item.key)
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
                    >
                      <StockPositionLogo
                        position={position}
                        className="hidden sm:flex"
                      />
                      <div className="min-w-0 flex-1 space-y-1.5">
                        <h3 className="flex items-center gap-1.5 text-base sm:text-lg font-semibold leading-tight">
                          <StockPositionLogo
                            position={position}
                            size="sm"
                            className="sm:hidden"
                          />
                          <span>{position.name}</span>
                        </h3>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {position.equityType && (
                            <span
                              className={cn(
                                "text-[0.7rem] inline-flex items-center rounded-full px-2 py-0.5 font-medium",
                                position.equityType === EquityType.STOCK
                                  ? "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300"
                                  : "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
                              )}
                            >
                              {
                                t.enums.equityType[
                                  position.equityType as keyof typeof t.enums.equityType
                                ]
                              }
                            </span>
                          )}
                          {position.entity && (
                            <button
                              type="button"
                              data-no-expand
                              onClick={() => {
                                const entityObj = entities.find(
                                  entity => entity.name === position.entity,
                                )
                                const id = entityObj?.id || position.entity
                                if (!id) return
                                setSelectedEntities(prev =>
                                  prev.includes(id) ? prev : [...prev, id],
                                )
                              }}
                              className={cn(
                                "px-2 py-0.5 rounded-full text-xs font-semibold transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary",
                                getColorForName(position.entity),
                              )}
                            >
                              {position.entity}
                            </button>
                          )}
                          {position.portfolioName && (
                            <Badge variant="secondary" className="text-xs">
                              {position.portfolioName}
                            </Badge>
                          )}
                          {position.source &&
                            position.source !== DataSource.REAL && (
                              <SourceBadge
                                source={position.source}
                                title={t.management?.source}
                                className="text-[0.65rem]"
                                onClick={
                                  position.source === DataSource.MANUAL
                                    ? () => enterEditMode()
                                    : undefined
                                }
                              />
                            )}
                          {isDirty && (
                            <span className="text-[0.65rem] font-semibold text-blue-600 dark:text-blue-400">
                              {manualTranslate("management.unsavedChanges")}
                            </span>
                          )}
                        </div>
                        {(formattedShares || formattedMarketPrice) && (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            {formattedShares && <span>{formattedShares}</span>}
                            {formattedShares && formattedMarketPrice && (
                              <span>×</span>
                            )}
                            {formattedMarketPrice && (
                              <span>{formattedMarketPrice}</span>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <div className="text-right space-y-0.5">
                          <div className="text-base sm:text-lg font-semibold leading-tight">
                            {position.formattedOriginalValue ||
                              position.formattedValue}
                          </div>
                          {position.currency !== defaultCurrency && (
                            <div className="text-xs text-muted-foreground">
                              {position.formattedValue}
                            </div>
                          )}
                          <div
                            className={cn(
                              "flex items-center gap-1 text-sm justify-end mt-1",
                              position.change >= 0
                                ? "text-green-500"
                                : "text-red-500",
                            )}
                          >
                            {position.change >= 0 ? (
                              <TrendingUp size={14} />
                            ) : (
                              <TrendingDown size={14} />
                            )}
                            <span>{position.change.toFixed(2)}%</span>
                          </div>
                        </div>
                        <ChevronDown
                          className={cn(
                            "hidden sm:block h-4 w-4 text-muted-foreground transition-transform duration-200",
                            isExpanded && "rotate-180",
                          )}
                        />
                      </div>
                      <ChevronDown
                        className={cn(
                          "sm:hidden absolute bottom-3 right-3 h-4 w-4 text-muted-foreground transition-transform duration-200",
                          isExpanded && "rotate-180",
                        )}
                      />
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
                          <div className="px-4 pb-4">
                            <div className="border-t border-border/50 pt-3 space-y-3">
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 text-sm">
                                {(formattedShares || formattedMarketPrice) && (
                                  <div>
                                    <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                      {t.investments.shares}
                                    </div>
                                    <div className="flex items-center gap-1 text-foreground">
                                      {formattedShares && (
                                        <>
                                          <span>{formattedShares}</span>
                                          {sharesLabel && (
                                            <span className="text-muted-foreground">
                                              {sharesLabel}
                                            </span>
                                          )}
                                        </>
                                      )}
                                      {formattedShares &&
                                        formattedMarketPrice && (
                                          <span className="text-muted-foreground">
                                            ×
                                          </span>
                                        )}
                                      {formattedMarketPrice && (
                                        <>
                                          <span>{formattedMarketPrice}</span>
                                          {formattedShares && eachLabel && (
                                            <span className="text-muted-foreground">
                                              {eachLabel}
                                            </span>
                                          )}
                                        </>
                                      )}
                                    </div>
                                    {formattedAvgBuyPrice && (
                                      <div className="text-xs text-muted-foreground mt-0.5">
                                        {t.investments.averageBuyPrice}:{" "}
                                        {formattedAvgBuyPrice}
                                      </div>
                                    )}
                                  </div>
                                )}
                                {position.symbol?.trim() && (
                                  <div>
                                    <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                      Ticker
                                    </div>
                                    <div className="text-foreground font-mono text-xs">
                                      {position.symbol}
                                    </div>
                                  </div>
                                )}
                                {position.isin && (
                                  <div>
                                    <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                      ISIN
                                    </div>
                                    <div className="text-foreground font-mono text-xs">
                                      {position.isin}
                                    </div>
                                  </div>
                                )}
                                {position.equityType === EquityType.ETF &&
                                  position.issuer && (
                                    <div>
                                      <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                        {t.investments.issuer}
                                      </div>
                                      <div className="text-foreground text-sm">
                                        {position.issuer}
                                      </div>
                                    </div>
                                  )}
                                {position.formattedGainLossAmount && (
                                  <div>
                                    <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                      {t.investments.sortAbsoluteGain}
                                    </div>
                                    <div
                                      className={cn(
                                        "font-medium",
                                        position.change >= 0
                                          ? "text-green-500"
                                          : "text-red-500",
                                      )}
                                    >
                                      {position.formattedGainLossAmount}
                                    </div>
                                  </div>
                                )}
                                <div>
                                  <div className="text-xs text-muted-foreground font-medium mb-0.5">
                                    {t.investments.ofInvestmentType.replace(
                                      "{type}",
                                      t.common.stocks.toLowerCase(),
                                    )}
                                  </div>
                                  <div className="font-medium text-blue-600 dark:text-blue-400">
                                    {percentageOfStocks.toFixed(1)}%
                                  </div>
                                </div>
                              </div>
                              {infoSheetUrl && (
                                <a
                                  href={infoSheetUrl}
                                  target="_blank"
                                  rel="noreferrer noopener"
                                  data-no-expand
                                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline transition-colors"
                                >
                                  <ExternalLink className="h-3.5 w-3.5" />
                                  {t.investments.openInfoSheet}
                                </a>
                              )}
                              {showActions && (
                                <div
                                  className="flex items-center gap-2 pt-2 border-t border-border/30"
                                  data-no-expand
                                >
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="flex items-center gap-2"
                                    onClick={() => {
                                      if (manualDraft?.originalId) {
                                        editByOriginalId(manualDraft.originalId)
                                      } else if (manualDraft) {
                                        editByLocalId(manualDraft.localId)
                                      } else if (item.originalId) {
                                        editByOriginalId(item.originalId)
                                      }
                                    }}
                                  >
                                    <Pencil className="h-3.5 w-3.5" />
                                    {t.common.edit}
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-red-500 hover:text-red-600"
                                    onClick={() => {
                                      if (manualDraft?.originalId) {
                                        deleteByOriginalId(
                                          manualDraft.originalId,
                                        )
                                      } else if (manualDraft) {
                                        deleteByLocalId(manualDraft.localId)
                                      } else if (item.originalId) {
                                        deleteByOriginalId(item.originalId)
                                      }
                                    }}
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </Button>
                                </div>
                              )}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                )
              })}
            </div>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
