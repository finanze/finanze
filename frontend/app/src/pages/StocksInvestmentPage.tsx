import React, { useMemo, useState, useRef, useCallback } from "react"
import { motion } from "framer-motion"
import { DataSource, type ExchangeRates } from "@/types"
import { useI18n, type Locale, type Translations } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { getColorForName, cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import {
  formatCurrency,
  formatPercentage,
  formatGainLoss,
} from "@/lib/formatters"
import {
  getStockAndFundPositions,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  convertCurrency,
  type StockFundPosition,
} from "@/utils/financialDataUtils"
import { ProductType, type StockDetail } from "@/types/position"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Pencil,
  Trash2,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
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
  } = useManualPositions()

  const stockDrafts = drafts as StockDraft[]

  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const filteredStockPositions = useMemo(() => {
    if (selectedEntities.length === 0) return positions
    return positions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [positions, selectedEntities])

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

  const formattedTotalValue = useMemo(
    () => formatCurrency(totalValue, locale, defaultCurrency),
    [totalValue, locale, defaultCurrency],
  )

  const sortedDisplayItems = useMemo(
    () =>
      [...displayItems].sort(
        (a, b) => (b.position.value || 0) - (a.position.value || 0),
      ),
    [displayItems],
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
            <Button variant="ghost" size="icon" onClick={navigateBack}>
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{t.common.stocksEtfs}</h1>
              <PinAssetButton assetId="stocks-etfs" />
            </div>
          </div>
          <ManualPositionsControls className="self-start sm:self-auto" />
        </div>
        <ManualPositionsUnsavedNotice />
      </motion.div>

      <motion.div variants={fadeListItem}>
        <InvestmentFilters
          entityOptions={entityOptions}
          selectedEntities={selectedEntities}
          onEntitiesChange={setSelectedEntities}
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
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
              <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {t.common.stocksEtfs}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="flex justify-between items-baseline">
                      <p className="text-2xl font-bold">
                        {formattedTotalValue}
                      </p>
                      {totalInitialInvestment > 0 &&
                        (() => {
                          const percentageValue =
                            ((totalValue - totalInitialInvestment) /
                              totalInitialInvestment) *
                            100
                          const sign = percentageValue >= 0 ? "+" : "-"
                          return (
                            <p
                              className={cn(
                                "text-sm font-medium",
                                percentageValue === 0
                                  ? "text-gray-500 dark:text-gray-400"
                                  : percentageValue > 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400",
                              )}
                            >
                              {sign}
                              {formatPercentage(
                                Math.abs(percentageValue),
                                locale,
                              )}
                            </p>
                          )
                        })()}
                    </div>
                    {totalInitialInvestment > 0 && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {t.dashboard.investedAmount}{" "}
                        {formatCurrency(
                          totalInitialInvestment,
                          locale,
                          defaultCurrency,
                        )}
                      </p>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {t.investments.numberOfAssets}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-2xl font-bold">
                      {sortedDisplayItems.length}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {sortedDisplayItems.length === 1
                        ? t.investments.asset
                        : t.investments.assets}
                    </p>
                  </CardContent>
                </Card>
              </div>
              <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
                <InvestmentDistributionChart
                  data={chartData}
                  title={t.common.distribution}
                  locale={locale}
                  currency={defaultCurrency}
                  hideLegend
                  containerClassName="overflow-visible w-full"
                  variant="bare"
                  onSliceClick={handleSliceClick}
                />
              </div>
            </div>

            <div className="space-y-4 pb-6">
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

                return (
                  <Card
                    key={item.key}
                    ref={el => {
                      if (identifier) {
                        itemRefs.current[identifier] = el
                      }
                    }}
                    className={cn(
                      "p-6 border-l-4 transition-colors",
                      highlightClass,
                    )}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 flex-wrap">
                          <h3 className="text-lg font-semibold">
                            {position.name}
                          </h3>
                          <div className="flex items-center gap-2 flex-wrap">
                            <button
                              type="button"
                              onClick={() => {
                                const entityObj = entities.find(
                                  entity => entity.name === position.entity,
                                )
                                const id = entityObj?.id || position.entity
                                setSelectedEntities(prev =>
                                  prev.includes(id) ? prev : [...prev, id],
                                )
                              }}
                              className={cn(
                                "px-2.5 py-0.5 rounded-full text-xs font-semibold transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary",
                                getColorForName(position.entity),
                              )}
                            >
                              {position.entity}
                            </button>
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
                                />
                              )}
                            {isDirty && (
                              <span className="text-[0.65rem] font-semibold text-blue-600 dark:text-blue-400">
                                {manualTranslate("management.unsavedChanges")}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 text-sm">
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.investments.symbol}:{" "}
                            </span>
                            <span className="font-medium">
                              {position.symbol}
                            </span>
                          </div>
                          {position.isin && (
                            <div>
                              <span className="text-gray-600 dark:text-gray-400">
                                {t.transactions.isin}:{" "}
                              </span>
                              <span className="font-medium">
                                {position.isin}
                              </span>
                            </div>
                          )}
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.investments.shares}:{" "}
                            </span>
                            <span className="font-medium">
                              {position.shares?.toLocaleString()}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.investments.price}:{" "}
                            </span>
                            <span className="font-medium">
                              {formatCurrency(
                                position.price,
                                locale,
                                position.currency,
                              )}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                        <div className="flex items-center gap-2 justify-end">
                          {position.formattedGainLossAmount && (
                            <span
                              className={cn(
                                "text-sm",
                                (position.gainLossAmount || 0) >= 0
                                  ? "text-green-500"
                                  : "text-red-500",
                              )}
                            >
                              {position.formattedGainLossAmount}
                            </span>
                          )}
                          <div className="text-xl font-semibold">
                            {position.formattedOriginalValue ||
                              position.formattedValue}
                          </div>
                        </div>
                        {position.currency !== defaultCurrency && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {position.formattedValue}
                          </div>
                        )}
                        <div className="text-sm text-gray-600 dark:text-gray-400">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfStocks.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.stocks.toLowerCase(),
                            )}
                        </div>
                        <div className="flex items-center gap-1 text-sm justify-end">
                          {position.change >= 0 ? (
                            <TrendingUp size={16} className="text-green-500" />
                          ) : (
                            <TrendingDown size={16} className="text-red-500" />
                          )}
                          <span
                            className={
                              position.change >= 0
                                ? "text-green-500"
                                : "text-red-500"
                            }
                          >
                            {position.change >= 0 ? "+" : ""}
                            {position.change.toFixed(2)}%
                          </span>
                        </div>
                        {showActions && (
                          <div className="flex items-center justify-end gap-2 pt-2">
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
                                  deleteByOriginalId(manualDraft.originalId)
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
