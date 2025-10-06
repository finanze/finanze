import {
  createContext,
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
  useContext,
  type ReactNode,
} from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { manualPositionConfigs } from "./manualPositionConfigs"
import type {
  ManualFormErrors,
  ManualPositionAsset,
  ManualPositionDraft,
  ManualSavePayloadByEntity,
} from "./manualPositionTypes"
import {
  DataSource,
  EntityOrigin,
  EntityType,
  type Entity,
  type Feature,
} from "@/types"

const MANUAL_POSITION_ASSETS = Object.keys(
  manualPositionConfigs,
) as ManualPositionAsset[]

const createEmptyFeatureRecord = (): Record<Feature, string> => ({
  POSITION: "",
  AUTO_CONTRIBUTIONS: "",
  TRANSACTIONS: "",
  HISTORIC: "",
})

const createPlaceholderEntity = (id: string, name: string): Entity => ({
  id,
  name,
  type: EntityType.FINANCIAL_INSTITUTION,
  origin: EntityOrigin.MANUAL,
  natural_id: id,
  features: ["POSITION"],
  last_fetch: createEmptyFeatureRecord(),
  virtual_features: createEmptyFeatureRecord(),
})
import { generateLocalId } from "@/utils/manualData"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { cn } from "@/lib/utils"
import { AlertCircle, Pencil, Plus, Save, X } from "lucide-react"
import { saveManualPositions } from "@/services/api"
import {
  ProductType,
  AccountType,
  type Account,
  type Card as CardDetail,
  type FundPortfolio,
  type FundDetail,
  type UpdatePositionRequest,
} from "@/types/position"
import {
  clearManualDraftsForAsset,
  getManualDraftsForAsset,
  setManualDraftsForAsset,
  setManualDeletedOriginalIdsForAsset,
  useManualDrafts,
  useManualDeletedOriginalIds,
} from "./manualDraftRegistry"

const serialize = (value: unknown) =>
  JSON.stringify(value, (_key, val) => {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      return Object.keys(val)
        .sort()
        .reduce<Record<string, unknown>>((acc, key) => {
          acc[key] = (val as Record<string, unknown>)[key]
          return acc
        }, {})
    }
    return val
  })

interface ManualPositionsManagerProps {
  asset: ManualPositionAsset
  className?: string
  children?: ReactNode
}

interface ManualPositionsContextValue {
  asset: ManualPositionAsset
  isEditMode: boolean
  hasLocalChanges: boolean
  isSaving: boolean
  manualEntities: Entity[]
  assetTitle: string
  assetDescription: string
  addLabel: string
  editLabel: string
  cancelLabel: string
  saveLabel: string
  translate: (path: string, params?: Record<string, any>) => string
  drafts: ManualPositionDraft<any>[]
  beginCreate: (options?: { entityId?: string }) => void
  editByOriginalId: (originalId: string) => void
  editByLocalId: (localId: string) => void
  deleteByOriginalId: (originalId: string) => void
  deleteByLocalId: (localId: string) => void
  enterEditMode: () => void
  requestSave: () => Promise<void>
  requestCancel: () => void
  getDraftByOriginalId: (
    originalId: string,
  ) => ManualPositionDraft<any> | undefined
  getDraftByLocalId: (localId: string) => ManualPositionDraft<any> | undefined
  getInitialDraftByOriginalId: (
    originalId: string,
  ) => ManualPositionDraft<any> | undefined
  isEntryDeleted: (originalId: string) => boolean
  isDraftDirty: (draft: ManualPositionDraft<any>) => boolean
  assetPath: string
  collectSavePayload: () => ManualSavePayloadByEntity
  setSavingState: (value: boolean) => void
  handleExternalSaveSuccess: () => void
}

type LinkedPortfolioOption = {
  value: string
  label: string
  source: DataSource
  name: string | null
  currency: string | null
  isDraft: boolean
  draftLocalId?: string
}

const ManualPositionsContext =
  createContext<ManualPositionsContextValue | null>(null)

export function useManualPositions() {
  const context = useContext(ManualPositionsContext)
  if (!context) {
    throw new Error(
      "useManualPositions must be used within a ManualPositionsManager",
    )
  }
  return context
}

export function ManualPositionsManager({
  asset,
  className,
  children,
}: ManualPositionsManagerProps) {
  const { t, locale } = useI18n()
  const { entities, settings, exchangeRates, showToast, fetchEntities } =
    useAppContext()
  const { positionsData, refreshEntity, refreshData } = useFinancialData()
  const fundPortfolioDrafts = useManualDrafts<FundPortfolio>("fundPortfolios")
  const fundDrafts = useManualDrafts<FundDetail>("funds")
  const cardDrafts = useManualDrafts<CardDetail>("bankCards")
  const assetRegistryDrafts = useManualDrafts<any>(asset)
  const allManualDraftCollections = MANUAL_POSITION_ASSETS.map(assetKey =>
    useManualDrafts<any>(assetKey),
  )
  const manualDraftEntitySignature = serialize(
    allManualDraftCollections.map(drafts =>
      drafts
        .filter(draft => {
          if (typeof draft.entityId !== "string") {
            return false
          }
          if (draft.isNewEntity) return true
          return draft.entityId.startsWith("new-")
        })
        .map(draft => ({
          entityId: draft.entityId,
          name: (draft.newEntityName ?? draft.entityName ?? "").trim(),
        })),
    ),
  )
  const deletedFundPortfolioOriginalIds =
    useManualDeletedOriginalIds("fundPortfolios")
  const deletedFundPortfolioIdSet = useMemo(
    () => new Set(deletedFundPortfolioOriginalIds),
    [deletedFundPortfolioOriginalIds],
  )

  const config = manualPositionConfigs[asset]

  const translate = useCallback(
    (path: string, params?: Record<string, any>) => {
      const segments = path.split(".")
      let current: any = t
      for (const segment of segments) {
        if (current && typeof current === "object" && segment in current) {
          current = current[segment]
        } else {
          return path
        }
      }
      if (typeof current !== "string") {
        return path
      }
      if (!params) return current
      return current.replace(/\{\{(.*?)\}\}/g, (_match, key) => {
        const trimmed = key.trim()
        return params[trimmed] ?? ""
      })
    },
    [t],
  )

  const assetPath = `management.manualPositions.${asset}`

  const manualEntities = useMemo(() => {
    const baseEntities = (entities ?? []).filter(
      entity => entity.type === EntityType.FINANCIAL_INSTITUTION,
    )
    const existingIds = new Set(baseEntities.map(entity => entity.id))
    const result: Entity[] = [...baseEntities]

    allManualDraftCollections.forEach(drafts => {
      drafts.forEach(draft => {
        const entityId = draft.entityId
        if (typeof entityId !== "string") {
          return
        }

        const isPlaceholder =
          Boolean(draft.isNewEntity) || entityId.startsWith("new-")
        if (!isPlaceholder || existingIds.has(entityId)) {
          return
        }

        const placeholderName = (
          draft.newEntityName ??
          draft.entityName ??
          ""
        ).trim()
        if (!placeholderName) {
          return
        }

        existingIds.add(entityId)
        result.push(createPlaceholderEntity(entityId, placeholderName))
      })
    })

    return result
  }, [entities, manualDraftEntitySignature])

  const linkedAccountOptions = useCallback(
    (entityId?: string | null) => {
      if (!positionsData?.positions || !entityId) {
        return []
      }

      const entityPosition = positionsData.positions[entityId]
      if (!entityPosition) return []

      const product = entityPosition.products[ProductType.ACCOUNT] as
        | { entries?: Account[] }
        | undefined
      if (!product?.entries?.length) return []

      const options = product.entries
        .filter(account => {
          if (!account.id) return false
          const source = account.source ?? DataSource.REAL
          if (source !== DataSource.MANUAL && source !== DataSource.REAL)
            return false

          if (asset === "fundPortfolios") {
            return account.type === AccountType.FUND_PORTFOLIO
          }

          if (asset === "bankCards") {
            return true
          }

          return false
        })
        .map(account => {
          const accountName =
            (account.name && account.name.trim()) ||
            account.iban ||
            translate("common.notAvailable")

          return {
            value: account.id,
            label: accountName,
          }
        })
        .sort((a, b) =>
          a.label.localeCompare(b.label, locale, { sensitivity: "base" }),
        )

      return options
    },
    [asset, positionsData, locale, translate],
  )

  const linkedPortfolioOptions = useCallback(
    (entityId?: string | null) => {
      if (asset !== "funds" || !entityId) {
        return []
      }

      const entityPosition = positionsData?.positions
        ? positionsData.positions[entityId]
        : undefined

      const product = entityPosition
        ? (entityPosition.products[ProductType.FUND_PORTFOLIO] as
            | { entries?: FundPortfolio[] }
            | undefined)
        : undefined
      const entries = product?.entries ?? []

      const isAllowedPortfolioSource = (source?: DataSource | null) => {
        const resolved = source ?? DataSource.REAL
        return resolved === DataSource.MANUAL || resolved === DataSource.REAL
      }

      const existingOptions: LinkedPortfolioOption[] = entries
        .filter(
          portfolio =>
            portfolio.id && isAllowedPortfolioSource(portfolio.source),
        )
        .map(portfolio => {
          const baseName =
            (portfolio.name && portfolio.name.trim()) ||
            translate("common.notAvailable")
          const currency = portfolio.currency?.toUpperCase()
          const label = currency ? `${baseName} (${currency})` : baseName
          return {
            value: portfolio.id!,
            label,
            source: portfolio.source ?? DataSource.REAL,
            name: portfolio.name ?? null,
            currency: portfolio.currency ?? null,
            isDraft: false,
          }
        })
        .filter(option => !deletedFundPortfolioIdSet.has(option.value))

      const draftOptions: LinkedPortfolioOption[] = fundPortfolioDrafts
        .filter(
          draft =>
            draft.entityId === entityId &&
            isAllowedPortfolioSource(draft.source),
        )
        .map(draft => {
          const baseName =
            (draft.name && draft.name.trim()) ||
            translate("common.notAvailable")
          const currency = draft.currency?.toUpperCase()
          const label = currency ? `${baseName} (${currency})` : baseName
          const value =
            (typeof draft.id === "string" && draft.id.trim()) ||
            (typeof draft.originalId === "string" && draft.originalId.trim()) ||
            draft.localId
          return {
            value,
            label,
            source: draft.source ?? DataSource.MANUAL,
            name: draft.name ?? null,
            currency: draft.currency ?? null,
            isDraft: !draft.originalId,
            draftLocalId: draft.localId,
          }
        })

      const seen = new Set(existingOptions.map(option => option.value))
      const merged: LinkedPortfolioOption[] = existingOptions.slice()
      draftOptions.forEach(option => {
        if (!seen.has(option.value)) {
          merged.push(option)
        }
      })

      return merged.sort((a, b) =>
        a.label.localeCompare(b.label, locale, { sensitivity: "base" }),
      )
    },
    [
      asset,
      positionsData,
      locale,
      translate,
      fundPortfolioDrafts,
      deletedFundPortfolioIdSet,
    ],
  )

  const defaultCurrency = settings.general.defaultCurrency

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

  const currencyOptions = useMemo(() => {
    const currencies = new Set<string>()
    currencies.add(defaultCurrency.toUpperCase())
    if (exchangeRates) {
      Object.entries(exchangeRates).forEach(([base, targets]) => {
        currencies.add(base.toUpperCase())
        Object.keys(targets || {}).forEach(target =>
          currencies.add(target.toUpperCase()),
        )
      })
    }
    const sorted = Array.from(currencies).sort()
    if (!supportedCurrencySet) return sorted
    return sorted.filter(code => supportedCurrencySet.has(code.toUpperCase()))
  }, [exchangeRates, defaultCurrency, supportedCurrencySet])

  const initialDrafts = useMemo(
    () =>
      config.buildDraftsFromPositions({
        positionsData,
        manualEntities,
      }),
    [config, positionsData, manualEntities],
  )

  const [drafts, setDrafts] =
    useState<ManualPositionDraft<any>[]>(initialDrafts)
  const latestDraftsRef = useRef(drafts)
  const hasSyncedRegistryRef = useRef(!["funds", "bankCards"].includes(asset))
  const registrySignatureRef = useRef<string | null>(null)

  const computeDraftSignature = useCallback(
    (items: ManualPositionDraft<any>[]) =>
      serialize(items.map(item => config.normalizeDraftForCompare(item))),
    [config],
  )

  const localDraftSignature = useMemo(
    () => computeDraftSignature(drafts),
    [computeDraftSignature, drafts],
  )

  const registryDraftSignature = useMemo(
    () => computeDraftSignature(assetRegistryDrafts),
    [assetRegistryDrafts, computeDraftSignature],
  )

  useEffect(() => {
    latestDraftsRef.current = drafts
  }, [drafts])

  const [isEditMode, setIsEditMode] = useState(false)
  const [hasLocalChanges, setHasLocalChanges] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [showDiscardFormConfirm, setShowDiscardFormConfirm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const [formState, setFormState] = useState<Record<string, string> | null>(
    null,
  )
  const [formErrors, setFormErrors] = useState<ManualFormErrors<any>>({})
  const [formMode, setFormMode] = useState<"create" | "edit">("create")
  const [activeDraft, setActiveDraft] =
    useState<ManualPositionDraft<any> | null>(null)
  const formInitialSnapshotRef = useRef<string | null>(null)

  useEffect(() => {
    if (!["funds", "bankCards"].includes(asset)) {
      return
    }

    if (!hasSyncedRegistryRef.current) {
      hasSyncedRegistryRef.current = true
      registrySignatureRef.current = registryDraftSignature
      return
    }

    if (registrySignatureRef.current === registryDraftSignature) {
      return
    }

    registrySignatureRef.current = registryDraftSignature

    if (localDraftSignature === registryDraftSignature) {
      return
    }

    const previousDrafts = latestDraftsRef.current
    const previousDraftMap = new Map(
      previousDrafts.map(draft => [draft.localId, draft] as const),
    )

    const removedPortfolioIds = new Set<string>()
    const affectedCardIds = new Set<string>()

    if (asset === "funds") {
      assetRegistryDrafts.forEach(draft => {
        const previous = previousDraftMap.get(draft.localId)
        const previousPortfolioId = previous?.portfolio?.id
        const nextPortfolioId = draft.portfolio?.id
        if (previousPortfolioId && !nextPortfolioId) {
          removedPortfolioIds.add(previousPortfolioId)
        }
      })
    } else if (asset === "bankCards") {
      assetRegistryDrafts.forEach(draft => {
        const previous = previousDraftMap.get(draft.localId)
        const previousRelated =
          typeof (previous as { related_account?: string | null })
            ?.related_account === "string"
            ? (
                previous as { related_account?: string | null }
              ).related_account?.trim()
            : ""
        const nextRelated =
          typeof (draft as { related_account?: string | null })
            .related_account === "string"
            ? (
                draft as { related_account?: string | null }
              ).related_account?.trim()
            : ""
        if (previousRelated && !nextRelated) {
          affectedCardIds.add(draft.localId)
        }
      })
    }

    setDrafts(assetRegistryDrafts)

    if (asset === "funds" && removedPortfolioIds.size > 0) {
      setFormState(prev => {
        if (!prev) return prev
        if (!("portfolio_id" in prev)) return prev
        const currentValue = (prev as Record<string, string>).portfolio_id
        if (currentValue && removedPortfolioIds.has(currentValue)) {
          const next = { ...prev }
          const fields = [
            "portfolio_id",
            "_portfolio_label",
            "_portfolio_source",
            "_portfolio_name",
            "_portfolio_currency",
          ]
          fields.forEach(field => {
            if (field in next) {
              ;(next as Record<string, string>)[field] = ""
            }
          })
          return next
        }
        return prev
      })
      setHasLocalChanges(true)
    }

    if (asset === "bankCards" && affectedCardIds.size > 0) {
      setFormState(prev => {
        if (!prev) return prev
        if (!("related_account" in prev)) return prev
        if (activeDraft && !affectedCardIds.has(activeDraft.localId)) {
          return prev
        }
        const currentValue = (prev as Record<string, string>).related_account
        if (!currentValue) {
          return prev
        }
        const next = { ...prev }
        ;(next as Record<string, string>).related_account = ""
        return next
      })
      if (activeDraft && affectedCardIds.has(activeDraft.localId)) {
        const updatedActive = assetRegistryDrafts.find(
          draft => draft.localId === activeDraft.localId,
        )
        if (updatedActive) {
          setActiveDraft(updatedActive)
        }
      }
      setHasLocalChanges(true)
    }
  }, [
    activeDraft,
    asset,
    assetRegistryDrafts,
    drafts,
    localDraftSignature,
    registryDraftSignature,
  ])

  useEffect(() => {
    return () => {
      clearManualDraftsForAsset(asset)
    }
  }, [asset])

  useEffect(() => {
    if (!hasLocalChanges && !formState) {
      setDrafts(initialDrafts)
    }
  }, [hasLocalChanges, initialDrafts, formState])

  useEffect(() => {
    if (!isEditMode) {
      setActiveDraft(null)
      setFormState(null)
      setFormErrors({})
    }
  }, [isEditMode])

  const openForm = useCallback(
    (
      mode: "create" | "edit",
      draft?: ManualPositionDraft<any>,
      options?: { entityId?: string },
    ) => {
      setFormMode(mode)
      if (mode === "edit" && draft) {
        const form = config.draftToForm(draft)
        setFormState(form)
        setActiveDraft(draft)
        setFormErrors({})
        formInitialSnapshotRef.current = serialize(form)
      } else {
        const baseForm = config.createEmptyForm({
          defaultCurrency,
          entityId:
            options?.entityId ||
            (manualEntities.length === 1 ? manualEntities[0].id : undefined),
        })
        if (!baseForm.entity_mode) {
          baseForm.entity_mode = "select"
        }
        if (options?.entityId) {
          baseForm.entity_id = options.entityId
          baseForm.entity_mode = "select"
        } else if (baseForm.entity_mode === "select") {
          if (!baseForm.entity_id && manualEntities.length === 1) {
            baseForm.entity_id = manualEntities[0].id
          }
        }
        if (!baseForm.new_entity_name) {
          baseForm.new_entity_name = ""
        }
        if (manualEntities.length === 0) {
          baseForm.entity_mode = "new"
          baseForm.entity_id = ""
        }
        setFormState(baseForm)
        setActiveDraft(null)
        setFormErrors({})
        formInitialSnapshotRef.current = serialize(baseForm)
      }
    },
    [config, defaultCurrency, manualEntities],
  )

  const closeForm = useCallback(() => {
    setFormState(null)
    setActiveDraft(null)
    setFormErrors({})
    formInitialSnapshotRef.current = null
  }, [])

  const handleAddDraft = useCallback(
    (entityId?: string) => {
      if (!isEditMode) {
        setIsEditMode(true)
        setTimeout(() => openForm("create", undefined, { entityId }), 0)
      } else {
        openForm("create", undefined, { entityId })
      }
    },
    [isEditMode, openForm],
  )

  const handleEditDraft = useCallback(
    (draft: ManualPositionDraft<any>) => {
      if (!isEditMode) {
        setIsEditMode(true)
        setTimeout(() => openForm("edit", draft), 0)
      } else {
        openForm("edit", draft)
      }
    },
    [isEditMode, openForm],
  )

  const updateField = useCallback((field: string, value: string) => {
    setFormState(prev => (prev ? { ...prev, [field]: value } : prev))
    setFormErrors(prev => {
      if (!prev || !(field in prev)) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }, [])

  const clearError = useCallback((field: string) => {
    setFormErrors(prev => {
      if (!prev || !(field in prev)) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }, [])

  const handleCloseForm = useCallback(() => {
    if (!formState) return
    const initial = formInitialSnapshotRef.current
    const current = serialize(formState)
    if (initial && initial !== current) {
      setShowDiscardFormConfirm(true)
      return
    }
    closeForm()
  }, [closeForm, formState])

  const upsertDraft = useCallback(
    (draft: ManualPositionDraft<any>) => {
      setDrafts(prev => {
        const index = prev.findIndex(item => item.localId === draft.localId)
        if (index >= 0) {
          const next = [...prev]
          next[index] = draft
          return next
        }
        return [...prev, draft]
      })
      setHasLocalChanges(true)
      closeForm()
    },
    [closeForm],
  )

  const handleSubmitForm = useCallback(() => {
    if (!formState) return

    const validation = config.validateForm(formState, {
      t: translate,
      currencyOptions,
    })

    const errors: ManualFormErrors<any> = validation ? { ...validation } : {}

    const entityMode = formState.entity_mode === "new" ? "new" : "select"
    let resolvedEntity: Entity | undefined
    let newEntityName: string | null = null
    let isSelectingPlaceholder = false

    if (entityMode === "select") {
      const entityId = formState.entity_id
      if (!entityId) {
        errors.entity_id = translate(
          "management.manualPositions.shared.validation.entity",
        )
      } else {
        resolvedEntity = manualEntities.find(item => item.id === entityId)
        if (!resolvedEntity) {
          errors.entity_id = translate(
            "management.manualPositions.shared.validation.entity",
          )
        }
        if (resolvedEntity && entityId.startsWith("new-")) {
          isSelectingPlaceholder = true
          const placeholderName = resolvedEntity.name?.trim()
          if (placeholderName) {
            newEntityName = placeholderName
          } else {
            errors.entity_id = translate(
              "management.manualPositions.shared.validation.entityName",
            )
          }
        }
      }
    } else {
      const rawName = (formState.new_entity_name ?? "").trim()
      if (!rawName) {
        errors.new_entity_name = translate(
          "management.manualPositions.shared.validation.entityName",
        )
      } else {
        const normalized = rawName.toLowerCase()
        const existingNames = manualEntities
          .map(entity => entity.name?.trim().toLowerCase())
          .filter((name): name is string => Boolean(name))
        const hasExisting = existingNames.includes(normalized)

        const duplicateDraft = drafts.some(draft => {
          if (!draft.isNewEntity) return false
          if (activeDraft && draft.localId === activeDraft.localId) return false
          const candidate = (draft.newEntityName ?? draft.entityName ?? "")
            .trim()
            .toLowerCase()
          return candidate === normalized
        })

        if (hasExisting || duplicateDraft) {
          errors.new_entity_name = translate(
            "management.manualPositions.shared.validation.entityNameExists",
          )
        } else {
          newEntityName = rawName
        }
      }
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    setFormErrors({})

    const previous = activeDraft ?? undefined
    const entry = config.buildEntryFromForm(formState, { previous })
    if (!entry) {
      showToast(
        translate("management.manualPositions.shared.genericError"),
        "error",
      )
      return
    }

    if (isSelectingPlaceholder && !newEntityName) {
      newEntityName =
        (previous?.newEntityName ?? previous?.entityName ?? "").trim() || null
      if (!newEntityName) {
        setFormErrors({
          entity_id: translate(
            "management.manualPositions.shared.validation.entityName",
          ),
        })
        return
      }
    }

    const isNewEntity = entityMode === "new" || isSelectingPlaceholder
    if (isNewEntity && (!newEntityName || newEntityName.trim() === "")) {
      setFormErrors({
        new_entity_name: translate(
          "management.manualPositions.shared.validation.entityName",
        ),
      })
      return
    }

    if (isNewEntity && newEntityName) {
      newEntityName = newEntityName.trim()
    }

    const resolvedEntityId = isNewEntity
      ? previous?.isNewEntity
        ? previous.entityId
        : isSelectingPlaceholder && resolvedEntity
          ? resolvedEntity.id
          : `new-${generateLocalId()}`
      : resolvedEntity!.id
    const resolvedEntityName = isNewEntity
      ? newEntityName!
      : resolvedEntity!.name

    if (isNewEntity && (entry as { id?: string }).id) {
      delete (entry as { id?: string }).id
    }

    const draft: ManualPositionDraft<any> = {
      ...entry,
      localId: previous?.localId ?? generateLocalId(),
      originalId: isNewEntity
        ? undefined
        : (previous?.originalId ??
          (typeof (entry as any).id === "string" && (entry as any).id
            ? (entry as any).id
            : undefined)),
      entityId: resolvedEntityId,
      entityName: resolvedEntityName,
      isNewEntity,
      newEntityName: isNewEntity ? newEntityName : null,
    }

    upsertDraft(draft)
  }, [
    formState,
    config,
    translate,
    currencyOptions,
    drafts,
    activeDraft,
    manualEntities,
    showToast,
    upsertDraft,
  ])

  const resolveAccountIdentifiers = useCallback(
    (draft: ManualPositionDraft<any>) => {
      const identifiers = new Set<string>()
      const add = (value?: string | null) => {
        if (!value) return
        const trimmed = value.trim()
        if (trimmed) identifiers.add(trimmed)
      }

      const candidateId = (draft as { id?: string }).id
      if (typeof candidateId === "string") {
        add(candidateId)
      }
      if (typeof draft.originalId === "string") {
        add(draft.originalId)
      }
      add(draft.localId)

      return Array.from(identifiers)
    },
    [],
  )

  const getLinkedManualCards = useCallback(
    (accountDraft: ManualPositionDraft<any>) => {
      const identifiers = resolveAccountIdentifiers(accountDraft)
      if (identifiers.length === 0) {
        return []
      }
      const identifierSet = new Set(identifiers)
      return cardDrafts.filter(card => {
        const related = card.related_account?.trim()
        if (!related) return false
        return identifierSet.has(related)
      })
    },
    [cardDrafts, resolveAccountIdentifiers],
  )

  const getLinkedManualPortfoliosForAccount = useCallback(
    (accountDraft: ManualPositionDraft<any>) => {
      const identifiers = resolveAccountIdentifiers(accountDraft)
      if (identifiers.length === 0) {
        return []
      }
      const identifierSet = new Set(identifiers)
      const matches = (value?: string | null) => {
        if (!value) return false
        const trimmed = value.trim()
        if (!trimmed) return false
        return identifierSet.has(trimmed)
      }

      const seen = new Set<string>()

      fundPortfolioDrafts.forEach(portfolio => {
        if (
          matches(portfolio.account_id) ||
          matches(portfolio.account?.id) ||
          matches(
            typeof (portfolio as { related_account?: string | null })
              .related_account === "string"
              ? (portfolio as { related_account?: string | null })
                  .related_account
              : null,
          )
        ) {
          seen.add(`draft:${portfolio.localId}`)
        }
      })

      if (positionsData?.positions) {
        const entityPortfolios = positionsData.positions[accountDraft.entityId]
          ?.products[ProductType.FUND_PORTFOLIO] as
          | { entries?: FundPortfolio[] }
          | undefined
        const entries = entityPortfolios?.entries ?? []
        entries.forEach((portfolio, index) => {
          if (portfolio.source !== DataSource.MANUAL) {
            return
          }
          if (portfolio.id && deletedFundPortfolioIdSet.has(portfolio.id)) {
            return
          }
          if (matches(portfolio.account_id) || matches(portfolio.account?.id)) {
            const key = portfolio.id
              ? `position:${portfolio.id}`
              : `position:${accountDraft.entityId}:${index}`
            seen.add(key)
          }
        })
      }

      return Array.from(seen)
    },
    [
      deletedFundPortfolioIdSet,
      fundPortfolioDrafts,
      positionsData,
      resolveAccountIdentifiers,
    ],
  )

  const unlinkCardsForAccount = useCallback(
    (accountDraft: ManualPositionDraft<any>) => {
      const identifiers = resolveAccountIdentifiers(accountDraft)
      if (identifiers.length === 0) {
        return
      }
      const currentCardDrafts = getManualDraftsForAsset<CardDetail>("bankCards")
      if (!currentCardDrafts.length) {
        return
      }
      const identifierSet = new Set(identifiers)
      let modified = false
      const nextCardDrafts = currentCardDrafts.map(draft => {
        const related = draft.related_account?.trim()
        if (related && identifierSet.has(related)) {
          modified = true
          return {
            ...draft,
            related_account: null,
          }
        }
        return draft
      })
      if (modified) {
        setManualDraftsForAsset("bankCards", nextCardDrafts)
      }
    },
    [resolveAccountIdentifiers],
  )

  const unlinkPortfoliosForAccount = useCallback(
    (accountDraft: ManualPositionDraft<any>) => {
      const identifiers = resolveAccountIdentifiers(accountDraft)
      if (identifiers.length === 0) {
        return
      }
      const currentPortfolioDrafts =
        getManualDraftsForAsset<FundPortfolio>("fundPortfolios")
      if (!currentPortfolioDrafts.length) {
        return
      }
      const identifierSet = new Set(identifiers)
      const matches = (value?: string | null) => {
        if (!value) return false
        const trimmed = value.trim()
        if (!trimmed) return false
        return identifierSet.has(trimmed)
      }
      let modified = false
      const nextPortfolioDrafts = currentPortfolioDrafts.map(draft => {
        const hasMatch =
          matches(draft.account_id) ||
          matches(draft.account?.id) ||
          matches(
            typeof (draft as { related_account?: string | null })
              .related_account === "string"
              ? (draft as { related_account?: string | null }).related_account
              : null,
          )
        if (!hasMatch) {
          return draft
        }
        modified = true
        const nextDraft = {
          ...draft,
          account_id: null,
          account: null,
        } as ManualPositionDraft<FundPortfolio>
        if ("related_account" in nextDraft) {
          ;(nextDraft as { related_account?: string | null }).related_account =
            null
        }
        return nextDraft
      })
      if (modified) {
        setManualDraftsForAsset("fundPortfolios", nextPortfolioDrafts)
      }
    },
    [resolveAccountIdentifiers],
  )

  const resolvePortfolioIdentifiers = useCallback(
    (draft: ManualPositionDraft<any>) => {
      const identifiers = new Set<string>()
      const add = (value?: string | null) => {
        if (!value) return
        const trimmed = value.trim()
        if (trimmed) identifiers.add(trimmed)
      }

      const candidateId = (draft as { id?: string }).id
      if (typeof candidateId === "string") {
        add(candidateId)
      }
      if (typeof draft.originalId === "string") {
        add(draft.originalId)
      }
      add(`draft:${draft.localId}`)
      add(draft.localId)

      return Array.from(identifiers)
    },
    [],
  )

  const getLinkedManualFunds = useCallback(
    (portfolioDraft: ManualPositionDraft<any>) => {
      const identifiers = resolvePortfolioIdentifiers(portfolioDraft)
      if (identifiers.length === 0) {
        return []
      }
      const identifierSet = new Set(identifiers)
      return fundDrafts.filter(fund => {
        const linkedId = fund.portfolio?.id
        if (!linkedId) return false
        return identifierSet.has(linkedId)
      })
    },
    [fundDrafts, resolvePortfolioIdentifiers],
  )

  const unlinkFundsForPortfolio = useCallback(
    (portfolioDraft: ManualPositionDraft<any>) => {
      const identifiers = resolvePortfolioIdentifiers(portfolioDraft)
      if (identifiers.length === 0) {
        return
      }
      const currentFundDrafts = getManualDraftsForAsset<FundDetail>("funds")
      if (!currentFundDrafts.length) {
        return
      }
      const identifierSet = new Set(identifiers)
      let modified = false
      const nextFundDrafts = currentFundDrafts.map(draft => {
        const linkedId = draft.portfolio?.id
        if (linkedId && identifierSet.has(linkedId)) {
          modified = true
          return {
            ...draft,
            portfolio: null,
          }
        }
        return draft
      })
      if (modified) {
        setManualDraftsForAsset("funds", nextFundDrafts)
      }
    },
    [resolvePortfolioIdentifiers],
  )

  const handleDeleteDraft = useCallback(() => {
    if (!deleteTarget) return
    const targetDraft = drafts.find(item => item.localId === deleteTarget)
    if (!targetDraft) {
      setDeleteTarget(null)
      return
    }
    if (asset === "fundPortfolios") {
      unlinkFundsForPortfolio(targetDraft)
    }
    if (asset === "bankAccounts") {
      unlinkCardsForAccount(targetDraft)
      unlinkPortfoliosForAccount(targetDraft)
    }
    setDrafts(prev => prev.filter(item => item.localId !== deleteTarget))
    setHasLocalChanges(true)
    setDeleteTarget(null)
  }, [
    asset,
    deleteTarget,
    drafts,
    unlinkPortfoliosForAccount,
    unlinkCardsForAccount,
    unlinkFundsForPortfolio,
  ])

  const handleCancelEdit = useCallback(() => {
    if (hasLocalChanges) {
      setShowCancelConfirm(true)
      return
    }
    setIsEditMode(false)
    setDrafts(initialDrafts)
  }, [hasLocalChanges, initialDrafts])

  const assetTitle = translate(`${assetPath}.title`)
  const assetDescription = translate(`${assetPath}.description`)

  const isManualDraft = useCallback((draft: ManualPositionDraft<any>) => {
    const source = (draft as { source?: DataSource | null }).source
    return source === DataSource.MANUAL
  }, [])

  const buildSavePayloadByEntity =
    useCallback((): ManualSavePayloadByEntity => {
      const result: ManualSavePayloadByEntity = new Map()

      const entityIds = new Set<string>()
      drafts.forEach(draft => {
        if (isManualDraft(draft)) {
          entityIds.add(draft.entityId)
        }
      })
      initialDrafts.forEach(draft => {
        if (isManualDraft(draft)) {
          entityIds.add(draft.entityId)
        }
      })

      entityIds.forEach(entityId => {
        const manualEntries = drafts.filter(
          draft => draft.entityId === entityId && isManualDraft(draft),
        )

        const entries = manualEntries.map(draft => ({
          draft,
          payload: config.toPayloadEntry(draft) as Record<string, any>,
        }))

        const isNewEntityGroup = manualEntries.some(draft => {
          if (draft.isNewEntity) return true
          if (typeof draft.entityId === "string") {
            return draft.entityId.startsWith("new-")
          }
          return false
        })
        const resolvedNewEntityName = isNewEntityGroup
          ? (manualEntries
              .map(
                draft =>
                  draft.newEntityName?.trim() ||
                  draft.entityName?.trim() ||
                  null,
              )
              .find((value): value is string => Boolean(value)) ?? null)
          : null

        result.set(entityId, {
          productType: config.productType,
          entries,
          isNewEntity: isNewEntityGroup,
          newEntityName: resolvedNewEntityName,
        })
      })

      return result
    }, [drafts, initialDrafts, config, isManualDraft])

  const saveManualUpdates = useCallback(
    async (payload: UpdatePositionRequest) => {
      await saveManualPositions(payload)
      if (payload.entity_id) {
        await refreshEntity(payload.entity_id)
      }
    },
    [refreshEntity],
  )

  const handleSaveChanges = useCallback(async () => {
    if (!hasLocalChanges || isSaving) {
      setIsEditMode(false)
      return
    }

    setIsSaving(true)
    try {
      const payloadsByEntity = buildSavePayloadByEntity()
      if (payloadsByEntity.size === 0) {
        setIsEditMode(false)
        setHasLocalChanges(false)
        return
      }

      const requestPromises: Promise<void>[] = []
      let createdNewEntity = false
      let missingNewEntityName = false

      payloadsByEntity.forEach(
        ({ productType, entries, isNewEntity, newEntityName }, entityId) => {
          const payloadEntries = entries.map(({ payload, draft }) => {
            const entry = { ...payload }
            if (!draft.originalId) {
              const nextId =
                typeof entry.id === "string" && entry.id.trim() !== ""
                  ? entry.id
                  : null
              return { ...entry, id: nextId }
            }
            return entry
          })

          if (isNewEntity && payloadEntries.length === 0) {
            return
          }

          const newDrafts = entries.filter(entry => entry.draft.isNewEntity)
          const isPlaceholderEntity =
            typeof entityId === "string" && entityId.startsWith("new-")
          const treatAsNewEntity =
            Boolean(isNewEntity) || isPlaceholderEntity || newDrafts.length > 0

          const requestPayload: UpdatePositionRequest = {
            products: {
              [productType]: {
                entries: payloadEntries,
              },
            },
          }

          if (treatAsNewEntity) {
            const trimmedName =
              newEntityName?.trim() ||
              newDrafts
                .map(entry => entry.draft.newEntityName?.trim())
                .find(Boolean) ||
              newDrafts
                .map(entry => entry.draft.entityName?.trim())
                .find(Boolean) ||
              null

            if (!trimmedName) {
              console.warn(
                "Skipping manual position payload without new entity name",
                { entityId },
              )
              missingNewEntityName = true
              return
            }

            requestPayload.new_entity_name = trimmedName
            if ("entity_id" in requestPayload) {
              delete requestPayload.entity_id
            }
            createdNewEntity = true
          } else {
            requestPayload.entity_id = entityId
          }

          requestPromises.push(saveManualUpdates(requestPayload))
        },
      )

      if (missingNewEntityName) {
        showToast(
          translate("management.manualPositions.toasts.saveError"),
          "error",
        )
        setIsSaving(false)
        return
      }

      if (requestPromises.length > 0) {
        await Promise.all(requestPromises)
      }

      if (createdNewEntity) {
        await fetchEntities()
        await refreshData()
      }
      showToast(
        translate("management.manualPositions.toasts.saveSuccess"),
        "success",
      )
      setIsEditMode(false)
      setHasLocalChanges(false)
    } catch (error) {
      console.error("Error saving manual positions", error)
      showToast(
        translate("management.manualPositions.toasts.saveError"),
        "error",
      )
    } finally {
      setIsSaving(false)
    }
  }, [
    buildSavePayloadByEntity,
    hasLocalChanges,
    isSaving,
    saveManualUpdates,
    fetchEntities,
    refreshData,
    showToast,
    translate,
  ])

  const collectSavePayload = useCallback((): ManualSavePayloadByEntity => {
    const payloads = buildSavePayloadByEntity()
    const clone: ManualSavePayloadByEntity = new Map()

    payloads.forEach((value, key) => {
      clone.set(key, {
        productType: value.productType,
        entries: value.entries.map(entry => ({
          draft: entry.draft,
          payload: { ...entry.payload },
        })),
        isNewEntity: value.isNewEntity,
        newEntityName: value.newEntityName ?? null,
      })
    })

    return clone
  }, [buildSavePayloadByEntity])

  const setSavingState = useCallback((value: boolean) => {
    setIsSaving(value)
  }, [])

  const handleExternalSaveSuccess = useCallback(() => {
    setIsEditMode(false)
    setHasLocalChanges(false)
  }, [])

  const addLabel = translate(`${assetPath}.add`)

  const editLabel = translate("common.edit")
  const cancelLabel = translate("common.cancel")
  const saveLabel = translate("common.save")

  const discardTitle = translate(
    "management.manualPositions.shared.discardChangesTitle",
  )
  const discardMessage = translate(
    "management.manualPositions.shared.discardChangesMessage",
  )
  const deleteTitle = translate("management.manualPositions.shared.deleteTitle")
  const baseDeleteMessage = translate(
    "management.manualPositions.shared.deleteMessage",
  )
  const linkedFundsWarningMessage = useMemo(() => {
    if (asset !== "fundPortfolios" || !deleteTarget) {
      return null
    }
    const draft = drafts.find(item => item.localId === deleteTarget)
    if (!draft) {
      return null
    }
    const linkedFunds = getLinkedManualFunds(draft)
    if (linkedFunds.length === 0) {
      return null
    }
    const key =
      linkedFunds.length === 1
        ? "management.manualPositions.fundPortfolios.deleteWarning.single"
        : "management.manualPositions.fundPortfolios.deleteWarning.plural"
    return translate(key, { count: linkedFunds.length })
  }, [asset, deleteTarget, drafts, getLinkedManualFunds, translate])

  const linkedBankAccountWarningMessage = useMemo(() => {
    if (asset !== "bankAccounts" || !deleteTarget) {
      return null
    }
    const draft = drafts.find(item => item.localId === deleteTarget)
    if (!draft) {
      return null
    }

    const linkedCards = getLinkedManualCards(draft)
    const linkedPortfolios = getLinkedManualPortfoliosForAccount(draft)

    if (linkedCards.length === 0 && linkedPortfolios.length === 0) {
      return null
    }

    const parts: string[] = []
    if (linkedCards.length > 0) {
      const key =
        linkedCards.length === 1
          ? "management.manualPositions.bankAccounts.deleteWarning.single"
          : "management.manualPositions.bankAccounts.deleteWarning.plural"
      parts.push(translate(key, { count: linkedCards.length }))
    }
    if (linkedPortfolios.length > 0) {
      const key =
        linkedPortfolios.length === 1
          ? "management.manualPositions.bankAccounts.deletePortfolioWarning.single"
          : "management.manualPositions.bankAccounts.deletePortfolioWarning.plural"
      parts.push(translate(key, { count: linkedPortfolios.length }))
    }

    return parts.join("\n\n")
  }, [
    asset,
    deleteTarget,
    drafts,
    getLinkedManualCards,
    getLinkedManualPortfoliosForAccount,
    translate,
  ])

  const getDraftByOriginalId = useCallback(
    (originalId: string) => drafts.find(item => item.originalId === originalId),
    [drafts],
  )

  const getDraftByLocalId = useCallback(
    (localId: string) => drafts.find(item => item.localId === localId),
    [drafts],
  )

  const editByLocalId = useCallback(
    (localId: string) => {
      const draft = getDraftByLocalId(localId)
      if (!draft) return
      handleEditDraft(draft)
    },
    [getDraftByLocalId, handleEditDraft],
  )

  const getInitialDraftByOriginalId = useCallback(
    (originalId: string) =>
      initialDrafts.find(item => item.originalId === originalId),
    [initialDrafts],
  )

  const normalizedInitialDrafts = useMemo(() => {
    const map = new Map<string, string>()
    initialDrafts.forEach(draft => {
      if (draft.originalId) {
        map.set(
          draft.originalId,
          serialize(config.normalizeDraftForCompare(draft)),
        )
      }
    })
    return map
  }, [initialDrafts, config])

  const deletedOriginalIds = useMemo(() => {
    const initialIds = new Set(
      initialDrafts.map(draft => draft.originalId).filter(Boolean) as string[],
    )
    drafts.forEach(draft => {
      if (draft.originalId) {
        initialIds.delete(draft.originalId)
      }
    })
    return initialIds
  }, [drafts, initialDrafts])

  useEffect(() => {
    setManualDraftsForAsset(asset, drafts)
    setManualDeletedOriginalIdsForAsset(asset, deletedOriginalIds)
  }, [asset, drafts, deletedOriginalIds])

  const editByOriginalId = useCallback(
    (originalId: string) => {
      const draft = getDraftByOriginalId(originalId)
      if (!draft) return
      handleEditDraft(draft)
    },
    [getDraftByOriginalId, handleEditDraft],
  )

  const deleteByOriginalId = useCallback(
    (originalId: string) => {
      const draft = getDraftByOriginalId(originalId)
      if (!draft) return
      setDeleteTarget(draft.localId)
    },
    [getDraftByOriginalId],
  )

  const deleteByLocalId = useCallback((localId: string) => {
    setDeleteTarget(localId)
  }, [])

  const enterEditMode = useCallback(() => {
    setIsEditMode(true)
  }, [])

  const beginCreate = useCallback(
    (options?: { entityId?: string }) => {
      handleAddDraft(options?.entityId)
    },
    [handleAddDraft],
  )

  const requestSave = useCallback(
    () => handleSaveChanges(),
    [handleSaveChanges],
  )

  const requestCancel = useCallback(
    () => handleCancelEdit(),
    [handleCancelEdit],
  )

  const isDraftDirty = useCallback(
    (draft: ManualPositionDraft<any>) => {
      if (!draft.originalId) return true
      const baseline = normalizedInitialDrafts.get(draft.originalId)
      if (!baseline) return true
      const normalized = serialize(config.normalizeDraftForCompare(draft))
      return normalized !== baseline
    },
    [config, normalizedInitialDrafts],
  )

  const contextValue = useMemo<ManualPositionsContextValue>(
    () => ({
      asset,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities,
      assetTitle,
      assetDescription,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      translate,
      drafts,
      beginCreate,
      editByOriginalId,
      editByLocalId,
      deleteByOriginalId,
      deleteByLocalId,
      enterEditMode,
      requestSave,
      requestCancel,
      getDraftByOriginalId,
      getDraftByLocalId,
      getInitialDraftByOriginalId,
      isEntryDeleted: originalId => deletedOriginalIds.has(originalId),
      isDraftDirty,
      assetPath,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    }),
    [
      asset,
      isEditMode,
      hasLocalChanges,
      isSaving,
      manualEntities,
      assetTitle,
      assetDescription,
      addLabel,
      editLabel,
      cancelLabel,
      saveLabel,
      translate,
      drafts,
      beginCreate,
      editByOriginalId,
      editByLocalId,
      deleteByOriginalId,
      deleteByLocalId,
      enterEditMode,
      requestSave,
      requestCancel,
      getDraftByOriginalId,
      getDraftByLocalId,
      getInitialDraftByOriginalId,
      deletedOriginalIds,
      isDraftDirty,
      assetPath,
      collectSavePayload,
      setSavingState,
      handleExternalSaveSuccess,
    ],
  )

  return (
    <ManualPositionsContext.Provider value={contextValue}>
      {className ? <div className={className}>{children}</div> : children}

      <ConfirmationDialog
        isOpen={showCancelConfirm}
        title={discardTitle}
        message={discardMessage}
        confirmText={translate("common.discard")}
        cancelText={translate("common.cancel")}
        onConfirm={() => {
          setShowCancelConfirm(false)
          setIsEditMode(false)
          setHasLocalChanges(false)
          setDrafts(initialDrafts)
        }}
        onCancel={() => setShowCancelConfirm(false)}
      />

      <ConfirmationDialog
        isOpen={showDiscardFormConfirm}
        title={discardTitle}
        message={discardMessage}
        confirmText={translate("common.discard")}
        cancelText={translate("common.cancel")}
        onConfirm={() => {
          setShowDiscardFormConfirm(false)
          closeForm()
        }}
        onCancel={() => setShowDiscardFormConfirm(false)}
      />

      <ConfirmationDialog
        isOpen={deleteTarget !== null}
        title={deleteTitle}
        message={baseDeleteMessage}
        confirmText={translate("common.delete")}
        cancelText={translate("common.cancel")}
        onConfirm={handleDeleteDraft}
        onCancel={() => setDeleteTarget(null)}
        warning={
          [linkedFundsWarningMessage, linkedBankAccountWarningMessage]
            .filter((value): value is string => Boolean(value))
            .join("\n\n") || undefined
        }
      />

      {formState && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-[16000]">
          <Card className="w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            <CardHeader className="space-y-2">
              <CardTitle>
                {formMode === "create"
                  ? translate(`${assetPath}.form.createTitle`)
                  : translate(`${assetPath}.form.editTitle`)}
              </CardTitle>
              <CardDescription>
                {formMode === "create"
                  ? translate(`${assetPath}.form.createDescription`)
                  : translate(`${assetPath}.form.editDescription`)}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto">
              {config.renderFormFields({
                form: formState,
                updateField: (field, value) =>
                  updateField(field as string, value),
                errors: formErrors,
                clearError: field => clearError(field as string),
                t: translate,
                entityOptions: manualEntities,
                currencyOptions,
                defaultCurrency,
                locale,
                mode: formMode,
                canEditEntity:
                  formMode === "create" ||
                  !activeDraft?.originalId ||
                  Boolean(activeDraft?.isNewEntity),
                accountOptions: linkedAccountOptions,
                portfolioOptions: linkedPortfolioOptions,
              })}
            </CardContent>
            <CardFooter className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleCloseForm}>
                {translate("common.cancel")}
              </Button>
              <Button onClick={handleSubmitForm}>
                {translate("common.save")}
              </Button>
            </CardFooter>
          </Card>
        </div>
      )}
    </ManualPositionsContext.Provider>
  )
}

export function ManualPositionsControls({ className }: { className?: string }) {
  const {
    isEditMode,
    hasLocalChanges,
    isSaving,
    manualEntities,
    addLabel,
    editLabel,
    cancelLabel,
    saveLabel,
    beginCreate,
    enterEditMode,
    requestCancel,
    requestSave,
  } = useManualPositions()

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 sm:justify-end",
        className,
      )}
    >
      <Button
        variant="outline"
        size="sm"
        onClick={() => beginCreate()}
        disabled={manualEntities.length === 0}
        className="flex items-center gap-2"
      >
        <Plus className="h-3.5 w-3.5" />
        {addLabel}
      </Button>
      {isEditMode ? (
        <>
          <Button
            variant="outline"
            size="sm"
            onClick={requestCancel}
            disabled={isSaving}
            className="flex items-center gap-2"
          >
            <X className="h-3.5 w-3.5" />
            {cancelLabel}
          </Button>
          <Button
            size="sm"
            onClick={requestSave}
            disabled={isSaving || (!hasLocalChanges && !isSaving)}
            className="flex items-center gap-2"
          >
            <Save className="h-3.5 w-3.5" />
            {saveLabel}
          </Button>
        </>
      ) : (
        <Button
          variant="default"
          size="sm"
          onClick={enterEditMode}
          className="flex items-center gap-2"
        >
          <Pencil className="h-3.5 w-3.5" />
          {editLabel}
        </Button>
      )}
    </div>
  )
}

export function ManualPositionsUnsavedNotice({
  className,
}: {
  className?: string
}) {
  const { isEditMode, hasLocalChanges, translate } = useManualPositions()

  if (!isEditMode || !hasLocalChanges) {
    return null
  }

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-100/70 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
        className,
      )}
    >
      <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
      <div>{translate("management.unsavedChanges")}</div>
    </div>
  )
}
