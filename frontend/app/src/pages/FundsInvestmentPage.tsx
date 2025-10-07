import React, { useMemo, useRef, useState, useCallback, useEffect } from "react"
import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getColorForName, getCurrencySymbol, cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
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
import {
  ProductType,
  AssetType,
  type FundDetail,
  type FundPortfolio,
  type PartialProductPositions,
  type UpdatePositionRequest,
} from "@/types/position"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Filter,
  FilterX,
  Pencil,
  Trash2,
  Plus,
  Save,
  X,
  AlertCircle,
  Lock,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { MultiSelect } from "@/components/ui/MultiSelect"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ManualPositionsManager,
  useManualPositions,
} from "@/components/manual/ManualPositionsManager"
import type { ManualPositionDraft } from "@/components/manual/manualPositionTypes"
import {
  mergeManualDisplayItems,
  type ManualDisplayItem,
} from "@/components/manual/manualDisplayUtils"
import { DataSource } from "@/types"
import { SourceBadge } from "@/components/ui/SourceBadge"
import { EntityBadge } from "@/components/ui/EntityBadge"
import { saveManualPositions } from "@/services/api"

type ManualPositionsContextValue = ReturnType<typeof useManualPositions>

// Local color classes for fund asset types (fund.assigns asset_type)
// Pastel background colors matching inner donut palette
const ASSET_CLASS_COLOR_BG: Record<AssetType, string> = {
  [AssetType.EQUITY]:
    "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  [AssetType.FIXED_INCOME]:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  [AssetType.MONEY_MARKET]:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  [AssetType.MIXED]:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  [AssetType.OTHER]:
    "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
}

const isAssetType = (value: string): value is AssetType => {
  return (Object.values(AssetType) as string[]).includes(value)
}

const getAssetTypeBadgeClass = (assetType?: AssetType | string | null) => {
  if (!assetType) return undefined
  if (!isAssetType(assetType)) return undefined
  return ASSET_CLASS_COLOR_BG[assetType]
}

type FundPositionWithEntity = StockFundPosition & {
  entityId: string
  entryId?: string
  source?: DataSource | null
}

type FundDraft = ManualPositionDraft<FundDetail>
type DisplayFundItem = ManualDisplayItem<FundPositionWithEntity, FundDraft>

type AggregatedManualSave = {
  products: PartialProductPositions
  isNewEntity: boolean
  newEntityName: string | null
  linkedPortfolioIds: Set<string>
}

interface ReadOnlyFundPortfolioItem {
  id: string
  name: string | null
  currency: string | null
  entityId: string
  entityName: string
  source: DataSource | null | undefined
}

interface FundsInvestmentPageContentProps {
  fundsContext: ManualPositionsContextValue
  portfolioContext: ManualPositionsContextValue
}

function FundsInvestmentPageContent({
  fundsContext,
  portfolioContext,
}: FundsInvestmentPageContentProps) {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const manual = fundsContext
  const portfolioManual = portfolioContext
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
  } = manual

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [selectedPortfolios, setSelectedPortfolios] = useState<string[]>([])

  // Get all fund positions
  const allFundPositions = useMemo<FundPositionWithEntity[]>(() => {
    const allPositions = getStockAndFundPositions(
      positionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    )

    return allPositions
      .filter(position => position.type === "FUND")
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
      }) as FundPositionWithEntity[]
  }, [
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
    entities,
  ])

  // Filter positions based on selected entities
  const filteredFundPositions = useMemo<FundPositionWithEntity[]>(() => {
    let base = allFundPositions
    if (selectedEntities.length > 0) {
      base = base.filter(p => selectedEntities.includes(p.entityId))
    }
    if (selectedPortfolios.length > 0) {
      base = base.filter(
        p => p.portfolioName && selectedPortfolios.includes(p.portfolioName),
      )
    }
    return base
  }, [allFundPositions, selectedEntities, selectedPortfolios])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithFunds = getEntitiesWithProductType(
      positionsData,
      ProductType.FUND,
    )
    const validIds = new Set(entitiesWithFunds)

    return (
      entities
        ?.filter(entity => {
          if (!entity.id || typeof entity.id !== "string") {
            return false
          }
          if (entity.id.startsWith("new-")) {
            return false
          }
          return validIds.has(entity.id)
        })
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  useEffect(() => {
    if (entityOptions.length === 0) {
      if (selectedEntities.length > 0) {
        setSelectedEntities([])
      }
      return
    }

    const allowed = new Set(entityOptions.map(option => option.value))
    setSelectedEntities(prev => {
      const next = prev.filter(id => allowed.has(id))
      return next.length === prev.length ? prev : next
    })
  }, [entityOptions])

  const portfolioOptions: MultiSelectOption[] = useMemo(() => {
    const names = new Set<string>()
    allFundPositions.forEach(p => {
      if (selectedEntities.length > 0 && !selectedEntities.includes(p.entityId))
        return
      if (p.portfolioName) names.add(p.portfolioName)
    })
    return Array.from(names)
      .sort()
      .map(name => ({ value: name, label: name }))
  }, [allFundPositions, selectedEntities])

  // Remove selected portfolios no longer available after entity filter changes
  useEffect(() => {
    setSelectedPortfolios(prev =>
      prev.filter(p => portfolioOptions.some(o => o.value === p)),
    )
  }, [portfolioOptions])

  const fundDrafts = drafts as FundDraft[]
  const manualPortfolioDrafts =
    portfolioManual.drafts as ManualPositionDraft<FundPortfolio>[]

  const readOnlyFundPortfolios = useMemo<ReadOnlyFundPortfolioItem[]>(() => {
    if (!positionsData?.positions) {
      return []
    }

    const list: ReadOnlyFundPortfolioItem[] = []

    Object.values(positionsData.positions).forEach(globalPosition => {
      const product = globalPosition.products[ProductType.FUND_PORTFOLIO] as
        | { entries?: FundPortfolio[] }
        | undefined
      const entries = product?.entries ?? []

      entries.forEach(portfolio => {
        const source = portfolio.source ?? DataSource.REAL
        if (source === DataSource.MANUAL) {
          return
        }

        const id =
          portfolio.id ||
          `${globalPosition.entity.id}-readonly-${
            portfolio.name?.trim() || "portfolio"
          }`

        list.push({
          id,
          name: portfolio.name ?? null,
          currency: portfolio.currency ?? null,
          entityId: globalPosition.entity.id,
          entityName: globalPosition.entity.name,
          source,
        })
      })
    })

    return list.sort((a, b) => {
      if (a.entityName !== b.entityName) {
        return a.entityName.localeCompare(b.entityName, locale, {
          sensitivity: "base",
        })
      }
      const nameA = a.name ?? ""
      const nameB = b.name ?? ""
      return nameA.localeCompare(nameB, locale, { sensitivity: "base" })
    })
  }, [positionsData, locale])

  const buildPositionFromDraft = useCallback(
    (draft: FundDraft): FundPositionWithEntity => {
      const shares = Number(draft.shares ?? 0)
      const averageBuy = draft.average_buy_price ?? 0
      const resolvedInitial =
        draft.initial_investment ?? (shares > 0 ? averageBuy * shares : 0)
      const resolvedMarket = draft.market_value ?? resolvedInitial

      const convertedValue =
        exchangeRates && draft.currency !== settings.general.defaultCurrency
          ? convertCurrency(
              resolvedMarket,
              draft.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          : resolvedMarket

      const gainLossAmount = resolvedMarket - resolvedInitial

      const convertedGainLoss =
        exchangeRates && draft.currency !== settings.general.defaultCurrency
          ? convertCurrency(
              gainLossAmount,
              draft.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          : gainLossAmount

      const entryId = draft.originalId ?? (draft.id || draft.localId)

      return {
        symbol: "",
        name: draft.name,
        portfolioName: draft.portfolio?.name ?? null,
        assetType: draft.asset_type ?? null,
        shares,
        price: averageBuy,
        value: convertedValue,
        originalValue: resolvedMarket,
        initialInvestment: resolvedInitial,
        currency: draft.currency,
        formattedValue: formatCurrency(
          convertedValue,
          locale,
          settings.general.defaultCurrency,
        ),
        formattedOriginalValue: formatCurrency(
          resolvedMarket,
          locale,
          draft.currency,
        ),
        formattedInitialInvestment: formatCurrency(
          resolvedInitial,
          locale,
          draft.currency,
        ),
        type: "FUND",
        change:
          resolvedMarket === 0 && resolvedInitial === 0
            ? 0
            : (resolvedMarket / (resolvedInitial || resolvedMarket || 1) - 1) *
              100,
        entity: draft.entityName,
        source: DataSource.MANUAL,
        isin: draft.isin,
        entryId,
        gainLossAmount: convertedGainLoss,
        formattedGainLossAmount:
          resolvedInitial > 0 && gainLossAmount !== 0
            ? formatGainLoss(
                convertedGainLoss,
                locale,
                settings.general.defaultCurrency,
              )
            : undefined,
        percentageOfTotalVariableRent: 0,
        percentageOfTotalPortfolio: 0,
        id: entryId,
        entityId: draft.entityId,
      }
    },
    [exchangeRates, settings.general.defaultCurrency, locale],
  )

  const displayItems = useMemo<DisplayFundItem[]>(
    () =>
      mergeManualDisplayItems({
        positions: filteredFundPositions,
        manualDrafts: fundDrafts,
        getPositionOriginalId: position => position.entryId ?? position.id,
        getDraftOriginalId: draft => draft.originalId,
        getDraftLocalId: draft => draft.localId,
        buildPositionFromDraft,
        isManualPosition: position =>
          (position.source as DataSource | undefined) === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: draft => {
          if (
            selectedEntities.length > 0 &&
            !selectedEntities.includes(draft.entityId)
          ) {
            return false
          }
          if (selectedPortfolios.length > 0) {
            return false
          }
          return true
        },
        getPositionKey: position => position.entryId ?? position.id,
        mergeDraftMetadata: (position, draft) => {
          if (draft.entityId && draft.entityId !== position.entityId) {
            return {
              ...position,
              entityId: draft.entityId,
              entity: draft.entityName,
            }
          }
          return position
        },
      }),
    [
      filteredFundPositions,
      fundDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      selectedPortfolios,
    ],
  )

  const displayPositions = useMemo(
    () => displayItems.map(item => item.position),
    [displayItems],
  )

  // Calculate chart data - map StockFundPosition to match chart expectations
  const chartData = useMemo(() => {
    const mappedPositions = displayPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.value,
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [displayPositions])

  // Inner donut (asset class split)
  const { assetTypeInnerData, assetTypeSplitPercentages } = useMemo(() => {
    if (!displayPositions.length) {
      return {
        assetTypeInnerData: [],
        assetTypeSplitPercentages: { equity: 0, fixed: 0 },
      }
    }

    const totals: Record<string, number> = {}
    let gapTotal = 0

    displayPositions.forEach(p => {
      const value = p.value || 0
      if (value <= 0) return
      if (!p.assetType) {
        gapTotal += value
        return
      }
      totals[p.assetType] = (totals[p.assetType] || 0) + value
    })

    const totalValue =
      Object.values(totals).reduce((acc, amount) => acc + amount, 0) + gapTotal

    const colorMap: Partial<Record<AssetType, string>> = {
      [AssetType.EQUITY]: "#ff7b7bff",
      [AssetType.FIXED_INCOME]: "#7db7ffff",
      [AssetType.MONEY_MARKET]: "#fde047ff",
      [AssetType.MIXED]: "#d8b4fcff",
      [AssetType.OTHER]: "#80ffacff",
    }

    const assetTypeLabels = (t.enums?.assetType || {}) as Record<string, string>

    const slices = Object.entries(totals).map(([rawType, value]) => ({
      name: assetTypeLabels[rawType] || rawType,
      value,
      color: colorMap[rawType as AssetType] || "#e5e7eb",
      percentage: totalValue > 0 ? (value / totalValue) * 100 : 0,
      rawType,
    }))

    if (gapTotal > 0) {
      slices.push({
        name: "",
        value: gapTotal,
        color: "transparent",
        percentage: totalValue > 0 ? (gapTotal / totalValue) * 100 : 0,
        rawType: "__GAP__",
        isGap: true,
      } as any)
    }

    const equityValue = totals[AssetType.EQUITY] || 0
    const fixedIncomeValue = totals[AssetType.FIXED_INCOME] || 0
    const moneyMarketValue = totals[AssetType.MONEY_MARKET] || 0
    const fixedAndMoneyMarketValue = fixedIncomeValue + moneyMarketValue
    const splitTotal = equityValue + fixedAndMoneyMarketValue

    const splitPercentages = {
      equity: splitTotal > 0 ? (equityValue / splitTotal) * 100 : 0,
      fixed: splitTotal > 0 ? (fixedAndMoneyMarketValue / splitTotal) * 100 : 0,
    }

    return {
      assetTypeInnerData: slices,
      assetTypeSplitPercentages: splitPercentages,
    }
  }, [displayPositions, t.enums])

  const totalInitialInvestment = useMemo(() => {
    return displayPositions.reduce((sum, position) => {
      const rawInitialInvestment =
        position.initialInvestment != null
          ? position.initialInvestment
          : (position.shares || 0) * (position.price || 0)

      const converted =
        exchangeRates && position.currency !== settings.general.defaultCurrency
          ? convertCurrency(
              rawInitialInvestment,
              position.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          : rawInitialInvestment

      return sum + converted
    }, 0)
  }, [displayPositions, exchangeRates, settings.general.defaultCurrency])

  const totalValue = useMemo(() => {
    return displayPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [displayPositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  const totalFundValue = useMemo(() => {
    return displayPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [displayPositions])

  // refs map for scrolling/highlighting
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const handleSliceClick = useCallback((slice: { name: string }) => {
    const ref = itemRefs.current[slice.name]
    if (ref) {
      ref.scrollIntoView({ behavior: "smooth", block: "center" })
      setHighlighted(slice.name)
      setTimeout(
        () => setHighlighted(prev => (prev === slice.name ? null : prev)),
        1500,
      )
    }
  }, [])

  const sortedDisplayItems = useMemo(
    () =>
      [...displayItems].sort(
        (a, b) => (b.position.value || 0) - (a.position.value || 0),
      ),
    [displayItems],
  )

  const showDraftList =
    portfolioManual.isEditMode &&
    (manualPortfolioDrafts.length > 0 || readOnlyFundPortfolios.length > 0)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const handleClearAllFilters = () => {
    setSelectedEntities([])
    setSelectedPortfolios([])
  }

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
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">
                {t.common.fundsInvestments}
              </h1>
              <PinAssetButton assetId="funds" />
            </div>
          </div>
          <FundsCombinedControls
            className="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-end"
            fundsContext={fundsContext}
            portfolioContext={portfolioContext}
          />
        </div>
        <CombinedUnsavedNotice
          fundsContext={fundsContext}
          portfolioContext={portfolioContext}
        />
      </motion.div>

      <motion.div
        variants={fadeListItem}
        className="pb-6 border-b border-gray-200 dark:border-gray-800"
      >
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Filter size={16} />
            <span>{t.transactions.filters}:</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 flex-1">
            <div className="w-full sm:max-w-xs">
              <MultiSelect
                options={entityOptions}
                value={selectedEntities}
                onChange={setSelectedEntities}
                placeholder={t.transactions.selectEntities}
              />
            </div>
            {portfolioOptions.length > 0 && (
              <div className="w-full sm:max-w-xs">
                <MultiSelect
                  options={portfolioOptions}
                  value={selectedPortfolios}
                  onChange={setSelectedPortfolios}
                  placeholder={(t.investments as any).portfolio}
                />
              </div>
            )}
          </div>
          {(selectedEntities.length > 0 || selectedPortfolios.length > 0) && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearAllFilters}
              className="flex items-center gap-2 self-start lg:self-auto"
            >
              <FilterX size={16} />
              {t.transactions.clear}
            </Button>
          )}
        </div>
      </motion.div>

      {showDraftList ? (
        <motion.div variants={fadeListItem}>
          <FundPortfolioDraftList
            manualDrafts={manualPortfolioDrafts}
            readOnlyPortfolios={readOnlyFundPortfolios}
            context={portfolioManual}
            isEditMode={portfolioManual.isEditMode}
          />
        </motion.div>
      ) : null}

      <motion.div variants={fadeListItem}>
        {sortedDisplayItems.length === 0 ? (
          <Card className="p-14 text-center flex flex-col items-center gap-4">
            {getIconForAssetType(
              ProductType.FUND,
              "h-16 w-16",
              "text-gray-400 dark:text-gray-600",
            )}
            <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
              {selectedEntities.length > 0
                ? t.investments.noPositionsFound.replace(
                    "{type}",
                    t.common.fundsInvestments.toLowerCase(),
                  )
                : t.investments.noPositionsAvailable.replace(
                    "{type}",
                    t.common.fundsInvestments.toLowerCase(),
                  )}
            </div>
          </Card>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
              {/* KPI vertical stack */}
              <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {t.common.fundsInvestments}
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
                              className={`text-sm font-medium ${percentageValue === 0 ? "text-gray-500 dark:text-gray-400" : percentageValue > 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
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
                          settings.general.defaultCurrency,
                        )}
                      </p>
                    )}
                  </CardContent>
                </Card>
                {assetTypeInnerData.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                        {t.enums?.kpis?.assetTypeSplit}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                      {(() => {
                        const equity = assetTypeSplitPercentages.equity || 0
                        const fixed = assetTypeSplitPercentages.fixed || 0
                        return (
                          <div>
                            <p className="text-2xl font-bold">
                              {Math.round(equity)}/{Math.round(fixed)}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                              {(t.enums?.assetType as any)?.[AssetType.EQUITY]}
                              {" / "}
                              {
                                (t.enums?.assetType as any)?.[
                                  AssetType.FIXED_INCOME
                                ]
                              }
                            </p>
                          </div>
                        )
                      })()}
                    </CardContent>
                  </Card>
                )}
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
              {/* Chart */}
              <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
                <InvestmentDistributionChart
                  data={chartData}
                  title={t.common.distribution}
                  locale={locale}
                  currency={settings.general.defaultCurrency}
                  hideLegend
                  containerClassName="overflow-visible w-full"
                  variant="bare"
                  onSliceClick={handleSliceClick}
                  innerData={assetTypeInnerData}
                />
              </div>
            </div>

            {/* Positions List (sorted desc by current value) */}
            <div className="space-y-4 pb-6">
              {sortedDisplayItems.map(item => {
                const { position, manualDraft, isManual, isDirty } = item
                const identifier = position.name || position.symbol || item.key

                const percentageOfFunds =
                  totalFundValue > 0
                    ? ((position.value || 0) / totalFundValue) * 100
                    : 0

                const distributionEntry = chartData.find(
                  c => c.name === (position.name || position.symbol),
                )
                const borderColor = distributionEntry?.color || "transparent"
                const isHighlighted = highlighted === identifier

                const highlightClass = isDirty
                  ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                  : isHighlighted
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
                                const candidateId =
                                  typeof position.entityId === "string"
                                    ? position.entityId
                                    : ""
                                if (
                                  !candidateId ||
                                  candidateId.startsWith("new-")
                                ) {
                                  return
                                }
                                const isValid = entityOptions.some(
                                  option => option.value === candidateId,
                                )
                                if (!isValid) {
                                  return
                                }
                                setSelectedEntities(prev =>
                                  prev.includes(candidateId)
                                    ? prev
                                    : [...prev, candidateId],
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
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedPortfolios(prev =>
                                    prev.includes(position.portfolioName!)
                                      ? prev
                                      : [...prev, position.portfolioName!],
                                  )
                                }}
                                className="text-xs inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 font-medium transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary"
                              >
                                {position.portfolioName}
                              </button>
                            )}
                            {position.assetType && (
                              <span
                                className={cn(
                                  "text-xs inline-flex items-center rounded-full px-2.5 py-0.5 font-medium",
                                  getAssetTypeBadgeClass(position.assetType) ||
                                    "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100",
                                )}
                              >
                                {(t.enums?.assetType as any)?.[
                                  position.assetType
                                ] || position.assetType}
                              </span>
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

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-4 text-sm">
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
                        {position.currency !==
                          settings.general.defaultCurrency && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {position.formattedValue}
                          </div>
                        )}
                        <div className="text-sm text-gray-600 dark:text-gray-400">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfFunds.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.funds.toLowerCase(),
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

export default function FundsInvestmentPage() {
  return (
    <ManualPositionsManager asset="funds">
      <FundsContextBridge />
    </ManualPositionsManager>
  )
}

function FundsContextBridge() {
  const fundsContext = useManualPositions()
  return (
    <ManualPositionsManager asset="fundPortfolios">
      <PortfolioContextBridge fundsContext={fundsContext} />
    </ManualPositionsManager>
  )
}

function PortfolioContextBridge({
  fundsContext,
}: {
  fundsContext: ManualPositionsContextValue
}) {
  const portfolioContext = useManualPositions()
  return (
    <FundsInvestmentPageContent
      fundsContext={fundsContext}
      portfolioContext={portfolioContext}
    />
  )
}

function FundsCombinedControls({
  className,
  fundsContext,
  portfolioContext,
}: {
  className?: string
  fundsContext: ManualPositionsContextValue
  portfolioContext: ManualPositionsContextValue
}) {
  const { refreshEntity } = useFinancialData()
  const { showToast } = useAppContext()
  const combinedIsEditMode =
    fundsContext.isEditMode || portfolioContext.isEditMode
  const combinedHasChanges =
    fundsContext.hasLocalChanges || portfolioContext.hasLocalChanges
  const combinedIsSaving = fundsContext.isSaving || portfolioContext.isSaving

  const handleEnterEdit = useCallback(() => {
    if (!fundsContext.isEditMode) {
      fundsContext.enterEditMode()
    }
    if (!portfolioContext.isEditMode) {
      portfolioContext.enterEditMode()
    }
  }, [fundsContext, portfolioContext])

  const handleAddPortfolioDraft = useCallback(() => {
    if (!portfolioContext.isEditMode) {
      portfolioContext.enterEditMode()
    }
    if (!fundsContext.isEditMode) {
      fundsContext.enterEditMode()
    }
    portfolioContext.beginCreate()
  }, [fundsContext, portfolioContext])

  const handleAddFundDraft = useCallback(() => {
    if (!fundsContext.isEditMode) {
      fundsContext.enterEditMode()
    }
    if (!portfolioContext.isEditMode) {
      portfolioContext.enterEditMode()
    }
    fundsContext.beginCreate()
  }, [fundsContext, portfolioContext])

  const handleCancel = useCallback(() => {
    if (portfolioContext.isEditMode) {
      portfolioContext.requestCancel()
    }
    if (fundsContext.isEditMode) {
      fundsContext.requestCancel()
    }
  }, [fundsContext, portfolioContext])

  const handleSave = useCallback(async () => {
    if (combinedIsSaving || !combinedHasChanges) {
      return
    }

    const fundPayloads = fundsContext.collectSavePayload()
    const portfolioPayloads = portfolioContext.collectSavePayload()

    const aggregated = new Map<string, AggregatedManualSave>()

    const ensureRecord = (entityId: string): AggregatedManualSave => {
      const existing = aggregated.get(entityId)
      if (existing) {
        return existing
      }
      const created: AggregatedManualSave = {
        products: {} as PartialProductPositions,
        isNewEntity: false,
        newEntityName: null,
        linkedPortfolioIds: new Set<string>(),
      }
      aggregated.set(entityId, created)
      return created
    }

    const updateMetadata = (
      record: AggregatedManualSave,
      entityId: string,
      payload: {
        isNewEntity: boolean
        newEntityName?: string | null
        entries: { draft: ManualPositionDraft<any> }[]
      },
    ) => {
      if (
        payload.isNewEntity ||
        payload.entries.some(entry => entry.draft.isNewEntity) ||
        (typeof entityId === "string" && entityId.startsWith("new-"))
      ) {
        record.isNewEntity = true
      }

      if (!record.newEntityName) {
        const candidateName =
          payload.newEntityName?.trim() ||
          payload.entries
            .map(entry =>
              (
                entry.draft.newEntityName ??
                entry.draft.entityName ??
                ""
              ).trim(),
            )
            .find(name => name.length > 0) ||
          null
        if (candidateName) {
          record.newEntityName = candidateName
        }
      }
    }

    fundPayloads.forEach((group, entityId) => {
      const record = ensureRecord(entityId)
      updateMetadata(record, entityId, {
        isNewEntity: group.isNewEntity,
        newEntityName: group.newEntityName,
        entries: group.entries as any,
      })

      group.entries.forEach(({ draft, payload }) => {
        const draftPortfolioId =
          typeof draft.portfolio?.id === "string"
            ? draft.portfolio.id.trim()
            : ""
        if (draftPortfolioId) {
          record.linkedPortfolioIds.add(draftPortfolioId)
        }
        const payloadPortfolioId =
          typeof payload.portfolio?.id === "string"
            ? payload.portfolio.id.trim()
            : ""
        if (payloadPortfolioId) {
          record.linkedPortfolioIds.add(payloadPortfolioId)
        }
      })

      const entries = group.entries.map(({ payload, draft }) => {
        const entry = { ...payload }
        if (!draft.originalId) {
          const nextId =
            typeof entry.id === "string" && entry.id.trim() !== ""
              ? entry.id.trim()
              : null
          return { ...entry, id: nextId }
        }
        return entry
      })

      ;(record.products as PartialProductPositions)[group.productType] = {
        entries: entries as any,
      } as any
    })

    portfolioPayloads.forEach((group, entityId) => {
      const record = ensureRecord(entityId)
      updateMetadata(record, entityId, {
        isNewEntity: group.isNewEntity,
        newEntityName: group.newEntityName,
        entries: group.entries as any,
      })

      const entries = group.entries.map(({ payload, draft }) => {
        const entry = { ...payload }
        if (!draft.originalId) {
          const resolvedId = typeof entry.id === "string" ? entry.id.trim() : ""
          if (!resolvedId || !record.linkedPortfolioIds.has(resolvedId)) {
            return { ...entry, id: null }
          }
          return { ...entry, id: resolvedId }
        }
        return entry
      })

      ;(record.products as PartialProductPositions)[group.productType] = {
        entries: entries as any,
      } as any
    })

    if (aggregated.size === 0) {
      fundsContext.handleExternalSaveSuccess()
      portfolioContext.handleExternalSaveSuccess()
      return
    }

    fundsContext.setSavingState(true)
    portfolioContext.setSavingState(true)

    try {
      const requestPromises: Promise<void>[] = []
      let missingNewEntityName = false

      aggregated.forEach(
        ({ products, isNewEntity, newEntityName }, entityId) => {
          const treatAsNewEntity =
            isNewEntity ||
            (typeof entityId === "string" && entityId.startsWith("new-"))

          const hasEntries = Object.values(products).some(product => {
            const entries = (product as { entries?: any[] } | undefined)
              ?.entries
            return Array.isArray(entries) && entries.length > 0
          })

          if (treatAsNewEntity && !hasEntries) {
            return
          }

          const requestPayload: UpdatePositionRequest = {
            products,
          }

          if (treatAsNewEntity) {
            const trimmedName = newEntityName?.trim()
            if (!trimmedName) {
              missingNewEntityName = true
              return
            }
            requestPayload.new_entity_name = trimmedName
          } else {
            requestPayload.entity_id = entityId
          }

          requestPromises.push(
            saveManualPositions(requestPayload).then(() => {
              if (requestPayload.entity_id) {
                return refreshEntity(requestPayload.entity_id)
              }
            }),
          )
        },
      )

      if (missingNewEntityName) {
        showToast(
          fundsContext.translate("management.manualPositions.toasts.saveError"),
          "error",
        )
        return
      }

      if (requestPromises.length === 0) {
        fundsContext.handleExternalSaveSuccess()
        portfolioContext.handleExternalSaveSuccess()
        return
      }

      await Promise.all(requestPromises)

      fundsContext.handleExternalSaveSuccess()
      portfolioContext.handleExternalSaveSuccess()
      showToast(
        fundsContext.translate("management.manualPositions.toasts.saveSuccess"),
        "success",
      )
    } catch (error) {
      console.error("Error saving manual funds and portfolios", error)
      showToast(
        fundsContext.translate("management.manualPositions.toasts.saveError"),
        "error",
      )
    } finally {
      fundsContext.setSavingState(false)
      portfolioContext.setSavingState(false)
    }
  }, [
    combinedHasChanges,
    combinedIsSaving,
    fundsContext,
    portfolioContext,
    refreshEntity,
    showToast,
  ])

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Button
        variant="outline"
        size="sm"
        onClick={handleAddPortfolioDraft}
        disabled={portfolioContext.manualEntities.length === 0}
        className="flex items-center gap-2"
      >
        <Plus className="h-3.5 w-3.5" />
        {portfolioContext.addLabel}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleAddFundDraft}
        disabled={fundsContext.manualEntities.length === 0}
        className="flex items-center gap-2"
      >
        <Plus className="h-3.5 w-3.5" />
        {fundsContext.addLabel}
      </Button>
      {combinedIsEditMode ? (
        <>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            disabled={combinedIsSaving}
            className="flex items-center gap-2"
          >
            <X className="h-3.5 w-3.5" />
            {fundsContext.cancelLabel}
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={combinedIsSaving || !combinedHasChanges}
            className="flex items-center gap-2"
          >
            <Save className="h-3.5 w-3.5" />
            {fundsContext.saveLabel}
          </Button>
        </>
      ) : (
        <Button
          variant="default"
          size="sm"
          onClick={handleEnterEdit}
          className="flex items-center gap-2"
        >
          <Pencil className="h-3.5 w-3.5" />
          {fundsContext.editLabel}
        </Button>
      )}
    </div>
  )
}

function CombinedUnsavedNotice({
  fundsContext,
  portfolioContext,
}: {
  fundsContext: ManualPositionsContextValue
  portfolioContext: ManualPositionsContextValue
}) {
  const shouldShow =
    (fundsContext.isEditMode || portfolioContext.isEditMode) &&
    (fundsContext.hasLocalChanges || portfolioContext.hasLocalChanges)

  if (!shouldShow) {
    return null
  }

  return (
    <div className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-100/70 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
      <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
      <div>{fundsContext.translate("management.unsavedChanges")}</div>
    </div>
  )
}

function FundPortfolioDraftList({
  manualDrafts,
  readOnlyPortfolios,
  context,
  isEditMode,
}: {
  manualDrafts: ManualPositionDraft<FundPortfolio>[]
  readOnlyPortfolios: ReadOnlyFundPortfolioItem[]
  context: ManualPositionsContextValue
  isEditMode: boolean
}) {
  const translate = context.translate
  const manualEntities = context.manualEntities

  const manualItems = useMemo(
    () =>
      [...manualDrafts].sort((a, b) => {
        if (a.entityName !== b.entityName) {
          return a.entityName.localeCompare(b.entityName, undefined, {
            sensitivity: "base",
          })
        }
        const nameA = a.name?.trim() || ""
        const nameB = b.name?.trim() || ""
        return nameA.localeCompare(nameB, undefined, {
          sensitivity: "base",
        })
      }),
    [manualDrafts],
  )

  const hasManual = manualItems.length > 0
  const hasReadOnly = readOnlyPortfolios.length > 0

  if (!isEditMode || (!hasManual && !hasReadOnly)) {
    return null
  }

  const renderSourceBadge = (source: DataSource | null | undefined) => {
    if (!source) return null
    if (source !== DataSource.MANUAL && source !== DataSource.SHEETS) {
      return null
    }

    return (
      <SourceBadge source={source} className="shrink-0">
        {translate(`enums.dataSource.${source}`)}
      </SourceBadge>
    )
  }

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-4 dark:border-primary/40 dark:bg-primary/10">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-primary dark:text-primary-200">
          {translate(
            "management.manualPositions.fundPortfolios.quickDrafts.title",
          )}
        </p>
        <p className="text-xs text-muted-foreground">
          {translate(
            "management.manualPositions.fundPortfolios.quickDrafts.description",
          )}
        </p>
      </div>
      <div className="mt-3 space-y-2">
        {manualItems.map(draft => {
          const name = draft.name?.trim() || translate("common.notAvailable")
          const currencyCode = draft.currency?.toUpperCase()
          const currencySymbol = currencyCode
            ? getCurrencySymbol(currencyCode)
            : null
          const source = draft.source ?? DataSource.MANUAL
          const isNew = !draft.originalId
          const isDirty =
            draft.originalId != null && context.isDraftDirty(draft)
          const entityInfo = manualEntities.find(
            item => item.id === draft.entityId,
          )
          const entityName =
            entityInfo?.name ||
            draft.entityName?.trim() ||
            translate("common.notAvailable")

          return (
            <div
              key={draft.localId}
              className="flex items-center justify-between gap-3 rounded-md border border-border/80 bg-background/80 px-3 py-2 text-sm dark:border-border/40 dark:bg-background/40"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-foreground truncate">
                    {name}
                  </span>
                  {isNew && (
                    <Badge variant="secondary" className="shrink-0">
                      {translate(
                        "management.manualPositions.shared.status.new",
                      )}
                    </Badge>
                  )}
                  {currencySymbol && (
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {currencySymbol}
                    </Badge>
                  )}
                  {!isNew && isDirty && (
                    <Badge
                      variant="outline"
                      className="shrink-0 border-blue-300 text-blue-600 dark:border-blue-500/40 dark:text-blue-300"
                    >
                      {translate(
                        "management.manualPositions.shared.status.updated",
                      )}
                    </Badge>
                  )}
                  {renderSourceBadge(source)}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {translate("management.manualPositions.shared.entity")}:
                  </span>
                  <EntityBadge
                    name={entityName}
                    origin={entityInfo?.origin}
                    className="shrink-0"
                  />
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => context.editByLocalId(draft.localId)}
                  aria-label={translate(
                    "management.manualPositions.fundPortfolios.quickDrafts.actions.edit",
                  )}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => context.deleteByLocalId(draft.localId)}
                  aria-label={translate(
                    "management.manualPositions.fundPortfolios.quickDrafts.actions.delete",
                  )}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )
        })}
        {hasReadOnly && (
          <div className="space-y-2 border-t border-border/60 pt-3 dark:border-border/30">
            {readOnlyPortfolios.map(portfolio => {
              const name =
                portfolio.name?.trim() || translate("common.notAvailable")
              const currencyCode = portfolio.currency?.toUpperCase()
              const currencySymbol = currencyCode
                ? getCurrencySymbol(currencyCode)
                : null
              const source = portfolio.source ?? DataSource.REAL
              const entityInfo = manualEntities.find(
                item => item.id === portfolio.entityId,
              )
              const entityName =
                entityInfo?.name ||
                portfolio.entityName?.trim() ||
                translate("common.notAvailable")

              return (
                <div
                  key={portfolio.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-border/70 bg-muted/40 px-3 py-2 text-sm dark:border-border/30 dark:bg-muted/20"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-foreground truncate">
                        {name}
                      </span>
                      {currencySymbol && (
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {currencySymbol}
                        </Badge>
                      )}
                      {renderSourceBadge(source)}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>
                        {translate("management.manualPositions.shared.entity")}:
                      </span>
                      <EntityBadge
                        name={entityName}
                        origin={entityInfo?.origin}
                        className="shrink-0"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Lock className="h-4 w-4" aria-hidden="true" />
                    <span className="sr-only">
                      {translate(
                        "management.manualPositions.fundPortfolios.quickDrafts.readOnly",
                      )}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
