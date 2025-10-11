import React, { useMemo, useState, useRef, useCallback, useEffect } from "react"
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
import { EntityBadge } from "@/components/ui/EntityBadge"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { getColorForName, cn } from "@/lib/utils"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  convertCurrency,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  formatSnakeCaseToHuman,
  getTransactionDisplayType,
} from "@/utils/financialDataUtils"
import { ProductType, type RealEstateCFDetail } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  Clock,
  Filter,
  FilterX,
  History,
  Percent,
  RotateCcw,
  Building,
  Pencil,
  Trash2,
  TrendingUp,
  Info,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { useNavigate } from "react-router-dom"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { getHistoric } from "@/services/api"
import type { HistoricQueryRequest, RealEstateCFEntry } from "@/types/historic"
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

interface AmountDisplay {
  formatted: string | null
  original: string | null
  converted: number | null
}

interface ProfitDisplay {
  amount: number | null
  formatted: string | null
  percent: number | null
  percentFormatted: string | null
}

interface HistoricDisplayItem {
  entry: RealEstateCFEntry
  entityId: string
  entityName: string
  invested: AmountDisplay
  returned: AmountDisplay
  repaid: AmountDisplay
  netReturn: AmountDisplay
  fees: AmountDisplay
  retentions: AmountDisplay
  interestsPaid: AmountDisplay
  profit: ProfitDisplay
  netProfit: ProfitDisplay
  interestRateFormatted: string
  projectType: string
  lastInvestDate: string
  lastTxDate: string
  effectiveMaturity: string
  originalMaturity: string
  extendedMaturity: string | null
}

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
  historicEntries: RealEstateCFEntry[]
  isHistoricVisible: boolean
  isHistoricLoading: boolean
  hasHistoricLoaded: boolean
  historicError: string | null
  onToggleHistoric: () => void
  onReloadHistoric: () => void
  historicSectionRef: React.RefObject<HTMLDivElement | null>
}

export default function RealEstateCFInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [isHistoricVisible, setIsHistoricVisible] = useState(false)
  const [historicEntries, setHistoricEntries] = useState<RealEstateCFEntry[]>(
    [],
  )
  const [isHistoricLoading, setIsHistoricLoading] = useState(false)
  const [hasHistoricLoaded, setHasHistoricLoaded] = useState(false)
  const [historicError, setHistoricError] = useState<string | null>(null)
  const historicFilterKeyRef = useRef<string>("")
  const historicSectionRef = useRef<HTMLDivElement | null>(null)

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

  const fetchErrorMessage = t.common.fetchError

  const loadHistoricEntries = useCallback(async () => {
    if (isHistoricLoading) {
      return
    }

    const filterKey =
      selectedEntities.length > 0 ? selectedEntities.join("|") : "ALL"

    setIsHistoricLoading(true)
    setHistoricError(null)
    setHasHistoricLoaded(false)
    setHistoricEntries([])

    try {
      const response = await getHistoric({
        product_types: [ProductType.REAL_ESTATE_CF],
        entities: selectedEntities.length > 0 ? selectedEntities : undefined,
      } satisfies HistoricQueryRequest)

      const entries = Array.isArray(response.entries)
        ? (response.entries.filter(
            entry => entry.product_type === ProductType.REAL_ESTATE_CF,
          ) as RealEstateCFEntry[])
        : []

      setHistoricEntries(entries)
      historicFilterKeyRef.current = filterKey
      setHasHistoricLoaded(true)
    } catch (error) {
      console.error("Failed to load real estate CF historic entries", error)
      const message = error instanceof Error ? error.message : fetchErrorMessage
      historicFilterKeyRef.current = filterKey
      setHistoricError(message)
    } finally {
      setIsHistoricLoading(false)
    }
  }, [fetchErrorMessage, isHistoricLoading, selectedEntities])

  const handleToggleHistoric = useCallback(() => {
    if (!isHistoricVisible) {
      setHistoricError(null)
    }

    setIsHistoricVisible(prev => !prev)
  }, [isHistoricVisible])

  const handleReloadHistoric = useCallback(() => {
    void loadHistoricEntries()
  }, [loadHistoricEntries])

  useEffect(() => {
    if (!isHistoricVisible || isHistoricLoading) {
      return
    }

    const filterKey =
      selectedEntities.length > 0 ? selectedEntities.join("|") : "ALL"

    if (hasHistoricLoaded && filterKey === historicFilterKeyRef.current) {
      return
    }

    if (historicError && filterKey === historicFilterKeyRef.current) {
      return
    }

    void loadHistoricEntries()
  }, [
    isHistoricVisible,
    isHistoricLoading,
    hasHistoricLoaded,
    selectedEntities,
    historicError,
    loadHistoricEntries,
  ])

  useEffect(() => {
    if (!isHistoricVisible) {
      return
    }

    const node = historicSectionRef.current
    if (node) {
      requestAnimationFrame(() => {
        node.scrollIntoView({ behavior: "smooth", block: "start" })
      })
    }
  }, [isHistoricVisible])

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
        historicEntries={historicEntries}
        isHistoricVisible={isHistoricVisible}
        isHistoricLoading={isHistoricLoading}
        hasHistoricLoaded={hasHistoricLoaded}
        historicError={historicError}
        onToggleHistoric={handleToggleHistoric}
        onReloadHistoric={handleReloadHistoric}
        historicSectionRef={historicSectionRef}
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
  historicEntries,
  isHistoricVisible,
  isHistoricLoading,
  hasHistoricLoaded,
  historicError,
  onToggleHistoric,
  onReloadHistoric,
  historicSectionRef,
}: RealEstateViewContentProps) {
  const navigate = useNavigate()
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
  const [expandedHistoricEntries, setExpandedHistoricEntries] = useState<
    Record<string, boolean>
  >({})

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

  const notAvailableLabel = t.common.notAvailable

  const activePositionNames = useMemo(() => {
    const names = new Set<string>()

    positions.forEach(position => {
      if (!position.name) {
        return
      }

      names.add(position.name.trim().toLowerCase())
    })

    return names
  }, [positions])

  const toAmountDisplay = useCallback(
    (value: number | null | undefined, currency: string): AmountDisplay => {
      if (value == null) {
        return {
          formatted: null,
          original: null,
          converted: null,
        }
      }

      const converted =
        exchangeRates && currency !== defaultCurrency
          ? convertCurrency(value, currency, defaultCurrency, exchangeRates)
          : value

      return {
        formatted: formatCurrency(converted, locale, defaultCurrency),
        original:
          currency !== defaultCurrency
            ? formatCurrency(value, locale, currency)
            : null,
        converted,
      }
    },
    [defaultCurrency, exchangeRates, locale],
  )

  const toProfitDisplay = useCallback(
    (
      base: AmountDisplay,
      amount: number | null | undefined,
      currency: string,
    ): ProfitDisplay => {
      if (amount == null) {
        return {
          amount: null,
          formatted: null,
          percent: null,
          percentFormatted: null,
        }
      }

      const converted =
        exchangeRates && currency !== defaultCurrency
          ? convertCurrency(amount, currency, defaultCurrency, exchangeRates)
          : amount

      const percent =
        base.converted && base.converted !== 0
          ? (converted / base.converted) * 100
          : null

      return {
        amount: converted,
        formatted: formatCurrency(converted, locale, defaultCurrency),
        percent,
        percentFormatted: percent !== null ? `${percent.toFixed(2)}%` : null,
      }
    },
    [defaultCurrency, exchangeRates, locale],
  )

  const historicDisplayItems = useMemo<HistoricDisplayItem[]>(() => {
    if (historicEntries.length === 0) {
      return []
    }

    return historicEntries
      .filter(entry => {
        if (!entry.effective_maturity) {
          return false
        }

        const normalizedName = entry.name?.trim().toLowerCase() ?? ""
        if (!normalizedName) {
          return true
        }

        return !activePositionNames.has(normalizedName)
      })
      .map(entry => {
        const invested = toAmountDisplay(entry.invested, entry.currency)
        const returned = toAmountDisplay(entry.returned ?? null, entry.currency)
        const repaid = toAmountDisplay(entry.repaid ?? null, entry.currency)
        const netReturn = toAmountDisplay(
          entry.net_return ?? null,
          entry.currency,
        )
        const fees = toAmountDisplay(entry.fees ?? null, entry.currency)
        const retentions = toAmountDisplay(
          entry.retentions ?? null,
          entry.currency,
        )
        const interestsPaid = toAmountDisplay(
          entry.interests ?? null,
          entry.currency,
        )

        const grossProfitValue =
          entry.returned != null ? entry.returned - entry.invested : null
        const profit = toProfitDisplay(
          invested,
          grossProfitValue,
          entry.currency,
        )
        const netProfitDifference =
          entry.net_return != null ? entry.net_return - entry.invested : null
        const netProfit = toProfitDisplay(
          invested,
          netProfitDifference,
          entry.currency,
        )

        const interestRateFormatted =
          entry.interest_rate != null
            ? `${(entry.interest_rate * 100).toFixed(2)}%`
            : notAvailableLabel

        const formatDateSafe = (value?: string | null) =>
          value ? formatDate(value, locale) : notAvailableLabel

        const extendedMaturity = entry.extended_maturity
          ? formatDate(entry.extended_maturity, locale)
          : null

        const projectType = translateProjectType(
          entry.type || entry.business_type || "",
        )

        return {
          entry,
          entityId: entry.entity.id,
          entityName: entry.entity.name,
          invested,
          returned,
          repaid,
          netReturn,
          fees,
          retentions,
          interestsPaid,
          profit,
          netProfit,
          interestRateFormatted,
          projectType,
          lastInvestDate: formatDateSafe(entry.last_invest_date),
          lastTxDate: formatDateSafe(entry.last_tx_date),
          effectiveMaturity: formatDateSafe(entry.effective_maturity),
          originalMaturity: formatDateSafe(entry.maturity),
          extendedMaturity,
        }
      })
  }, [
    historicEntries,
    activePositionNames,
    locale,
    notAvailableLabel,
    toAmountDisplay,
    toProfitDisplay,
    translateProjectType,
  ])

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

      <motion.div
        variants={fadeListItem}
        className="pb-6 border-b border-gray-200 dark:border-gray-800"
      >
        <div className="flex flex-wrap gap-4 xl:flex-nowrap xl:items-center xl:justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 flex-1 min-w-[200px]">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              <Filter size={16} />
              <span>{t.transactions.filters}</span>
            </div>
            <div className="w-full sm:max-w-xs">
              <MultiSelect
                options={entityOptions}
                value={selectedEntities}
                onChange={setSelectedEntities}
              />
            </div>
            {selectedEntities.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2 self-start sm:self-auto"
                onClick={() => setSelectedEntities([])}
              >
                <FilterX size={16} />
                {t.transactions.clear}
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2 self-start xl:self-auto">
            <Button
              variant={isHistoricVisible ? "default" : "outline"}
              size="sm"
              className="flex items-center gap-2"
              onClick={onToggleHistoric}
            >
              <History size={16} />
              {isHistoricVisible
                ? t.investments.historicSection.toggleShort.hide
                : t.investments.historicSection.toggleShort.show}
            </Button>
          </div>
        </div>
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
                  <div key="entity" className="flex items-center">
                    {entityButton}
                  </div>,
                  <div key="type" className="flex items-center gap-1 text-sm">
                    <Building size={14} />
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {translateProjectType(rawProjectType)}
                    </span>
                  </div>,
                  <div
                    key="interest"
                    className="flex items-center gap-1 text-sm"
                  >
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

                        <div className="flex flex-col gap-2 text-sm text-gray-600 dark:text-gray-400 sm:flex-row sm:flex-wrap sm:items-center">
                          {summaryItems.map((item, index) => (
                            <React.Fragment key={index}>
                              {item}
                              {index < summaryItems.length - 1 && (
                                <span className="hidden text-gray-400 dark:text-gray-500 sm:inline">
                                  •
                                </span>
                              )}
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

                      <div className="text-right space-y-1 flex-shrink-0 self-stretch sm:self-auto w-full sm:w-auto">
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

      {isHistoricVisible && (
        <motion.section
          ref={historicSectionRef}
          variants={fadeListItem}
          className="space-y-4 pb-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-semibold">
              {t.investments.historicSection.heading}
            </h2>
            <div className="flex items-center gap-2 self-start sm:self-auto">
              {isHistoricLoading && <LoadingSpinner size="sm" />}
              <Button
                variant="ghost"
                size="icon"
                aria-label={t.common.refresh}
                onClick={onReloadHistoric}
                disabled={isHistoricLoading}
              >
                <RotateCcw
                  size={16}
                  className={cn(isHistoricLoading ? "animate-spin" : "")}
                />
              </Button>
            </div>
          </div>

          {historicError ? (
            <Card className="p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-red-500 dark:text-red-400">
                    {t.common.error}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {historicError}
                  </p>
                </div>
                <Button size="sm" onClick={onReloadHistoric}>
                  {t.common.retry}
                </Button>
              </div>
            </Card>
          ) : !hasHistoricLoaded ? (
            <Card className="p-6 flex items-center justify-center gap-3 text-sm text-gray-600 dark:text-gray-400">
              <LoadingSpinner size="sm" />
              <span>{t.common.loading}</span>
            </Card>
          ) : historicDisplayItems.length === 0 ? (
            <Card className="p-10 text-center text-sm text-gray-600 dark:text-gray-400">
              {(selectedEntities.length > 0
                ? t.investments.historicSection.emptyFiltered
                : t.investments.historicSection.empty
              ).replace("{type}", t.common.realEstateCf)}
            </Card>
          ) : (
            <div className="space-y-3">
              {historicDisplayItems.map(item => {
                const isExpanded =
                  expandedHistoricEntries[item.entry.id] ?? false
                const transactions = item.entry.related_txs ?? []

                const chargesStats = [
                  {
                    key: "fees",
                    label: t.investments.historicSection.fees,
                    amount: item.fees,
                  },
                  {
                    key: "retentions",
                    label: t.investments.historicSection.retentions,
                    amount: item.retentions,
                  },
                  {
                    key: "interests",
                    label: t.investments.historicSection.interests,
                    amount: item.interestsPaid,
                  },
                ].filter(
                  stat =>
                    stat.amount.converted !== null &&
                    Math.abs(stat.amount.converted) > 0,
                )

                const baseStats = [
                  {
                    key: "returned",
                    label: t.investments.historicSection.returned,
                    amount: item.returned,
                  },
                  {
                    key: "repaid",
                    label: t.investments.historicSection.repaid,
                    amount: item.repaid,
                  },
                  {
                    key: "netReturn",
                    label: t.investments.historicSection.netReturn,
                    amount: item.netReturn,
                  },
                ]

                const profitColor = (value: number | null) => {
                  if (value == null) {
                    return "text-gray-500 dark:text-gray-400"
                  }
                  if (value > 0) {
                    return "text-emerald-600 dark:text-emerald-400"
                  }
                  if (value < 0) {
                    return "text-red-500 dark:text-red-400"
                  }
                  return "text-gray-500 dark:text-gray-400"
                }

                const handleEntityClick = (
                  event: React.MouseEvent<HTMLDivElement>,
                ) => {
                  event.stopPropagation()
                  const id = item.entityId
                  if (!id) {
                    return
                  }
                  setSelectedEntities(prev =>
                    prev.includes(id) ? prev : [...prev, id],
                  )
                }

                const handleToggle = () => {
                  setExpandedHistoricEntries(prev => ({
                    ...prev,
                    [item.entry.id]: !isExpanded,
                  }))
                }

                const handleTransactionRedirect = () => {
                  navigate(`/transactions?historic_entry_id=${item.entry.id}`)
                }

                const profitDisplay =
                  item.profit.formatted && item.profit.amount !== null
                    ? item.profit.amount > 0
                      ? `+${item.profit.formatted}`
                      : item.profit.formatted
                    : (item.profit.formatted ?? notAvailableLabel)

                const handleHeaderClick = (
                  event: React.MouseEvent<HTMLDivElement>,
                ) => {
                  const target = event.target as HTMLElement
                  if (target.closest("[data-historic-stop]") !== null) {
                    return
                  }
                  handleToggle()
                }

                const handleHeaderKeyDown = (
                  event: React.KeyboardEvent<HTMLDivElement>,
                ) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    handleToggle()
                  }
                }

                const headerItems: React.ReactNode[] = [
                  <EntityBadge
                    key="entity"
                    name={item.entityName}
                    onClick={handleEntityClick}
                    className="cursor-pointer"
                    data-historic-stop
                  />,
                  <div key="type" className="flex items-center gap-1 text-sm">
                    <Building
                      size={14}
                      className="text-gray-400 dark:text-gray-500"
                    />
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {item.projectType || notAvailableLabel}
                    </span>
                  </div>,
                  <div
                    key="interest"
                    className="flex items-center gap-1 text-sm"
                  >
                    <Percent
                      size={14}
                      className="text-gray-400 dark:text-gray-500"
                    />
                    <span className="font-medium text-emerald-600 dark:text-emerald-400">
                      {item.interestRateFormatted}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {t.investments.annually}
                    </span>
                  </div>,
                  <div
                    key="maturity"
                    className="flex items-center gap-1 text-sm"
                  >
                    <Calendar
                      size={14}
                      className="text-gray-400 dark:text-gray-500"
                    />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {t.investments.maturity}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {item.effectiveMaturity}
                    </span>
                  </div>,
                ]

                return (
                  <Card key={item.entry.id} className="p-4 space-y-3">
                    <div
                      className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between cursor-pointer select-none"
                      onClick={handleHeaderClick}
                      onKeyDown={handleHeaderKeyDown}
                      role="button"
                      tabIndex={0}
                      aria-expanded={isExpanded}
                    >
                      <div className="space-y-2 flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                          {item.entry.name}
                        </h3>
                        <div className="flex flex-col gap-2 text-sm text-gray-600 dark:text-gray-400 sm:flex-row sm:flex-wrap sm:items-center">
                          {headerItems.map((metaItem, index) => (
                            <React.Fragment key={index}>
                              {metaItem}
                              {index < headerItems.length - 1 && (
                                <span className="hidden text-gray-400 dark:text-gray-500 sm:inline">
                                  •
                                </span>
                              )}
                            </React.Fragment>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 self-center">
                        <div className="flex flex-col items-end gap-1 text-right">
                          <span className="text-base font-semibold text-gray-900 dark:text-gray-100">
                            {item.invested.formatted ?? notAvailableLabel}
                          </span>
                          {item.invested.original && (
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              {item.invested.original}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1 text-right">
                          <span
                            className={cn(
                              "text-sm",
                              profitColor(item.profit.amount),
                            )}
                          >
                            {profitDisplay}
                          </span>
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="space-y-4 border-t border-gray-200 dark:border-gray-800 pt-4">
                        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
                          <div className="rounded-lg border border-gray-200 dark:border-gray-800/60 p-3 sm:p-4 space-y-3 text-sm text-gray-600 dark:text-gray-400">
                            <div className="flex items-center gap-2">
                              <TrendingUp
                                size={14}
                                className="text-gray-400 dark:text-gray-500"
                              />
                              <span>{t.investments.investment}</span>
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {item.lastInvestDate}
                              </span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <Clock
                                size={14}
                                className="text-gray-400 dark:text-gray-500"
                              />
                              <span>
                                {t.investments.historicSection.lastTx}
                              </span>
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {item.lastTxDate}
                              </span>
                              {transactions.length > 0 && (
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      className="h-8 gap-1 px-2 text-xs"
                                      aria-label={
                                        t.investments.historicSection
                                          .transactionsSummary
                                      }
                                      data-historic-stop
                                    >
                                      <Info size={14} />
                                      {
                                        t.investments.historicSection
                                          .transactionsSummaryShort
                                      }
                                    </Button>
                                  </PopoverTrigger>
                                  <PopoverContent
                                    align="start"
                                    className="w-80 space-y-2"
                                  >
                                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                      {
                                        t.investments.historicSection
                                          .transactionsSummary
                                      }
                                    </p>
                                    <div className="space-y-1">
                                      {transactions.map(tx => {
                                        const amountDisplay = toAmountDisplay(
                                          tx.amount,
                                          tx.currency,
                                        )
                                        const direction =
                                          getTransactionDisplayType(tx.type)
                                        const isCharge =
                                          direction === "out" &&
                                          (tx.type === "FEE" ||
                                            tx.type === "INTEREST")
                                        const amountColor =
                                          direction === "in"
                                            ? "text-emerald-600 dark:text-emerald-400"
                                            : isCharge
                                              ? "text-red-500 dark:text-red-400"
                                              : "text-gray-600 dark:text-gray-300"
                                        const sign =
                                          direction === "in" ? "+" : "-"
                                        const formattedAmount =
                                          amountDisplay.formatted
                                            ? `${sign} ${amountDisplay.formatted}`
                                            : notAvailableLabel

                                        return (
                                          <button
                                            key={tx.id}
                                            type="button"
                                            onClick={handleTransactionRedirect}
                                            className="w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-muted focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary"
                                          >
                                            <div className="flex items-center justify-between gap-3">
                                              <div className="flex items-center gap-2">
                                                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                                  {formatSnakeCaseToHuman(
                                                    tx.type,
                                                  )}
                                                </span>
                                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                                  {formatDate(tx.date, locale)}
                                                </span>
                                              </div>
                                              <span
                                                className={cn(
                                                  "text-sm font-semibold",
                                                  amountColor,
                                                )}
                                              >
                                                {formattedAmount}
                                              </span>
                                            </div>
                                            {amountDisplay.original && (
                                              <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
                                                {amountDisplay.original}
                                              </span>
                                            )}
                                          </button>
                                        )
                                      })}
                                    </div>
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      className="w-full"
                                      onClick={handleTransactionRedirect}
                                    >
                                      {
                                        t.investments.historicSection
                                          .viewTransactions
                                      }
                                    </Button>
                                  </PopoverContent>
                                </Popover>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <Calendar
                                size={14}
                                className="text-gray-400 dark:text-gray-500"
                              />
                              <span>
                                {t.investments.historicSection.originalMaturity}
                              </span>
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {item.originalMaturity}
                              </span>
                            </div>
                            {item.extendedMaturity && (
                              <div className="flex items-center gap-2 pl-4 sm:pl-6">
                                <ArrowRight
                                  size={14}
                                  className="text-gray-400 dark:text-gray-500"
                                />
                                <span>
                                  {
                                    t.investments.historicSection
                                      .extendedMaturity
                                  }
                                </span>
                                <span className="font-medium text-gray-900 dark:text-gray-100">
                                  {item.extendedMaturity}
                                </span>
                              </div>
                            )}
                          </div>
                          <div className="rounded-lg border border-gray-200 dark:border-gray-800/60 p-3 sm:p-4 flex flex-col items-start md:items-end gap-3 text-sm">
                            <div className="flex flex-wrap items-baseline gap-2">
                              <span className="text-sm text-gray-500 dark:text-gray-400">
                                {t.investments.profit}
                              </span>
                              <span
                                className={cn(
                                  "text-sm font-semibold",
                                  profitColor(item.profit.amount),
                                )}
                              >
                                {item.profit.formatted ?? notAvailableLabel}
                              </span>
                              {item.profit.percentFormatted && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  {item.profit.percentFormatted}
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap items-baseline gap-2">
                              <span className="text-sm text-gray-500 dark:text-gray-400">
                                {t.investments.historicSection.netProfit}
                              </span>
                              <span
                                className={cn(
                                  "text-sm font-semibold",
                                  profitColor(item.netProfit.amount),
                                )}
                              >
                                {item.netProfit.formatted ?? notAvailableLabel}
                              </span>
                              {item.netProfit.percentFormatted && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  {item.netProfit.percentFormatted}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-lg border border-gray-200 dark:border-gray-800/60 p-3 sm:p-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                            {baseStats.map(stat => (
                              <div
                                key={stat.key}
                                className="flex items-baseline justify-between gap-3"
                              >
                                <span>{stat.label}:</span>
                                <span className="font-medium text-gray-900 dark:text-gray-100">
                                  {stat.amount.formatted ?? notAvailableLabel}
                                </span>
                              </div>
                            ))}
                          </div>
                          {chargesStats.length > 0 && (
                            <div className="rounded-lg border border-gray-200 dark:border-gray-800/60 p-3 sm:p-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                              {chargesStats.map(stat => (
                                <div
                                  key={stat.key}
                                  className="flex items-baseline justify-between gap-3"
                                >
                                  <span>{stat.label}:</span>
                                  <span className="font-medium text-gray-900 dark:text-gray-100">
                                    {stat.amount.formatted ?? notAvailableLabel}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {transactions.length === 0 && (
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {t.investments.historicSection.noTransactions}
                          </p>
                        )}
                      </div>
                    )}
                  </Card>
                )
              })}
            </div>
          )}
        </motion.section>
      )}
    </motion.div>
  )
}
