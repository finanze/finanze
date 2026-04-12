import React, { useMemo, useState, useRef, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { DataSource, EntityOrigin, type ExchangeRates } from "@/types"
import { useI18n, type Locale, type Translations } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  convertCurrency,
  calculateInvestmentDistribution,
} from "@/utils/financialDataUtils"
import { ProductType, type Deposit } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpDown,
  Calendar,
  ChevronDown,
  Layers,
  Percent,
  TrendingUp,
  Pencil,
  Trash2,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { useNavigate } from "react-router-dom"
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
import { EntityBadge } from "@/components/ui/EntityBadge"

interface DepositPosition {
  id: string
  entryId?: string
  name: string
  entity: string
  entityId?: string | null
  entityOrigin: EntityOrigin | null
  amount: number
  convertedAmount: number
  expectedInterests: number | null
  convertedExpectedAmount: number | null
  formattedAmount: string
  formattedConvertedAmount: string
  formattedExpectedAmount: string | null
  interest_rate: number
  maturity: string
  creation: string
  currency: string
  source?: DataSource | null
}

type DepositDraft = ManualPositionDraft<Deposit>
type DisplayDepositItem = ManualDisplayItem<DepositPosition, DepositDraft>

interface DepositsViewContentProps {
  t: Translations
  locale: Locale
  navigateBack: () => void
  filteredEntities: Entity[]
  selectedEntities: string[]
  setSelectedEntities: React.Dispatch<React.SetStateAction<string[]>>
  positions: DepositPosition[]
  entities: Entity[]
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
}

export default function DepositsInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all deposit positions
  const allDepositPositions = useMemo<DepositPosition[]>(() => {
    if (!positionsData?.positions) return []

    const deposits: DepositPosition[] = []

    Object.values(positionsData.positions)
      .flat()
      .forEach(entityPosition => {
        const depositProduct = entityPosition.products[ProductType.DEPOSIT]
        if (
          depositProduct &&
          "entries" in depositProduct &&
          depositProduct.entries.length > 0
        ) {
          const entityName = entityPosition.entity?.name || "Unknown"
          const entityId = entityPosition.entity?.id || null
          const entityOrigin = entityPosition.entity?.origin ?? null

          depositProduct.entries.forEach((deposit: any, index: number) => {
            const entryId = deposit.id ? String(deposit.id) : undefined
            const amount = Number(deposit.amount ?? 0)
            const expectedInterestsRaw =
              deposit.expected_interests != null
                ? Number(deposit.expected_interests)
                : 0
            const hasExpectedInterests =
              Number.isFinite(expectedInterestsRaw) &&
              expectedInterestsRaw !== 0
            const expectedInterests = hasExpectedInterests
              ? expectedInterestsRaw
              : null
            const convertedAmount = convertCurrency(
              amount,
              deposit.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )

            const convertedExpectedAmount =
              expectedInterests != null
                ? convertCurrency(
                    expectedInterests,
                    deposit.currency,
                    settings.general.defaultCurrency,
                    exchangeRates,
                  )
                : null

            deposits.push({
              id:
                entryId ??
                `${entityId ?? "entity"}-deposit-${deposit.name ?? index}`,
              entryId,
              name: deposit.name ?? "—",
              entity: entityName,
              entityId,
              entityOrigin,
              amount,
              convertedAmount,
              expectedInterests,
              convertedExpectedAmount,
              formattedAmount: formatCurrency(amount, locale, deposit.currency),
              formattedConvertedAmount: formatCurrency(
                convertedAmount,
                locale,
                settings.general.defaultCurrency,
              ),
              formattedExpectedAmount:
                convertedExpectedAmount != null
                  ? formatCurrency(
                      convertedExpectedAmount,
                      locale,
                      settings.general.defaultCurrency,
                    )
                  : null,
              interest_rate: Number(deposit.interest_rate ?? 0),
              maturity: deposit.maturity || "",
              creation: deposit.creation || "",
              currency: deposit.currency,
              source:
                (deposit.source as DataSource | undefined) ?? DataSource.REAL,
            })
          })
        }
      })

    return deposits
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  // Get entity options for the filter - only entities with deposits
  const filteredEntities = useMemo(() => {
    const entitiesWithDeposits = new Set(
      allDepositPositions.map(position => position.entityId).filter(Boolean),
    )
    return entities?.filter(entity => entitiesWithDeposits.has(entity.id)) ?? []
  }, [entities, allDepositPositions])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <ManualPositionsManager asset="deposits">
      <DepositsViewContent
        t={t}
        locale={locale}
        navigateBack={() => navigate(-1)}
        filteredEntities={filteredEntities}
        selectedEntities={selectedEntities}
        setSelectedEntities={setSelectedEntities}
        entities={entities ?? []}
        defaultCurrency={settings.general.defaultCurrency}
        positions={allDepositPositions}
        exchangeRates={exchangeRates}
      />
    </ManualPositionsManager>
  )
}

function DepositsViewContent({
  t,
  locale,
  navigateBack,
  filteredEntities,
  selectedEntities,
  setSelectedEntities,
  positions,
  entities,
  defaultCurrency,
  exchangeRates,
}: DepositsViewContentProps) {
  const {
    drafts,
    isEditMode,
    enterEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    isEntryDeleted,
    translate: manualTranslate,
    isDraftDirty: manualIsDraftDirty,
  } = useManualPositions()

  const depositDrafts = drafts as DepositDraft[]

  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<"amount" | "start" | "maturity">(
    "amount",
  )
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>(
    {},
  )

  const toggleCardExpanded = useCallback((key: string) => {
    setExpandedCards(prev => ({ ...prev, [key]: !prev[key] }))
  }, [])

  const entityOriginMap = useMemo(() => {
    const map: Record<string, EntityOrigin | null> = {}
    entities.forEach(entity => {
      map[entity.id] = entity.origin ?? null
    })
    return map
  }, [entities])

  const filteredDepositPositions = useMemo(() => {
    if (selectedEntities.length === 0) return positions
    return positions.filter(position => {
      if (!position.entityId) return false
      return selectedEntities.includes(position.entityId)
    })
  }, [positions, selectedEntities])

  const buildPositionFromDraft = useCallback(
    (draft: DepositDraft): DepositPosition => {
      const amount = Number(draft.amount ?? 0)
      const expectedInterestsRaw =
        draft.expected_interests != null ? Number(draft.expected_interests) : 0
      const hasExpectedInterests =
        Number.isFinite(expectedInterestsRaw) && expectedInterestsRaw !== 0
      const expectedInterests = hasExpectedInterests
        ? expectedInterestsRaw
        : null

      const convertedAmount =
        exchangeRates && draft.currency !== defaultCurrency
          ? convertCurrency(
              amount,
              draft.currency,
              defaultCurrency,
              exchangeRates,
            )
          : amount

      const convertedExpectedAmount =
        expectedInterests != null
          ? exchangeRates && draft.currency !== defaultCurrency
            ? convertCurrency(
                expectedInterests,
                draft.currency,
                defaultCurrency,
                exchangeRates,
              )
            : expectedInterests
          : null

      const entryId = String(draft.originalId ?? draft.id ?? draft.localId)

      return {
        id: entryId,
        entryId,
        name: draft.name ?? "—",
        entity: draft.entityName,
        entityId: draft.entityId,
        entityOrigin:
          draft.entityId && entityOriginMap[draft.entityId]
            ? entityOriginMap[draft.entityId]
            : null,
        amount,
        convertedAmount,
        expectedInterests,
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
        interest_rate: Number(draft.interest_rate ?? 0),
        maturity: draft.maturity || "",
        creation: draft.creation || "",
        currency: draft.currency,
        source: DataSource.MANUAL,
      }
    },
    [exchangeRates, defaultCurrency, locale],
  )

  const displayItems = useMemo<DisplayDepositItem[]>(
    () =>
      mergeManualDisplayItems({
        positions: filteredDepositPositions,
        manualDrafts: depositDrafts,
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
          if (!needsEntityUpdate) return position
          return {
            ...position,
            entityId: draft.entityId,
            entity: draft.entityName,
            entityOrigin:
              draft.entityId && entityOriginMap[draft.entityId]
                ? entityOriginMap[draft.entityId]
                : position.entityOrigin,
          }
        },
      }),
    [
      filteredDepositPositions,
      depositDrafts,
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

  const weightedAverageInterest = useMemo(() => {
    if (displayPositions.length === 0) return 0
    const totalWeightedInterest = displayPositions.reduce((sum, position) => {
      const weight = position.convertedAmount || 0
      const interest = position.interest_rate || 0
      return sum + weight * interest
    }, 0)
    return totalValue > 0 ? (totalWeightedInterest / totalValue) * 100 : 0
  }, [displayPositions, totalValue])

  const totalExpectedReturn = useMemo(() => {
    return displayPositions.reduce((sum, position) => {
      return sum + (position.convertedExpectedAmount || 0)
    }, 0)
  }, [displayPositions])

  const sortedDisplayItems = useMemo(
    () =>
      [...displayItems].sort((a, b) => {
        let aVal: number | string
        let bVal: number | string
        switch (sortBy) {
          case "start":
            aVal = a.position.creation || ""
            bVal = b.position.creation || ""
            break
          case "maturity":
            aVal = a.position.maturity || ""
            bVal = b.position.maturity || ""
            break
          default:
            aVal = a.position.convertedAmount || 0
            bVal = b.position.convertedAmount || 0
        }
        const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
        return sortOrder === "desc" ? -cmp : cmp
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
              <h1 className="text-2xl font-bold">{t.common.deposits}</h1>
              <PinAssetButton
                assetId="deposits"
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
          filteredEntities={filteredEntities}
          selectedEntities={selectedEntities}
          onEntitiesChange={setSelectedEntities}
        />
      </motion.div>

      <motion.div variants={fadeListItem}>
        {sortedDisplayItems.length === 0 ? (
          <Card className="p-14 text-center flex flex-col items-center gap-4">
            {getIconForAssetType(
              ProductType.DEPOSIT,
              "h-16 w-16",
              "text-gray-400 dark:text-gray-600",
            )}
            <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
              {selectedEntities.length > 0
                ? t.investments.noPositionsFound.replace(
                    "{type}",
                    t.common.deposits.toLowerCase(),
                  )
                : t.investments.noPositionsAvailable.replace(
                    "{type}",
                    t.common.deposits.toLowerCase(),
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
                    {
                      icon: <Percent className="h-3 w-3" />,
                      value: `${weightedAverageInterest.toFixed(2)}% ${t.investments.annually}`,
                    },
                    {
                      icon: <TrendingUp className="h-3 w-3" />,
                      value: formatCurrency(
                        totalExpectedReturn,
                        locale,
                        defaultCurrency,
                      ),
                    },
                  ]}
                  centerContent={{
                    rawValue: totalValue,
                    gainPercentage:
                      totalValue > 0
                        ? (totalExpectedReturn / totalValue) * 100
                        : undefined,
                    infoRows: [
                      {
                        label: t.dashboard.investedAmount,
                        value: formatCurrency(
                          totalValue,
                          locale,
                          defaultCurrency,
                        ),
                      },
                      ...(totalExpectedReturn > 0
                        ? [
                            {
                              label: t.investments.expectedProfit,
                              value: formatCurrency(
                                totalExpectedReturn,
                                locale,
                                defaultCurrency,
                              ),
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
                    { value: "start", label: t.investments.sortStart },
                    { value: "maturity", label: t.investments.sortMaturity },
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

                const identifier = position.name || item.key
                const isExpanded = expandedCards[item.key] ?? false

                const percentageOfDeposits =
                  totalValue > 0
                    ? ((position.convertedAmount || 0) / totalValue) * 100
                    : 0

                const expectedReturnPct =
                  position.expectedInterests != null && position.amount > 0
                    ? (position.expectedInterests / position.amount) * 100
                    : null

                const distributionEntry = chartData.find(
                  entry => entry.name === position.name,
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
                      "border-l-4 transition-colors overflow-hidden",
                      highlightClass,
                    )}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div
                      className="flex items-start justify-between gap-3 p-4 cursor-pointer hover:bg-accent/40 transition-colors"
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
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
                    >
                      <div className="flex-1 min-w-0 space-y-1.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-base sm:text-lg leading-tight">
                            {position.name}
                          </h3>
                          <EntityBadge
                            name={position.entity}
                            origin={position.entityOrigin}
                            className="text-xs"
                            title={position.entity}
                            data-no-expand
                            onClick={() => {
                              const targetId = position.entityId
                                ? position.entityId
                                : (entities.find(
                                    e => e.name === position.entity,
                                  )?.id ?? position.entity)
                              setSelectedEntities(prev =>
                                targetId && prev.includes(targetId)
                                  ? prev
                                  : targetId
                                    ? [...prev, targetId]
                                    : prev,
                              )
                            }}
                          />
                          {position.source &&
                            position.source !== DataSource.REAL && (
                              <SourceBadge
                                source={position.source}
                                title={t.management?.source}
                                className="text-[0.65rem]"
                                onClick={() => enterEditMode()}
                              />
                            )}
                          {isDirty && (
                            <span className="text-[0.65rem] font-semibold text-blue-600 dark:text-blue-400">
                              {manualTranslate("management.unsavedChanges")}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
                          <Percent
                            size={12}
                            className="text-gray-400 dark:text-gray-500"
                          />
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                            {(position.interest_rate * 100).toFixed(2)}%
                          </span>
                          <span className="text-gray-400 dark:text-gray-500">
                            ·
                          </span>
                          <Calendar
                            size={12}
                            className="text-gray-400 dark:text-gray-500"
                          />
                          <span>{formatDate(position.maturity, locale)}</span>
                        </div>
                      </div>

                      <div className="flex items-start gap-2 flex-shrink-0">
                        <div className="text-right space-y-0.5">
                          <div className="text-base sm:text-lg font-semibold leading-tight">
                            {position.formattedAmount}
                          </div>
                          {position.currency !== defaultCurrency && (
                            <div className="text-xs text-muted-foreground">
                              {position.formattedConvertedAmount}
                            </div>
                          )}
                          {position.formattedExpectedAmount && (
                            <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400 mt-0.5">
                              {position.formattedExpectedAmount}
                            </div>
                          )}
                        </div>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-muted-foreground transition-transform duration-200 mt-1",
                            isExpanded && "rotate-180",
                          )}
                        />
                      </div>
                    </div>

                    <AnimatePresence initial={false}>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2, ease: "easeInOut" }}
                          className="overflow-hidden"
                        >
                          <div className="px-4 pb-4 pt-1 space-y-3 border-t border-border">
                            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500 pt-2">
                              <div className="flex items-center gap-2">
                                <Calendar
                                  size={12}
                                  className="text-gray-400 dark:text-gray-500"
                                />
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.investments.investment}
                                </span>
                                <span className="text-gray-900 dark:text-gray-100">
                                  {formatDate(position.creation, locale)}
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

                            {position.formattedExpectedAmount && (
                              <div className="flex items-center gap-2 text-sm">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.investments.expected}
                                </span>
                                <span className="font-medium text-green-600 dark:text-green-400">
                                  {position.formattedExpectedAmount}
                                  {expectedReturnPct !== null && (
                                    <span className="ml-1 text-xs text-emerald-500 dark:text-emerald-300">
                                      ({expectedReturnPct.toFixed(2)}%)
                                    </span>
                                  )}
                                </span>
                              </div>
                            )}

                            <div className="text-sm text-gray-600 dark:text-gray-400">
                              <span className="font-medium text-blue-600 dark:text-blue-400">
                                {percentageOfDeposits.toFixed(1)}%
                              </span>
                              {" " +
                                t.investments.ofInvestmentType.replace(
                                  "{type}",
                                  t.common.deposits.toLowerCase(),
                                )}
                            </div>

                            {showActions && (
                              <div className="flex items-center gap-2 pt-1">
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
