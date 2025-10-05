import React, { useMemo, useState, useRef, useCallback } from "react"
import { motion } from "framer-motion"
import { DataSource, EntityOrigin, type ExchangeRates } from "@/types"
import { useI18n, type Locale, type Translations } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { SourceBadge } from "@/components/ui/SourceBadge"
import { cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  convertCurrency,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  formatSnakeCaseToHuman,
} from "@/utils/financialDataUtils"
import { ProductType, type FactoringDetail } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ArrowLeft,
  Calendar,
  Percent,
  TrendingUp,
  Pencil,
  Trash2,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"
import {
  ManualPositionsManager,
  ManualPositionsControls,
  ManualPositionsUnsavedNotice,
  useManualPositions,
} from "@/components/manual/ManualPositionsManager"
import type { ManualPositionDraft } from "@/components/manual/manualPositionTypes"
import {
  mergeManualDisplayItems,
  type ManualDisplayItem,
} from "@/components/manual/manualDisplayUtils"
import type { Entity } from "@/types"
import { EntityBadge } from "@/components/ui/EntityBadge"

interface FactoringPosition extends Record<string, unknown> {
  id: string
  entryId?: string
  name: string
  entity: string
  entityId?: string | null
  entityOrigin: EntityOrigin | null
  convertedAmount: number
  convertedExpectedAmount: number | null
  formattedAmount: string
  formattedConvertedAmount: string
  formattedExpectedAmount: string | null
  convertedProfit: number | null
  formattedProfit: string | null
  profitabilityPct: number | null
  interest_rate: number
  gross_interest_rate: number
  maturity: string
  last_invest_date: string
  state: string
  type: string
  currency: string
  source?: DataSource | null
}

type FactoringDraft = ManualPositionDraft<FactoringDetail>
type DisplayFactoringItem = ManualDisplayItem<FactoringPosition, FactoringDraft>

interface FactoringViewContentProps {
  t: Translations
  locale: Locale
  navigateBack: () => void
  entityOptions: MultiSelectOption[]
  selectedEntities: string[]
  setSelectedEntities: React.Dispatch<React.SetStateAction<string[]>>
  positions: FactoringPosition[]
  entities: Entity[]
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
}

export default function FactoringInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all factoring positions
  const allFactoringPositions = useMemo<FactoringPosition[]>(() => {
    if (!positionsData?.positions) return []

    const factoring: FactoringPosition[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      const factoringProduct = entityPosition.products[ProductType.FACTORING]
      if (
        factoringProduct &&
        "entries" in factoringProduct &&
        factoringProduct.entries.length > 0
      ) {
        const entityName = entityPosition.entity?.name || "Unknown"
        const entityOrigin = entityPosition.entity?.origin ?? null

        factoringProduct.entries.forEach((factor: any) => {
          const convertedAmount = convertCurrency(
            factor.amount,
            factor.currency,
            settings.general.defaultCurrency,
            exchangeRates,
          )

          // Profitability provided as decimal (e.g. 0.1 = 10%)
          const profitabilityDecimal = !isNaN(factor.profitability)
            ? factor.profitability
            : null
          const rawProfit =
            profitabilityDecimal !== null
              ? factor.amount * profitabilityDecimal
              : null
          const expectedAtMaturity =
            rawProfit !== null ? factor.amount + rawProfit : null
          const convertedExpectedAmount =
            expectedAtMaturity !== null
              ? convertCurrency(
                  expectedAtMaturity,
                  factor.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const convertedProfit =
            rawProfit !== null
              ? convertCurrency(
                  rawProfit,
                  factor.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const profitabilityPct =
            profitabilityDecimal !== null ? profitabilityDecimal * 100 : null

          const entryId = factor.id ? String(factor.id) : undefined
          const source =
            (factor.source as DataSource | undefined) ?? DataSource.REAL

          factoring.push({
            ...(factor as FactoringPosition),
            entryId,
            entity: entityName,
            entityId: entityPosition.entity?.id,
            entityOrigin,
            convertedAmount,
            convertedExpectedAmount,
            formattedAmount: formatCurrency(
              factor.amount,
              locale,
              factor.currency,
            ),
            formattedConvertedAmount: formatCurrency(
              convertedAmount,
              locale,
              settings.general.defaultCurrency,
            ),
            formattedExpectedAmount: convertedExpectedAmount
              ? formatCurrency(
                  convertedExpectedAmount,
                  locale,
                  settings.general.defaultCurrency,
                )
              : null,
            convertedProfit,
            formattedProfit: convertedProfit
              ? formatCurrency(
                  convertedProfit,
                  locale,
                  settings.general.defaultCurrency,
                )
              : null,
            profitabilityPct,
            source,
          })
        })
      }
    })

    return factoring
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithFactoring = getEntitiesWithProductType(
      positionsData,
      ProductType.FACTORING,
    )
    return (
      entities
        ?.filter(entity => entitiesWithFactoring.includes(entity.id))
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
    <ManualPositionsManager asset="factoring">
      <FactoringViewContent
        t={t}
        locale={locale}
        navigateBack={() => navigate(-1)}
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        setSelectedEntities={setSelectedEntities}
        positions={allFactoringPositions}
        entities={entities ?? []}
        defaultCurrency={settings.general.defaultCurrency}
        exchangeRates={exchangeRates}
      />
    </ManualPositionsManager>
  )
}

function FactoringViewContent({
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
}: FactoringViewContentProps) {
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

  const factoringDrafts = drafts as FactoringDraft[]

  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const entityOriginMap = useMemo(() => {
    const map: Record<string, EntityOrigin | null> = {}
    entities.forEach(entity => {
      map[entity.id] = entity.origin ?? null
    })
    return map
  }, [entities])

  const filteredFactoringPositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return positions
    }
    return positions.filter(position => {
      if (!position.entityId) return false
      return selectedEntities.includes(position.entityId)
    })
  }, [positions, selectedEntities])

  const buildPositionFromDraft = useCallback(
    (draft: FactoringDraft): FactoringPosition => {
      const amount = Number(draft.amount ?? 0)
      const interestRate = Number(draft.interest_rate ?? 0)
      const grossInterestRate = Number(
        draft.gross_interest_rate ?? draft.interest_rate ?? 0,
      )
      const profitabilityDecimalRaw =
        draft.profitability != null ? Number(draft.profitability) : 0
      const hasProfitability =
        Number.isFinite(profitabilityDecimalRaw) &&
        profitabilityDecimalRaw !== 0
      const profitabilityDecimal = hasProfitability
        ? profitabilityDecimalRaw
        : 0

      const convertedAmount =
        exchangeRates && draft.currency !== defaultCurrency
          ? convertCurrency(
              amount,
              draft.currency,
              defaultCurrency,
              exchangeRates,
            )
          : amount

      const rawProfit = hasProfitability ? amount * profitabilityDecimal : null

      const convertedProfit =
        rawProfit !== null
          ? exchangeRates && draft.currency !== defaultCurrency
            ? convertCurrency(
                rawProfit,
                draft.currency,
                defaultCurrency,
                exchangeRates,
              )
            : rawProfit
          : null

      const expectedAtMaturity = rawProfit !== null ? amount + rawProfit : null

      const convertedExpectedAmount =
        expectedAtMaturity !== null
          ? exchangeRates && draft.currency !== defaultCurrency
            ? convertCurrency(
                expectedAtMaturity,
                draft.currency,
                defaultCurrency,
                exchangeRates,
              )
            : expectedAtMaturity
          : null

      const entryId = draft.originalId ?? (draft.id || draft.localId)
      const entityOrigin = entityOriginMap[draft.entityId] ?? null

      return {
        id: entryId,
        entryId,
        name: draft.name,
        entity: draft.entityName,
        entityId: draft.entityId,
        entityOrigin,
        convertedAmount,
        convertedExpectedAmount,
        formattedAmount: formatCurrency(amount, locale, draft.currency),
        formattedConvertedAmount: formatCurrency(
          convertedAmount,
          locale,
          defaultCurrency,
        ),
        formattedExpectedAmount:
          convertedExpectedAmount != null
            ? formatCurrency(convertedExpectedAmount, locale, defaultCurrency)
            : null,
        convertedProfit,
        formattedProfit:
          convertedProfit != null
            ? formatCurrency(convertedProfit, locale, defaultCurrency)
            : null,
        profitabilityPct: hasProfitability ? profitabilityDecimal * 100 : null,
        interest_rate: interestRate,
        gross_interest_rate: grossInterestRate,
        maturity: draft.maturity || "",
        last_invest_date: draft.last_invest_date || "",
        state: draft.state || "",
        type: draft.type || "",
        currency: draft.currency,
        source: DataSource.MANUAL,
      }
    },
    [exchangeRates, defaultCurrency, locale, entityOriginMap],
  )

  const displayItems = useMemo<DisplayFactoringItem[]>(
    () =>
      mergeManualDisplayItems({
        positions: filteredFactoringPositions,
        manualDrafts: factoringDrafts,
        getPositionOriginalId: position =>
          position.entryId ?? String(position.id),
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
        getPositionKey: position => position.entryId ?? String(position.id),
        mergeDraftMetadata: (position, draft) => {
          let updated = position
          let changed = false

          if (draft.entityId && draft.entityId !== position.entityId) {
            updated = {
              ...updated,
              entityId: draft.entityId,
              entity: draft.entityName,
              entityOrigin: entityOriginMap[draft.entityId] ?? null,
            }
            changed = true
          }
          const overrides: Partial<FactoringPosition> = {}

          if (draft.name && draft.name !== position.name) {
            overrides.name = draft.name
          }

          if (draft.state && draft.state !== position.state) {
            overrides.state = draft.state
          }

          if (draft.type && draft.type !== position.type) {
            overrides.type = draft.type
          }

          if (
            draft.last_invest_date &&
            draft.last_invest_date !== position.last_invest_date
          ) {
            overrides.last_invest_date = draft.last_invest_date
          }

          if (draft.maturity && draft.maturity !== position.maturity) {
            overrides.maturity = draft.maturity
          }

          if (Object.keys(overrides).length > 0) {
            updated = { ...updated, ...overrides }
            changed = true
          }

          const targetEntityId =
            draft.entityId ?? updated.entityId ?? position.entityId ?? null
          const desiredOrigin =
            targetEntityId != null
              ? (entityOriginMap[targetEntityId] ?? null)
              : null
          if (desiredOrigin !== updated.entityOrigin) {
            updated = { ...updated, entityOrigin: desiredOrigin }
            changed = true
          }

          return changed ? updated : position
        },
      }),
    [
      filteredFactoringPositions,
      factoringDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      entityOriginMap,
    ],
  )

  const displayPositions = useMemo(
    () => displayItems.map(item => item.position),
    [displayItems],
  )

  const chartData = useMemo(() => {
    const mappedPositions = displayPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.convertedAmount,
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [displayPositions])

  const totalValue = useMemo(
    () =>
      displayPositions.reduce(
        (sum, position) => sum + (position.convertedAmount || 0),
        0,
      ),
    [displayPositions],
  )

  const formattedTotalValue = useMemo(
    () => formatCurrency(totalValue, locale, defaultCurrency),
    [totalValue, locale, defaultCurrency],
  )

  const { weightedAverageInterest, weightedAverageProfitability, totalProfit } =
    useMemo(() => {
      if (displayPositions.length === 0) {
        return {
          weightedAverageInterest: 0,
          weightedAverageProfitability: 0,
          totalProfit: 0,
        }
      }

      let weightedInterestAcc = 0
      let weightedProfitabilityAcc = 0
      let profitAcc = 0

      displayPositions.forEach(position => {
        const weight = position.convertedAmount || 0
        weightedInterestAcc += (position.interest_rate || 0) * weight
        if (
          position.profitabilityPct !== null &&
          !Number.isNaN(position.profitabilityPct) &&
          weight
        ) {
          weightedProfitabilityAcc += position.profitabilityPct * weight
        }
        profitAcc += position.convertedProfit || 0
      })

      return {
        weightedAverageInterest:
          totalValue > 0 ? (weightedInterestAcc / totalValue) * 100 : 0,
        weightedAverageProfitability:
          totalValue > 0 ? weightedProfitabilityAcc / totalValue : 0,
        totalProfit: profitAcc,
      }
    }, [displayPositions, totalValue])

  const sortedDisplayItems = useMemo(
    () =>
      [...displayItems].sort(
        (a, b) =>
          (b.position.convertedAmount || 0) - (a.position.convertedAmount || 0),
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
              <h1 className="text-2xl font-bold">{t.common.factoring}</h1>
              <PinAssetButton assetId="factoring" />
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
              ProductType.FACTORING,
              "h-16 w-16",
              "text-gray-400 dark:text-gray-600",
            )}
            <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
              {selectedEntities.length > 0
                ? t.investments.noPositionsFound.replace(
                    "{type}",
                    t.common.factoring.toLowerCase(),
                  )
                : t.investments.noPositionsAvailable.replace(
                    "{type}",
                    t.common.factoring.toLowerCase(),
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
                      {t.dashboard.investedAmount}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-2xl font-bold">{formattedTotalValue}</p>
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
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {t.investments.weightedAverageInterest}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-2xl font-bold">
                      {weightedAverageInterest.toFixed(2)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {t.investments.annually}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                      {t.investments.expectedProfit}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      {formatCurrency(totalProfit, locale, defaultCurrency)}
                    </p>
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">
                      {weightedAverageProfitability.toFixed(2)}%
                      <span className="ml-1 text-gray-500 dark:text-gray-400">
                        {t.investments.profitability}
                      </span>
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
                const { position, manualDraft, isManual, isDirty, originalId } =
                  item

                if (originalId && isEntryDeleted(originalId)) {
                  return null
                }

                const identifier = position.name || item.key

                const percentageOfFactoring =
                  totalValue > 0
                    ? ((position.convertedAmount || 0) / totalValue) * 100
                    : 0

                const distributionEntry = chartData.find(
                  (entry: (typeof chartData)[number]) =>
                    entry.name === position.name,
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
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                          <h3 className="font-semibold text-lg">
                            {position.name}
                          </h3>
                          <div className="flex items-center gap-2 flex-wrap">
                            <EntityBadge
                              name={position.entity}
                              origin={position.entityOrigin}
                              className="text-xs"
                              title={position.entity}
                              onClick={() => {
                                const targetId =
                                  position.entityId ??
                                  entities.find(
                                    entity => entity.name === position.entity,
                                  )?.id ??
                                  position.entity
                                setSelectedEntities(prev =>
                                  targetId && prev.includes(targetId)
                                    ? prev
                                    : targetId
                                      ? [...prev, targetId]
                                      : prev,
                                )
                              }}
                            />
                            <Badge variant="default" className="text-xs">
                              {formatSnakeCaseToHuman(position.state)}
                            </Badge>
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

                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-600 dark:text-gray-400">
                          <div className="flex items-center gap-1">
                            <Percent size={14} />
                            <span>
                              <span className="text-green-600 dark:text-green-400 font-medium">
                                {(position.interest_rate * 100).toFixed(2)}%
                              </span>
                              {" / "}
                              <span className="text-blue-600 dark:text-neutral-500 font-medium">
                                {(position.gross_interest_rate * 100).toFixed(
                                  2,
                                )}
                                %
                              </span>
                              {" " + t.investments.gross}
                            </span>
                          </div>

                          <div className="flex items-center gap-1">
                            <Calendar size={14} />
                            <span>
                              {t.investments.maturity}:{" "}
                              {formatDate(position.maturity, locale)}
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500">
                          <div className="flex items-center gap-1">
                            <TrendingUp size={12} />
                            <span>
                              {t.investments.lastInvest}:{" "}
                              {formatDate(position.last_invest_date, locale)}
                            </span>
                          </div>
                          <span>
                            {t.investments.type}:{" "}
                            {formatSnakeCaseToHuman(position.type)}
                          </span>
                        </div>

                        {(position.formattedExpectedAmount ||
                          position.formattedProfit) && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-sm">
                            {position.formattedExpectedAmount && (
                              <div>
                                <span className="text-gray-600 dark:text-gray-400">
                                  {t.investments.expectedAtMaturity}:{" "}
                                </span>
                                <span className="font-medium text-green-600 dark:text-green-400">
                                  {position.formattedExpectedAmount}
                                </span>
                              </div>
                            )}
                            {position.formattedProfit && (
                              <div>
                                <span className="text-gray-600 dark:text-gray-400">
                                  {t.investments.profit}:{" "}
                                </span>
                                <span className="font-medium text-emerald-600 dark:text-emerald-400">
                                  {position.formattedProfit}
                                  {position.profitabilityPct !== null && (
                                    <span className="ml-1 text-xs text-emerald-500 dark:text-emerald-300">
                                      ({position.profitabilityPct.toFixed(2)}%)
                                    </span>
                                  )}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                        <div className="text-2xl font-bold">
                          {position.formattedAmount}
                        </div>
                        {position.currency !== defaultCurrency && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {position.formattedConvertedAmount}
                          </div>
                        )}
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-0.5">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfFactoring.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.factoring.toLowerCase(),
                            )}
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
                                } else if (originalId) {
                                  editByOriginalId(originalId)
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
                                } else if (originalId) {
                                  deleteByOriginalId(originalId)
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
