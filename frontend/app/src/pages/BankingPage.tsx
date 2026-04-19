import React, { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { useI18n, type Locale, type Translations } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  ManualPositionsManager,
  useManualPositions,
} from "@/components/manual/ManualPositionsManager"
import {
  mergeManualDisplayItems,
  type ManualDisplayItem,
} from "@/components/manual/manualDisplayUtils"
import type {
  ManualPositionAsset,
  ManualPositionDraft,
  ManualSavePayloadByEntity,
} from "@/components/manual/manualPositionTypes"
import { convertCurrency } from "@/utils/financialDataUtils"
import { formatCurrency, formatDate, formatPercentage } from "@/lib/formatters"
import { getAccountTypeColor, getAccountTypeIcon } from "@/utils/dashboardUtils"
import { cn } from "@/lib/utils"
import { SourceBadge } from "@/components/ui/SourceBadge"
import { EntityBadge } from "@/components/ui/EntityBadge"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  ArrowLeft,
  Wallet,
  CreditCard,
  HandCoins,
  Percent,
  Calendar,
  Shield,
  AlertCircle,
  Pencil,
  Plus,
  Save,
  Trash2,
  X,
  Copy,
  Check,
  Loader2,
  Binary,
  ChevronDown,
} from "lucide-react"
import {
  ProductType,
  AccountType,
  CardType,
  LoanType,
  InterestType,
  type Account,
  type Card as CardModel,
  type Loan,
  type CreditDetail,
  type PartialProductPositions,
  type UpdatePositionRequest,
} from "@/types/position"
import {
  DataSource,
  EntityOrigin,
  EntityType,
  type ExchangeRates,
} from "@/types"
import { saveManualPositions } from "@/services/api"

interface AccountPosition extends Account {
  entityId: string
  entityName: string
  entryId: string
  entityOrigin: EntityOrigin | null
}

interface CardPosition extends CardModel {
  entityId: string
  entityName: string
  entryId: string
  entityOrigin: EntityOrigin | null
}

interface LoanPosition extends Loan {
  entityId: string
  entityName: string
  entryId: string
  entityOrigin: EntityOrigin | null
}

interface CreditPosition extends CreditDetail {
  entityId: string
  entityName: string
  entryId: string
  entityOrigin: EntityOrigin | null
}

interface AccountsSummary {
  totalBalance: number
  weightedInterest: number
  count: number
}

interface CardsSummary {
  totalUsed: number
  count: number
}

interface LoansSummary {
  totalDebt: number
  totalMonthlyPayments: number
  weightedInterest: number
  count: number
}

interface CreditsSummary {
  totalDrawn: number
  totalLimit: number
  weightedInterest: number
  count: number
}

const formatIban = (iban?: string | null, reveal?: boolean) => {
  if (!iban) return null
  if (reveal) {
    return iban.replace(/(.{4})/g, "$1 ").trim()
  }
  return `•••• •••• •••• ${iban.slice(-4)}`
}

const formatCardNumber = (ending?: string | null) =>
  ending ? `•••• •••• •••• ${ending}` : "•••• •••• •••• ••••"

const isFiniteNumber = (value: number | null | undefined): value is number =>
  typeof value === "number" && Number.isFinite(value)

type AccountDraft = ManualPositionDraft<Account>
type CardDraft = ManualPositionDraft<CardModel>
type LoanDraft = ManualPositionDraft<Loan>
type CreditDraft = ManualPositionDraft<CreditDetail>

type AccountDisplay = AccountPosition & {
  convertedTotal: number
  convertedRetained: number | null
  convertedPendingTransfers: number | null
}

type CardDisplay = CardPosition & {
  convertedUsed: number
  convertedLimit: number | null
}

type LoanDisplay = LoanPosition & {
  convertedCurrentInstallment: number
  convertedLoanAmount: number
  convertedPrincipalOutstanding: number
  convertedPrincipalPaid: number
}

type CreditDisplay = CreditPosition & {
  convertedDrawnAmount: number
  convertedCreditLimit: number
}

type CreditDisplayItem = ManualDisplayItem<CreditDisplay, CreditDraft>

interface CreditEditHandlers {
  editByOriginalId: (id: string) => void
  editByLocalId: (id: string) => void
  deleteByOriginalId: (id: string) => void
  deleteByLocalId: (id: string) => void
  isEditMode: boolean
}

const MANUAL_ASSETS_ORDER: ManualPositionAsset[] = [
  "bankAccounts",
  "bankCards",
  "bankLoans",
  "bankCredits",
]

interface ManualSectionController {
  asset: ManualPositionAsset
  assetTitle: string
  addLabel: string
  editLabel: string
  cancelLabel: string
  saveLabel: string
  isEditMode: boolean
  hasLocalChanges: boolean
  isSaving: boolean
  canCreate: boolean
  beginCreate: (options?: { entityId?: string }) => void
  enterEditMode: () => void
  requestCancel: () => void
  requestSave: () => Promise<void>
  translate: (path: string, params?: Record<string, any>) => string
  collectSavePayload: () => ManualSavePayloadByEntity
  setSavingState: (value: boolean) => void
  handleSaveSuccess: () => void
}

type ManualControllerRegistrar = (
  asset: ManualPositionAsset,
  controller: ManualSectionController | null,
) => void

function BankingManualControls({
  controllers,
  t,
  showToast,
  refreshEntity,
  fetchEntities,
  refreshData,
  className,
}: {
  controllers: ManualSectionController[]
  t: Translations
  showToast: (message: string, type: "success" | "error" | "warning") => void
  refreshEntity: (entityId: string) => Promise<void>
  fetchEntities: () => Promise<void>
  refreshData: () => Promise<void>
  className?: string
}) {
  const [isSaving, setIsSaving] = useState(false)

  if (controllers.length === 0) {
    return null
  }

  const isAnyEditMode = controllers.some(controller => controller.isEditMode)
  const isAnySaving =
    isSaving || controllers.some(controller => controller.isSaving)
  const hasAnyChanges = controllers.some(
    controller => controller.hasLocalChanges,
  )
  const unsavedControllers = controllers.filter(
    controller => controller.isEditMode && controller.hasLocalChanges,
  )

  const handleCancel = useCallback(() => {
    controllers.forEach(controller => {
      controller.requestCancel()
    })
  }, [controllers])

  const handleSave = useCallback(async () => {
    if (isAnySaving) return

    if (!hasAnyChanges) {
      controllers.forEach(controller => controller.handleSaveSuccess())
      return
    }

    setIsSaving(true)
    controllers.forEach(controller => controller.setSavingState(true))

    try {
      const aggregated = new Map<
        string,
        {
          products: PartialProductPositions
          isNewEntity: boolean
          newEntityName: string | null
        }
      >()

      controllers.forEach(controller => {
        const payloadMap = controller.collectSavePayload()
        payloadMap.forEach(
          ({ productType, entries, isNewEntity, newEntityName }, entityId) => {
            const record = aggregated.get(entityId) ?? {
              products: {} as PartialProductPositions,
              isNewEntity: false,
              newEntityName: null,
            }

            const payloadEntries = entries.map(({ payload, draft }) => {
              const base = { ...payload } as Record<string, any>

              const resolvedId = (() => {
                if (typeof base.id === "string" && base.id.trim() !== "") {
                  return base.id
                }
                if (typeof draft.originalId === "string" && draft.originalId) {
                  return draft.originalId
                }
                return draft.localId
              })()

              if (resolvedId) {
                base.id = resolvedId
              } else {
                delete base.id
              }

              if (productType === ProductType.CARD) {
                const relatedAccount =
                  typeof (draft as any).related_account === "string"
                    ? (draft as any).related_account.trim()
                    : ""
                base.related_account = relatedAccount ? relatedAccount : null
              }

              return base
            })

            ;(record.products as PartialProductPositions)[productType] = {
              entries: payloadEntries as any,
            } as any

            const hasDraftNewEntity = entries.some(entry => {
              if (entry.draft.isNewEntity) return true
              const draftEntityId = entry.draft.entityId
              return (
                typeof draftEntityId === "string" &&
                draftEntityId.startsWith("new-")
              )
            })

            if (
              hasDraftNewEntity ||
              isNewEntity ||
              (typeof entityId === "string" && entityId.startsWith("new-"))
            ) {
              record.isNewEntity = true
            }

            if (!record.newEntityName) {
              const candidateName =
                newEntityName?.trim() ||
                entries
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

            aggregated.set(entityId, record)
          },
        )
      })

      if (aggregated.size === 0) {
        controllers.forEach(controller => controller.handleSaveSuccess())
        return
      }

      const requests: { payload: UpdatePositionRequest }[] = []
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

          requests.push({ payload: requestPayload })
        },
      )

      if (missingNewEntityName) {
        const translate = controllers[0]?.translate
        if (translate) {
          showToast(
            translate("management.manualPositions.toasts.saveError"),
            "error",
          )
        } else if (t.common?.error) {
          showToast(t.common.error, "error")
        }
        controllers.forEach(controller => controller.setSavingState(false))
        setIsSaving(false)
        return
      }

      if (requests.length === 0) {
        controllers.forEach(controller => controller.handleSaveSuccess())
        return
      }

      let createdNewEntity = false
      for (const { payload } of requests) {
        await saveManualPositions(payload)
        if (payload.entity_id) {
          await refreshEntity(payload.entity_id)
        }
        if (payload.new_entity_name) {
          createdNewEntity = true
        }
      }

      if (createdNewEntity) {
        await fetchEntities()
        await refreshData()
      }

      controllers.forEach(controller => controller.handleSaveSuccess())

      const translate = controllers[0]?.translate
      if (translate) {
        showToast(
          translate("management.manualPositions.toasts.saveSuccess"),
          "success",
        )
      }
    } catch (error) {
      console.error("Error saving manual positions", error)
      const translate = controllers[0]?.translate
      if (translate) {
        showToast(
          translate("management.manualPositions.toasts.saveError"),
          "error",
        )
      } else if (t.common?.error) {
        showToast(t.common.error, "error")
      }
    } finally {
      controllers.forEach(controller => controller.setSavingState(false))
      setIsSaving(false)
    }
  }, [
    controllers,
    hasAnyChanges,
    isAnySaving,
    refreshEntity,
    fetchEntities,
    refreshData,
    showToast,
    t,
  ])

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {isAnyEditMode && (
        <div className="flex flex-wrap items-center gap-2 justify-center md:justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            disabled={isAnySaving}
            className="flex items-center gap-2"
          >
            <X className="h-3.5 w-3.5" />
            {t.common.cancel}
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isAnySaving || !hasAnyChanges}
            className="flex items-center gap-2"
          >
            {isAnySaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            <span className="hidden sm:inline">{t.common.save}</span>
          </Button>
        </div>
      )}
      {unsavedControllers.length > 0 && (
        <div className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-100/70 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div className="space-y-1">
            <div>
              {unsavedControllers[0].translate("management.unsavedChanges")}
            </div>
            <div className="text-xs text-amber-700 dark:text-amber-300">
              {unsavedControllers
                .map(controller => controller.assetTitle)
                .join(", ")}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function BankingPage() {
  const { t, locale } = useI18n()
  const { positionsData, isLoading, refreshEntity, refreshData } =
    useFinancialData()
  const { settings, exchangeRates, entities, showToast, fetchEntities } =
    useAppContext()
  const navigate = useNavigate()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [showAccountNumbers, setShowAccountNumbers] = useState(false)

  const [collapsedSections, setCollapsedSections] = useState<
    Record<string, boolean>
  >(() => {
    try {
      const raw = localStorage.getItem("bankingSections")
      return raw ? JSON.parse(raw) : {}
    } catch {
      return {}
    }
  })

  const toggleSection = useCallback((section: string) => {
    setCollapsedSections(prev => {
      const next = { ...prev, [section]: !prev[section] }
      localStorage.setItem("bankingSections", JSON.stringify(next))
      return next
    })
  }, [])

  const [accountsSummary, setAccountsSummary] = useState<AccountsSummary>({
    totalBalance: 0,
    weightedInterest: 0,
    count: 0,
  })
  const [cardsSummary, setCardsSummary] = useState<CardsSummary>({
    totalUsed: 0,
    count: 0,
  })
  const [loansSummary, setLoansSummary] = useState<LoansSummary>({
    totalDebt: 0,
    totalMonthlyPayments: 0,
    weightedInterest: 0,
    count: 0,
  })
  const [creditsSummary, setCreditsSummary] = useState<CreditsSummary>({
    totalDrawn: 0,
    totalLimit: 0,
    weightedInterest: 0,
    count: 0,
  })
  const [creditDisplayItems, setCreditDisplayItems] = useState<
    CreditDisplayItem[]
  >([])
  const [creditEditHandlers, setCreditEditHandlers] =
    useState<CreditEditHandlers | null>(null)

  const [manualControllersMap, setManualControllersMap] = useState<
    Partial<Record<ManualPositionAsset, ManualSectionController>>
  >({})

  const registerManualController = useCallback<ManualControllerRegistrar>(
    (asset, controller) => {
      setManualControllersMap(prev => {
        const previous = prev[asset]
        if (controller) {
          if (previous === controller) {
            return prev
          }
          return { ...prev, [asset]: controller }
        }
        if (previous === undefined) {
          return prev
        }
        const next = { ...prev }
        delete next[asset]
        return next
      })
    },
    [],
  )

  const manualControllers = useMemo(
    () =>
      MANUAL_ASSETS_ORDER.map(
        assetKey => manualControllersMap[assetKey],
      ).filter((controller): controller is ManualSectionController =>
        Boolean(controller),
      ),
    [manualControllersMap],
  )

  const enterGlobalEditMode = useCallback(() => {
    manualControllers.forEach(controller => {
      controller.enterEditMode()
    })
  }, [manualControllers])

  const entityOrigins = useMemo<Record<string, EntityOrigin | null>>(() => {
    const map: Record<string, EntityOrigin | null> = {}
    entities?.forEach(entity => {
      map[entity.id] = entity.origin ?? null
    })
    return map
  }, [entities])

  const accountPositions = useMemo<AccountPosition[]>(() => {
    if (!positionsData?.positions) return []
    return Object.values(positionsData.positions)
      .flat()
      .flatMap(entityPosition => {
        const entityMeta = entities?.find(
          entity => entity.id === entityPosition.entity.id,
        )
        if (
          entityMeta &&
          entityMeta.type !== EntityType.FINANCIAL_INSTITUTION
        ) {
          return []
        }

        const product = entityPosition.products[ProductType.ACCOUNT] as
          | { entries?: Account[] }
          | undefined
        if (!product?.entries?.length) return []

        const entityId = entityPosition.entity.id
        const entityName = entityMeta?.name ?? entityPosition.entity.name
        const entityOrigin =
          entityMeta?.origin ?? entityPosition.entity.origin ?? null

        return product.entries.map(account => ({
          ...account,
          entityId,
          entityName,
          entryId: account.id,
          entityOrigin,
        }))
      })
  }, [positionsData, entities])

  const cardPositions = useMemo<CardPosition[]>(() => {
    if (!positionsData?.positions) return []
    return Object.values(positionsData.positions)
      .flat()
      .flatMap(entityPosition => {
        const entityMeta = entities?.find(
          entity => entity.id === entityPosition.entity.id,
        )
        if (
          entityMeta &&
          entityMeta.type !== EntityType.FINANCIAL_INSTITUTION
        ) {
          return []
        }

        const product = entityPosition.products[ProductType.CARD] as
          | { entries?: CardModel[] }
          | undefined
        if (!product?.entries?.length) return []

        const entityId = entityPosition.entity.id
        const entityName = entityMeta?.name ?? entityPosition.entity.name
        const entityOrigin =
          entityMeta?.origin ?? entityPosition.entity.origin ?? null

        return product.entries.map(card => ({
          ...card,
          entityId,
          entityName,
          entryId: card.id,
          entityOrigin,
        }))
      })
  }, [positionsData, entities])

  const loanPositions = useMemo<LoanPosition[]>(() => {
    if (!positionsData?.positions) return []
    return Object.values(positionsData.positions)
      .flat()
      .flatMap(entityPosition => {
        const entityMeta = entities?.find(
          entity => entity.id === entityPosition.entity.id,
        )
        if (
          entityMeta &&
          entityMeta.type !== EntityType.FINANCIAL_INSTITUTION
        ) {
          return []
        }

        const product = entityPosition.products[ProductType.LOAN] as
          | { entries?: Loan[] }
          | undefined
        if (!product?.entries?.length) return []

        const entityId = entityPosition.entity.id
        const entityName = entityMeta?.name ?? entityPosition.entity.name
        const entityOrigin =
          entityMeta?.origin ?? entityPosition.entity.origin ?? null

        return product.entries.map(loan => ({
          ...loan,
          entityId,
          entityName,
          entryId: loan.id,
          entityOrigin,
        }))
      })
  }, [positionsData, entities])

  const creditPositions = useMemo<CreditPosition[]>(() => {
    if (!positionsData?.positions) return []
    return Object.values(positionsData.positions)
      .flat()
      .flatMap(entityPosition => {
        const entityMeta = entities?.find(
          entity => entity.id === entityPosition.entity.id,
        )
        if (
          entityMeta &&
          entityMeta.type !== EntityType.FINANCIAL_INSTITUTION
        ) {
          return []
        }

        const product = entityPosition.products[ProductType.CREDIT] as
          | { entries?: CreditDetail[] }
          | undefined
        if (!product?.entries?.length) return []

        const entityId = entityPosition.entity.id
        const entityName = entityMeta?.name ?? entityPosition.entity.name
        const entityOrigin =
          entityMeta?.origin ?? entityPosition.entity.origin ?? null

        return product.entries.map(credit => ({
          ...credit,
          entityId,
          entityName,
          entryId: credit.id,
          entityOrigin,
        }))
      })
  }, [positionsData, entities])

  const filteredAccounts = useMemo(() => {
    if (selectedEntities.length === 0) return accountPositions
    return accountPositions.filter(account =>
      selectedEntities.includes(account.entityId),
    )
  }, [accountPositions, selectedEntities])

  const filteredCards = useMemo(() => {
    if (selectedEntities.length === 0) return cardPositions
    return cardPositions.filter(card =>
      selectedEntities.includes(card.entityId),
    )
  }, [cardPositions, selectedEntities])

  const filteredLoans = useMemo(() => {
    if (selectedEntities.length === 0) return loanPositions
    return loanPositions.filter(loan =>
      selectedEntities.includes(loan.entityId),
    )
  }, [loanPositions, selectedEntities])

  const filteredCredits = useMemo(() => {
    if (selectedEntities.length === 0) return creditPositions
    return creditPositions.filter(credit =>
      selectedEntities.includes(credit.entityId),
    )
  }, [creditPositions, selectedEntities])

  const bankingEntities = useMemo(() => {
    const ids = new Set<string>()
    accountPositions.forEach(position => ids.add(position.entityId))
    cardPositions.forEach(position => ids.add(position.entityId))
    loanPositions.forEach(position => ids.add(position.entityId))
    creditPositions.forEach(position => ids.add(position.entityId))

    return (
      entities?.filter(entity => {
        const entityId = entity.id
        if (typeof entityId !== "string" || entityId.length === 0) {
          return false
        }
        if (entityId.startsWith("new-")) {
          return false
        }
        if (entity.type !== EntityType.FINANCIAL_INSTITUTION) {
          return false
        }
        return ids.has(entityId)
      }) ?? []
    )
  }, [accountPositions, cardPositions, loanPositions, entities])

  useEffect(() => {
    if (bankingEntities.length === 0) {
      if (selectedEntities.length > 0) {
        setSelectedEntities([])
      }
      return
    }

    const allowed = new Set(bankingEntities.map(e => e.id))
    setSelectedEntities(prev => {
      const next = prev.filter(id => allowed.has(id))
      return next.length === prev.length ? prev : next
    })
  }, [bankingEntities, selectedEntities])

  const handleFocusEntity = useCallback(
    (entityId: string) => {
      if (!entityId || entityId.startsWith("new-")) {
        return
      }
      const entityType = entities?.find(entity => entity.id === entityId)?.type
      if (entityType && entityType !== EntityType.FINANCIAL_INSTITUTION) {
        return
      }
      setSelectedEntities(prev =>
        prev.includes(entityId) ? prev : [...prev, entityId],
      )
    },
    [entities],
  )

  const updateAccountsSummary = useCallback((summary: AccountsSummary) => {
    setAccountsSummary(prev =>
      prev.totalBalance === summary.totalBalance &&
      prev.weightedInterest === summary.weightedInterest &&
      prev.count === summary.count
        ? prev
        : summary,
    )
  }, [])

  const updateCardsSummary = useCallback((summary: CardsSummary) => {
    setCardsSummary(prev =>
      prev.totalUsed === summary.totalUsed && prev.count === summary.count
        ? prev
        : summary,
    )
  }, [])

  const updateLoansSummary = useCallback((summary: LoansSummary) => {
    setLoansSummary(prev =>
      prev.totalDebt === summary.totalDebt &&
      prev.totalMonthlyPayments === summary.totalMonthlyPayments &&
      prev.weightedInterest === summary.weightedInterest &&
      prev.count === summary.count
        ? prev
        : summary,
    )
  }, [])

  const updateCreditsSummary = useCallback((summary: CreditsSummary) => {
    setCreditsSummary(prev =>
      prev.totalDrawn === summary.totalDrawn &&
      prev.totalLimit === summary.totalLimit &&
      prev.weightedInterest === summary.weightedInterest &&
      prev.count === summary.count
        ? prev
        : summary,
    )
  }, [])

  const totalAccountBalance = accountsSummary.totalBalance
  const totalCardUsed = cardsSummary.totalUsed
  const totalLoanDebt = loansSummary.totalDebt + creditsSummary.totalDrawn
  const totalMonthlyPayments = loansSummary.totalMonthlyPayments
  const combinedDebtCount = loansSummary.count + creditsSummary.count

  const combinedWeightedInterest = useMemo(() => {
    const loanWeight = loansSummary.weightedInterest * loansSummary.totalDebt
    const creditWeight =
      creditsSummary.weightedInterest * creditsSummary.totalDrawn
    const totalBase = loansSummary.totalDebt + creditsSummary.totalDrawn
    return totalBase > 0 ? (loanWeight + creditWeight) / totalBase : 0
  }, [loansSummary, creditsSummary])

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <motion.div
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeListItem}>
        <div className="mb-6 space-y-4">
          <div className="flex flex-col gap-3 [@media(min-width:500px)]:flex-row [@media(min-width:500px)]:items-center [@media(min-width:500px)]:justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                className="p-1 h-8 w-8"
                onClick={() => navigate(-1)}
              >
                <ArrowLeft size={20} />
              </Button>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold">{t.banking.title}</h1>
                <PinAssetButton
                  assetId="banking"
                  className="hidden md:inline-flex"
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2 [@media(min-width:500px)]:justify-end">
              {manualControllers.length > 0 && (
                <BankingManualControls
                  controllers={manualControllers}
                  t={t}
                  showToast={showToast}
                  refreshEntity={refreshEntity}
                  fetchEntities={fetchEntities}
                  refreshData={refreshData}
                  className="items-center [@media(min-width:450px)]:items-end"
                />
              )}
            </div>
          </div>
          <InvestmentFilters
            filteredEntities={bankingEntities}
            selectedEntities={selectedEntities}
            onEntitiesChange={setSelectedEntities}
          />
        </div>
      </motion.div>

      <motion.div variants={fadeListItem}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {accountsSummary.count > 0 && (
            <Card className="p-4">
              <div className="mb-2 flex items-center gap-2">
                <Wallet className="h-5 w-5 text-blue-500" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t.banking.totalBalance}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalAccountBalance,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              {accountsSummary.weightedInterest > 0 && (
                <div className="mt-2 flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                  <Percent className="h-3 w-3" />
                  {formatPercentage(
                    accountsSummary.weightedInterest * 100,
                    locale,
                  )}
                  <span>{t.banking.avgInterest}</span>
                </div>
              )}
            </Card>
          )}

          {cardsSummary.count > 0 && (
            <Card className="p-4">
              <div className="mb-2 flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-orange-500" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t.banking.totalCardUsed}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalCardUsed,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {cardsSummary.count}{" "}
                {cardsSummary.count === 1 ? t.banking.card : t.banking.cards}
              </div>
            </Card>
          )}

          {combinedDebtCount > 0 && (
            <Card className="p-4">
              <div className="mb-2 flex items-center gap-2">
                <HandCoins className="h-5 w-5 text-red-500" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t.banking.totalDebt}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalLoanDebt,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              {combinedWeightedInterest > 0 && (
                <div className="mt-2 flex items-center gap-1 text-xs text-red-500 dark:text-red-400">
                  <Percent className="h-3 w-3" />
                  {formatPercentage(combinedWeightedInterest * 100, locale)}
                  <span>{t.banking.avgInterest}</span>
                </div>
              )}
            </Card>
          )}

          {loansSummary.count > 0 && (
            <Card className="p-4">
              <div className="mb-2 flex items-center gap-2">
                <Calendar className="h-5 w-5 text-purple-500" />
                <span className="text-sm font-medium text-muted-foreground">
                  {t.banking.monthlyPayments}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalMonthlyPayments,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {loansSummary.count}{" "}
                {loansSummary.count === 1 ? t.banking.loan : t.banking.loans}
              </div>
            </Card>
          )}
        </div>
      </motion.div>
      <ManualPositionsManager asset="bankAccounts">
        <BankAccountsSection
          t={t}
          locale={locale}
          positions={filteredAccounts}
          defaultCurrency={settings.general.defaultCurrency}
          exchangeRates={exchangeRates}
          showAccountNumbers={showAccountNumbers}
          onToggleAccountNumbers={() => setShowAccountNumbers(v => !v)}
          onSummaryChange={updateAccountsSummary}
          onFocusEntity={handleFocusEntity}
          selectedEntities={selectedEntities}
          entityOrigins={entityOrigins}
          onRegisterController={registerManualController}
          onEnterGlobalEditMode={enterGlobalEditMode}
          collapsed={!!collapsedSections.accounts}
          onToggleCollapsed={() => toggleSection("accounts")}
        />
      </ManualPositionsManager>

      <ManualPositionsManager asset="bankCards">
        <BankCardsSection
          t={t}
          locale={locale}
          positions={filteredCards}
          defaultCurrency={settings.general.defaultCurrency}
          exchangeRates={exchangeRates}
          onSummaryChange={updateCardsSummary}
          onFocusEntity={handleFocusEntity}
          selectedEntities={selectedEntities}
          entityOrigins={entityOrigins}
          onRegisterController={registerManualController}
          onEnterGlobalEditMode={enterGlobalEditMode}
          collapsed={!!collapsedSections.cards}
          onToggleCollapsed={() => toggleSection("cards")}
        />
      </ManualPositionsManager>

      <ManualPositionsManager asset="bankLoans">
        <BankLoansSection
          t={t}
          locale={locale}
          positions={filteredLoans}
          creditDisplayItems={creditDisplayItems}
          creditEditHandlers={creditEditHandlers}
          defaultCurrency={settings.general.defaultCurrency}
          exchangeRates={exchangeRates}
          onLoansSummaryChange={updateLoansSummary}
          onFocusEntity={handleFocusEntity}
          selectedEntities={selectedEntities}
          entityOrigins={entityOrigins}
          onRegisterController={registerManualController}
          onEnterGlobalEditMode={enterGlobalEditMode}
          collapsed={!!collapsedSections.loans}
          onToggleCollapsed={() => toggleSection("loans")}
          onBeginCreditCreate={(entityId?: string) => {
            enterGlobalEditMode()
            const creditCtrl = manualControllersMap["bankCredits"]
            if (creditCtrl) {
              creditCtrl.beginCreate(entityId ? { entityId } : undefined)
            }
          }}
        />
      </ManualPositionsManager>
      <ManualPositionsManager asset="bankCredits">
        <BankCreditsBridge
          onRegisterController={registerManualController}
          onCreditsSummaryChange={updateCreditsSummary}
          selectedEntities={selectedEntities}
          entityOrigins={entityOrigins}
          defaultCurrency={settings.general.defaultCurrency}
          exchangeRates={exchangeRates}
          creditPositions={filteredCredits}
          onCreditDisplayItemsChange={setCreditDisplayItems}
          onCreditEditHandlersChange={setCreditEditHandlers}
        />
      </ManualPositionsManager>
    </motion.div>
  )
}

interface SectionCommonProps {
  t: Translations
  locale: Locale
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
  onFocusEntity: (entityId: string) => void
  selectedEntities: string[]
  entityOrigins: Record<string, EntityOrigin | null>
  onRegisterController: ManualControllerRegistrar
  onEnterGlobalEditMode: () => void
  collapsed: boolean
  onToggleCollapsed: () => void
}

interface BankAccountsSectionProps extends SectionCommonProps {
  positions: AccountPosition[]
  showAccountNumbers: boolean
  onToggleAccountNumbers: () => void
  onSummaryChange: (summary: AccountsSummary) => void
}

function BankAccountsSection({
  t,
  locale,
  positions,
  defaultCurrency,
  exchangeRates,
  showAccountNumbers,
  onToggleAccountNumbers,
  onSummaryChange,
  onFocusEntity,
  selectedEntities,
  entityOrigins,
  onRegisterController,
  onEnterGlobalEditMode,
  collapsed,
  onToggleCollapsed,
}: BankAccountsSectionProps) {
  const {
    asset,
    drafts,
    isEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    beginCreate,
    translate: manualTranslate,
    isEntryDeleted,
    isDraftDirty: manualIsDraftDirty,
    assetPath,
    manualEntities,
    hasLocalChanges,
    isSaving,
    assetTitle,
    addLabel,
    editLabel,
    cancelLabel,
    saveLabel,
    requestSave,
    requestCancel,
    enterEditMode,
    collectSavePayload,
    setSavingState,
    handleExternalSaveSuccess,
  } = useManualPositions()

  const [copiedIban, setCopiedIban] = useState<string | null>(null)

  const handleCopyIban = useCallback(async (iban: string) => {
    try {
      await navigator.clipboard.writeText(iban)
      setCopiedIban(iban)

      setTimeout(() => {
        setCopiedIban(null)
      }, 2000)
    } catch (error) {
      console.error("Failed to copy IBAN:", error)
      const textArea = document.createElement("textarea")
      textArea.value = iban
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand("copy")
      document.body.removeChild(textArea)

      setCopiedIban(iban)
      setTimeout(() => {
        setCopiedIban(null)
      }, 2000)
    }
  }, [])

  const accountController = useMemo<ManualSectionController>(
    () => ({
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      canCreate: manualEntities.length > 0,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      translate: manualTranslate,
      collectSavePayload,
      setSavingState,
      handleSaveSuccess: handleExternalSaveSuccess,
    }),
    [
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities.length,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      manualTranslate,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    ],
  )

  useEffect(() => {
    onRegisterController(asset, accountController)
    return () => onRegisterController(asset, null)
  }, [asset, accountController, onRegisterController])

  const defaultEntityId =
    selectedEntities.length === 1 ? selectedEntities[0] : undefined
  const canCreate = manualEntities.length > 0

  const accountDrafts = drafts as AccountDraft[]

  const computedPositions = useMemo<AccountDisplay[]>(
    () =>
      positions.map(account => {
        const total = account.total ?? 0
        const convertedTotal = convertCurrency(
          total,
          account.currency,
          defaultCurrency,
          exchangeRates,
        )

        const retained = account.retained ?? null
        const convertedRetained = isFiniteNumber(retained)
          ? convertCurrency(
              retained,
              account.currency,
              defaultCurrency,
              exchangeRates,
            )
          : null

        const pending = account.pending_transfers ?? null
        const convertedPending = isFiniteNumber(pending)
          ? convertCurrency(
              pending,
              account.currency,
              defaultCurrency,
              exchangeRates,
            )
          : null

        return {
          ...account,
          convertedTotal,
          convertedRetained,
          convertedPendingTransfers: convertedPending,
        }
      }),
    [positions, defaultCurrency, exchangeRates],
  )

  const buildPositionFromDraft = useCallback(
    (draft: AccountDraft): AccountDisplay => {
      const entryId = draft.originalId ?? draft.id ?? draft.localId
      const total = draft.total ?? 0
      const retained = draft.retained ?? null
      const pending = draft.pending_transfers ?? null

      const convertedTotal = convertCurrency(
        total,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )
      const convertedRetained = isFiniteNumber(retained)
        ? convertCurrency(
            retained,
            draft.currency,
            defaultCurrency,
            exchangeRates,
          )
        : null
      const convertedPending = isFiniteNumber(pending)
        ? convertCurrency(
            pending,
            draft.currency,
            defaultCurrency,
            exchangeRates,
          )
        : null

      return {
        ...draft,
        id: entryId,
        entryId,
        entityId: draft.entityId,
        entityName: draft.entityName,
        entityOrigin: entityOrigins[draft.entityId] ?? null,
        total,
        retained,
        pending_transfers: pending,
        convertedTotal,
        convertedRetained,
        convertedPendingTransfers: convertedPending,
        source: DataSource.MANUAL,
      }
    },
    [defaultCurrency, exchangeRates, entityOrigins],
  )

  const displayItems = useMemo<
    ManualDisplayItem<AccountDisplay, AccountDraft>[]
  >(
    () =>
      mergeManualDisplayItems<AccountDisplay, AccountDraft>({
        positions: computedPositions,
        manualDrafts: accountDrafts,
        getPositionOriginalId: (position: AccountDisplay) => position.entryId,
        getDraftOriginalId: (draft: AccountDraft) => draft.originalId,
        getDraftLocalId: (draft: AccountDraft) => draft.localId,
        getPositionKey: (position: AccountDisplay) => position.entryId,
        buildPositionFromDraft,
        isManualPosition: (position: AccountDisplay) =>
          position.source === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: (draft: AccountDraft) =>
          selectedEntities.length === 0 ||
          selectedEntities.includes(draft.entityId),
        mergeDraftMetadata: (
          position: AccountDisplay,
          draft: AccountDraft,
        ) => ({
          ...position,
          entityId: draft.entityId,
          entityName: draft.entityName,
          entityOrigin: entityOrigins[draft.entityId] ?? null,
        }),
      }),
    [
      computedPositions,
      accountDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      entityOrigins,
    ],
  )

  const summary = useMemo<AccountsSummary>(() => {
    const totals = displayItems.reduce(
      (accumulator, item) => {
        if (item.originalId && isEntryDeleted(item.originalId)) {
          return accumulator
        }

        const total = item.position.convertedTotal ?? 0
        accumulator.sum += total
        const interest = item.position.interest ?? 0
        if (total > 0 && interest > 0) {
          accumulator.weighted += interest * total
        }
        accumulator.count += 1
        return accumulator
      },
      { sum: 0, weighted: 0, count: 0 },
    )

    const weightedInterest = totals.sum > 0 ? totals.weighted / totals.sum : 0

    return {
      totalBalance: totals.sum,
      weightedInterest,
      count: totals.count,
    }
  }, [displayItems, isEntryDeleted])

  useEffect(() => {
    onSummaryChange(summary)
  }, [summary, onSummaryChange])

  const manualEmptyTitle = manualTranslate(`${assetPath}.empty.title`)
  const manualEmptyDescription = manualTranslate(
    `${assetPath}.empty.description`,
  )

  return (
    <motion.div variants={fadeListItem} className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="flex items-center gap-2 cursor-pointer"
          onClick={onToggleCollapsed}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              collapsed && "-rotate-90",
            )}
          />
          <Wallet className="h-5 w-5" />
          <h2 className="text-xl font-semibold">
            {t.banking.accounts}
            <span className="ml-2 text-sm text-muted-foreground">
              ({summary.count})
            </span>
          </h2>
        </button>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Button
              variant={showAccountNumbers ? "outline" : "ghost"}
              size="sm"
              className="flex items-center gap-1 h-8 px-2 text-xs"
              onClick={onToggleAccountNumbers}
            >
              <Binary className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Iban</span>
            </Button>
            {!isEditMode && (
              <Button
                variant="default"
                size="icon"
                className="h-8 w-8"
                onClick={onEnterGlobalEditMode}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8"
              onClick={() => {
                onEnterGlobalEditMode()
                beginCreate(
                  defaultEntityId ? { entityId: defaultEntityId } : undefined,
                )
              }}
              disabled={!canCreate}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {!collapsed &&
        (summary.count === 0 ? (
          <Card className="flex flex-col items-center gap-4 p-10 text-center">
            <div className="text-blue-500 dark:text-blue-400">
              <Wallet className="mx-auto h-12 w-12" />
            </div>
            <h3 className="text-lg font-semibold">{manualEmptyTitle}</h3>
            <p className="text-sm text-muted-foreground">
              {manualEmptyDescription}
            </p>
          </Card>
        ) : (
          <TooltipProvider delayDuration={120}>
            <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
              {displayItems.map(item => {
                const { position, manualDraft, isManual, isDirty, originalId } =
                  item

                if (originalId && isEntryDeleted(originalId)) {
                  return null
                }

                const hasInterest =
                  isFiniteNumber(position.interest) &&
                  (position.interest ?? 0) > 0
                const hasRetained =
                  isFiniteNumber(position.convertedRetained) &&
                  Math.abs(position.convertedRetained ?? 0) > 0
                const hasPendingTransfers =
                  isFiniteNumber(position.convertedPendingTransfers) &&
                  Math.abs(position.convertedPendingTransfers ?? 0) > 0
                const hasFooter =
                  hasInterest || hasRetained || hasPendingTransfers

                const highlightClass = isDirty
                  ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                  : ""
                const showActions = isEditMode && isManual

                return (
                  <Card
                    key={item.key}
                    className={cn(
                      "flex w-full flex-col gap-4 self-center p-4 transition-shadow hover:shadow-lg",
                      highlightClass,
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-2">
                        {getAccountTypeIcon(position.type as AccountType)}
                        <Badge
                          variant="secondary"
                          className={cn(
                            "text-xs",
                            getAccountTypeColor(position.type),
                          )}
                        >
                          {t.accountTypes[position.type] || position.type}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2">
                        <SourceBadge
                          source={position.source}
                          onClick={
                            position.source === DataSource.MANUAL
                              ? onEnterGlobalEditMode
                              : undefined
                          }
                        />
                        <EntityBadge
                          name={position.entityName}
                          origin={position.entityOrigin}
                          onClick={() => onFocusEntity(position.entityId)}
                          className="text-xs"
                          title={position.entityName}
                        />
                      </div>
                    </div>

                    <div className="flex flex-1 flex-col justify-between gap-4">
                      <div className="space-y-2">
                        {position.name && (
                          <h3 className="text-lg font-semibold">
                            {position.name}
                          </h3>
                        )}
                        {position.iban && (
                          <div className="flex items-center gap-2 group">
                            <div className="font-mono text-sm text-muted-foreground">
                              {formatIban(position.iban, showAccountNumbers)}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 ${
                                copiedIban === position.iban
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                              }`}
                              onClick={() => handleCopyIban(position.iban!)}
                              title={
                                copiedIban === position.iban
                                  ? t.common.copied
                                  : t.common.copy
                              }
                            >
                              {copiedIban === position.iban ? (
                                <Check className="h-3 w-3" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </Button>
                          </div>
                        )}
                        <div className="space-y-1">
                          <div className="text-2xl font-bold">
                            {formatCurrency(
                              position.convertedTotal,
                              locale,
                              defaultCurrency,
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {position.currency !== defaultCurrency && (
                              <span>
                                {formatCurrency(
                                  position.total ?? 0,
                                  locale,
                                  position.currency,
                                )}
                                <span aria-hidden="true" className="px-1">
                                  •
                                </span>
                              </span>
                            )}
                            <span>{t.banking.available}</span>
                          </div>
                        </div>
                      </div>

                      {hasFooter && (
                        <div className="flex flex-wrap items-center gap-4 border-t border-border pt-3 text-xs">
                          {hasInterest && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  className="flex cursor-help items-center gap-1 text-green-600 transition-colors hover:text-green-500 dark:text-green-400 dark:hover:text-green-300"
                                >
                                  <Percent className="h-3 w-3" />
                                  {formatPercentage(
                                    (position.interest ?? 0) * 100,
                                    locale,
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {t.banking.interestRate}
                              </TooltipContent>
                            </Tooltip>
                          )}
                          {hasRetained && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  className="flex cursor-help items-center gap-1 text-orange-500 transition-colors hover:text-orange-400"
                                >
                                  <Shield className="h-3 w-3" />
                                  {formatCurrency(
                                    position.convertedRetained ?? 0,
                                    locale,
                                    defaultCurrency,
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {t.banking.retainedAmount}
                              </TooltipContent>
                            </Tooltip>
                          )}
                          {hasPendingTransfers && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  className="flex cursor-help items-center gap-1 text-blue-500 transition-colors hover:text-blue-400"
                                >
                                  <AlertCircle className="h-3 w-3" />
                                  {formatCurrency(
                                    position.convertedPendingTransfers ?? 0,
                                    locale,
                                    defaultCurrency,
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {t.banking.pendingTransfers}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      )}

                      {isDirty && (
                        <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
                          {manualTranslate("management.unsavedChanges")}
                        </p>
                      )}

                      {showActions && (
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="flex items-center gap-1"
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
                            className="flex items-center gap-1 text-red-500 transition-colors hover:text-red-600"
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
                            {t.common.delete}
                          </Button>
                        </div>
                      )}
                    </div>
                  </Card>
                )
              })}
            </div>
          </TooltipProvider>
        ))}
    </motion.div>
  )
}

interface BankCardsSectionProps extends SectionCommonProps {
  positions: CardPosition[]
  onSummaryChange: (summary: CardsSummary) => void
}

function BankCardsSection({
  t,
  locale,
  positions,
  defaultCurrency,
  exchangeRates,
  onSummaryChange,
  onFocusEntity,
  selectedEntities,
  entityOrigins,
  onRegisterController,
  onEnterGlobalEditMode,
  collapsed,
  onToggleCollapsed,
}: BankCardsSectionProps) {
  const {
    asset,
    drafts,
    isEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    beginCreate,
    translate: manualTranslate,
    isEntryDeleted,
    isDraftDirty: manualIsDraftDirty,
    assetPath,
    manualEntities,
    hasLocalChanges,
    isSaving,
    assetTitle,
    addLabel,
    editLabel,
    cancelLabel,
    saveLabel,
    requestSave,
    requestCancel,
    enterEditMode,
    collectSavePayload,
    setSavingState,
    handleExternalSaveSuccess,
  } = useManualPositions()

  const cardController = useMemo<ManualSectionController>(
    () => ({
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      canCreate: manualEntities.length > 0,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      translate: manualTranslate,
      collectSavePayload,
      setSavingState,
      handleSaveSuccess: handleExternalSaveSuccess,
    }),
    [
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities.length,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      manualTranslate,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    ],
  )

  useEffect(() => {
    onRegisterController(asset, cardController)
    return () => onRegisterController(asset, null)
  }, [asset, cardController, onRegisterController])

  const defaultEntityId =
    selectedEntities.length === 1 ? selectedEntities[0] : undefined
  const canCreate = manualEntities.length > 0

  const cardDrafts = drafts as CardDraft[]

  const computedPositions = useMemo<CardDisplay[]>(
    () =>
      positions.map(card => {
        const convertedUsed = convertCurrency(
          card.used ?? 0,
          card.currency,
          defaultCurrency,
          exchangeRates,
        )
        const convertedLimit = isFiniteNumber(card.limit)
          ? convertCurrency(
              card.limit ?? 0,
              card.currency,
              defaultCurrency,
              exchangeRates,
            )
          : null

        return {
          ...card,
          convertedUsed,
          convertedLimit,
        }
      }),
    [positions, defaultCurrency, exchangeRates],
  )

  const buildPositionFromDraft = useCallback(
    (draft: CardDraft): CardDisplay => {
      const entryId = draft.originalId ?? draft.id ?? draft.localId
      const convertedUsed = convertCurrency(
        draft.used ?? 0,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )
      const convertedLimit = isFiniteNumber(draft.limit)
        ? convertCurrency(
            draft.limit ?? 0,
            draft.currency,
            defaultCurrency,
            exchangeRates,
          )
        : null

      return {
        ...draft,
        id: entryId,
        entryId,
        entityId: draft.entityId,
        entityName: draft.entityName,
        entityOrigin: entityOrigins[draft.entityId] ?? null,
        convertedUsed,
        convertedLimit,
        source: DataSource.MANUAL,
      }
    },
    [defaultCurrency, exchangeRates, entityOrigins],
  )

  const displayItems = useMemo<ManualDisplayItem<CardDisplay, CardDraft>[]>(
    () =>
      mergeManualDisplayItems<CardDisplay, CardDraft>({
        positions: computedPositions,
        manualDrafts: cardDrafts,
        getPositionOriginalId: (position: CardDisplay) => position.entryId,
        getDraftOriginalId: (draft: CardDraft) => draft.originalId,
        getDraftLocalId: (draft: CardDraft) => draft.localId,
        getPositionKey: (position: CardDisplay) => position.entryId,
        buildPositionFromDraft,
        isManualPosition: (position: CardDisplay) =>
          position.source === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: (draft: CardDraft) =>
          selectedEntities.length === 0 ||
          selectedEntities.includes(draft.entityId),
        mergeDraftMetadata: (position: CardDisplay, draft: CardDraft) => ({
          ...position,
          entityId: draft.entityId,
          entityName: draft.entityName,
          entityOrigin: entityOrigins[draft.entityId] ?? null,
        }),
      }),
    [
      computedPositions,
      cardDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      entityOrigins,
    ],
  )

  const summary = useMemo<CardsSummary>(() => {
    const totals = displayItems.reduce(
      (accumulator, item) => {
        if (item.originalId && isEntryDeleted(item.originalId)) {
          return accumulator
        }

        accumulator.total += item.position.convertedUsed ?? 0
        accumulator.count += 1
        return accumulator
      },
      { total: 0, count: 0 },
    )

    return {
      totalUsed: totals.total,
      count: totals.count,
    }
  }, [displayItems, isEntryDeleted])

  useEffect(() => {
    onSummaryChange(summary)
  }, [summary, onSummaryChange])

  const manualEmptyTitle = manualTranslate(`${assetPath}.empty.title`)
  const manualEmptyDescription = manualTranslate(
    `${assetPath}.empty.description`,
  )

  return (
    <motion.div variants={fadeListItem} className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="flex items-center gap-2 cursor-pointer"
          onClick={onToggleCollapsed}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              collapsed && "-rotate-90",
            )}
          />
          <CreditCard className="h-5 w-5" />
          <h2 className="text-xl font-semibold">
            {t.banking.cards}
            <span className="ml-2 text-sm text-muted-foreground">
              ({summary.count})
            </span>
          </h2>
        </button>
        {!collapsed && (
          <div className="flex items-center gap-2">
            {!isEditMode && (
              <Button
                variant="default"
                size="icon"
                className="h-8 w-8"
                onClick={onEnterGlobalEditMode}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8"
              onClick={() => {
                onEnterGlobalEditMode()
                beginCreate(
                  defaultEntityId ? { entityId: defaultEntityId } : undefined,
                )
              }}
              disabled={!canCreate}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {!collapsed &&
        (summary.count === 0 ? (
          <Card className="flex flex-col items-center gap-4 p-10 text-center">
            <div className="text-orange-500 dark:text-orange-400">
              <CreditCard className="mx-auto h-12 w-12" />
            </div>
            <h3 className="text-lg font-semibold">{manualEmptyTitle}</h3>
            <p className="text-sm text-muted-foreground">
              {manualEmptyDescription}
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 items-center">
            {displayItems.map(item => {
              const { position, manualDraft, isManual, isDirty, originalId } =
                item

              if (originalId && isEntryDeleted(originalId)) {
                return null
              }

              const showActions = isEditMode && isManual
              const highlightClass = isDirty
                ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                : ""

              const gradientClass =
                position.type === CardType.CREDIT
                  ? "from-blue-600 to-blue-800"
                  : "from-green-600 to-green-800"

              const utilization =
                position.convertedLimit && position.convertedLimit > 0
                  ? Math.min(
                      (position.convertedUsed / position.convertedLimit) * 100,
                      200,
                    )
                  : 0

              return (
                <Card
                  key={item.key}
                  className={cn(
                    "flex flex-col overflow-hidden transition-shadow hover:shadow-lg",
                    highlightClass,
                    !position.active && "opacity-60 grayscale",
                  )}
                >
                  <div
                    className={cn(
                      "relative flex flex-col justify-center gap-2 p-6 text-white",
                      "bg-gradient-to-br",
                      gradientClass,
                    )}
                  >
                    <div className="absolute right-3 top-3 flex items-center gap-2">
                      <SourceBadge
                        source={position.source}
                        onClick={
                          position.source === DataSource.MANUAL
                            ? onEnterGlobalEditMode
                            : undefined
                        }
                      />
                      <EntityBadge
                        name={position.entityName}
                        origin={position.entityOrigin}
                        onClick={() => onFocusEntity(position.entityId)}
                        className="text-xs"
                      />
                    </div>
                    <div className="mb-4 flex items-center gap-2">
                      <CreditCard className="h-5 w-5" />
                      <span className="text-sm font-medium">
                        {position.type === CardType.CREDIT
                          ? t.cardTypes.CREDIT
                          : t.cardTypes.DEBIT}
                      </span>
                    </div>
                    <div className="mb-2 font-mono text-lg">
                      {formatCardNumber(position.ending)}
                    </div>
                    {position.name && (
                      <div className="text-sm opacity-90">{position.name}</div>
                    )}
                    {!position.active && (
                      <Badge
                        variant="destructive"
                        className="absolute left-3 bottom-3 text-xs"
                      >
                        {manualTranslate(`${assetPath}.summary.inactive`)}
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-1 flex-col space-y-3 p-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">
                        {t.banking.used}
                      </span>
                      <span className="font-semibold">
                        {formatCurrency(
                          position.convertedUsed,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    {Number(position.convertedLimit || 0) > 0 && (
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">
                          {t.banking.limit}
                        </span>
                        <span>
                          {formatCurrency(
                            position.convertedLimit!,
                            locale,
                            defaultCurrency,
                          )}
                        </span>
                      </div>
                    )}
                    {Number(position.convertedLimit || 0) > 0 && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>{t.banking.utilization}</span>
                          <span>
                            {formatPercentage(
                              Math.min(utilization, 100),
                              locale,
                            )}
                          </span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-muted">
                          <div
                            className={cn(
                              "h-2 rounded-full",
                              utilization > 80
                                ? "bg-red-500"
                                : utilization > 60
                                  ? "bg-yellow-400"
                                  : "bg-emerald-500",
                            )}
                            style={{ width: `${Math.min(utilization, 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                    {position.currency !== defaultCurrency && (
                      <div className="border-t border-border pt-2 text-xs text-muted-foreground">
                        {formatCurrency(
                          position.used,
                          locale,
                          position.currency,
                        )}
                        {isFiniteNumber(position.limit) &&
                          ` / ${formatCurrency(position.limit ?? 0, locale, position.currency)}`}
                      </div>
                    )}
                    {isDirty && (
                      <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
                        {manualTranslate("management.unsavedChanges")}
                      </p>
                    )}
                    {showActions && (
                      <div className="mt-auto flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (manualDraft?.originalId) {
                              editByOriginalId(manualDraft.originalId)
                            } else if (manualDraft) {
                              editByLocalId(manualDraft.localId)
                            } else if (item.originalId) {
                              editByOriginalId(item.originalId)
                            }
                          }}
                          className="flex items-center gap-1"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          {t.common.edit}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="flex items-center gap-1 text-red-500 hover:text-red-600"
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
                          {t.common.delete}
                        </Button>
                      </div>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>
        ))}
    </motion.div>
  )
}

interface BankLoansSectionProps extends SectionCommonProps {
  positions: LoanPosition[]
  creditDisplayItems: CreditDisplayItem[]
  creditEditHandlers: CreditEditHandlers | null
  onLoansSummaryChange: (summary: LoansSummary) => void
  onBeginCreditCreate: (entityId?: string) => void
}

function BankLoansSection({
  t,
  locale,
  positions,
  creditDisplayItems,
  creditEditHandlers,
  defaultCurrency,
  exchangeRates,
  onLoansSummaryChange,
  onFocusEntity,
  selectedEntities,
  entityOrigins,
  onRegisterController,
  onEnterGlobalEditMode,
  collapsed,
  onToggleCollapsed,
  onBeginCreditCreate,
}: BankLoansSectionProps) {
  const {
    asset,
    drafts,
    isEditMode,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    beginCreate,
    translate: manualTranslate,
    isEntryDeleted,
    isDraftDirty: manualIsDraftDirty,
    assetPath,
    manualEntities,
    hasLocalChanges,
    isSaving,
    assetTitle,
    addLabel,
    editLabel,
    cancelLabel,
    saveLabel,
    requestSave,
    requestCancel,
    enterEditMode,
    collectSavePayload,
    setSavingState,
    handleExternalSaveSuccess,
  } = useManualPositions()

  const loanController = useMemo<ManualSectionController>(
    () => ({
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      canCreate: manualEntities.length > 0,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      translate: manualTranslate,
      collectSavePayload,
      setSavingState,
      handleSaveSuccess: handleExternalSaveSuccess,
    }),
    [
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities.length,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      manualTranslate,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    ],
  )

  useEffect(() => {
    onRegisterController(asset, loanController)
    return () => onRegisterController(asset, null)
  }, [asset, loanController, onRegisterController])

  const defaultEntityId =
    selectedEntities.length === 1 ? selectedEntities[0] : undefined
  const canCreate = manualEntities.length > 0
  const [addPopoverOpen, setAddPopoverOpen] = useState(false)

  const loanDrafts = drafts as LoanDraft[]

  const computedPositions = useMemo<LoanDisplay[]>(
    () =>
      positions.map(loan => {
        const convertedCurrentInstallment = convertCurrency(
          loan.current_installment ?? 0,
          loan.currency,
          defaultCurrency,
          exchangeRates,
        )
        const convertedLoanAmount = convertCurrency(
          loan.loan_amount ?? 0,
          loan.currency,
          defaultCurrency,
          exchangeRates,
        )
        const convertedPrincipalOutstanding = convertCurrency(
          loan.principal_outstanding ?? 0,
          loan.currency,
          defaultCurrency,
          exchangeRates,
        )
        const convertedPrincipalPaid = convertCurrency(
          loan.principal_paid ?? 0,
          loan.currency,
          defaultCurrency,
          exchangeRates,
        )

        return {
          ...loan,
          convertedCurrentInstallment,
          convertedLoanAmount,
          convertedPrincipalOutstanding,
          convertedPrincipalPaid,
        }
      }),
    [positions, defaultCurrency, exchangeRates],
  )

  const buildPositionFromDraft = useCallback(
    (draft: LoanDraft): LoanDisplay => {
      const entryId = draft.originalId ?? draft.id ?? draft.localId
      const convertedCurrentInstallment = convertCurrency(
        draft.current_installment ?? 0,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )
      const convertedLoanAmount = convertCurrency(
        draft.loan_amount ?? 0,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )
      const convertedPrincipalOutstanding = convertCurrency(
        draft.principal_outstanding ?? 0,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )
      const convertedPrincipalPaid = convertCurrency(
        draft.principal_paid ?? 0,
        draft.currency,
        defaultCurrency,
        exchangeRates,
      )

      return {
        ...draft,
        id: entryId,
        entryId,
        entityId: draft.entityId,
        entityName: draft.entityName,
        entityOrigin: entityOrigins[draft.entityId] ?? null,
        convertedCurrentInstallment,
        convertedLoanAmount,
        convertedPrincipalOutstanding,
        convertedPrincipalPaid,
        source: DataSource.MANUAL,
      }
    },
    [defaultCurrency, exchangeRates, entityOrigins],
  )

  const displayItems = useMemo<ManualDisplayItem<LoanDisplay, LoanDraft>[]>(
    () =>
      mergeManualDisplayItems<LoanDisplay, LoanDraft>({
        positions: computedPositions,
        manualDrafts: loanDrafts,
        getPositionOriginalId: (position: LoanDisplay) => position.entryId,
        getDraftOriginalId: (draft: LoanDraft) => draft.originalId,
        getDraftLocalId: (draft: LoanDraft) => draft.localId,
        getPositionKey: (position: LoanDisplay) => position.entryId,
        buildPositionFromDraft,
        isManualPosition: (position: LoanDisplay) =>
          position.source === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: (draft: LoanDraft) =>
          selectedEntities.length === 0 ||
          selectedEntities.includes(draft.entityId),
        mergeDraftMetadata: (position: LoanDisplay, draft: LoanDraft) => ({
          ...position,
          entityId: draft.entityId,
          entityName: draft.entityName,
          entityOrigin: entityOrigins[draft.entityId] ?? null,
        }),
      }),
    [
      computedPositions,
      loanDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      entityOrigins,
    ],
  )

  const summary = useMemo<LoansSummary>(() => {
    const aggregates = displayItems.reduce(
      (accumulator, item) => {
        if (item.originalId && isEntryDeleted(item.originalId)) {
          return accumulator
        }

        const currentOutstanding =
          item.position.convertedPrincipalOutstanding ?? 0
        accumulator.debt += currentOutstanding
        accumulator.monthly += item.position.convertedCurrentInstallment ?? 0
        const interest = item.position.interest_rate ?? 0
        if (currentOutstanding > 0 && interest > 0) {
          accumulator.weighted += interest * currentOutstanding
        }
        accumulator.count += 1
        return accumulator
      },
      { debt: 0, monthly: 0, weighted: 0, count: 0 },
    )
    const weightedInterest =
      aggregates.debt > 0 ? aggregates.weighted / aggregates.debt : 0

    return {
      totalDebt: aggregates.debt,
      totalMonthlyPayments: aggregates.monthly,
      weightedInterest,
      count: aggregates.count,
    }
  }, [displayItems, isEntryDeleted])

  useEffect(() => {
    onLoansSummaryChange(summary)
  }, [summary, onLoansSummaryChange])

  const totalSectionCount = summary.count + creditDisplayItems.length

  const manualEmptyTitle = manualTranslate(`${assetPath}.empty.title`)
  const manualEmptyDescription = manualTranslate(
    `${assetPath}.empty.description`,
  )

  return (
    <motion.div variants={fadeListItem} className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="flex items-center gap-2 cursor-pointer"
          onClick={onToggleCollapsed}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              collapsed && "-rotate-90",
            )}
          />
          <HandCoins className="h-5 w-5" />
          <h2 className="text-xl font-semibold">
            {t.banking.loansAndCredits}
            <span className="ml-2 text-sm text-muted-foreground">
              ({totalSectionCount})
            </span>
          </h2>
        </button>
        {!collapsed && (
          <div className="flex items-center gap-2">
            {!isEditMode && (
              <Button
                variant="default"
                size="icon"
                className="h-8 w-8"
                onClick={onEnterGlobalEditMode}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            <Popover open={addPopoverOpen} onOpenChange={setAddPopoverOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="default"
                  size="icon"
                  className="h-8 w-8"
                  disabled={!canCreate}
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-44 p-1">
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => {
                    setAddPopoverOpen(false)
                    onEnterGlobalEditMode()
                    beginCreate(
                      defaultEntityId
                        ? { entityId: defaultEntityId }
                        : undefined,
                    )
                  }}
                >
                  <HandCoins className="h-4 w-4" />
                  {t.enums.productType.LOAN}
                </button>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-sm hover:bg-accent"
                  onClick={() => {
                    setAddPopoverOpen(false)
                    onBeginCreditCreate(defaultEntityId ?? undefined)
                  }}
                >
                  <Shield className="h-4 w-4" />
                  {t.enums.productType.CREDIT}
                </button>
              </PopoverContent>
            </Popover>
          </div>
        )}
      </div>

      {!collapsed &&
        (totalSectionCount === 0 ? (
          <Card className="flex flex-col items-center gap-4 p-10 text-center">
            <div className="text-red-500 dark:text-red-400">
              <HandCoins className="mx-auto h-12 w-12" />
            </div>
            <h3 className="text-lg font-semibold">{manualEmptyTitle}</h3>
            <p className="text-sm text-muted-foreground">
              {manualEmptyDescription}
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
            {displayItems.map(item => {
              const { position, manualDraft, isManual, isDirty, originalId } =
                item

              if (originalId && isEntryDeleted(originalId)) {
                return null
              }

              const showActions = isEditMode && isManual
              const highlightClass = isDirty
                ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                : ""
              const repaymentProgress =
                position.convertedLoanAmount > 0
                  ? Math.min(
                      (position.convertedPrincipalPaid /
                        position.convertedLoanAmount) *
                        100,
                      200,
                    )
                  : 0
              const interestTypeKey = position.interest_type
                ? position.interest_type.toLowerCase()
                : null
              const normalizedInterestType =
                interestTypeKey === "fixed" ||
                interestTypeKey === "variable" ||
                interestTypeKey === "mixed"
                  ? interestTypeKey
                  : null
              const interestTypeLabel =
                normalizedInterestType &&
                t.realEstate?.loans?.interestTypes?.[normalizedInterestType]
                  ? t.realEstate.loans.interestTypes[normalizedInterestType]
                  : null
              const euriborRateText = isFiniteNumber(position.euribor_rate)
                ? formatPercentage((position.euribor_rate ?? 0) * 100, locale)
                : null
              const fixedYearsValue =
                typeof position.fixed_years === "number"
                  ? position.fixed_years
                  : null
              return (
                <Card
                  key={item.key}
                  className={cn(
                    "flex h-full flex-col gap-4 p-6 transition-shadow hover:shadow-lg",
                    highlightClass,
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <Badge
                      variant="secondary"
                      className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    >
                      {position.type === LoanType.MORTGAGE
                        ? t.loanTypes.MORTGAGE
                        : t.loanTypes.STANDARD}
                    </Badge>
                    <div className="flex items-center gap-2">
                      <SourceBadge
                        source={position.source}
                        onClick={
                          position.source === DataSource.MANUAL
                            ? onEnterGlobalEditMode
                            : undefined
                        }
                      />
                      <EntityBadge
                        name={position.entityName}
                        origin={position.entityOrigin}
                        onClick={() => onFocusEntity(position.entityId)}
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {position.name && (
                    <h3 className="text-lg font-semibold">{position.name}</h3>
                  )}

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.principalOutstanding}
                      </span>
                      <span className="text-xl font-semibold text-red-500">
                        {formatCurrency(
                          position.convertedPrincipalOutstanding,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {(position.installment_frequency &&
                          (t.banking as any).installmentByFrequency?.[
                            position.installment_frequency
                          ]) ||
                          t.banking.monthlyInstallment}
                      </span>
                      <span className="text-lg font-semibold">
                        {formatCurrency(
                          position.convertedCurrentInstallment,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.interestRate}
                      </span>
                      <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                        <span className="flex items-center gap-1">
                          <Percent className="h-3 w-3" />
                          {formatPercentage(
                            (position.interest_rate ?? 0) * 100,
                            locale,
                          )}
                        </span>
                        {euriborRateText && (
                          <span className="text-xs text-muted-foreground">
                            {manualTranslate(`${assetPath}.fields.euriborRate`)}
                            : {euriborRateText}
                          </span>
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 md:grid-cols-2">
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.principalPaid}
                      </span>
                      <span className="text-sm">
                        {formatCurrency(
                          position.convertedPrincipalPaid,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.originalAmount}
                      </span>
                      <span className="text-sm">
                        {formatCurrency(
                          position.convertedLoanAmount,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 md:grid-cols-3">
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.paymentDate}
                      </span>
                      <span className="flex items-center gap-2 text-sm">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        {position.next_payment_date
                          ? formatDate(position.next_payment_date, locale)
                          : t.common.notAvailable}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {manualTranslate(`${assetPath}.fields.creation`)} /{" "}
                        {manualTranslate(`${assetPath}.fields.maturity`)}
                      </span>
                      <span className="text-sm">
                        {position.creation
                          ? formatDate(position.creation, locale)
                          : t.common.notAvailable}
                        <span aria-hidden="true" className="px-1">
                          •
                        </span>
                        {position.maturity
                          ? formatDate(position.maturity, locale)
                          : t.common.notAvailable}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {manualTranslate(`${assetPath}.fields.interestType`)}
                      </span>
                      <div className="text-sm font-medium">
                        {interestTypeLabel ||
                          position.interest_type ||
                          t.common.notAvailable}
                      </div>
                      {position.interest_type === InterestType.MIXED &&
                        fixedYearsValue != null && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            {manualTranslate(
                              `${assetPath}.helpers.fixedRateDuration`,
                              {
                                years: fixedYearsValue,
                              },
                            )}
                          </div>
                        )}
                      {position.interest_type === InterestType.MIXED &&
                        isFiniteNumber(position.fixed_interest_rate) && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            {manualTranslate(
                              `${assetPath}.fields.fixedInterestRate`,
                            )}
                            {": "}
                            {formatPercentage(
                              (position.fixed_interest_rate ?? 0) * 100,
                              locale,
                            )}
                          </div>
                        )}
                    </div>
                  </div>

                  {position.convertedLoanAmount > 0 && (
                    <div className="mt-4 space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{t.banking.repaymentProgress}</span>
                        <span>
                          {formatPercentage(
                            Math.min(repaymentProgress, 100),
                            locale,
                          )}
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-emerald-500"
                          style={{
                            width: `${Math.min(repaymentProgress, 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {position.currency !== defaultCurrency && (
                    <div className="mt-3 grid grid-cols-1 gap-2 border-t border-border pt-3 text-xs text-muted-foreground md:grid-cols-2">
                      <div>
                        <span className="block">
                          {t.banking.principalOutstanding}:
                        </span>
                        <span>
                          {formatCurrency(
                            position.principal_outstanding ?? 0,
                            locale,
                            position.currency,
                          )}
                        </span>
                      </div>
                      <div>
                        <span className="block">
                          {(position.installment_frequency &&
                            (t.banking as any).installmentByFrequency?.[
                              position.installment_frequency
                            ]) ||
                            t.banking.monthlyInstallment}
                          :
                        </span>
                        <span>
                          {formatCurrency(
                            position.current_installment ?? 0,
                            locale,
                            position.currency,
                          )}
                        </span>
                      </div>
                    </div>
                  )}

                  {isDirty && (
                    <p className="mt-3 text-xs font-medium text-blue-600 dark:text-blue-400">
                      {manualTranslate("management.unsavedChanges")}
                    </p>
                  )}

                  {showActions && (
                    <div className="mt-4 flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (manualDraft?.originalId) {
                            editByOriginalId(manualDraft.originalId)
                          } else if (manualDraft) {
                            editByLocalId(manualDraft.localId)
                          } else if (item.originalId) {
                            editByOriginalId(item.originalId)
                          }
                        }}
                        className="flex items-center gap-1"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        {t.common.edit}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex items-center gap-1 text-red-500 hover:text-red-600"
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
                        {t.common.delete}
                      </Button>
                    </div>
                  )}
                </Card>
              )
            })}
            {creditDisplayItems.map(item => {
              const {
                position: credit,
                manualDraft: creditDraft,
                isManual: creditIsManual,
                isDirty: creditIsDirty,
                originalId: creditOriginalId,
              } = item
              const available =
                credit.convertedCreditLimit - credit.convertedDrawnAmount
              const utilization =
                credit.convertedCreditLimit > 0
                  ? (credit.convertedDrawnAmount /
                      credit.convertedCreditLimit) *
                    100
                  : 0
              const showCreditActions =
                creditEditHandlers?.isEditMode && creditIsManual
              const creditHighlightClass = creditIsDirty
                ? "ring-2 ring-offset-0 ring-blue-400/60 dark:ring-blue-500/40"
                : ""
              return (
                <Card
                  key={item.key}
                  className={cn(
                    "flex h-full flex-col gap-4 p-6 transition-shadow hover:shadow-lg",
                    creditHighlightClass,
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <Badge
                      variant="secondary"
                      className="bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                    >
                      {t.enums.productType.CREDIT}
                    </Badge>
                    <div className="flex items-center gap-2">
                      <SourceBadge
                        source={credit.source}
                        onClick={
                          credit.source === DataSource.MANUAL
                            ? onEnterGlobalEditMode
                            : undefined
                        }
                      />
                      <EntityBadge
                        name={credit.entityName}
                        origin={credit.entityOrigin}
                        onClick={() => onFocusEntity(credit.entityId)}
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {credit.name && (
                    <h3 className="text-lg font-semibold">{credit.name}</h3>
                  )}

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.creditDrawn}
                      </span>
                      <span className="text-xl font-semibold text-red-500">
                        {formatCurrency(
                          credit.convertedDrawnAmount,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.creditLimit}
                      </span>
                      <span className="text-lg font-semibold">
                        {formatCurrency(
                          credit.convertedCreditLimit,
                          locale,
                          defaultCurrency,
                        )}
                      </span>
                    </div>
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.interestRate}
                      </span>
                      <span className="flex items-center gap-1 text-sm font-medium">
                        <Percent className="h-3 w-3" />
                        {formatPercentage(
                          (credit.interest_rate ?? 0) * 100,
                          locale,
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 md:grid-cols-2">
                    <div>
                      <span className="block text-sm text-muted-foreground">
                        {t.banking.availableCredit}
                      </span>
                      <span className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                        {formatCurrency(available, locale, defaultCurrency)}
                      </span>
                    </div>
                    {credit.pledged_amount != null &&
                      credit.pledged_amount > 0 && (
                        <div>
                          <span className="block text-sm text-muted-foreground">
                            {manualTranslate(
                              "management.manualPositions.bankCredits.fields.pledgedAmount",
                            )}
                          </span>
                          <span className="text-sm">
                            {formatCurrency(
                              convertCurrency(
                                credit.pledged_amount,
                                credit.currency,
                                defaultCurrency,
                                exchangeRates,
                              ),
                              locale,
                              defaultCurrency,
                            )}
                          </span>
                        </div>
                      )}
                  </div>

                  {credit.creation && (
                    <div className="border-t border-border pt-4">
                      <span className="block text-sm text-muted-foreground">
                        {manualTranslate(
                          "management.manualPositions.bankCredits.fields.creation",
                        )}
                      </span>
                      <span className="flex items-center gap-2 text-sm">
                        <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                        {formatDate(credit.creation, locale)}
                      </span>
                    </div>
                  )}

                  {credit.convertedCreditLimit > 0 && (
                    <div className="mt-2 space-y-1">
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{t.banking.utilization}</span>
                        <span>
                          {formatPercentage(Math.min(utilization, 100), locale)}
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-rose-500"
                          style={{ width: `${Math.min(utilization, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {credit.currency !== defaultCurrency && (
                    <div className="mt-3 grid grid-cols-1 gap-2 border-t border-border pt-3 text-xs text-muted-foreground md:grid-cols-2">
                      <div>
                        <span className="block">{t.banking.creditDrawn}:</span>
                        <span>
                          {formatCurrency(
                            credit.drawn_amount ?? 0,
                            locale,
                            credit.currency,
                          )}
                        </span>
                      </div>
                      <div>
                        <span className="block">{t.banking.creditLimit}:</span>
                        <span>
                          {formatCurrency(
                            credit.credit_limit ?? 0,
                            locale,
                            credit.currency,
                          )}
                        </span>
                      </div>
                    </div>
                  )}

                  {creditIsDirty && (
                    <p className="mt-3 text-xs font-medium text-blue-600 dark:text-blue-400">
                      {manualTranslate("management.unsavedChanges")}
                    </p>
                  )}

                  {showCreditActions && creditEditHandlers && (
                    <div className="mt-4 flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (creditDraft?.originalId) {
                            creditEditHandlers.editByOriginalId(
                              creditDraft.originalId,
                            )
                          } else if (creditDraft) {
                            creditEditHandlers.editByLocalId(
                              creditDraft.localId,
                            )
                          } else if (creditOriginalId) {
                            creditEditHandlers.editByOriginalId(
                              creditOriginalId,
                            )
                          }
                        }}
                        className="flex items-center gap-1"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        {t.common.edit}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex items-center gap-1 text-red-500 hover:text-red-600"
                        onClick={() => {
                          if (creditDraft?.originalId) {
                            creditEditHandlers.deleteByOriginalId(
                              creditDraft.originalId,
                            )
                          } else if (creditDraft) {
                            creditEditHandlers.deleteByLocalId(
                              creditDraft.localId,
                            )
                          } else if (creditOriginalId) {
                            creditEditHandlers.deleteByOriginalId(
                              creditOriginalId,
                            )
                          }
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {t.common.delete}
                      </Button>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        ))}
    </motion.div>
  )
}

function BankCreditsBridge({
  onRegisterController,
  onCreditsSummaryChange,
  onCreditDisplayItemsChange,
  onCreditEditHandlersChange,
  selectedEntities,
  entityOrigins,
  defaultCurrency,
  exchangeRates,
  creditPositions,
}: {
  onRegisterController: ManualControllerRegistrar
  onCreditsSummaryChange: (summary: CreditsSummary) => void
  onCreditDisplayItemsChange: (items: CreditDisplayItem[]) => void
  onCreditEditHandlersChange: (handlers: CreditEditHandlers) => void
  selectedEntities: string[]
  entityOrigins: Record<string, EntityOrigin | null>
  defaultCurrency: string
  exchangeRates: ExchangeRates | null
  creditPositions: CreditPosition[]
}) {
  const {
    asset,
    drafts,
    isEditMode,
    beginCreate,
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    translate: manualTranslate,
    isEntryDeleted,
    isDraftDirty: manualIsDraftDirty,
    manualEntities,
    hasLocalChanges,
    isSaving,
    assetTitle,
    addLabel,
    editLabel,
    cancelLabel,
    saveLabel,
    requestSave,
    requestCancel,
    enterEditMode,
    collectSavePayload,
    setSavingState,
    handleExternalSaveSuccess,
  } = useManualPositions()

  const creditController = useMemo<ManualSectionController>(
    () => ({
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      canCreate: manualEntities.length > 0,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      translate: manualTranslate,
      collectSavePayload,
      setSavingState,
      handleSaveSuccess: handleExternalSaveSuccess,
    }),
    [
      asset,
      assetTitle,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities.length,
      beginCreate,
      enterEditMode,
      requestCancel,
      requestSave,
      manualTranslate,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    ],
  )

  useEffect(() => {
    onRegisterController(asset, creditController)
    return () => onRegisterController(asset, null)
  }, [asset, creditController, onRegisterController])

  const creditDrafts = drafts as CreditDraft[]

  const computedPositions = useMemo<CreditDisplay[]>(
    () =>
      creditPositions.map(credit => ({
        ...credit,
        convertedDrawnAmount: convertCurrency(
          credit.drawn_amount ?? 0,
          credit.currency,
          defaultCurrency,
          exchangeRates,
        ),
        convertedCreditLimit: convertCurrency(
          credit.credit_limit ?? 0,
          credit.currency,
          defaultCurrency,
          exchangeRates,
        ),
      })),
    [creditPositions, defaultCurrency, exchangeRates],
  )

  const buildPositionFromDraft = useCallback(
    (draft: CreditDraft): CreditDisplay => {
      const entryId = draft.originalId ?? draft.id ?? draft.localId
      return {
        ...draft,
        id: entryId,
        entryId,
        entityId: draft.entityId,
        entityName: draft.entityName,
        entityOrigin: entityOrigins[draft.entityId] ?? null,
        convertedDrawnAmount: convertCurrency(
          draft.drawn_amount ?? 0,
          draft.currency,
          defaultCurrency,
          exchangeRates,
        ),
        convertedCreditLimit: convertCurrency(
          draft.credit_limit ?? 0,
          draft.currency,
          defaultCurrency,
          exchangeRates,
        ),
        source: DataSource.MANUAL,
      }
    },
    [defaultCurrency, exchangeRates, entityOrigins],
  )

  const displayItems = useMemo(
    () =>
      mergeManualDisplayItems<CreditDisplay, CreditDraft>({
        positions: computedPositions,
        manualDrafts: creditDrafts,
        getPositionOriginalId: (pos: CreditDisplay) => pos.entryId,
        getDraftOriginalId: (draft: CreditDraft) => draft.originalId,
        getDraftLocalId: (draft: CreditDraft) => draft.localId,
        getPositionKey: (pos: CreditDisplay) => pos.entryId,
        buildPositionFromDraft,
        isManualPosition: (pos: CreditDisplay) =>
          pos.source === DataSource.MANUAL,
        isDraftDirty: manualIsDraftDirty,
        isEntryDeleted,
        shouldIncludeDraft: (draft: CreditDraft) =>
          selectedEntities.length === 0 ||
          selectedEntities.includes(draft.entityId),
        mergeDraftMetadata: (pos: CreditDisplay, draft: CreditDraft) => ({
          ...pos,
          entityId: draft.entityId,
          entityName: draft.entityName,
          entityOrigin: entityOrigins[draft.entityId] ?? null,
        }),
      }),
    [
      computedPositions,
      creditDrafts,
      buildPositionFromDraft,
      manualIsDraftDirty,
      isEntryDeleted,
      selectedEntities,
      entityOrigins,
    ],
  )

  const creditsSummary = useMemo<CreditsSummary>(() => {
    const aggregates = displayItems.reduce(
      (acc, item) => {
        if (item.originalId && isEntryDeleted(item.originalId)) return acc
        const drawn = item.position.convertedDrawnAmount ?? 0
        acc.drawn += drawn
        acc.limit += item.position.convertedCreditLimit ?? 0
        const interest = item.position.interest_rate ?? 0
        if (drawn > 0 && interest > 0) {
          acc.weighted += interest * drawn
        }
        acc.count += 1
        return acc
      },
      { drawn: 0, limit: 0, weighted: 0, count: 0 },
    )
    const weightedInterest =
      aggregates.drawn > 0 ? aggregates.weighted / aggregates.drawn : 0
    return {
      totalDrawn: aggregates.drawn,
      totalLimit: aggregates.limit,
      weightedInterest,
      count: aggregates.count,
    }
  }, [displayItems, isEntryDeleted])

  useEffect(() => {
    onCreditsSummaryChange(creditsSummary)
  }, [creditsSummary, onCreditsSummaryChange])

  const visibleCreditItems = useMemo(
    () =>
      displayItems.filter(
        item => !(item.originalId && isEntryDeleted(item.originalId)),
      ),
    [displayItems, isEntryDeleted],
  )

  useEffect(() => {
    onCreditDisplayItemsChange(visibleCreditItems)
  }, [visibleCreditItems, onCreditDisplayItemsChange])

  useEffect(() => {
    onCreditEditHandlersChange({
      editByOriginalId,
      editByLocalId,
      deleteByOriginalId,
      deleteByLocalId,
      isEditMode,
    })
  }, [
    editByOriginalId,
    editByLocalId,
    deleteByOriginalId,
    deleteByLocalId,
    isEditMode,
    onCreditEditHandlersChange,
  ])

  return null
}
