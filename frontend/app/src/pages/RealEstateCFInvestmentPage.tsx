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
import { SourceBadge } from "@/components/ui/SourceBadge"
import { getColorForName, cn } from "@/lib/utils"
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
import { ProductType, type RealEstateCFDetail } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ArrowLeft,
  Calendar,
  Percent,
  Building,
  Pencil,
  Trash2,
  TrendingUp,
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

interface RealEstatePosition extends Record<string, unknown> {
  id: string
  entryId?: string
  name: string
  entity: string
  entityId?: string | null
  state: string
  investment_project_type: string
  type?: string | null
  interest_rate: number
  last_invest_date: string
  maturity: string
  currency: string
  convertedAmount: number
  convertedPendingAmount: number | null
  formattedAmount: string
  formattedConvertedAmount: string
  formattedPendingAmount: string | null
  formattedProfit: string | null
  profitabilityPct: number | null
  convertedProfit: number | null
  source?: DataSource | null
  business_type?: string | null
  formattedExpectedAtMaturity?: string | null
  convertedExpectedAtMaturity?: number | null
}

type RealEstateCFDraft = ManualPositionDraft<RealEstateCFDetail>
type DisplayRealEstateItem = ManualDisplayItem<
  RealEstatePosition,
  RealEstateCFDraft
>

interface RealEstateViewContentProps {
  t: Translations
  locale: Locale
  navigateBack: () => void
  entityOptions: MultiSelectOption[]
  selectedEntities: string[]
  setSelectedEntities: React.Dispatch<React.SetStateAction<string[]>>
  positions: RealEstatePosition[]
  entities: Entity[]
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
}

export default function RealEstateCFInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  const allRealEstatePositions = useMemo<RealEstatePosition[]>(() => {
    if (!positionsData?.positions) return []

    const realEstates: RealEstatePosition[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      const realEstateProduct =
        entityPosition.products[ProductType.REAL_ESTATE_CF]
      if (
        realEstateProduct &&
        "entries" in realEstateProduct &&
        realEstateProduct.entries.length > 0
      ) {
        const entityName = entityPosition.entity?.name || "Unknown"

        realEstateProduct.entries.forEach((realEstate: any) => {
          const investmentType =
            realEstate.investment_project_type ??
            realEstate.type ??
            realEstate.business_type ??
            ""
          const convertedAmount = convertCurrency(
            realEstate.amount,
            realEstate.currency,
            settings.general.defaultCurrency,
            exchangeRates,
          )

          const convertedPendingAmount = isNaN(realEstate.pending_amount)
            ? null
            : convertCurrency(
                realEstate.pending_amount,
                realEstate.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              )

          const profitabilityDecimal = !isNaN(realEstate.profitability)
            ? realEstate.profitability
            : null
          const rawProfit =
            profitabilityDecimal !== null
              ? realEstate.amount * profitabilityDecimal
              : null
          const rawExpectedAtMaturity =
            rawProfit !== null ? realEstate.amount + rawProfit : null
          const convertedExpectedAtMaturity =
            rawExpectedAtMaturity !== null
              ? convertCurrency(
                  rawExpectedAtMaturity,
                  realEstate.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const convertedProfit =
            rawProfit !== null
              ? convertCurrency(
                  rawProfit,
                  realEstate.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const profitabilityPct =
            profitabilityDecimal !== null ? profitabilityDecimal * 100 : null

          const entryId = realEstate.id ? String(realEstate.id) : undefined
          const source =
            (realEstate.source as DataSource | undefined) ?? DataSource.REAL

          realEstates.push({
            ...(realEstate as RealEstatePosition),
            entryId,
            investment_project_type: investmentType,
            entity: entityName,
            entityId: entityPosition.entity?.id,
            convertedAmount,
            convertedPendingAmount,
            formattedAmount: formatCurrency(
              realEstate.amount,
              locale,
              realEstate.currency,
            ),
            formattedConvertedAmount: formatCurrency(
              convertedAmount,
              locale,
              settings.general.defaultCurrency,
            ),
            formattedPendingAmount:
              convertedPendingAmount !== null
                ? formatCurrency(
                    convertedPendingAmount,
                    locale,
                    settings.general.defaultCurrency,
                  )
                : null,
            convertedExpectedAtMaturity,
            formattedExpectedAtMaturity:
              convertedExpectedAtMaturity !== null
                ? formatCurrency(
                    convertedExpectedAtMaturity,
                    locale,
                    settings.general.defaultCurrency,
                  )
                : null,
            convertedProfit,
            formattedProfit:
              convertedProfit !== null
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

    return realEstates
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithRealEstate = getEntitiesWithProductType(
      positionsData,
      ProductType.REAL_ESTATE_CF,
    )
    return (
      entities
        ?.filter(entity => entitiesWithRealEstate.includes(entity.id))
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
    <ManualPositionsManager asset="realEstateCf">
      <RealEstateViewContent
        t={t}
        locale={locale}
        navigateBack={() => navigate(-1)}
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        setSelectedEntities={setSelectedEntities}
        positions={allRealEstatePositions}
        entities={entities ?? []}
        defaultCurrency={settings.general.defaultCurrency}
        exchangeRates={exchangeRates}
      />
    </ManualPositionsManager>
  )
}

function RealEstateViewContent({
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
}: RealEstateViewContentProps) {
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

  const realEstateDrafts = drafts as RealEstateCFDraft[]

  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const filteredRealEstatePositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return positions
    }
    return positions.filter(position => {
      if (!position.entityId) return false
      return selectedEntities.includes(position.entityId)
    })
  }, [positions, selectedEntities])

  const investmentStateLabels =
    (t.investments.states as Record<string, string> | undefined) ?? undefined
  const investmentProjectTypeLabels =
    (t.investments.projectTypes as Record<string, string> | undefined) ??
    undefined

  const translateState = (value?: string | null) => {
    if (!value) return ""
    const normalized = value.toUpperCase()
    return investmentStateLabels?.[normalized] ?? formatSnakeCaseToHuman(value)
  }

  const translateProjectType = (value?: string | null) => {
    if (!value) return ""
    const normalized = value.toUpperCase()
    return (
      investmentProjectTypeLabels?.[normalized] ?? formatSnakeCaseToHuman(value)
    )
  }

  const buildPositionFromDraft = useCallback(
    (draft: RealEstateCFDraft): RealEstatePosition => {
      const amount = Number(draft.amount ?? 0)
      const pendingAmountRaw =
        draft.pending_amount != null ? Number(draft.pending_amount) : amount
      const pendingAmount = Number.isFinite(pendingAmountRaw)
        ? pendingAmountRaw
        : amount
      const interestRate = Number(draft.interest_rate ?? 0)
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

      const convertedPendingAmount =
        exchangeRates && draft.currency !== defaultCurrency
          ? convertCurrency(
              pendingAmount,
              draft.currency,
              defaultCurrency,
              exchangeRates,
            )
          : pendingAmount

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

      const rawExpectedAtMaturity =
        rawProfit !== null ? amount + rawProfit : null

      const convertedExpectedAtMaturity =
        rawExpectedAtMaturity !== null
          ? exchangeRates && draft.currency !== defaultCurrency
            ? convertCurrency(
                rawExpectedAtMaturity,
                draft.currency,
                defaultCurrency,
                exchangeRates,
              )
            : rawExpectedAtMaturity
          : null

      const entryId = draft.originalId ?? (draft.id || draft.localId)

      return {
        id: entryId,
        entryId,
        name: draft.name,
        entity: draft.entityName,
        entityId: draft.entityId,
        state: draft.state,
        investment_project_type: draft.type || draft.business_type || "",
        type: draft.type ?? null,
        interest_rate: interestRate,
        last_invest_date: draft.last_invest_date || "",
        maturity: draft.maturity || "",
        currency: draft.currency,
        convertedAmount,
        convertedPendingAmount,
        formattedAmount: formatCurrency(amount, locale, draft.currency),
        formattedConvertedAmount: formatCurrency(
          convertedAmount,
          locale,
          defaultCurrency,
        ),
        formattedPendingAmount:
          convertedPendingAmount !== null
            ? formatCurrency(convertedPendingAmount, locale, defaultCurrency)
            : null,
        formattedProfit:
          convertedProfit !== null
            ? formatCurrency(convertedProfit, locale, defaultCurrency)
            : null,
        profitabilityPct:
          rawProfit !== null ? profitabilityDecimal * 100 : null,
        convertedProfit,
        source: DataSource.MANUAL,
        business_type: draft.business_type ?? null,
        formattedExpectedAtMaturity:
          convertedExpectedAtMaturity !== null
            ? formatCurrency(
                convertedExpectedAtMaturity,
                locale,
                defaultCurrency,
              )
            : null,
        convertedExpectedAtMaturity,
      }
    },
    [exchangeRates, defaultCurrency, locale],
  )

  const displayItems = useMemo<DisplayRealEstateItem[]>(
    () =>
      mergeManualDisplayItems({
        positions: filteredRealEstatePositions,
        manualDrafts: realEstateDrafts,
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
            }
            changed = true
          }

          const overrides: Partial<RealEstatePosition> = {}

          if (draft.name && draft.name !== position.name) {
            overrides.name = draft.name
          }

          if (draft.state && draft.state !== position.state) {
            overrides.state = draft.state
          }

          const draftInvestmentType = draft.type || draft.business_type || ""
          if (
            draftInvestmentType &&
            draftInvestmentType !== position.investment_project_type
          ) {
            overrides.investment_project_type = draftInvestmentType
          }

          if (draft.type && draft.type !== position.type) {
            overrides.type = draft.type
          }

          if (
            draft.business_type &&
            draft.business_type !== position.business_type
          ) {
            overrides.business_type = draft.business_type
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

          return changed ? updated : position
        },
      }),
    [
      filteredRealEstatePositions,
      realEstateDrafts,
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

  const chartData = useMemo(() => {
    const mappedPositions = displayPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue:
        position.convertedPendingAmount ?? position.convertedAmount ?? 0,
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [displayPositions])

  const totalValue = useMemo(
    () =>
      displayPositions.reduce(
        (sum, position) => sum + (position.convertedPendingAmount || 0),
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
        const weight = position.convertedPendingAmount || 0
        weightedInterestAcc += (position.interest_rate || 0) * weight
        if (position.profitabilityPct !== null && weight) {
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
          (b.position.convertedPendingAmount || 0) -
          (a.position.convertedPendingAmount || 0),
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
              <h1 className="text-2xl font-bold">{t.common.realEstateCf}</h1>
              <PinAssetButton assetId="real-estate-cf" />
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
              ProductType.REAL_ESTATE_CF,
              "h-16 w-16",
              "text-gray-400 dark:text-gray-600",
            )}
            <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
              {selectedEntities.length > 0
                ? t.investments.noPositionsFound.replace(
                    "{type}",
                    t.common.realEstateCf.toLowerCase(),
                  )
                : t.investments.noPositionsAvailable.replace(
                    "{type}",
                    t.common.realEstateCf.toLowerCase(),
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
                      {t.investments.interest} {t.investments.annually}
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
                      <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
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

                const percentageOfRealEstate =
                  totalValue > 0
                    ? ((position.convertedPendingAmount || 0) / totalValue) *
                      100
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

                const entityButton = (
                  <button
                    key="entity"
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
                )

                const rawProjectType =
                  position.investment_project_type ||
                  position.business_type ||
                  position.type ||
                  ""

                const summaryItems: React.ReactNode[] = [
                  entityButton,
                  <div key="type" className="flex items-center gap-1">
                    <Building size={14} />
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {translateProjectType(rawProjectType)}
                    </span>
                  </div>,
                  <div key="interest" className="flex items-center gap-1">
                    <Percent size={14} />
                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                      {(position.interest_rate * 100).toFixed(2)}%
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {t.investments.annually}
                    </span>
                  </div>,
                ]

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
                            <Badge variant="default" className="text-xs">
                              {translateState(position.state)}
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

                        <div className="flex flex-wrap items-center gap-1 text-sm text-gray-600 dark:text-gray-400">
                          {summaryItems.map((item, index) => (
                            <React.Fragment key={index}>
                              {index > 0 && (
                                <span className="text-gray-400 dark:text-gray-500">
                                  •
                                </span>
                              )}
                              {item}
                            </React.Fragment>
                          ))}
                        </div>

                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500">
                          <div className="flex items-center gap-2">
                            <TrendingUp
                              size={14}
                              className="text-gray-400 dark:text-gray-500"
                            />
                            <span className="text-gray-500 dark:text-gray-400">
                              {t.investments.investment}
                            </span>
                            <span className="text-gray-900 dark:text-gray-100">
                              {formatDate(position.last_invest_date, locale)}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <Calendar
                              size={14}
                              className="text-gray-400 dark:text-gray-500"
                            />
                            <span className="text-gray-500 dark:text-gray-400">
                              {t.investments.maturity}
                            </span>
                            <span className="text-gray-900 dark:text-gray-100">
                              {formatDate(position.maturity, locale)}
                            </span>
                          </div>
                        </div>
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
                        {(position.formattedPendingAmount ||
                          position.formattedProfit) && (
                          <div className="space-y-1 text-sm">
                            {position.formattedPendingAmount && (
                              <div className="flex flex-wrap items-center gap-1 sm:justify-end">
                                <span className="text-gray-600 dark:text-gray-400">
                                  {t.investments.pending}
                                </span>
                                <span className="font-medium text-orange-600 dark:text-orange-400">
                                  {position.formattedPendingAmount}
                                </span>
                              </div>
                            )}
                            {position.formattedProfit && (
                              <div className="flex flex-wrap items-center gap-1 sm:justify-end">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.investments.expected}
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
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-0.5">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfRealEstate.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.realEstateCf.toLowerCase(),
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
