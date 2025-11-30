import {
  useMemo,
  useState,
  useEffect,
  useCallback,
  useRef,
  type FormEvent,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import { format } from "date-fns"
import { useNavigate } from "react-router-dom"
import {
  Info,
  PiggyBank,
  CalendarDays,
  ArrowLeft,
  TrendingUp,
  Folder,
  BarChart3,
  Plus,
  Save,
  Pencil,
  X,
  Trash2,
  AlertCircle,
  Loader2,
  Bitcoin,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { DatePicker } from "@/components/ui/DatePicker"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { SourceBadge, getSourceIcon } from "@/components/ui/SourceBadge"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { cn } from "@/lib/utils"
import { convertCurrency } from "@/utils/financialDataUtils"
import { getProductTypeColor } from "@/utils/dashboardUtils"
import {
  ContributionFrequency,
  ContributionTargetType,
  ContributionTargetSubtype,
  ManualContributionsRequest,
  ManualPeriodicContribution,
  PeriodicContribution,
} from "@/types/contributions"
import { DataSource, EntityType } from "@/types"
import {
  AccountType,
  ProductType,
  type Accounts,
  type CryptoCurrencies,
  type FundInvestments,
  type StockInvestments,
} from "@/types/position"
import { saveManualContributions } from "@/services/api"

interface ManualContributionDraft extends ManualPeriodicContribution {
  localId: string
  originalId?: string
}

interface ManualContributionFormState {
  localId: string
  originalId?: string
  entity_id: string
  name: string
  target: string
  target_name: string
  target_type: ContributionTargetType
  target_subtype: ContributionTargetSubtype | ""
  amount: string
  currency: string
  since: string
  until: string
  frequency: ContributionFrequency
}

type ManualContributionField =
  | "entity_id"
  | "name"
  | "target_type"
  | "target"
  | "amount"
  | "currency"
  | "since"

type ManualContributionErrors = Partial<Record<ManualContributionField, string>>

type TargetSubtypeOption = {
  value: ContributionTargetSubtype | "FUND_PORTFOLIO" | "CRYPTO"
  label: string
  targetType: ContributionTargetType
}

interface TargetSuggestion {
  value: string
  label: string
  secondary?: string
}

const isValidIsin = (value: string) => {
  const normalized = value.trim().toUpperCase()
  return /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(normalized)
}

const isValidIban = (value: string) => {
  const normalized = value.trim().replace(/\s+/g, "").toUpperCase()
  return /^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$/.test(normalized)
}

const monthlyMultiplier = (f: ContributionFrequency) => {
  switch (f) {
    case ContributionFrequency.WEEKLY:
      return 52 / 12
    case ContributionFrequency.BIWEEKLY:
      return 26 / 12
    case ContributionFrequency.BIMONTHLY:
      return 6 / 12
    case ContributionFrequency.QUARTERLY:
      return 4 / 12
    case ContributionFrequency.SEMIANNUAL:
      return 2 / 12
    case ContributionFrequency.YEARLY:
      return 1 / 12
    case ContributionFrequency.MONTHLY:
    default:
      return 1
  }
}

export default function AutoContributionsPage() {
  const { t, locale } = useI18n()
  const { settings, entities, exchangeRates, showToast } = useAppContext()
  const { contributions, positionsData, refreshData } = useFinancialData()
  const navigate = useNavigate()
  const defaultCurrency = settings.general.defaultCurrency
  const abortControllerRef = useRef<AbortController | null>(null)

  // DO NOT change periodicByEntity (user fixed previously)
  const periodicByEntity = contributions || {}

  const flatContributions: {
    entityId: string
    contribution: PeriodicContribution
  }[] = useMemo(() => {
    const acc: { entityId: string; contribution: PeriodicContribution }[] = []
    Object.entries(periodicByEntity).forEach(([entityId, data]) => {
      if (data && Array.isArray((data as any).periodic)) {
        ;(data as any).periodic.forEach((c: PeriodicContribution) =>
          acc.push({ entityId, contribution: c }),
        )
      }
    })
    return acc
  }, [periodicByEntity])

  const monthlyTotal = useMemo(() => {
    return flatContributions.reduce((acc, { contribution }) => {
      if (!contribution.active) {
        return acc
      }

      const normalized =
        contribution.amount * monthlyMultiplier(contribution.frequency)
      const converted = convertCurrency(
        normalized,
        contribution.currency,
        defaultCurrency,
        exchangeRates,
      )

      return acc + converted
    }, 0)
  }, [flatContributions, exchangeRates, defaultCurrency])

  const grouped = useMemo(() => {
    const map: Record<string, PeriodicContribution[]> = {}
    flatContributions.forEach(({ entityId, contribution }) => {
      if (!map[entityId]) map[entityId] = []
      map[entityId].push(contribution)
    })
    Object.keys(map).forEach(id => {
      map[id].sort((a, b) => {
        if (a.active !== b.active) return a.active ? -1 : 1
        const aHas = !!a.next_date
        const bHas = !!b.next_date
        if (aHas && bHas)
          return (
            new Date(a.next_date!).getTime() - new Date(b.next_date!).getTime()
          )
        if (aHas !== bHas) return aHas ? -1 : 1
        return 0
      })
    })
    return map
  }, [flatContributions])

  const freqLabel = (f: ContributionFrequency) =>
    (t.management.contributionFrequency as any)?.[f] || f

  const activeCount = useMemo(
    () => flatContributions.filter(c => c.contribution.active).length,
    [flatContributions],
  )

  const colors = [
    "#6366F1",
    "#10B981",
    "#F59E0B",
    "#EF4444",
    "#3B82F6",
    "#8B5CF6",
    "#EC4899",
    "#14B8A6",
    "#F97316",
    "#0EA5E9",
  ]

  const financialEntities = useMemo(
    () =>
      (entities ?? []).filter(
        entity =>
          entity.type === EntityType.FINANCIAL_INSTITUTION ||
          entity.type === EntityType.CRYPTO_WALLET,
      ),
    [entities],
  )

  const supportedCurrencySet = useMemo(() => {
    if (typeof Intl.supportedValuesOf !== "function") {
      return null
    }
    try {
      return new Set(
        Intl.supportedValuesOf("currency").map(code => code.toUpperCase()),
      )
    } catch {
      return null
    }
  }, [])

  const distributionData = useMemo(() => {
    const map = new Map<
      string,
      { amount: number; type?: string; byType: boolean }
    >()
    flatContributions.forEach(({ contribution }) => {
      if (!contribution.active) return
      const normalized =
        contribution.amount * monthlyMultiplier(contribution.frequency)
      const converted = convertCurrency(
        normalized,
        contribution.currency,
        defaultCurrency,
        exchangeRates,
      )
      const key =
        (contribution as any).target_name ||
        contribution.target ||
        contribution.target_type
      const byType = !((contribution as any).target_name || contribution.target)
      const existing = map.get(key)
      if (existing) existing.amount += converted
      else
        map.set(key, {
          amount: converted,
          type: contribution.target_type,
          byType,
        })
    })
    const entries = Array.from(map.entries()).map(([key, v]) => ({
      name: v.byType
        ? (t.enums?.productType as any)?.[v.type || key] || key
        : key,
      rawKey: key,
      value: v.amount,
      byType: v.byType,
    }))
    entries.sort((a, b) => b.value - a.value)
    const total = entries.reduce((a, b) => a + b.value, 0) || 1
    return entries.map(e => ({
      ...e,
      percentage: (e.value / total) * 100,
      total,
    }))
  }, [flatContributions, t, exchangeRates, defaultCurrency])

  const barColor = (i: number) => colors[i % colors.length]

  const distributionColorMap = useMemo(() => {
    const m: Record<string, string> = {}
    distributionData.forEach((d, i) => {
      m[d.rawKey] = colors[i % colors.length]
    })
    return m
  }, [distributionData])

  const manualEntriesFromData = useMemo<ManualContributionDraft[]>(() => {
    const fallbackName = t.management.manualContributions.unnamed

    return flatContributions
      .filter(({ contribution }) => contribution.source === DataSource.MANUAL)
      .map(({ entityId, contribution }) => ({
        localId: contribution.id,
        originalId: contribution.id,
        entity_id: entityId,
        name:
          contribution.alias ||
          contribution.target_name ||
          contribution.target ||
          fallbackName,
        target: contribution.target || "",
        target_name: contribution.target_name ?? null,
        target_type: contribution.target_type,
        target_subtype: contribution.target_subtype ?? null,
        amount: contribution.amount,
        currency: (contribution.currency || defaultCurrency).toUpperCase(),
        since: contribution.since,
        until: contribution.until ?? null,
        frequency: contribution.frequency,
      }))
  }, [defaultCurrency, flatContributions, t])

  const [manualDrafts, setManualDrafts] = useState<ManualContributionDraft[]>(
    manualEntriesFromData,
  )
  const [isEditMode, setIsEditMode] = useState(false)
  const [hasLocalChanges, setHasLocalChanges] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<"create" | "edit">("create")
  const [modalForm, setModalForm] =
    useState<ManualContributionFormState | null>(null)
  const [formErrors, setFormErrors] = useState<ManualContributionErrors>({})
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [showModalDiscardConfirm, setShowModalDiscardConfirm] = useState(false)
  const modalInitialSnapshotRef = useRef<ManualContributionFormState | null>(
    null,
  )

  useEffect(() => {
    if (!hasLocalChanges) {
      setManualDrafts(manualEntriesFromData)
    }
  }, [manualEntriesFromData, hasLocalChanges])

  const groupedEntries = useMemo(() => {
    const entries = new Map<string, PeriodicContribution[]>()
    Object.entries(grouped).forEach(([entityId, list]) => {
      entries.set(entityId, list)
    })
    manualDrafts.forEach(draft => {
      if (!entries.has(draft.entity_id)) {
        entries.set(draft.entity_id, [])
      }
    })
    return entries
  }, [grouped, manualDrafts])

  const manualDraftsByEntity = useMemo(() => {
    const map = new Map<string, ManualContributionDraft[]>()
    manualDrafts.forEach(draft => {
      const existing = map.get(draft.entity_id)
      if (existing) existing.push(draft)
      else map.set(draft.entity_id, [draft])
    })
    return map
  }, [manualDrafts])

  const manualDraftByOriginalId = useMemo(() => {
    const map = new Map<string, ManualContributionDraft>()
    manualDrafts.forEach(draft => {
      if (draft.originalId) {
        map.set(draft.originalId, draft)
      }
    })
    return map
  }, [manualDrafts])

  const manualOriginalById = useMemo(() => {
    const map = new Map<string, ManualContributionDraft>()
    manualEntriesFromData.forEach(entry => {
      map.set(entry.localId, entry)
      if (entry.originalId) {
        map.set(entry.originalId, entry)
      }
    })
    return map
  }, [manualEntriesFromData])

  const manualDraftEqualsOriginal = useCallback(
    (draft: ManualContributionDraft) => {
      if (!draft.originalId) return false
      const original =
        manualOriginalById.get(draft.originalId) ||
        manualOriginalById.get(draft.localId)
      if (!original) return false
      return (
        draft.entity_id === original.entity_id &&
        draft.name === original.name &&
        draft.target === original.target &&
        (draft.target_name ?? null) === (original.target_name ?? null) &&
        draft.target_type === original.target_type &&
        (draft.target_subtype ?? null) === (original.target_subtype ?? null) &&
        draft.amount === original.amount &&
        draft.currency === original.currency &&
        draft.since === original.since &&
        (draft.until ?? null) === (original.until ?? null) &&
        draft.frequency === original.frequency
      )
    },
    [manualOriginalById],
  )

  const isManualDraftDirty = useCallback(
    (draft: ManualContributionDraft) => {
      if (!draft.originalId) return true
      return !manualDraftEqualsOriginal(draft)
    },
    [manualDraftEqualsOriginal],
  )

  const currencyOptions = useMemo(() => {
    const currencies = new Set<string>()
    currencies.add(defaultCurrency.toUpperCase())
    Object.entries(exchangeRates || {}).forEach(([base, targets]) => {
      currencies.add(base.toUpperCase())
      Object.keys(targets || {}).forEach(target =>
        currencies.add(target.toUpperCase()),
      )
    })
    const sorted = Array.from(currencies).sort()
    if (!supportedCurrencySet) {
      return sorted
    }
    return sorted.filter(code => supportedCurrencySet.has(code.toUpperCase()))
  }, [exchangeRates, defaultCurrency, supportedCurrencySet])

  const targetSubtypeOptions = useMemo<TargetSubtypeOption[]>(() => {
    const subtypeLabels = t.enums?.contributionTargetSubtype as
      | Record<string, string>
      | undefined
    const productLabels = t.enums?.productType as
      | Record<string, string>
      | undefined

    return [
      {
        value: ContributionTargetSubtype.STOCK,
        label:
          subtypeLabels?.[ContributionTargetSubtype.STOCK] ??
          ContributionTargetSubtype.STOCK,
        targetType: ContributionTargetType.STOCK_ETF,
      },
      {
        value: ContributionTargetSubtype.ETF,
        label:
          subtypeLabels?.[ContributionTargetSubtype.ETF] ??
          ContributionTargetSubtype.ETF,
        targetType: ContributionTargetType.STOCK_ETF,
      },
      {
        value: ContributionTargetSubtype.MUTUAL_FUND,
        label:
          subtypeLabels?.[ContributionTargetSubtype.MUTUAL_FUND] ??
          ContributionTargetSubtype.MUTUAL_FUND,
        targetType: ContributionTargetType.FUND,
      },
      {
        value: ContributionTargetSubtype.PENSION_FUND,
        label:
          subtypeLabels?.[ContributionTargetSubtype.PENSION_FUND] ??
          ContributionTargetSubtype.PENSION_FUND,
        targetType: ContributionTargetType.FUND,
      },
      {
        value: ContributionTargetSubtype.PRIVATE_EQUITY,
        label:
          subtypeLabels?.[ContributionTargetSubtype.PRIVATE_EQUITY] ??
          ContributionTargetSubtype.PRIVATE_EQUITY,
        targetType: ContributionTargetType.FUND,
      },
      {
        value: "FUND_PORTFOLIO" as const,
        label:
          productLabels?.[ContributionTargetType.FUND_PORTFOLIO] ??
          ContributionTargetType.FUND_PORTFOLIO,
        targetType: ContributionTargetType.FUND_PORTFOLIO,
      },
      {
        value: "CRYPTO" as const,
        label: productLabels?.["CRYPTO"] ?? "Crypto",
        targetType: ContributionTargetType.CRYPTO,
      },
    ]
  }, [t.enums?.contributionTargetSubtype, t.enums?.productType])

  const frequencyOptions = useMemo(
    () => Object.values(ContributionFrequency),
    [],
  )

  const generateLocalId = useCallback(() => {
    const globalCrypto = globalThis.crypto as Crypto | undefined
    if (globalCrypto?.randomUUID) {
      return globalCrypto.randomUUID()
    }
    return `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`
  }, [])

  const draftToFormState = useCallback(
    (draft: ManualContributionDraft): ManualContributionFormState => ({
      localId: draft.localId,
      originalId: draft.originalId,
      entity_id: draft.entity_id,
      name: draft.name,
      target: draft.target,
      target_name: draft.target_name ?? "",
      target_type: draft.target_type,
      target_subtype:
        draft.target_type === ContributionTargetType.FUND_PORTFOLIO ||
        draft.target_type === ContributionTargetType.CRYPTO
          ? ""
          : (draft.target_subtype ?? ""),
      amount: draft.amount ? draft.amount.toString() : "",
      currency: draft.currency,
      since: draft.since,
      until: draft.until ?? "",
      frequency: draft.frequency,
    }),
    [],
  )

  const formToDraft = useCallback(
    (form: ManualContributionFormState): ManualContributionDraft => {
      const normalizedTarget =
        form.target_type === ContributionTargetType.FUND_PORTFOLIO
          ? form.target.trim().replace(/\s+/g, "").toUpperCase()
          : form.target_type === ContributionTargetType.CRYPTO
            ? form.target.trim().toUpperCase()
            : form.target.trim().toUpperCase()

      return {
        localId: form.localId,
        originalId: form.originalId,
        entity_id: form.entity_id,
        name: form.name.trim(),
        target: normalizedTarget,
        target_name: form.target_name.trim() ? form.target_name.trim() : null,
        target_type: form.target_type,
        target_subtype:
          form.target_type === ContributionTargetType.FUND_PORTFOLIO ||
          form.target_type === ContributionTargetType.CRYPTO
            ? null
            : form.target_subtype
              ? (form.target_subtype as ContributionTargetSubtype)
              : null,
        amount: Number.parseFloat(form.amount),
        currency: form.currency,
        since: form.since,
        until: form.until ? form.until : null,
        frequency: form.frequency,
      }
    },
    [],
  )

  const createEmptyFormState = useCallback(
    (): ManualContributionFormState => ({
      localId: generateLocalId(),
      originalId: undefined,
      entity_id: "",
      name: "",
      target: "",
      target_name: "",
      target_type: ContributionTargetType.FUND,
      target_subtype: ContributionTargetSubtype.MUTUAL_FUND,
      amount: "",
      currency: defaultCurrency.toUpperCase(),
      since: format(new Date(), "yyyy-MM-dd"),
      until: "",
      frequency: ContributionFrequency.MONTHLY,
    }),
    [generateLocalId, defaultCurrency],
  )

  const clearFormError = useCallback((field: ManualContributionField) => {
    setFormErrors(prev => {
      if (!(field in prev)) return prev
      const rest = { ...prev }
      delete rest[field]
      return rest
    })
  }, [])

  const validateForm = useCallback(
    (form: ManualContributionFormState): ManualContributionErrors => {
      const errors: ManualContributionErrors = {}

      if (!form.entity_id) {
        errors.entity_id = t.management.manualContributions.validation.entity
      }
      if (!form.name.trim()) {
        errors.name = t.management.manualContributions.validation.name
      }
      if (!form.target_type) {
        errors.target_type =
          t.management.manualContributions.validation.targetType
      }
      if (!form.target.trim()) {
        errors.target = t.management.manualContributions.validation.target
      }
      const amountValue = Number.parseFloat(form.amount)
      if (!form.amount || Number.isNaN(amountValue) || amountValue <= 0) {
        errors.amount = t.management.manualContributions.validation.amount
      }
      if (!form.currency) {
        errors.currency = t.management.manualContributions.validation.currency
      }
      if (!form.since) {
        errors.since = t.management.manualContributions.validation.since
      }

      return errors
    },
    [t],
  )

  const areFormStatesEqual = useCallback(
    (a: ManualContributionFormState, b: ManualContributionFormState) =>
      a.entity_id === b.entity_id &&
      a.name === b.name &&
      a.target === b.target &&
      a.target_name === b.target_name &&
      a.target_type === b.target_type &&
      a.target_subtype === b.target_subtype &&
      a.amount === b.amount &&
      a.currency === b.currency &&
      a.since === b.since &&
      a.until === b.until &&
      a.frequency === b.frequency,
    [],
  )

  const modalSuggestions = useMemo<TargetSuggestion[]>(() => {
    if (!modalForm) return []
    const entityPositions = positionsData?.positions?.[modalForm.entity_id]
    if (!entityPositions?.products) return []

    const suggestions = new Map<string, TargetSuggestion>()

    switch (modalForm.target_type) {
      case ContributionTargetType.FUND: {
        const funds =
          (
            entityPositions.products[ProductType.FUND] as
              | FundInvestments
              | undefined
          )?.entries ?? []
        funds.forEach(fund => {
          if (!fund.isin) return
          const value = fund.isin.toUpperCase()
          if (!suggestions.has(value)) {
            suggestions.set(value, {
              value,
              label: value,
              secondary: fund.name,
            })
          }
        })
        break
      }
      case ContributionTargetType.STOCK_ETF: {
        const stocks =
          (
            entityPositions.products[ProductType.STOCK_ETF] as
              | StockInvestments
              | undefined
          )?.entries ?? []
        stocks.forEach(stock => {
          if (!stock.isin) return
          const value = stock.isin.toUpperCase()
          if (!suggestions.has(value)) {
            const secondary = stock.ticker
              ? `${stock.name} · ${stock.ticker}`
              : stock.name
            suggestions.set(value, {
              value,
              label: value,
              secondary,
            })
          }
        })
        break
      }
      case ContributionTargetType.FUND_PORTFOLIO: {
        const accounts =
          (
            entityPositions.products[ProductType.ACCOUNT] as
              | Accounts
              | undefined
          )?.entries ?? []
        accounts
          .filter(
            account =>
              account.type === AccountType.FUND_PORTFOLIO && account.iban,
          )
          .forEach(account => {
            const normalized = account.iban!.replace(/\s+/g, "").toUpperCase()
            if (!suggestions.has(normalized)) {
              suggestions.set(normalized, {
                value: normalized,
                label: normalized,
                secondary: account.name || undefined,
              })
            }
          })
        break
      }
      case ContributionTargetType.CRYPTO: {
        const cryptoWallets =
          (
            entityPositions.products[ProductType.CRYPTO] as
              | CryptoCurrencies
              | undefined
          )?.entries ?? []
        cryptoWallets.forEach(wallet => {
          wallet.assets?.forEach(asset => {
            if (!asset.symbol || !asset.crypto_asset) return
            const value = asset.symbol.toUpperCase()
            if (!suggestions.has(value)) {
              suggestions.set(value, {
                value,
                label: value,
                secondary: asset.name || undefined,
              })
            }
          })
        })
        break
      }
      default:
        break
    }

    return Array.from(suggestions.values())
  }, [modalForm, positionsData])

  const handleEnterEditMode = useCallback(() => {
    setIsEditMode(true)
    setIsModalOpen(false)
    setModalForm(null)
    setFormErrors({})
    modalInitialSnapshotRef.current = null
  }, [])

  const resetEditState = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setIsEditMode(false)
    setHasLocalChanges(false)
    setIsModalOpen(false)
    setModalForm(null)
    setFormErrors({})
    setManualDrafts(manualEntriesFromData)
    modalInitialSnapshotRef.current = null
  }, [manualEntriesFromData])

  const handleRequestCancelEdit = useCallback(() => {
    if (isSaving) return
    if (hasLocalChanges) {
      setShowCancelConfirm(true)
      return
    }
    resetEditState()
  }, [hasLocalChanges, isSaving, resetEditState])

  const handleConfirmCancelEdit = useCallback(() => {
    setShowCancelConfirm(false)
    resetEditState()
  }, [resetEditState])

  const handleDismissCancelEdit = useCallback(() => {
    setShowCancelConfirm(false)
  }, [])

  const handleOpenCreateModal = useCallback(() => {
    if (!isEditMode) {
      handleEnterEditMode()
      setManualDrafts(manualEntriesFromData)
      setHasLocalChanges(false)
    }
    const form = createEmptyFormState()
    modalInitialSnapshotRef.current = { ...form }
    setModalMode("create")
    setModalForm(form)
    setFormErrors({})
    setIsModalOpen(true)
  }, [
    createEmptyFormState,
    handleEnterEditMode,
    isEditMode,
    manualEntriesFromData,
  ])

  const handleEditManual = useCallback(
    (draft: ManualContributionDraft) => {
      if (!isEditMode) {
        handleEnterEditMode()
      }
      const formState = draftToFormState(draft)
      modalInitialSnapshotRef.current = { ...formState }
      setModalMode("edit")
      setModalForm(formState)
      setFormErrors({})
      setIsModalOpen(true)
    },
    [draftToFormState, handleEnterEditMode, isEditMode],
  )

  const handleDeleteManual = useCallback((localId: string) => {
    setManualDrafts(prev => prev.filter(draft => draft.localId !== localId))
    setHasLocalChanges(true)
  }, [])

  const closeModal = useCallback(() => {
    setIsModalOpen(false)
    setModalForm(null)
    setFormErrors({})
    modalInitialSnapshotRef.current = null
  }, [])

  const handleRequestCloseModal = useCallback(() => {
    if (!modalForm) {
      closeModal()
      return
    }
    const snapshot = modalInitialSnapshotRef.current
    if (snapshot && !areFormStatesEqual(modalForm, snapshot)) {
      setShowModalDiscardConfirm(true)
      return
    }
    closeModal()
  }, [areFormStatesEqual, closeModal, modalForm])

  const handleConfirmDiscardModal = useCallback(() => {
    setShowModalDiscardConfirm(false)
    closeModal()
  }, [closeModal])

  const handleDismissDiscardModal = useCallback(() => {
    setShowModalDiscardConfirm(false)
  }, [])

  const handleModalSubmit = useCallback(
    (event?: FormEvent<HTMLFormElement>) => {
      event?.preventDefault()
      if (!modalForm) return

      const validation = validateForm(modalForm)
      setFormErrors(validation)
      if (Object.keys(validation).length > 0) {
        return
      }

      const updatedDraft = formToDraft(modalForm)
      setManualDrafts(prev => {
        const index = prev.findIndex(
          draft => draft.localId === updatedDraft.localId,
        )
        if (index >= 0) {
          const next = [...prev]
          next[index] = updatedDraft
          return next
        }
        return [...prev, updatedDraft]
      })
      setHasLocalChanges(true)
      closeModal()
    },
    [closeModal, formToDraft, modalForm, validateForm],
  )

  const handleSaveAll = useCallback(async () => {
    if (isSaving || !isEditMode) return
    if (!hasLocalChanges) {
      setIsEditMode(false)
      return
    }

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setIsSaving(true)
    try {
      const payload: ManualContributionsRequest = {
        entries: manualDrafts.map(draft => ({
          entity_id: draft.entity_id,
          name: draft.name,
          target: draft.target,
          target_name: draft.target_name ?? null,
          target_type: draft.target_type,
          target_subtype: draft.target_subtype ?? null,
          amount: draft.amount,
          currency: draft.currency,
          since: draft.since,
          until: draft.until ?? null,
          frequency: draft.frequency,
        })),
      }

      await saveManualContributions(payload)
      showToast(t.management.saveSuccess, "success")
      setHasLocalChanges(false)
      setIsModalOpen(false)
      setModalForm(null)
      setIsEditMode(false)
      await refreshData()
    } catch (error: any) {
      if (error?.name === "AbortError") {
        return
      }
      console.error("Error saving manual contributions:", error)
      showToast(t.management.saveError, "error")
    } finally {
      abortControllerRef.current = null
      setIsSaving(false)
    }
  }, [
    hasLocalChanges,
    isEditMode,
    isSaving,
    manualDrafts,
    refreshData,
    showToast,
    t.management.saveError,
    t.management.saveSuccess,
  ])

  const getNextDateInfo = (nextDate?: string) => {
    if (!nextDate) return null
    const today = new Date()
    const next = new Date(nextDate)
    const diffDays = Math.ceil(
      (next.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
    )
    if (diffDays < 0)
      return { text: formatDate(nextDate, locale), className: "text-red-500" }
    if (diffDays === 0)
      return { text: t.management.today, className: "text-red-500" }
    if (diffDays === 1)
      return { text: t.management.tomorrow, className: "text-amber-500" }
    if (diffDays <= 7)
      return {
        text: t.management.inDays.replace("{days}", diffDays.toString()),
        className: "text-amber-500",
      }
    return {
      text: formatDate(nextDate, locale),
      className: "text-muted-foreground",
    }
  }

  const typeIcon = (type: string, color?: string) => {
    const style = color ? { color } : undefined
    switch (type) {
      case "STOCK_ETF":
      case "FUND":
        return <BarChart3 className="h-5 w-5" style={style} />
      case "FUND_PORTFOLIO":
        return <Folder className="h-5 w-5" style={style} />
      case "CRYPTO":
        return <Bitcoin className="h-5 w-5" style={style} />
      default:
        return <TrendingUp className="h-5 w-5" style={style} />
    }
  }

  const renderContributionCard = (
    contribution: PeriodicContribution | null,
    entityId: string,
    manualDraft?: ManualContributionDraft,
    isDirty = false,
  ) => {
    const key = manualDraft?.localId || contribution?.id || entityId
    const targetType =
      manualDraft?.target_type ||
      contribution?.target_type ||
      ContributionTargetType.FUND
    const productTypeLabel =
      (t.enums?.productType as any)?.[targetType] || targetType
    const displayName = manualDraft
      ? manualDraft.name || manualDraft.target_name || productTypeLabel
      : contribution?.alias || contribution?.target_name || productTypeLabel
    const amount = manualDraft?.amount ?? contribution?.amount ?? 0
    const currency =
      manualDraft?.currency ?? contribution?.currency ?? defaultCurrency
    const frequency =
      manualDraft?.frequency ??
      contribution?.frequency ??
      ContributionFrequency.MONTHLY
    const normalizedMonthlyAmount = amount * monthlyMultiplier(frequency)
    const convertedAmount = convertCurrency(
      amount,
      currency,
      defaultCurrency,
      exchangeRates,
    )
    const convertedMonthlyAmount = convertCurrency(
      normalizedMonthlyAmount,
      currency,
      defaultCurrency,
      exchangeRates,
    )
    const showOriginalCurrency = currency !== defaultCurrency
    const active = contribution?.active ?? true
    const nextInfo = active ? getNextDateInfo(contribution?.next_date) : null
    const source = contribution?.source ?? DataSource.MANUAL
    const SourceIcon = getSourceIcon(source)
    const target = manualDraft?.target ?? contribution?.target ?? ""
    const targetName =
      manualDraft?.target_name ?? contribution?.target_name ?? null
    const targetSubtype =
      manualDraft?.target_subtype ?? contribution?.target_subtype ?? null
    const targetSubtypeLabel = targetSubtype
      ? (t.enums?.contributionTargetSubtype as any)?.[targetSubtype] ||
        targetSubtype
      : null
    const since = manualDraft?.since ?? contribution?.since ?? ""
    const until = manualDraft
      ? manualDraft.until
      : (contribution?.until ?? null)
    const colorKey = manualDraft
      ? manualDraft.target_name || manualDraft.target || manualDraft.target_type
      : (contribution as any)?.target_name ||
        contribution?.target ||
        contribution?.target_type
    const iconColor = colorKey ? distributionColorMap[colorKey] : undefined
    const productTypeBadgeClass = getProductTypeColor(
      targetType as unknown as ProductType,
    )

    return (
      <Card
        key={key}
        className={cn(
          "px-5 py-4 flex flex-col transition-shadow hover:shadow-md border-border/60 dark:border-border/60 h-full",
          !active && "opacity-50",
          isDirty &&
            "ring-2 ring-primary/60 ring-offset-2 ring-offset-background",
        )}
      >
        <div className="flex items-start gap-4">
          <div className="shrink-0 mt-1">{typeIcon(targetType, iconColor)}</div>
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-semibold text-base leading-tight truncate">
                  {displayName}
                </h3>
              </div>
              <div className="flex items-start gap-2">
                <div className="flex flex-col items-end gap-1">
                  <div className="text-2xl font-semibold tracking-tight leading-none">
                    {formatCurrency(convertedAmount, locale, defaultCurrency)}
                  </div>
                  {showOriginalCurrency && (
                    <div className="text-xs text-muted-foreground">
                      {formatCurrency(amount, locale, currency)}
                    </div>
                  )}
                </div>
                {isEditMode && manualDraft && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEditManual(manualDraft)}
                      aria-label={t.common.edit}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300"
                      onClick={() => handleDeleteManual(manualDraft.localId)}
                      aria-label={t.common.delete}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between pt-1 text-[0.7rem] font-medium">
              <div className="flex items-center gap-3 flex-wrap">
                <Badge
                  className={cn(
                    "gap-1 border-transparent px-2 py-0.5",
                    productTypeBadgeClass,
                  )}
                >
                  {productTypeLabel}
                </Badge>
                {targetSubtype &&
                  targetSubtype !== ContributionTargetSubtype.MUTUAL_FUND &&
                  targetSubtypeLabel && (
                    <Badge className="border-transparent bg-muted text-foreground/80 dark:bg-muted/70 px-2 py-0.5">
                      {targetSubtypeLabel}
                    </Badge>
                  )}
                <SourceBadge
                  source={source}
                  title={t.management.source}
                  className="bg-muted text-foreground/80 dark:bg-muted/70 px-2 py-0.5 rounded-full"
                  iconClassName="h-3 w-3"
                />
                <Badge className="bg-muted text-foreground/80 dark:bg-muted/70 flex items-center gap-1 px-2 py-0.5 rounded-full">
                  <CalendarDays className="h-3 w-3" /> {freqLabel(frequency)}
                </Badge>
                {isDirty && (
                  <Badge className="bg-primary/10 text-primary dark:bg-primary/20">
                    {t.management.manualContributions.unsavedBadge}
                  </Badge>
                )}
                {nextInfo && (
                  <span
                    className={cn(
                      "flex items-center gap-1",
                      nextInfo.className,
                    )}
                  >
                    <CalendarDays className="h-3 w-3" /> {nextInfo.text}
                  </span>
                )}
              </div>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={t.common.viewDetails}
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </PopoverTrigger>
                <PopoverContent side="left" align="start" className="w-80">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="font-medium text-muted-foreground">
                        {t.management.targetType}
                      </span>
                      <span className="font-medium">{productTypeLabel}</span>
                    </div>
                    {targetSubtypeLabel && (
                      <div className="flex justify-between gap-4">
                        <span className="font-medium text-muted-foreground">
                          {t.management.targetSubtype}
                        </span>
                        <span className="truncate max-w-[55%] text-right">
                          {targetSubtypeLabel}
                        </span>
                      </div>
                    )}
                    {targetName && (
                      <div className="flex justify-between gap-4">
                        <span className="font-medium text-muted-foreground">
                          {t.management.manualContributions.targetName}
                        </span>
                        <span className="truncate max-w-[55%] text-right">
                          {targetName}
                        </span>
                      </div>
                    )}
                    {target && (
                      <div className="flex justify-between gap-4">
                        <span className="font-medium text-muted-foreground">
                          {t.management.target}
                        </span>
                        <span className="truncate max-w-[55%] text-right">
                          {target}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between gap-4">
                      <span className="font-medium text-muted-foreground">
                        {t.management.since}
                      </span>
                      <span>
                        {since
                          ? formatDate(since, locale)
                          : t.common.notAvailable}
                      </span>
                    </div>
                    {until && (
                      <div className="flex justify-between gap-4">
                        <span className="font-medium text-muted-foreground">
                          {t.management.until}
                        </span>
                        <span>{formatDate(until, locale)}</span>
                      </div>
                    )}
                    <div className="flex justify-between gap-4">
                      <span className="font-medium text-muted-foreground">
                        {t.management.enabled}
                      </span>
                      <span
                        className={cn(
                          "font-medium",
                          active ? "text-green-500" : "text-red-500",
                        )}
                      >
                        {active ? t.management.enabled : t.management.disabled}
                      </span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="font-medium text-muted-foreground">
                        {t.management.monthlyAverageContribution}
                      </span>
                      <div className="text-right">
                        <div className="font-medium">
                          {formatCurrency(
                            convertedMonthlyAmount,
                            locale,
                            defaultCurrency,
                          )}
                        </div>
                        {showOriginalCurrency && (
                          <div className="text-xs text-muted-foreground">
                            {formatCurrency(
                              normalizedMonthlyAmount,
                              locale,
                              currency,
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    {source !== DataSource.REAL && (
                      <div className="flex justify-between gap-4">
                        <span className="font-medium text-muted-foreground">
                          {t.management.source}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          {SourceIcon ? (
                            <SourceIcon className="h-3.5 w-3.5" />
                          ) : null}
                          {t.enums?.dataSource?.[source] || source}
                        </span>
                      </div>
                    )}
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </div>
      </Card>
    )
  }

  const showEmptyState =
    flatContributions.length === 0 &&
    manualDrafts.every(draft => draft.originalId)

  const showIsinWarning = (() => {
    if (!modalForm) return false
    const isFundOrStock =
      modalForm.target_type === ContributionTargetType.FUND ||
      modalForm.target_type === ContributionTargetType.STOCK_ETF
    if (!isFundOrStock) return false
    const normalizedTarget = modalForm.target.trim()
    if (normalizedTarget.length === 0) return false
    const isDgsCode =
      modalForm.target_type === ContributionTargetType.FUND &&
      /^N\d{2,}$/i.test(normalizedTarget)
    if (isDgsCode) return false
    return !isValidIsin(normalizedTarget)
  })()

  const showIbanWarning =
    modalForm &&
    modalForm.target_type === ContributionTargetType.FUND_PORTFOLIO &&
    modalForm.target.trim().length > 0 &&
    !isValidIban(modalForm.target)

  useEffect(() => () => abortControllerRef.current?.abort(), [])

  return (
    <motion.div
      className="space-y-6 pb-6"
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
    >
      <motion.div
        variants={fadeListItem}
        className="flex items-center justify-between gap-4 flex-wrap"
      >
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/management")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">
              {t.management.autoContributions}
            </h1>
            <PinAssetButton assetId="management-auto-contributions" />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpenCreateModal}
            disabled={financialEntities.length === 0}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            {t.management.manualContributions.add}
          </Button>
          {isEditMode ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRequestCancelEdit}
                disabled={isSaving}
              >
                <X className="h-3.5 w-3.5 mr-1" />
                {t.common.cancel}
              </Button>
              <Button
                size="sm"
                onClick={handleSaveAll}
                disabled={isSaving || !hasLocalChanges}
              >
                {isSaving ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    {t.common.saving}
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Save className="h-3.5 w-3.5" />
                    {t.common.save}
                  </span>
                )}
              </Button>
            </>
          ) : (
            <Button variant="default" size="sm" onClick={handleEnterEditMode}>
              <Pencil className="h-3.5 w-3.5 mr-1" />
              {t.common.edit}
            </Button>
          )}
        </div>
      </motion.div>

      {isEditMode && hasLocalChanges && (
        <motion.div
          variants={fadeListItem}
          className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-100/70 dark:bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200"
        >
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div>{t.management.unsavedChanges}</div>
        </motion.div>
      )}

      <motion.div variants={fadeListItem} className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4">
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-3">
              <CalendarDays className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                {t.management.monthlyAverageContributions}
              </span>
            </div>
            <div>
              <div className="text-3xl font-bold leading-tight tracking-tight">
                {formatCurrency(monthlyTotal, locale, defaultCurrency)}
              </div>
            </div>
          </Card>
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                {t.management.activeContributions}
              </span>
            </div>
            <div>
              <div className="text-3xl font-bold leading-tight tracking-tight">
                {activeCount}
              </div>
            </div>
          </Card>
        </div>
        {distributionData.length > 0 && (
          <Card className="p-5 flex flex-col lg:col-span-2 min-w-0">
            <div className="flex items-center justify-between mb-3">
              <h3
                className="text-sm font-medium text-muted-foreground"
                title={t.management.monthlyPerTarget}
              >
                {t.management.monthlyPerTarget}
              </h3>
              <span className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">
                {formatCurrency(
                  distributionData[0].total,
                  locale,
                  defaultCurrency,
                )}
              </span>
            </div>
            <div className="space-y-3 overflow-auto lg:max-h-72 pr-1 scrollbar-thin scrollbar-thumb-border/30">
              {distributionData.map((d, i) => (
                <div key={d.rawKey} className="group">
                  <div className="flex justify-between gap-4 text-xs font-medium mb-1">
                    <span className="truncate" title={d.name}>
                      {d.name}
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground group-hover:text-foreground transition-colors">
                      {formatCurrency(d.value, locale, defaultCurrency)} ·{" "}
                      {d.percentage.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${d.percentage}%`,
                        background: barColor(i),
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </motion.div>

      {showEmptyState && (
        <motion.div variants={fadeListItem}>
          <Card className="p-10 flex flex-col items-center gap-4 text-center">
            <PiggyBank className="h-12 w-12 text-muted-foreground" />
            <div>
              <h2 className="text-lg font-semibold mb-1">
                {t.management.noAutoContributionsTitle}
              </h2>
              <p className="text-sm text-muted-foreground max-w-md">
                {t.management.noAutoContributionsDescription}
              </p>
            </div>
          </Card>
        </motion.div>
      )}

      {Array.from(groupedEntries.entries()).map(([entityId, list]) => {
        const entityName =
          entities.find(entity => entity.id === entityId)?.name || entityId
        const draftsForEntity = manualDraftsByEntity.get(entityId) || []
        const unsavedDrafts = draftsForEntity.filter(draft => !draft.originalId)

        return (
          <div key={entityId} className="space-y-4">
            <h2 className="text-sm font-semibold text-muted-foreground tracking-wide">
              {entityName}
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {list.map(c => {
                const manualDraft = manualDraftByOriginalId.get(c.id)
                if (
                  isEditMode &&
                  c.source === DataSource.MANUAL &&
                  !manualDraft
                ) {
                  return null
                }
                const isDirty = manualDraft
                  ? isManualDraftDirty(manualDraft)
                  : false

                return (
                  <div key={manualDraft?.localId ?? c.id} className="h-full">
                    {renderContributionCard(c, entityId, manualDraft, isDirty)}
                  </div>
                )
              })}
              {isEditMode &&
                unsavedDrafts.map(draft => (
                  <div key={draft.localId} className="h-full">
                    {renderContributionCard(
                      null,
                      entityId,
                      draft,
                      isManualDraftDirty(draft),
                    )}
                  </div>
                ))}
            </div>
          </div>
        )
      })}

      <AnimatePresence>
        {isModalOpen && modalForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[10002]"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-3xl"
            >
              <Card className="max-h-[calc(100vh-2rem)] flex flex-col">
                <CardHeader className="pb-4 shrink-0">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-xl">
                        {modalMode === "create"
                          ? t.management.manualContributions.createTitle
                          : t.management.manualContributions.editTitle}
                      </CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleRequestCloseModal}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <form
                  onSubmit={handleModalSubmit}
                  className="flex flex-1 flex-col overflow-hidden"
                >
                  <CardContent className="space-y-4 flex-1 overflow-y-auto px-6 sm:px-8">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="entity">
                          {t.management.manualContributions.entity}
                        </Label>
                        <select
                          id="entity"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          value={modalForm.entity_id}
                          onChange={event => {
                            const selectedEntityId = event.target.value
                            const selectedEntity = financialEntities.find(
                              e => e.id === selectedEntityId,
                            )
                            const isCryptoWallet =
                              selectedEntity?.type === EntityType.CRYPTO_WALLET
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    entity_id: selectedEntityId,
                                    ...(isCryptoWallet && {
                                      target_type:
                                        ContributionTargetType.CRYPTO,
                                      target_subtype: "",
                                    }),
                                  }
                                : prev,
                            )
                            clearFormError("entity_id")
                          }}
                        >
                          <option value="" disabled>
                            {t.common.selectOptions}
                          </option>
                          {financialEntities.map(entity => (
                            <option key={entity.id} value={entity.id}>
                              {entity.name}
                            </option>
                          ))}
                        </select>
                        {formErrors.entity_id && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.entity_id}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="name">{t.management.name}</Label>
                        <Input
                          id="name"
                          value={modalForm.name}
                          onChange={event => {
                            setModalForm(prev =>
                              prev
                                ? { ...prev, name: event.target.value }
                                : prev,
                            )
                            clearFormError("name")
                          }}
                        />
                        {formErrors.name && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.name}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="targetSubtype">
                          {t.management.targetSubtype}
                        </Label>
                        {(() => {
                          const selectedEntity = financialEntities.find(
                            e => e.id === modalForm.entity_id,
                          )
                          const isCryptoWallet =
                            selectedEntity?.type === EntityType.CRYPTO_WALLET
                          const filteredOptions = isCryptoWallet
                            ? targetSubtypeOptions.filter(
                                opt =>
                                  opt.targetType ===
                                  ContributionTargetType.CRYPTO,
                              )
                            : targetSubtypeOptions
                          return (
                            <select
                              id="targetSubtype"
                              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                              value={
                                modalForm.target_type ===
                                ContributionTargetType.FUND_PORTFOLIO
                                  ? "FUND_PORTFOLIO"
                                  : modalForm.target_type ===
                                      ContributionTargetType.CRYPTO
                                    ? "CRYPTO"
                                    : modalForm.target_subtype || ""
                              }
                              disabled={isCryptoWallet}
                              onChange={event => {
                                const value = event.target.value as
                                  | ContributionTargetSubtype
                                  | "FUND_PORTFOLIO"
                                  | "CRYPTO"
                                const option = filteredOptions.find(
                                  opt => opt.value === value,
                                )
                                if (!option) {
                                  return
                                }
                                setModalForm(prev =>
                                  prev
                                    ? {
                                        ...prev,
                                        target_type: option.targetType,
                                        target_subtype:
                                          value === "FUND_PORTFOLIO" ||
                                          value === "CRYPTO"
                                            ? ""
                                            : value,
                                      }
                                    : prev,
                                )
                                clearFormError("target_type")
                              }}
                            >
                              <option value="" disabled>
                                {t.common.selectOptions}
                              </option>
                              {filteredOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          )
                        })()}
                        {formErrors.target_type && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.target_type}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="target">{t.management.target}</Label>
                        <Input
                          id="target"
                          value={modalForm.target}
                          onChange={event => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    target: event.target.value,
                                  }
                                : prev,
                            )
                            clearFormError("target")
                          }}
                          placeholder={
                            t.management.manualContributions.targetHelper
                          }
                        />
                        {formErrors.target && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.target}
                          </p>
                        )}
                        {(showIsinWarning || showIbanWarning) && (
                          <div className="flex items-start gap-2 text-xs text-amber-600 dark:text-amber-400 mt-1">
                            <AlertCircle className="h-3.5 w-3.5 mt-0.5" />
                            <span>
                              {showIsinWarning
                                ? t.management.manualContributions.warnings.isin
                                : t.management.manualContributions.warnings
                                    .iban}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="targetName">
                          {t.management.manualContributions.targetName}
                        </Label>
                        <Input
                          id="targetName"
                          value={modalForm.target_name}
                          onChange={event => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    target_name: event.target.value,
                                  }
                                : prev,
                            )
                          }}
                          placeholder={
                            t.management.manualContributions.targetNameHelper
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          {t.management.manualContributions.targetNameHelper}
                        </p>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="currency">
                          {t.management.manualContributions.currency}
                        </Label>
                        <select
                          id="currency"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          value={modalForm.currency}
                          onChange={event => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    currency: event.target.value,
                                  }
                                : prev,
                            )
                            clearFormError("currency")
                          }}
                        >
                          {currencyOptions.map(option => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                        {formErrors.currency && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.currency}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="amount">{t.management.amount}</Label>
                        <Input
                          id="amount"
                          type="number"
                          inputMode="decimal"
                          min="0"
                          step="0.01"
                          value={modalForm.amount}
                          onChange={event => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    amount: event.target.value,
                                  }
                                : prev,
                            )
                            clearFormError("amount")
                          }}
                        />
                        {formErrors.amount && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.amount}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="frequency">
                          {t.management.frequencyLabel}
                        </Label>
                        <select
                          id="frequency"
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          value={modalForm.frequency}
                          onChange={event => {
                            const value = event.target
                              .value as ContributionFrequency
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    frequency: value,
                                  }
                                : prev,
                            )
                          }}
                        >
                          {frequencyOptions.map(option => (
                            <option key={option} value={option}>
                              {(t.management.contributionFrequency as any)?.[
                                option
                              ] || option}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label>{t.management.since}</Label>
                        <DatePicker
                          value={modalForm.since}
                          onChange={value => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    since: value,
                                  }
                                : prev,
                            )
                            clearFormError("since")
                          }}
                        />
                        {formErrors.since && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                            {formErrors.since}
                          </p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label>{t.management.until}</Label>
                        <DatePicker
                          value={modalForm.until}
                          onChange={value => {
                            setModalForm(prev =>
                              prev
                                ? {
                                    ...prev,
                                    until: value,
                                  }
                                : prev,
                            )
                          }}
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {t.management.manualContributions.suggestions}
                      </div>
                      {modalSuggestions.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {modalSuggestions.map(suggestion => (
                            <Button
                              key={suggestion.value}
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setModalForm(prev =>
                                  prev
                                    ? {
                                        ...prev,
                                        target: suggestion.value,
                                        target_name:
                                          prev.target_name.trim().length > 0
                                            ? prev.target_name
                                            : (suggestion.secondary ??
                                              suggestion.value),
                                        name:
                                          prev.name.trim().length > 0
                                            ? prev.name
                                            : (suggestion.secondary ??
                                              (prev.target_name.trim().length >
                                              0
                                                ? prev.target_name
                                                : suggestion.value)),
                                      }
                                    : prev,
                                )
                                clearFormError("target")
                                clearFormError("name")
                              }}
                            >
                              <span className="text-xs">
                                <span className="font-medium">
                                  {suggestion.label}
                                </span>
                                {suggestion.secondary && (
                                  <span className="block text-[0.7rem] text-muted-foreground">
                                    {suggestion.secondary}
                                  </span>
                                )}
                              </span>
                            </Button>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          {t.management.manualContributions.noSuggestions}
                        </p>
                      )}
                    </div>
                  </CardContent>
                  <CardFooter className="flex justify-end gap-2 shrink-0 px-6 pb-6 pt-4">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleRequestCloseModal}
                    >
                      {t.common.cancel}
                    </Button>
                    <Button type="submit">
                      {modalMode === "create" ? t.common.add : t.common.save}
                    </Button>
                  </CardFooter>
                </form>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <ConfirmationDialog
        isOpen={showCancelConfirm}
        title={t.management.manualContributions.cancelDialog.title}
        message={t.management.manualContributions.cancelDialog.message}
        confirmText={t.management.manualContributions.cancelDialog.confirm}
        cancelText={t.management.manualContributions.cancelDialog.cancel}
        onConfirm={handleConfirmCancelEdit}
        onCancel={handleDismissCancelEdit}
      />
      <ConfirmationDialog
        isOpen={showModalDiscardConfirm}
        title={t.management.manualContributions.modalDiscardDialog.title}
        message={t.management.manualContributions.modalDiscardDialog.message}
        confirmText={
          t.management.manualContributions.modalDiscardDialog.confirm
        }
        cancelText={t.management.manualContributions.modalDiscardDialog.cancel}
        onConfirm={handleConfirmDiscardModal}
        onCancel={handleDismissDiscardModal}
      />
    </motion.div>
  )
}
