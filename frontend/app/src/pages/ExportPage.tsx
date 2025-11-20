import { useEffect, useMemo, useState, useCallback, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  FileSpreadsheet,
  FileUp,
  Info,
  Plus,
  PlusCircle,
  RotateCcw,
  Save as SaveIcon,
  Settings,
  LayoutTemplate,
  Trash2,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext, type AppSettings } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import {
  updateSheets,
  importFetch,
  getTemplates,
  getTemplateFields,
  createTemplate,
  updateTemplate as updateTemplateRequest,
  deleteTemplate as deleteTemplateRequest,
} from "@/services/api"
import {
  EntityType,
  ExternalIntegrationStatus,
  type ImportError,
  TemplateType,
  type Template,
  type TemplateCreatePayload,
  type TemplateUpdatePayload,
  type TemplateFeatureDefinition,
  type Feature,
} from "@/types"
import { ApiErrorException } from "@/utils/apiErrors"
import { cn } from "@/lib/utils"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { ErrorDetailsDialog } from "@/components/ui/ErrorDetailsDialog"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { Switch } from "@/components/ui/Switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs"
import {
  cleanObject,
  processDataFields,
  sanitizeStablecoins,
} from "@/lib/settingsUtils"
import { ProductType } from "@/types/position"
import { TemplateManagerDialog } from "@/components/templates/TemplateManagerDialog"

const EXPORT_SECTIONS = [
  "position",
  "contributions",
  "transactions",
  "historic",
] as const

type ExportSectionKey = (typeof EXPORT_SECTIONS)[number]

const IMPORT_SECTIONS = ["position", "transactions"] as const

type ImportSectionKey = (typeof IMPORT_SECTIONS)[number]

const SECTION_FEATURE_MAP: Record<ExportSectionKey, Feature> = {
  position: "POSITION",
  contributions: "AUTO_CONTRIBUTIONS",
  transactions: "TRANSACTIONS",
  historic: "HISTORIC",
}

type SheetsConfigDraft = NonNullable<
  NonNullable<AppSettings["export"]>["sheets"]
>

type ImportConfigDraft = NonNullable<
  NonNullable<AppSettings["importing"]>["sheets"]
>

const AVAILABLE_POSITION_OPTIONS = [
  ProductType.ACCOUNT,
  ProductType.CARD,
  ProductType.LOAN,
  ProductType.FUND,
  ProductType.STOCK_ETF,
  ProductType.FACTORING,
  ProductType.CRYPTO,
  ProductType.DEPOSIT,
  ProductType.REAL_ESTATE_CF,
] as const

const AVAILABLE_TRANSACTION_PRODUCTS = [
  ProductType.ACCOUNT,
  ProductType.STOCK_ETF,
  ProductType.FUND,
  ProductType.FUND_PORTFOLIO,
  ProductType.FACTORING,
  ProductType.REAL_ESTATE_CF,
  ProductType.DEPOSIT,
] as const

const AVAILABLE_HISTORIC_PRODUCTS = [
  ProductType.REAL_ESTATE_CF,
  ProductType.FACTORING,
] as const

const AVAILABLE_IMPORT_POSITION_OPTIONS = [
  ProductType.ACCOUNT,
  ProductType.CARD,
  ProductType.LOAN,
  ProductType.FUND,
  ProductType.STOCK_ETF,
  ProductType.FACTORING,
  ProductType.DEPOSIT,
  ProductType.REAL_ESTATE_CF,
] as const

const AVAILABLE_IMPORT_TRANSACTION_PRODUCTS = [
  ProductType.ACCOUNT,
  ProductType.STOCK_ETF,
  ProductType.FUND,
  ProductType.FUND_PORTFOLIO,
  ProductType.FACTORING,
  ProductType.REAL_ESTATE_CF,
  ProductType.DEPOSIT,
] as const

const buildProductOptions = (
  productTypes: readonly ProductType[],
  labels: Record<string, string>,
): MultiSelectOption[] =>
  productTypes.reduce<MultiSelectOption[]>((acc, productType) => {
    const label = labels[productType]
    if (label) {
      acc.push({ value: productType, label })
    }
    return acc
  }, [])

const sortTemplatesByName = (templates: Template[]) =>
  [...templates].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
  )

interface ManualImportResult {
  gotData: boolean
  errors?: ImportError[]
}

const CREATE_IMPORT_TEMPLATE_OPTION = "__create_import_template__"

type TemplateSelectionPayload<TParams = Record<string, string> | null> = {
  id: string
  params: TParams
}

const normalizeExportTemplateValue = (
  value: any,
): TemplateSelectionPayload<Record<string, string> | null> | undefined => {
  if (!value) {
    return undefined
  }
  if (typeof value === "string") {
    return { id: value, params: null }
  }
  if (typeof value === "object" && value.id) {
    return {
      id: String(value.id),
      params:
        value.params === undefined || value.params === null
          ? null
          : (value.params as Record<string, string>),
    }
  }
  return undefined
}

const normalizeImportTemplateValue = (
  value: any,
): TemplateSelectionPayload<Record<string, string>> | undefined => {
  if (!value) {
    return undefined
  }
  if (typeof value === "string") {
    return { id: value, params: {} }
  }
  if (typeof value === "object" && value.id) {
    const paramsRecord =
      value.params && typeof value.params === "object"
        ? (value.params as Record<string, string>)
        : {}
    return {
      id: String(value.id),
      params: paramsRecord,
    }
  }
  return undefined
}

const extractTemplateId = (value: any): string | null => {
  if (!value) {
    return null
  }
  if (typeof value === "string") {
    return value
  }
  if (typeof value === "object" && value.id) {
    return String(value.id)
  }
  return null
}

export default function ExportPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const {
    settings,
    exportState,
    setExportState,
    showToast,
    fetchEntities,
    entities,
    externalIntegrations,
    saveSettings,
    fetchSettings,
  } = useAppContext()
  const { refreshData } = useFinancialData()
  const [activeTab, setActiveTab] = useState<"export" | "import">("export")
  const [successAnimation, setSuccessAnimation] = useState(false)
  const [showImportConfirm, setShowImportConfirm] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [importSuccessAnimation, setImportSuccessAnimation] = useState(false)
  const [importErrors, setImportErrors] = useState<ImportError[] | null>(null)
  const [showErrorDetails, setShowErrorDetails] = useState(false)
  const [showExportConfig, setShowExportConfig] = useState(false)
  const [showImportConfig, setShowImportConfig] = useState(false)
  const [exportConfigDraft, setExportConfigDraft] =
    useState<SheetsConfigDraft | null>(null)
  const [importConfigDraft, setImportConfigDraft] =
    useState<ImportConfigDraft | null>(null)
  const [exportValidationErrors, setExportValidationErrors] = useState<
    Record<string, string[]>
  >({})
  const [importValidationErrors, setImportValidationErrors] = useState<
    Record<string, string[]>
  >({})
  const [isSavingExportConfig, setIsSavingExportConfig] = useState(false)
  const [isSavingImportConfig, setIsSavingImportConfig] = useState(false)
  const [isRevertingExportConfig, setIsRevertingExportConfig] = useState(false)
  const [isRevertingImportConfig, setIsRevertingImportConfig] = useState(false)
  const [expandedExportSections, setExpandedExportSections] = useState<
    Record<string, boolean>
  >({})
  const [expandedImportSections, setExpandedImportSections] = useState<
    Record<string, boolean>
  >({})
  const [exportExtraSettingsExpanded, setExportExtraSettingsExpanded] =
    useState<Record<string, boolean>>({})
  const [importExtraSettingsExpanded, setImportExtraSettingsExpanded] =
    useState<Record<string, boolean>>({})
  const [resetExportDraftRequested, setResetExportDraftRequested] =
    useState(false)
  const [resetImportDraftRequested, setResetImportDraftRequested] =
    useState(false)
  const [templatesByType, setTemplatesByType] = useState<
    Record<TemplateType, Template[]>
  >({
    [TemplateType.EXPORT]: [],
    [TemplateType.IMPORT]: [],
  })
  const [templatesLoaded, setTemplatesLoaded] = useState<
    Record<TemplateType, boolean>
  >({
    [TemplateType.EXPORT]: false,
    [TemplateType.IMPORT]: false,
  })
  const [templatesLoading, setTemplatesLoading] = useState<
    Record<TemplateType, boolean>
  >({
    [TemplateType.EXPORT]: false,
    [TemplateType.IMPORT]: false,
  })
  const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false)
  const [templateDialogType, setTemplateDialogType] = useState(
    TemplateType.EXPORT,
  )
  const [templateFields, setTemplateFields] = useState<Partial<
    Record<Feature, TemplateFeatureDefinition[]>
  > | null>(null)
  const [isLoadingTemplateFields, setIsLoadingTemplateFields] = useState(false)

  const createExportConfigDraft = (
    source?: SheetsConfigDraft | null,
  ): SheetsConfigDraft => {
    const base = JSON.parse(JSON.stringify(source ?? {})) as Record<string, any>

    const draft: Record<string, any> = {
      ...base,
      globals: {
        ...(base.globals ?? {}),
      },
    }

    delete draft.enabled

    EXPORT_SECTIONS.forEach(section => {
      draft[section] = Array.isArray(base[section])
        ? base[section].map(item => {
            const nextItem: Record<string, any> = { ...(item ?? {}) }
            const normalizedTemplate = normalizeExportTemplateValue(
              (item as Record<string, any>)?.template,
            )
            if (normalizedTemplate) {
              nextItem.template = normalizedTemplate
            } else {
              delete nextItem.template
            }
            return nextItem
          })
        : []
    })

    return draft as SheetsConfigDraft
  }

  const createImportConfigDraft = (
    source?: ImportConfigDraft | null,
  ): ImportConfigDraft => {
    const base = JSON.parse(JSON.stringify(source ?? {})) as Record<string, any>

    const draft: Record<string, any> = {
      ...base,
      globals: {
        ...(base.globals ?? {}),
      },
    }

    delete draft.enabled

    IMPORT_SECTIONS.forEach(section => {
      draft[section] = Array.isArray(base[section])
        ? base[section].map(item => {
            const nextItem: Record<string, any> = { ...(item ?? {}) }
            const normalizedTemplate = normalizeImportTemplateValue(
              (item as Record<string, any>)?.template,
            )
            if (normalizedTemplate) {
              nextItem.template = normalizedTemplate
            } else {
              delete nextItem.template
            }

            // Initialize temporary UI fields for entity mode
            nextItem._entity_mode = "select"
            nextItem._new_entity_name = ""

            return nextItem
          })
        : []
    })

    return draft as ImportConfigDraft
  }

  useEffect(() => {
    if (showExportConfig && resetExportDraftRequested) {
      setExportConfigDraft(createExportConfigDraft(settings.export?.sheets))
      setExportValidationErrors({})
      setExpandedExportSections(
        EXPORT_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
          acc[section] = false
          return acc
        }, {}),
      )
      setExportExtraSettingsExpanded({})
      setResetExportDraftRequested(false)
    }
  }, [showExportConfig, resetExportDraftRequested, settings.export])

  useEffect(() => {
    if (showImportConfig && resetImportDraftRequested) {
      setImportConfigDraft(createImportConfigDraft(settings.importing?.sheets))
      setImportValidationErrors({})
      setExpandedImportSections(
        IMPORT_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
          acc[section] = false
          return acc
        }, {}),
      )
      setImportExtraSettingsExpanded({})
      setResetImportDraftRequested(false)
    }
  }, [showImportConfig, resetImportDraftRequested, settings.importing])

  useEffect(() => {
    if (!importConfigDraft) {
      return
    }

    const allowedEntityNames = new Set(
      (entities ?? [])
        .filter(
          entity =>
            entity.type === EntityType.FINANCIAL_INSTITUTION &&
            entity.name &&
            entity.id,
        )
        .map(entity => entity.name.trim()),
    )

    setImportConfigDraft(prev => {
      if (!prev) {
        return prev
      }

      let draftChanged = false
      const nextDraft: Record<string, any> = { ...prev }

      IMPORT_SECTIONS.forEach(section => {
        const items = (prev as Record<string, any>)[section]
        if (!Array.isArray(items)) {
          return
        }

        let sectionChanged = false
        const nextItems = items.map(item => {
          const entityValue = (item?.template?.params?.entity as string)?.trim()
          if (
            entityValue &&
            !allowedEntityNames.has(entityValue) &&
            item._entity_mode !== "new"
          ) {
            sectionChanged = true
            return {
              ...item,
              _entity_mode: "new",
              _new_entity_name: item._new_entity_name || entityValue,
            }
          }
          return item
        })

        if (sectionChanged) {
          draftChanged = true
          nextDraft[section] = nextItems
        }
      })

      return draftChanged ? (nextDraft as ImportConfigDraft) : prev
    })
  }, [importConfigDraft, entities])

  const productTypeLabels = useMemo(() => {
    const enums = (t.enums as Record<string, any>) ?? {}
    return (enums.productType as Record<string, string>) ?? {}
  }, [t])

  const featureLabels = useMemo(() => {
    const labels = (t.features as Record<string, string>) ?? {}
    return {
      POSITION: labels.POSITION ?? "POSITION",
      AUTO_CONTRIBUTIONS: labels.AUTO_CONTRIBUTIONS ?? "AUTO_CONTRIBUTIONS",
      TRANSACTIONS: labels.TRANSACTIONS ?? "TRANSACTIONS",
      HISTORIC: labels.HISTORIC ?? "HISTORIC",
    }
  }, [t])

  const positionOptions = useMemo<MultiSelectOption[]>(
    () => buildProductOptions(AVAILABLE_POSITION_OPTIONS, productTypeLabels),
    [productTypeLabels],
  )

  const transactionProductOptions = useMemo<MultiSelectOption[]>(
    () =>
      buildProductOptions(AVAILABLE_TRANSACTION_PRODUCTS, productTypeLabels),
    [productTypeLabels],
  )

  const historicProductOptions = useMemo<MultiSelectOption[]>(
    () => buildProductOptions(AVAILABLE_HISTORIC_PRODUCTS, productTypeLabels),
    [productTypeLabels],
  )

  const handleOpenExportConfig = () => {
    setExportConfigDraft(createExportConfigDraft(settings.export?.sheets))
    setExportValidationErrors({})
    setExpandedExportSections(() =>
      EXPORT_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
        acc[section] = false
        return acc
      }, {}),
    )
    setExportExtraSettingsExpanded({})
    setShowExportConfig(true)
    if (!templatesLoaded[TemplateType.EXPORT]) {
      loadTemplates(TemplateType.EXPORT)
    }
  }

  const handleCloseExportConfig = () => {
    setShowExportConfig(false)
    setExportConfigDraft(null)
    setExportValidationErrors({})
    setExpandedExportSections({})
    setExportExtraSettingsExpanded({})
  }

  const handleOpenImportConfig = () => {
    setImportConfigDraft(createImportConfigDraft(settings.importing?.sheets))
    setImportValidationErrors({})
    setExpandedImportSections(() =>
      IMPORT_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
        acc[section] = false
        return acc
      }, {}),
    )
    setImportExtraSettingsExpanded({})
    setShowImportConfig(true)
    if (!templatesLoaded[TemplateType.IMPORT]) {
      loadTemplates(TemplateType.IMPORT)
    }
  }

  const handleCloseImportConfig = () => {
    setShowImportConfig(false)
    setImportConfigDraft(null)
    setImportValidationErrors({})
    setExpandedImportSections({})
    setImportExtraSettingsExpanded({})
  }

  const toggleExportSection = (section: ExportSectionKey) => {
    setExpandedExportSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const toggleImportSection = (section: ImportSectionKey) => {
    setExpandedImportSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const toggleExportExtraSettings = (itemKey: string) => {
    setExportExtraSettingsExpanded(prev => ({
      ...prev,
      [itemKey]: !prev[itemKey],
    }))
  }

  const toggleImportExtraSettings = (itemKey: string) => {
    setImportExtraSettingsExpanded(prev => ({
      ...prev,
      [itemKey]: !prev[itemKey],
    }))
  }

  const clearExportGlobalsError = () => {
    setExportValidationErrors(prev => {
      if (!prev.globals) {
        return prev
      }
      const next = { ...prev }
      delete next.globals
      return next
    })
  }

  const clearImportGlobalsError = () => {
    setImportValidationErrors(prev => {
      if (!prev.importGlobals) {
        return prev
      }
      const next = { ...prev }
      delete next.importGlobals
      return next
    })
  }

  const clearExportItemError = (section: ExportSectionKey, index: number) => {
    setExportValidationErrors(prev => {
      const sectionErrors = prev[section]
      if (!sectionErrors) {
        return prev
      }
      const updated = [...sectionErrors]
      updated[index] = ""
      const next = { ...prev }
      if (updated.every(error => !error)) {
        delete next[section]
      } else {
        next[section] = updated
      }
      return next
    })
  }

  const clearImportItemError = (section: ImportSectionKey, index: number) => {
    const errorKey = `import_${section}`
    setImportValidationErrors(prev => {
      const sectionErrors = prev[errorKey]
      if (!sectionErrors) {
        return prev
      }
      const updated = [...sectionErrors]
      updated[index] = ""
      const next = { ...prev }
      if (updated.every(error => !error)) {
        delete next[errorKey]
      } else {
        next[errorKey] = updated
      }
      return next
    })
  }

  const handleExportGlobalChange = (
    field: "spreadsheetId" | "dateFormat" | "datetimeFormat",
    value: string,
  ) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const globals = {
        ...(prev.globals ?? {}),
        [field]: value.trim() === "" ? null : value,
      }
      return {
        ...prev,
        globals,
      }
    })

    if (field === "spreadsheetId" && value.trim()) {
      clearExportGlobalsError()
    }
  }

  const handleImportGlobalChange = (
    field: "spreadsheetId" | "dateFormat" | "datetimeFormat",
    value: string,
  ) => {
    setImportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const globals = {
        ...(prev.globals ?? {}),
        [field]: value.trim() === "" ? null : value,
      }
      return {
        ...prev,
        globals,
      }
    })

    if (field === "spreadsheetId" && value.trim()) {
      clearImportGlobalsError()
    }
  }

  const handleAddExportItem = (section: ExportSectionKey) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const newItem: Record<string, any> = { range: "", lastUpdate: false }

      if (["position", "transactions", "historic"].includes(section)) {
        newItem.data = []
      }

      if (
        ["historic", "position", "contributions", "transactions"].includes(
          section,
        )
      ) {
        newItem.filters = []
      }

      items.push(newItem)

      return {
        ...prev,
        [section]: items,
      }
    })

    setExpandedExportSections(prev => ({
      ...prev,
      [section]: true,
    }))
  }

  const handleRemoveExportItem = (section: ExportSectionKey, index: number) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      items.splice(index, 1)

      return {
        ...prev,
        [section]: items,
      }
    })

    setExportValidationErrors(prev => {
      if (!prev[section]) {
        return prev
      }
      const next = { ...prev }
      const updated = [...next[section]]
      updated.splice(index, 1)
      if (updated.length === 0 || updated.every(error => !error)) {
        delete next[section]
      } else {
        next[section] = updated
      }
      return next
    })

    setExportExtraSettingsExpanded(prev => {
      const next: Record<string, boolean> = {}
      Object.entries(prev).forEach(([key, value]) => {
        if (!key.startsWith(`${section}-`)) {
          next[key] = value
        }
      })
      return next
    })
  }

  const handleUpdateExportItem = (
    section: ExportSectionKey,
    index: number,
    field: string,
    value: any,
  ) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      items[index] = {
        ...items[index],
        [field]: value,
      }

      return {
        ...prev,
        [section]: items,
      }
    })

    if (field === "range" || field === "data") {
      const hasValue = Array.isArray(value)
        ? value.length > 0
        : typeof value === "string"
          ? value.trim().length > 0
          : value !== null && value !== undefined

      if (hasValue) {
        clearExportItemError(section, index)
      }
    }
  }

  const handleAddExportFilter = (section: ExportSectionKey, index: number) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const filters = Array.isArray(items[index]?.filters)
        ? [...items[index].filters]
        : []

      filters.push({ field: "", values: "" })

      items[index] = {
        ...items[index],
        filters,
      }

      return {
        ...prev,
        [section]: items,
      }
    })
  }

  const handleRemoveExportFilter = (
    section: ExportSectionKey,
    itemIndex: number,
    filterIndex: number,
  ) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const filters = Array.isArray(items[itemIndex]?.filters)
        ? [...items[itemIndex].filters]
        : []

      filters.splice(filterIndex, 1)

      items[itemIndex] = {
        ...items[itemIndex],
        filters,
      }

      return {
        ...prev,
        [section]: items,
      }
    })
  }

  const handleUpdateExportFilter = (
    section: ExportSectionKey,
    itemIndex: number,
    filterIndex: number,
    field: "field" | "values",
    value: string,
  ) => {
    setExportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const filters = Array.isArray(items[itemIndex]?.filters)
        ? [...items[itemIndex].filters]
        : []

      filters[filterIndex] = {
        ...filters[filterIndex],
        [field]: value,
      }

      items[itemIndex] = {
        ...items[itemIndex],
        filters,
      }

      return {
        ...prev,
        [section]: items,
      }
    })
  }

  const handleAddImportItem = (section: ImportSectionKey) => {
    setImportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const newItem: Record<string, any> = {
        range: "",
        _entity_mode: "select",
        _new_entity_name: "",
      }

      if (["position", "transactions"].includes(section)) {
        newItem.data = ""
      }

      items.push(newItem)

      return {
        ...prev,
        [section]: items,
      }
    })

    setExpandedImportSections(prev => ({
      ...prev,
      [section]: true,
    }))
  }

  const handleRemoveImportItem = (section: ImportSectionKey, index: number) => {
    setImportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      items.splice(index, 1)

      return {
        ...prev,
        [section]: items,
      }
    })

    setImportValidationErrors(prev => {
      const errorKey = `import_${section}`
      if (!prev[errorKey]) {
        return prev
      }
      const next = { ...prev }
      const updated = [...next[errorKey]]
      updated.splice(index, 1)
      if (updated.length === 0 || updated.every(error => !error)) {
        delete next[errorKey]
      } else {
        next[errorKey] = updated
      }
      return next
    })

    setImportExtraSettingsExpanded(prev => {
      const next: Record<string, boolean> = {}
      Object.entries(prev).forEach(([key, value]) => {
        if (!key.startsWith(`${section}-`)) {
          next[key] = value
        }
      })
      return next
    })
  }

  const handleUpdateImportItem = (
    section: ImportSectionKey,
    index: number,
    field: string,
    value: any,
  ) => {
    setImportConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      items[index] = {
        ...items[index],
        [field]: value,
      }

      return {
        ...prev,
        [section]: items,
      }
    })

    if (
      field === "range" ||
      field === "data" ||
      field === "template" ||
      field === "_entity_mode" ||
      field === "_new_entity_name"
    ) {
      const hasValue = Array.isArray(value)
        ? value.length > 0
        : typeof value === "string"
          ? value.trim().length > 0
          : value !== null && value !== undefined

      if (hasValue) {
        clearImportItemError(section, index)
      }
    }
  }

  const runExportValidation = (config: SheetsConfigDraft | null) => {
    if (!config) {
      setExportValidationErrors({})
      return true
    }

    const errors: Record<string, string[]> = {}
    const configRecord = config as Record<string, any>

    const sectionsConfigured = EXPORT_SECTIONS.some(section => {
      const items = configRecord[section]
      return Array.isArray(items) && items.length > 0
    })

    if (sectionsConfigured) {
      const spreadsheetId =
        (configRecord.globals?.spreadsheetId as string | undefined)?.trim() ??
        ""
      if (!spreadsheetId) {
        errors.globals = [t.settings.errors.spreadsheetIdRequired]
      }
    }

    EXPORT_SECTIONS.forEach(section => {
      const items = Array.isArray(configRecord[section])
        ? (configRecord[section] as any[])
        : []

      if (items.length === 0) {
        return
      }

      const sectionErrors: string[] = []

      items.forEach((item, index) => {
        const entryErrors: string[] = []
        const range = (item?.range as string | undefined)?.trim() ?? ""
        if (!range) {
          entryErrors.push(t.settings.errors.rangeRequired)
        }

        if (["position", "transactions", "historic"].includes(section)) {
          const dataValue = item?.data
          const hasData = Array.isArray(dataValue)
            ? dataValue.length > 0
            : typeof dataValue === "string"
              ? dataValue.trim().length > 0
              : !!dataValue

          if (!hasData) {
            entryErrors.push(t.settings.errors.dataRequired)
          }
        }

        if (entryErrors.length > 0) {
          sectionErrors[index] = entryErrors.join(" ")
        }
      })

      if (sectionErrors.length > 0) {
        errors[section] = sectionErrors
      }
    })

    setExportValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const runImportValidation = (config: ImportConfigDraft | null) => {
    if (!config) {
      setImportValidationErrors({})
      return true
    }

    const errors: Record<string, string[]> = {}
    const configRecord = config as Record<string, any>

    const sectionsConfigured = IMPORT_SECTIONS.some(section => {
      const items = configRecord[section]
      return Array.isArray(items) && items.length > 0
    })

    if (sectionsConfigured) {
      const spreadsheetId =
        (configRecord.globals?.spreadsheetId as string | undefined)?.trim() ??
        ""
      if (!spreadsheetId) {
        errors.importGlobals = [t.settings.errors.importSpreadsheetIdRequired]
      }
    }

    IMPORT_SECTIONS.forEach(section => {
      const items = Array.isArray(configRecord[section])
        ? (configRecord[section] as any[])
        : []

      if (items.length === 0) {
        return
      }

      const sectionErrors: string[] = []
      const errorKey = `import_${section}`

      items.forEach((item, index) => {
        const entryErrors: string[] = []
        const range = (item?.range as string | undefined)?.trim() ?? ""
        if (!range) {
          entryErrors.push(t.settings.errors.rangeRequired)
        }

        if (["position", "transactions"].includes(section)) {
          const dataValue = item?.data
          const hasData = Array.isArray(dataValue)
            ? dataValue.length > 0
            : typeof dataValue === "string"
              ? dataValue.trim().length > 0
              : !!dataValue

          if (!hasData) {
            entryErrors.push(t.settings.errors.dataRequired)
          }

          const templateId = extractTemplateId(item?.template)
          if (!templateId) {
            entryErrors.push(t.export.templates.templateSelectRequired)
          }

          const entityMode = (item._entity_mode as string) ?? "select"
          if (entityMode === "new") {
            const newEntityName = (item._new_entity_name as string) ?? ""
            if (!newEntityName.trim()) {
              entryErrors.push(t.export.import.entityRequired)
            }
          }
        }

        if (entryErrors.length > 0) {
          sectionErrors[index] = entryErrors.join(" ")
        }
      })

      if (sectionErrors.length > 0) {
        errors[errorKey] = sectionErrors
      }
    })

    setImportValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSaveExportConfig = async () => {
    if (!exportConfigDraft) {
      return
    }

    const isValid = runExportValidation(exportConfigDraft)
    if (!isValid) {
      showToast(t.settings.validationError, "error")
      return
    }

    try {
      setIsSavingExportConfig(true)

      const sanitizedStablecoins = sanitizeStablecoins(
        settings.assets?.crypto?.stablecoins,
      )

      const exportSheets = JSON.parse(
        JSON.stringify(exportConfigDraft),
      ) as SheetsConfigDraft

      delete (exportSheets as Record<string, any>).enabled

      const exportSheetsRecord = exportSheets as Record<string, any>
      if (Array.isArray(exportSheetsRecord.contributions)) {
        exportSheetsRecord.contributions = exportSheetsRecord.contributions.map(
          (item: Record<string, any>) => {
            if (item && typeof item === "object") {
              const next = { ...item }
              delete next.data
              return next
            }
            return item
          },
        )
      }

      const settingsForSave: AppSettings = {
        ...settings,
        export: {
          ...(settings.export ?? {}),
          sheets: exportSheets,
        },
        assets: {
          ...settings.assets,
          crypto: {
            ...settings.assets?.crypto,
            stablecoins: sanitizedStablecoins,
          },
        },
      }

      const processedSettings = processDataFields({ ...settingsForSave })
      const cleanedSettings = cleanObject(processedSettings) as AppSettings

      if (cleanedSettings.assets?.crypto) {
        cleanedSettings.assets.crypto.hideUnknownTokens =
          settings.assets?.crypto?.hideUnknownTokens ?? false
      }

      const wasSaved = await saveSettings(cleanedSettings)
      if (!wasSaved) {
        return
      }

      setShowExportConfig(false)
      setExportConfigDraft(null)
    } catch (error) {
      console.error("Error saving export config:", error)
      showToast(t.settings.saveError, "error")
    } finally {
      setIsSavingExportConfig(false)
    }
  }

  const handleSaveImportConfig = async () => {
    if (!importConfigDraft) {
      return
    }

    const isValid = runImportValidation(importConfigDraft)
    if (!isValid) {
      showToast(t.settings.validationError, "error")
      return
    }

    try {
      setIsSavingImportConfig(true)

      const sanitizedStablecoins = sanitizeStablecoins(
        settings.assets?.crypto?.stablecoins,
      )

      const importConfig = JSON.parse(
        JSON.stringify(importConfigDraft),
      ) as ImportConfigDraft

      delete (importConfig as Record<string, any>).enabled

      // Process entity fields: move entity into template.params and remove temporary fields
      IMPORT_SECTIONS.forEach(section => {
        const items = (importConfig as Record<string, any>)[section]
        if (Array.isArray(items)) {
          items.forEach((item: any) => {
            // Determine final entity value
            const entityMode = item._entity_mode || "select"
            const finalEntity =
              entityMode === "new"
                ? (item._new_entity_name || "").trim()
                : (item.template?.params?.entity || "").trim()

            // Store entity in template.params
            if (item.template && typeof item.template === "object") {
              const nextParams = { ...(item.template.params ?? {}) }
              if (finalEntity) {
                nextParams.entity = finalEntity
              } else {
                delete nextParams.entity
              }
              item.template.params =
                Object.keys(nextParams).length > 0 ? nextParams : null
            }

            // Remove temporary UI fields
            delete item._entity_mode
            delete item._new_entity_name
          })
        }
      })

      const settingsForSave: AppSettings = {
        ...settings,
        importing: {
          ...(settings.importing ?? {}),
          sheets: importConfig,
        },
        assets: {
          ...settings.assets,
          crypto: {
            ...settings.assets?.crypto,
            stablecoins: sanitizedStablecoins,
          },
        },
      }

      const processedSettings = processDataFields({ ...settingsForSave })
      const cleanedSettings = cleanObject(processedSettings) as AppSettings

      if (cleanedSettings.assets?.crypto) {
        cleanedSettings.assets.crypto.hideUnknownTokens =
          settings.assets?.crypto?.hideUnknownTokens ?? false
      }

      const wasSaved = await saveSettings(cleanedSettings)
      if (!wasSaved) {
        return
      }

      setShowImportConfig(false)
      setImportConfigDraft(null)
    } catch (error) {
      console.error("Error saving import config:", error)
      showToast(t.settings.saveError, "error")
    } finally {
      setIsSavingImportConfig(false)
    }
  }

  const handleRevertExportConfig = async () => {
    try {
      setIsRevertingExportConfig(true)
      await fetchSettings()
      setExportValidationErrors({})
      setResetExportDraftRequested(true)
    } catch (error) {
      console.error("Error reverting export config:", error)
      showToast(t.settings.fetchError, "error")
    } finally {
      setIsRevertingExportConfig(false)
    }
  }

  const handleRevertImportConfig = async () => {
    try {
      setIsRevertingImportConfig(true)
      await fetchSettings()
      setImportValidationErrors({})
      setResetImportDraftRequested(true)
    } catch (error) {
      console.error("Error reverting import config:", error)
      showToast(t.settings.fetchError, "error")
    } finally {
      setIsRevertingImportConfig(false)
    }
  }

  const sheetsConfig = settings?.export?.sheets
  const sectionCounts = {
    position: sheetsConfig?.position?.length || 0,
    contributions: sheetsConfig?.contributions?.length || 0,
    transactions: sheetsConfig?.transactions?.length || 0,
    historic: sheetsConfig?.historic?.length || 0,
  }
  const hasSheetSections = Object.values(sectionCounts).some(count => count > 0)

  const importConfig = settings?.importing?.sheets
  const importSectionCounts = {
    position: importConfig?.position?.length || 0,
    transactions: importConfig?.transactions?.length || 0,
  }
  const hasImportSections = Object.values(importSectionCounts).some(
    count => count > 0,
  )

  const googleSheetsIntegration = externalIntegrations.find(
    integration => integration.id === "GOOGLE_SHEETS",
  )
  const isGoogleSheetsIntegrationEnabled =
    googleSheetsIntegration?.status === ExternalIntegrationStatus.ON
  const canExport = isGoogleSheetsIntegrationEnabled && hasSheetSections
  const canImport = isGoogleSheetsIntegrationEnabled && hasImportSections
  const sheetsConfigured = hasSheetSections
  const importConfigured = hasImportSections

  const isExportDisabled =
    !canExport || exportState.isExporting || successAnimation
  const isImportDisabled = !canImport || isImporting || importSuccessAnimation

  const goToIntegrationsSettings = () => navigate("/settings?tab=integrations")

  const IntegrationRequiredBadge = ({
    integrationName = "Google Sheets",
  }: {
    integrationName?: string
  }) => (
    <Popover>
      <PopoverTrigger asChild>
        <Badge
          variant="outline"
          className="bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/20 dark:text-red-300 dark:hover:bg-red-900/30 cursor-pointer transition-colors"
        >
          {t.entities.requires} {integrationName}
        </Badge>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-9 w-9 text-red-500" />
            <h4 className="font-medium text-sm">
              {t.entities.setupIntegrationsMessage}
            </h4>
          </div>
          <div className="space-y-1">
            <div className="text-sm ml-8">• {integrationName}</div>
          </div>
          <Button
            size="sm"
            className="w-full mt-8"
            onClick={goToIntegrationsSettings}
          >
            <Settings className="mr-2 h-3 w-3" />
            {t.entities.goToSettings}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )

  const handleExport = async () => {
    try {
      setExportState(prev => ({ ...prev, isExporting: true }))
      await updateSheets()

      setSuccessAnimation(true)
      showToast(t.common.exportSuccess, "success")
      setExportState(prev => ({
        ...prev,
        isExporting: false,
        lastExportTime: Date.now(),
      }))

      setTimeout(() => {
        setSuccessAnimation(false)
      }, 2000)
    } catch (error) {
      console.error("Export error:", error)
      if (error instanceof ApiErrorException) {
        const code = error.code
        if (code.startsWith("sheet.not_found.")) {
          const sheetName = code.split(".").pop() || ""
          showToast(
            t.export.sheetNotFound.replace("{sheetName}", sheetName),
            "error",
          )
          setExportState(prev => ({ ...prev, isExporting: false }))
          return
        }
      }
      showToast(t.common.exportError, "error")
      setExportState(prev => ({ ...prev, isExporting: false }))
    }
  }

  const runManualImport = async (): Promise<ManualImportResult | null> => {
    try {
      const response = await importFetch()

      if (response.code === "COMPLETED") {
        let gotData = false
        if (
          (
            response?.data?.positions ||
            response?.data?.transactions?.account ||
            response?.data?.transactions?.investment
          )?.length
        ) {
          gotData = true
          showToast(t.common.importSuccess, "success")
        }

        return { gotData, errors: response.errors }
      }

      let errorMessage = t.common.fetchError
      if (response.code.toString() !== "UNEXPECTED_ERROR") {
        errorMessage =
          t.errors[response.code as keyof typeof t.errors] ||
          t.common.fetchError
      }
      showToast(errorMessage, "error")
      return null
    } catch {
      showToast(t.common.importError, "error")
      return null
    }
  }

  const handleConfirmImport = async () => {
    setIsImporting(true)
    let result: ManualImportResult | null = null

    try {
      result = await runManualImport()
    } finally {
      setIsImporting(false)
      setShowImportConfirm(false)
    }

    if (result) {
      const { gotData, errors } = result
      if (errors && errors.length > 0) {
        setImportErrors(errors)
        setShowErrorDetails(true)
      } else {
        setImportErrors(null)
      }

      if (gotData) {
        setImportSuccessAnimation(true)
        try {
          await Promise.all([fetchEntities(), refreshData()])
        } finally {
          setTimeout(() => {
            setImportSuccessAnimation(false)
          }, 2000)
        }
      }
    }
  }

  const handleOpenImport = () => {
    setImportErrors(null)
    setShowErrorDetails(false)
    setImportSuccessAnimation(false)
    setShowImportConfirm(true)
  }

  const handleCancelImport = () => {
    setShowImportConfirm(false)
  }

  const handleCloseErrorDetails = () => {
    setShowErrorDetails(false)
    setImportErrors(null)
  }

  const sectionSupportsData = (section: ExportSectionKey) =>
    section === "position" ||
    section === "transactions" ||
    section === "historic"

  const sectionSupportsFilters = (section: ExportSectionKey) =>
    section === "historic" ||
    section === "position" ||
    section === "contributions" ||
    section === "transactions"

  const getExportDataOptions = (section: ExportSectionKey) => {
    if (section === "position") {
      return positionOptions
    }
    if (section === "transactions") {
      return transactionProductOptions
    }
    if (section === "historic") {
      return historicProductOptions
    }
    return []
  }

  const importPositionOptions = useMemo<MultiSelectOption[]>(
    () =>
      buildProductOptions(AVAILABLE_IMPORT_POSITION_OPTIONS, productTypeLabels),
    [productTypeLabels],
  )

  const importTransactionProductOptions = useMemo<MultiSelectOption[]>(
    () =>
      buildProductOptions(
        AVAILABLE_IMPORT_TRANSACTION_PRODUCTS,
        productTypeLabels,
      ),
    [productTypeLabels],
  )

  const getImportDataOptions = (section: ImportSectionKey) => {
    if (section === "position") {
      return importPositionOptions
    }
    if (section === "transactions") {
      return importTransactionProductOptions
    }
    return []
  }

  const updateTemplatesState = useCallback(
    (type: TemplateType, updater: (list: Template[]) => Template[]) => {
      setTemplatesByType(prev => {
        const current = prev[type] ?? []
        return {
          ...prev,
          [type]: sortTemplatesByName(updater(current)),
        }
      })
      setTemplatesLoaded(prev => ({ ...prev, [type]: true }))
    },
    [],
  )

  const loadTemplates = useCallback(
    async (type: TemplateType, options?: { force?: boolean }) => {
      if (templatesLoading[type]) {
        return
      }
      if (!options?.force && templatesLoaded[type]) {
        return
      }
      setTemplatesLoading(prev => ({ ...prev, [type]: true }))
      try {
        const data = await getTemplates(type)
        setTemplatesByType(prev => ({
          ...prev,
          [type]: sortTemplatesByName(data),
        }))
        setTemplatesLoaded(prev => ({ ...prev, [type]: true }))
      } catch (error) {
        console.error("Failed to load templates", error)
        showToast(t.export.templates.toast.loadError, "error")
      } finally {
        setTemplatesLoading(prev => ({ ...prev, [type]: false }))
      }
    },
    [
      templatesLoading,
      templatesLoaded,
      showToast,
      t.export.templates.toast.loadError,
    ],
  )

  const fetchTemplateFields = useCallback(
    async (force = false) => {
      if (templateFields && !force) {
        return
      }
      if (isLoadingTemplateFields) {
        return
      }
      setIsLoadingTemplateFields(true)
      try {
        const fields = await getTemplateFields()
        setTemplateFields(
          fields as Partial<Record<Feature, TemplateFeatureDefinition[]>>,
        )
      } catch (error) {
        console.error("Failed to load template fields", error)
        showToast(t.export.templates.toast.fieldsError, "error")
      } finally {
        setIsLoadingTemplateFields(false)
      }
    },
    [
      templateFields,
      isLoadingTemplateFields,
      showToast,
      t.export.templates.toast.fieldsError,
    ],
  )

  const handleCreateTemplate = useCallback(
    async (payload: TemplateCreatePayload) => {
      try {
        const created = await createTemplate(payload)
        if (created) {
          updateTemplatesState(payload.type, list => [...list, created])
        } else {
          await loadTemplates(payload.type, { force: true })
        }
        showToast(t.export.templates.toast.createSuccess, "success")
      } catch (error) {
        console.error("Failed to create template", error)
        showToast(t.export.templates.toast.saveError, "error")
        throw error
      }
    },
    [
      updateTemplatesState,
      loadTemplates,
      showToast,
      t.export.templates.toast.createSuccess,
      t.export.templates.toast.saveError,
    ],
  )

  const handleUpdateTemplate = useCallback(
    async (payload: TemplateUpdatePayload) => {
      try {
        const updated = await updateTemplateRequest(payload)
        if (updated) {
          updateTemplatesState(payload.type, list =>
            list.map(template =>
              template.id === updated.id ? updated : template,
            ),
          )
        } else {
          await loadTemplates(payload.type, { force: true })
        }
        showToast(t.export.templates.toast.updateSuccess, "success")
      } catch (error) {
        console.error("Failed to update template", error)
        showToast(t.export.templates.toast.saveError, "error")
        throw error
      }
    },
    [
      updateTemplatesState,
      loadTemplates,
      showToast,
      t.export.templates.toast.updateSuccess,
      t.export.templates.toast.saveError,
    ],
  )

  const handleDeleteTemplate = useCallback(
    async (id: string) => {
      try {
        await deleteTemplateRequest(id)
        updateTemplatesState(templateDialogType, list =>
          list.filter(template => template.id !== id),
        )
        showToast(t.export.templates.toast.deleteSuccess, "success")
      } catch (error) {
        console.error("Failed to delete template", error)
        showToast(t.export.templates.toast.deleteError, "error")
        throw error
      }
    },
    [
      templateDialogType,
      updateTemplatesState,
      showToast,
      t.export.templates.toast.deleteSuccess,
      t.export.templates.toast.deleteError,
    ],
  )

  const handleOpenTemplatesDialog = (type: TemplateType) => {
    setTemplateDialogType(type)
    setIsTemplateDialogOpen(true)
    if (!templatesLoaded[type]) {
      loadTemplates(type)
    }
    fetchTemplateFields()
  }

  const handleCloseTemplatesDialog = () => {
    setIsTemplateDialogOpen(false)
  }

  const initialTemplateFetchRef = useRef<Record<TemplateType, boolean>>({
    [TemplateType.EXPORT]: false,
    [TemplateType.IMPORT]: false,
  })

  useEffect(() => {
    if (initialTemplateFetchRef.current[TemplateType.EXPORT]) {
      return
    }
    initialTemplateFetchRef.current[TemplateType.EXPORT] = true
    loadTemplates(TemplateType.EXPORT)
  }, [loadTemplates])

  useEffect(() => {
    if (activeTab !== "import") {
      return
    }
    if (initialTemplateFetchRef.current[TemplateType.IMPORT]) {
      return
    }
    initialTemplateFetchRef.current[TemplateType.IMPORT] = true
    loadTemplates(TemplateType.IMPORT)
  }, [activeTab, loadTemplates])

  const renderTemplatesCard = (type: TemplateType) => {
    const templateTexts = t.export.templates
    const templates = templatesByType[type] ?? []
    const isLoading = templatesLoading[type]
    const cardTitle = templateTexts.cardTitle[type]
    const cardDescription = templateTexts.cardDescription[type]
    const countLabel =
      templates.length === 0
        ? templateTexts.cardNotConfigured
        : templateTexts.cardCountLabel.replace(
            "{count}",
            String(templates.length),
          )

    return (
      <Card key={`templates-${type}`}>
        <CardHeader className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <LayoutTemplate className="h-5 w-5 text-primary" />
              <CardTitle>{cardTitle}</CardTitle>
            </div>
            <Badge variant="outline">
              {isLoading ? (
                <span className="flex items-center gap-1 text-xs">
                  <LoadingSpinner className="h-4 w-4" />
                  {t.common.loading}
                </span>
              ) : (
                countLabel
              )}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>{cardDescription}</p>
            <Button
              className="w-full sm:w-auto"
              onClick={() => handleOpenTemplatesDialog(type)}
            >
              <LayoutTemplate className="mr-2 h-4 w-4" />
              {templateTexts.manageButton}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  const renderExportSection = (section: ExportSectionKey) => {
    if (!exportConfigDraft) {
      return null
    }

    const configRecord = exportConfigDraft as Record<string, any>
    const items = Array.isArray(configRecord[section])
      ? (configRecord[section] as any[])
      : []
    const sectionLabel = (t.settings as Record<string, any>)[section] as string
    const isExpanded = expandedExportSections[section] ?? false
    const sectionErrors = exportValidationErrors[section] ?? []
    const addLabel = sectionLabel
      ? `${t.common.add} ${sectionLabel}`
      : t.common.add
    const templateFeature = SECTION_FEATURE_MAP[section]
    const exportTemplateOptions = (templatesByType[TemplateType.EXPORT] ?? [])
      .filter(template => template.feature === templateFeature && template.id)
      .map(template => ({
        value: String(template.id),
        label: template.name,
      }))
    const hasExportTemplates = exportTemplateOptions.length > 0
    const templateOptions = [
      ...exportTemplateOptions,
      {
        value: CREATE_IMPORT_TEMPLATE_OPTION,
        label: t.export.templates.templateCreateOption,
        icon: PlusCircle,
      },
    ]

    return (
      <div
        key={section}
        className="overflow-hidden rounded-lg border border-border/60 bg-card/80"
      >
        <button
          type="button"
          onClick={() => toggleExportSection(section)}
          className="flex w-full items-center justify-between bg-muted/50 px-3 py-3 text-left text-sm font-semibold capitalize transition-colors hover:bg-muted sm:px-4"
        >
          <div className="flex items-center gap-2">
            <span>{sectionLabel}</span>
            <Badge variant="secondary">{items.length}</Badge>
          </div>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {isExpanded ? (
          <div className="space-y-3 border-t border-border/60 px-2.5 py-3 sm:px-4 sm:py-4">
            {items.length === 0 ? (
              <div className="rounded-md border border-dashed border-border/60 bg-muted/10 px-3 py-3 text-sm text-muted-foreground">
                {t.settings.noItems}
              </div>
            ) : (
              items.map((item, index) => {
                const sectionError = sectionErrors[index]?.trim()
                const rangeError = sectionError
                  ? sectionError.includes(
                      t.settings.errors.rangeRequired.trim(),
                    )
                  : false
                const dataError = sectionError
                  ? sectionError.includes(t.settings.errors.dataRequired.trim())
                  : false
                const filters = Array.isArray(item?.filters)
                  ? (item.filters as Record<string, any>[])
                  : []
                const itemKey = `${section}-${index}`
                const extraKey = `${itemKey}-extra`
                const extraExpanded =
                  exportExtraSettingsExpanded[extraKey] ?? false
                const showDatetimeInput = section !== "contributions"
                const filtersCount = filters.length

                const selectedTemplateId = extractTemplateId(item?.template)
                const templateSelector = (
                  <div className="flex-1 space-y-1.5 sm:space-y-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor={`${itemKey}-template`} className="mb-0">
                        {t.export.templates.templateSelectLabel}
                      </Label>
                      <Popover>
                        <PopoverTrigger asChild>
                          <button
                            className="inline-flex text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                            aria-label={t.export.templates.templateSelectInfo}
                          >
                            <Info className="h-3.5 w-3.5" />
                          </button>
                        </PopoverTrigger>
                        <PopoverContent side="right" className="w-64">
                          <p className="text-sm">
                            {t.export.templates.templateSelectInfo}
                          </p>
                        </PopoverContent>
                      </Popover>
                    </div>
                    <MultiSelect
                      options={templateOptions}
                      value={selectedTemplateId ? [selectedTemplateId] : []}
                      onChange={value => {
                        const nextValue = value[value.length - 1] ?? null
                        if (nextValue === CREATE_IMPORT_TEMPLATE_OPTION) {
                          handleOpenTemplatesDialog(TemplateType.EXPORT)
                          return
                        }
                        handleUpdateExportItem(
                          section,
                          index,
                          "template",
                          nextValue
                            ? { id: nextValue, params: null }
                            : undefined,
                        )
                      }}
                      placeholder={t.export.templates.templateSelectPlaceholder}
                    />
                    {!hasExportTemplates ? (
                      <p className="text-xs text-muted-foreground">
                        {t.export.templates.templateSelectNoOptions}
                      </p>
                    ) : null}
                  </div>
                )

                return (
                  <div
                    key={itemKey}
                    className="space-y-3 rounded-lg border border-border/50 bg-background/90 p-2.5 shadow-sm sm:space-y-4 sm:p-4"
                  >
                    <div className="space-y-1.5 sm:space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <Label htmlFor={`${itemKey}-range`} className="flex-1">
                          {t.settings.range}
                          <span className="ml-1 text-red-500">*</span>
                        </Label>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveExportItem(section, index)}
                          aria-label={t.common.delete}
                          className="text-red-500 hover:text-red-600 focus-visible:ring-red-500 dark:hover:text-red-400"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span className="sr-only">{t.common.delete}</span>
                        </Button>
                      </div>
                      <Input
                        id={`${itemKey}-range`}
                        value={(item?.range as string) ?? ""}
                        onChange={event =>
                          handleUpdateExportItem(
                            section,
                            index,
                            "range",
                            event.target.value,
                          )
                        }
                        className={cn(
                          rangeError
                            ? "border-red-500 focus-visible:ring-red-500"
                            : undefined,
                        )}
                        placeholder={t.settings.rangePlaceholder}
                      />
                      {rangeError ? (
                        <p className="text-xs text-red-500">
                          {t.settings.errors.rangeRequired.trim()}
                        </p>
                      ) : null}
                    </div>

                    {sectionSupportsData(section) ? (
                      <div className="grid gap-2.5 sm:gap-3 md:grid-cols-2">
                        <div className="flex-1 space-y-1.5 sm:space-y-2">
                          <div className="flex items-center gap-2">
                            <Label htmlFor={`${itemKey}-data`} className="mb-0">
                              {t.settings.data}
                              <span className="ml-1 text-red-500">*</span>
                            </Label>
                            {/* hidden placeholder icon to keep vertical alignment with template label that has info icon */}
                            <span className="inline-flex h-3.5 w-3.5 opacity-0">
                              <Info className="h-3.5 w-3.5" />
                            </span>
                          </div>
                          <MultiSelect
                            options={getExportDataOptions(section)}
                            value={
                              Array.isArray(item?.data)
                                ? (item.data as string[])
                                : item?.data
                                  ? [item.data as string]
                                  : []
                            }
                            onChange={value =>
                              handleUpdateExportItem(
                                section,
                                index,
                                "data",
                                value,
                              )
                            }
                            placeholder={t.settings.selectDataTypes}
                            className={cn(
                              dataError
                                ? "[&>div:first-child]:border-red-500 [&>div:first-child]:ring-red-500/50"
                                : undefined,
                            )}
                          />
                          {dataError ? (
                            <p className="text-xs text-red-500">
                              {t.settings.errors.dataRequired.trim()}
                            </p>
                          ) : null}
                        </div>
                        {templateSelector}
                      </div>
                    ) : (
                      templateSelector
                    )}

                    <div className="rounded-md border border-border/50 bg-muted/10">
                      <button
                        type="button"
                        onClick={() => toggleExportExtraSettings(extraKey)}
                        className="flex w-full items-center justify-between px-2.5 py-2 text-sm font-medium transition-colors hover:bg-muted/40 sm:px-4"
                      >
                        <span>{t.settings.extraSettings}</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-muted-foreground transition-transform",
                            extraExpanded ? "rotate-180" : undefined,
                          )}
                        />
                      </button>
                      {extraExpanded ? (
                        <div className="space-y-3 border-t border-border/50 px-2.5 py-2.5 sm:px-4 sm:py-4">
                          <div className="flex items-center justify-between space-x-2">
                            <Label
                              htmlFor={`${itemKey}-last-update`}
                              className="flex flex-col space-y-1"
                            >
                              <span>{t.settings.exportCurrentDate}</span>
                            </Label>
                            <Switch
                              id={`${itemKey}-last-update`}
                              checked={(item?.lastUpdate as boolean) ?? false}
                              onCheckedChange={checked =>
                                handleUpdateExportItem(
                                  section,
                                  index,
                                  "lastUpdate",
                                  checked,
                                )
                              }
                            />
                          </div>
                          <div className="space-y-1.5 sm:space-y-2">
                            <Label htmlFor={`${itemKey}-spreadsheet`}>
                              {t.export.spreadsheetId}
                            </Label>
                            <Input
                              id={`${itemKey}-spreadsheet`}
                              value={(item?.spreadsheetId as string) ?? ""}
                              onChange={event =>
                                handleUpdateExportItem(
                                  section,
                                  index,
                                  "spreadsheetId",
                                  event.target.value,
                                )
                              }
                              placeholder={t.settings.spreadsheetIdPlaceholder}
                            />
                          </div>
                          <div
                            className={cn(
                              "grid gap-2.5 sm:gap-3",
                              showDatetimeInput ? "md:grid-cols-2" : undefined,
                            )}
                          >
                            <div className="space-y-1.5 sm:space-y-2">
                              <Label htmlFor={`${itemKey}-date-format`}>
                                {t.settings.dateFormat}
                              </Label>
                              <Input
                                id={`${itemKey}-date-format`}
                                value={(item?.dateFormat as string) ?? ""}
                                onChange={event =>
                                  handleUpdateExportItem(
                                    section,
                                    index,
                                    "dateFormat",
                                    event.target.value,
                                  )
                                }
                                placeholder={t.settings.dateFormatPlaceholder}
                              />
                            </div>
                            {showDatetimeInput ? (
                              <div className="space-y-1.5 sm:space-y-2">
                                <Label htmlFor={`${itemKey}-datetime-format`}>
                                  {t.settings.datetimeFormat}
                                </Label>
                                <Input
                                  id={`${itemKey}-datetime-format`}
                                  value={(item?.datetimeFormat as string) ?? ""}
                                  onChange={event =>
                                    handleUpdateExportItem(
                                      section,
                                      index,
                                      "datetimeFormat",
                                      event.target.value,
                                    )
                                  }
                                  placeholder={
                                    t.settings.datetimeFormatPlaceholder
                                  }
                                />
                              </div>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </div>

                    {sectionSupportsFilters(section) ? (
                      <div className="space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-medium">
                            {t.settings.filters}
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({filtersCount})
                            </span>
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              handleAddExportFilter(section, index)
                            }
                          >
                            <PlusCircle className="mr-2 h-4 w-4" />
                            {t.settings.addFilter}
                          </Button>
                        </div>
                        {filtersCount > 0 ? (
                          <div className="space-y-2">
                            {filters.map(
                              (
                                filter: Record<string, any>,
                                filterIndex: number,
                              ) => (
                                <div
                                  key={`${itemKey}-filter-${filterIndex}`}
                                  className="grid gap-2 rounded-md border border-border/50 bg-background/80 p-2.5 sm:p-3 md:grid-cols-[1fr_1fr_auto]"
                                >
                                  <div className="space-y-1.5 sm:space-y-2">
                                    <Label
                                      htmlFor={`${itemKey}-filter-${filterIndex}-field`}
                                    >
                                      {t.settings.field}
                                    </Label>
                                    <Input
                                      id={`${itemKey}-filter-${filterIndex}-field`}
                                      value={(filter?.field as string) ?? ""}
                                      onChange={event =>
                                        handleUpdateExportFilter(
                                          section,
                                          index,
                                          filterIndex,
                                          "field",
                                          event.target.value,
                                        )
                                      }
                                    />
                                  </div>
                                  <div className="space-y-1.5 sm:space-y-2">
                                    <Label
                                      htmlFor={`${itemKey}-filter-${filterIndex}-values`}
                                    >
                                      {t.settings.valuesPlaceholder}
                                    </Label>
                                    <Input
                                      id={`${itemKey}-filter-${filterIndex}-values`}
                                      value={(filter?.values as string) ?? ""}
                                      onChange={event =>
                                        handleUpdateExportFilter(
                                          section,
                                          index,
                                          filterIndex,
                                          "values",
                                          event.target.value,
                                        )
                                      }
                                      placeholder={t.settings.valuesPlaceholder}
                                    />
                                  </div>
                                  <div className="flex items-end justify-end">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() =>
                                        handleRemoveExportFilter(
                                          section,
                                          index,
                                          filterIndex,
                                        )
                                      }
                                      aria-label={t.common.delete}
                                      className="text-red-500 hover:text-red-600 focus-visible:ring-red-500 dark:hover:text-red-400"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </div>
                              ),
                            )}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                )
              })
            )}

            <div className="flex justify-start pt-1 sm:pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddExportItem(section)}
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                {addLabel}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  const renderExportConfigDialog = () => {
    if (!showExportConfig || !exportConfigDraft) {
      return null
    }

    const globalsError = exportValidationErrors.globals?.[0]
    const globals = (exportConfigDraft.globals ?? {}) as Record<string, any>

    return (
      <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-1 sm:p-3 lg:p-6">
        <Card className="flex max-h-[90vh] w-full max-w-5xl flex-col">
          <CardContent className="flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
            <div className="space-y-1 pb-1">
              <h2 className="text-lg font-semibold">
                {t.export.googleSheetsExportDialogTitle}
              </h2>
            </div>
            <div className="space-y-2.5 rounded-lg border border-border/60 bg-muted/20 p-3 sm:space-y-3 sm:p-5">
              <div>
                <h3 className="text-sm font-semibold">{t.settings.globals}</h3>
                <p className="text-xs text-muted-foreground">
                  {t.settings.sheetsDescription}
                </p>
              </div>
              <div className="grid gap-2.5 sm:gap-3 md:grid-cols-2">
                <div className="space-y-1.5 sm:space-y-2 md:col-span-2">
                  <Label htmlFor="export-spreadsheet-id">
                    {t.export.spreadsheetId}
                  </Label>
                  <Input
                    id="export-spreadsheet-id"
                    value={(globals.spreadsheetId as string) ?? ""}
                    onChange={event =>
                      handleExportGlobalChange(
                        "spreadsheetId",
                        event.target.value,
                      )
                    }
                    className={cn(
                      globalsError
                        ? "border-red-500 focus-visible:ring-red-500"
                        : undefined,
                    )}
                    placeholder={t.settings.spreadsheetIdPlaceholder}
                  />
                  {globalsError ? (
                    <p className="text-xs text-red-500">{globalsError}</p>
                  ) : null}
                </div>
                <div className="space-y-1.5 sm:space-y-2">
                  <Label htmlFor="export-date-format">
                    {t.settings.dateFormat}
                  </Label>
                  <Input
                    id="export-date-format"
                    value={(globals.dateFormat as string) ?? ""}
                    onChange={event =>
                      handleExportGlobalChange("dateFormat", event.target.value)
                    }
                    placeholder={t.settings.dateFormatPlaceholder}
                  />
                </div>
                <div className="space-y-1.5 sm:space-y-2">
                  <Label htmlFor="export-datetime-format">
                    {t.settings.datetimeFormat}
                  </Label>
                  <Input
                    id="export-datetime-format"
                    value={(globals.datetimeFormat as string) ?? ""}
                    onChange={event =>
                      handleExportGlobalChange(
                        "datetimeFormat",
                        event.target.value,
                      )
                    }
                    placeholder={t.settings.datetimeFormatPlaceholder}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {EXPORT_SECTIONS.map(section => renderExportSection(section))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCloseExportConfig}
              disabled={isSavingExportConfig}
              className="inline-flex items-center gap-2"
            >
              <X className="h-4 w-4" />
              {t.common.cancel}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRevertExportConfig}
              disabled={isSavingExportConfig || isRevertingExportConfig}
              aria-label={t.common.discard}
            >
              {isRevertingExportConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isRevertingExportConfig ? t.common.loading : t.common.discard}
              </span>
            </Button>
            <Button
              size="icon"
              onClick={handleSaveExportConfig}
              disabled={isSavingExportConfig}
              aria-label={t.common.save}
            >
              {isSavingExportConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <SaveIcon className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isSavingExportConfig ? t.settings.saving : t.common.save}
              </span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  const renderImportSection = (section: ImportSectionKey) => {
    if (!importConfigDraft) {
      return null
    }

    const configRecord = importConfigDraft as Record<string, any>
    const items = Array.isArray(configRecord[section])
      ? (configRecord[section] as any[])
      : []
    const sectionLabel = (t.settings as Record<string, any>)[section] as string
    const isExpanded = expandedImportSections[section] ?? false
    const sectionErrors = importValidationErrors[`import_${section}`] ?? []
    const addLabel = sectionLabel
      ? `${t.common.add} ${sectionLabel}`
      : t.common.add

    return (
      <div
        key={section}
        className="overflow-hidden rounded-lg border border-border/60 bg-card/80"
      >
        <button
          type="button"
          onClick={() => toggleImportSection(section)}
          className="flex w-full items-center justify-between bg-muted/50 px-3 py-3 text-left text-sm font-semibold capitalize transition-colors hover:bg-muted sm:px-4"
        >
          <div className="flex items-center gap-2">
            <span>{sectionLabel}</span>
            <Badge variant="secondary">{items.length}</Badge>
          </div>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        {isExpanded ? (
          <div className="space-y-3 border-t border-border/60 px-2.5 py-3 sm:px-4 sm:py-4">
            {items.length === 0 ? (
              <div className="rounded-md border border-dashed border-border/60 bg-muted/10 px-3 py-3 text-sm text-muted-foreground">
                {t.settings.noItems}
              </div>
            ) : (
              items.map((item, index) => {
                const sectionError = sectionErrors[index]?.trim()
                const rangeError = sectionError
                  ? sectionError.includes(
                      t.settings.errors.rangeRequired.trim(),
                    )
                  : false
                const dataError = sectionError
                  ? sectionError.includes(t.settings.errors.dataRequired.trim())
                  : false
                const itemKey = `${section}-import-${index}`
                const extraKey = `${itemKey}-extra`
                const extraExpanded =
                  importExtraSettingsExpanded[extraKey] ?? false
                const templateFeature =
                  SECTION_FEATURE_MAP[section as ExportSectionKey]
                const importTemplateOptions = (
                  templatesByType[TemplateType.IMPORT] ?? []
                )
                  .filter(
                    template =>
                      template.feature === templateFeature && template.id,
                  )
                  .map(template => ({
                    value: String(template.id),
                    label: template.name,
                  }))
                const hasImportTemplates = importTemplateOptions.length > 0
                const templateSelectOptions = [
                  ...importTemplateOptions,
                  {
                    value: CREATE_IMPORT_TEMPLATE_OPTION,
                    label: t.export.templates.templateCreateOption,
                    icon: PlusCircle,
                  },
                ]
                const selectedImportTemplateId = extractTemplateId(
                  item?.template,
                )
                const templateError =
                  sectionError?.includes(
                    t.export.templates.templateSelectRequired.trim(),
                  ) ?? false
                const entityError =
                  sectionError?.includes(
                    t.export.import.entityRequired.trim(),
                  ) ?? false

                const entityOptions = (entities ?? [])
                  .filter(
                    entity =>
                      entity.name &&
                      entity.id &&
                      entity.type === EntityType.FINANCIAL_INSTITUTION,
                  )
                  .map(entity => ({
                    value: entity.name,
                    label: entity.name,
                  }))
                const entityValue =
                  (
                    item?.template?.params?.entity as string | undefined
                  )?.trim() ?? ""
                const isKnownEntity = entityOptions.some(
                  option => option.value === entityValue,
                )
                const baseEntityMode =
                  ((item as Record<string, any>)?._entity_mode as string) ??
                  "select"
                const isCreatingEntity =
                  baseEntityMode === "new" || (!!entityValue && !isKnownEntity)
                const selectedEntity = isCreatingEntity ? "" : entityValue
                const customEntityValue = isCreatingEntity
                  ? ((item._new_entity_name as string) ??
                    (!isKnownEntity ? entityValue : ""))
                  : ""
                const showEntitySelector = !!selectedImportTemplateId

                const templateSelector = (
                  <div className="space-y-1.5 sm:space-y-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor={`${itemKey}-template`} className="mb-0">
                        {t.export.templates.templateSelectLabel}
                        <span className="ml-1 text-red-500">*</span>
                      </Label>
                      <Popover>
                        <PopoverTrigger asChild>
                          <button
                            className="inline-flex rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            aria-label={t.export.templates.templateSelectInfo}
                          >
                            <Info className="h-3.5 w-3.5" />
                          </button>
                        </PopoverTrigger>
                        <PopoverContent side="right" className="w-64">
                          <p className="text-sm">
                            {t.export.templates.templateSelectInfo}
                          </p>
                        </PopoverContent>
                      </Popover>
                    </div>
                    <MultiSelect
                      options={templateSelectOptions}
                      value={
                        selectedImportTemplateId
                          ? [selectedImportTemplateId]
                          : []
                      }
                      onChange={value => {
                        const nextValue = value[value.length - 1] ?? null
                        if (nextValue === CREATE_IMPORT_TEMPLATE_OPTION) {
                          handleOpenTemplatesDialog(TemplateType.IMPORT)
                          return
                        }
                        handleUpdateImportItem(
                          section,
                          index,
                          "template",
                          nextValue ? { id: nextValue, params: {} } : undefined,
                        )
                      }}
                      placeholder={t.export.templates.templateSelectPlaceholder}
                      className={cn(
                        templateError
                          ? "[&>div:first-child]:border-red-500 [&>div:first-child]:ring-red-500/50"
                          : undefined,
                      )}
                    />
                    {templateError ? (
                      <p className="text-xs text-red-500">
                        {t.export.templates.templateSelectRequired}
                      </p>
                    ) : !hasImportTemplates ? (
                      <p className="text-xs text-muted-foreground">
                        {t.export.templates.templateSelectNoOptions}
                      </p>
                    ) : null}
                  </div>
                )

                return (
                  <div
                    key={itemKey}
                    className="space-y-3 rounded-lg border border-border/50 bg-background/90 p-2.5 shadow-sm sm:space-y-4 sm:p-4"
                  >
                    <div className="space-y-1.5 sm:space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <Label htmlFor={`${itemKey}-range`} className="flex-1">
                          {t.settings.range}
                          <span className="ml-1 text-red-500">*</span>
                        </Label>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveImportItem(section, index)}
                          aria-label={t.common.delete}
                          className="text-red-500 hover:text-red-600 focus-visible:ring-red-500 dark:hover:text-red-400"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span className="sr-only">{t.common.delete}</span>
                        </Button>
                      </div>
                      <Input
                        id={`${itemKey}-range`}
                        value={(item?.range as string) ?? ""}
                        onChange={event =>
                          handleUpdateImportItem(
                            section,
                            index,
                            "range",
                            event.target.value,
                          )
                        }
                        className={cn(
                          rangeError
                            ? "border-red-500 focus-visible:ring-red-500"
                            : undefined,
                        )}
                        placeholder={t.settings.rangePlaceholder}
                      />
                      {rangeError ? (
                        <p className="text-xs text-red-500">
                          {t.settings.errors.rangeRequired.trim()}
                        </p>
                      ) : null}
                    </div>

                    {section === "position" || section === "transactions" ? (
                      <div className="grid gap-2.5 sm:gap-3 md:grid-cols-2">
                        <div className="flex-1 space-y-1.5 sm:space-y-2">
                          <div className="flex items-center gap-2">
                            <Label htmlFor={`${itemKey}-data`} className="mb-0">
                              {t.settings.data}
                              <span className="ml-1 text-red-500">*</span>
                            </Label>
                            <span className="inline-flex h-3.5 w-3.5 opacity-0">
                              <Info className="h-3.5 w-3.5" />
                            </span>
                          </div>
                          <MultiSelect
                            options={getImportDataOptions(section)}
                            value={item?.data ? [item.data as string] : []}
                            onChange={value => {
                              if (value.length === 0) {
                                handleUpdateImportItem(
                                  section,
                                  index,
                                  "data",
                                  null,
                                )
                              } else {
                                const currentValue = item?.data
                                const newValue = value[value.length - 1]
                                if (newValue !== currentValue) {
                                  handleUpdateImportItem(
                                    section,
                                    index,
                                    "data",
                                    newValue,
                                  )
                                }
                              }
                            }}
                            placeholder={t.settings.selectDataTypes}
                            className={cn(
                              dataError
                                ? "[&>div:first-child]:border-red-500 [&>div:first-child]:ring-red-500/50"
                                : undefined,
                            )}
                          />
                          {dataError ? (
                            <p className="text-xs text-red-500">
                              {t.settings.errors.dataRequired.trim()}
                            </p>
                          ) : null}
                        </div>
                        {templateSelector}
                      </div>
                    ) : null}

                    {showEntitySelector &&
                    (section === "position" || section === "transactions") ? (
                      <div className="space-y-1.5 sm:space-y-2">
                        <div className="flex items-center gap-2">
                          <Label htmlFor={`${itemKey}-entity`} className="mb-0">
                            {t.export.import.entityLabel}
                          </Label>
                          <Popover>
                            <PopoverTrigger asChild>
                              <button
                                className="inline-flex rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                aria-label={t.export.import.entityInfo}
                              >
                                <Info className="h-3.5 w-3.5" />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent side="right" className="w-64">
                              <p className="text-sm">
                                {t.export.import.entityInfo}
                              </p>
                            </PopoverContent>
                          </Popover>
                        </div>
                        <div className="flex items-stretch gap-2">
                          <div className="flex-1">
                            {isCreatingEntity ? (
                              <Input
                                id={`${itemKey}-entity-input`}
                                value={customEntityValue}
                                placeholder={t.export.import.entityPlaceholder}
                                onChange={e => {
                                  handleUpdateImportItem(
                                    section,
                                    index,
                                    "_new_entity_name",
                                    e.target.value,
                                  )
                                }}
                                className={cn(
                                  entityError
                                    ? "border-red-500 focus-visible:ring-red-500"
                                    : undefined,
                                )}
                              />
                            ) : (
                              <select
                                id={`${itemKey}-entity-select`}
                                className={cn(
                                  "w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                  entityError
                                    ? "border-red-500 ring-red-500/50"
                                    : undefined,
                                )}
                                value={selectedEntity}
                                onChange={e => {
                                  const normalized =
                                    normalizeImportTemplateValue(item.template)
                                  if (!normalized?.id) {
                                    return
                                  }
                                  const nextParams = {
                                    ...(normalized.params ?? {}),
                                  }
                                  if (e.target.value) {
                                    nextParams.entity = e.target.value
                                  } else {
                                    delete nextParams.entity
                                  }
                                  const sanitizedParams =
                                    Object.keys(nextParams).length > 0
                                      ? nextParams
                                      : null

                                  handleUpdateImportItem(
                                    section,
                                    index,
                                    "template",
                                    {
                                      id: normalized.id,
                                      params: sanitizedParams,
                                    },
                                  )
                                }}
                              >
                                <option value="">
                                  {t.export.import.entityPlaceholder}
                                </option>
                                {entityOptions.map(option => (
                                  <option
                                    key={option.value}
                                    value={option.value}
                                  >
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            onClick={() => {
                              const newMode = isCreatingEntity
                                ? "select"
                                : "new"
                              handleUpdateImportItem(
                                section,
                                index,
                                "_entity_mode",
                                newMode,
                              )
                              if (newMode === "select") {
                                handleUpdateImportItem(
                                  section,
                                  index,
                                  "_new_entity_name",
                                  "",
                                )
                              } else {
                                // Clear entity from template.params
                                const currentTemplate = item.template
                                if (
                                  currentTemplate &&
                                  typeof currentTemplate === "object"
                                ) {
                                  const normalized =
                                    normalizeImportTemplateValue(
                                      currentTemplate,
                                    )
                                  if (normalized?.id) {
                                    const nextParams = {
                                      ...(normalized.params ?? {}),
                                    }
                                    delete nextParams.entity
                                    const sanitizedParams =
                                      Object.keys(nextParams).length > 0
                                        ? nextParams
                                        : null
                                    handleUpdateImportItem(
                                      section,
                                      index,
                                      "template",
                                      {
                                        id: normalized.id,
                                        params: sanitizedParams,
                                      },
                                    )
                                  }
                                }
                              }
                            }}
                            className="h-10 w-10 shrink-0"
                            title={
                              isCreatingEntity
                                ? t.common.cancel
                                : t.export.import.entityCreateOption
                            }
                          >
                            {isCreatingEntity ? (
                              <X className="h-4 w-4" />
                            ) : (
                              <Plus className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        {entityError ? (
                          <p className="text-xs text-red-500">
                            {t.export.import.entityRequired}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="rounded-md border border-border/50 bg-muted/10">
                      <button
                        type="button"
                        onClick={() => toggleImportExtraSettings(extraKey)}
                        className="flex w-full items-center justify-between px-2.5 py-2 text-sm font-medium transition-colors hover:bg-muted/40 sm:px-4"
                      >
                        <span>{t.settings.extraSettings}</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-muted-foreground transition-transform",
                            extraExpanded ? "rotate-180" : undefined,
                          )}
                        />
                      </button>
                      {extraExpanded ? (
                        <div className="space-y-3 border-t border-border/50 px-2.5 py-2.5 sm:px-4 sm:py-4">
                          <div className="space-y-1.5 sm:space-y-2">
                            <Label htmlFor={`${itemKey}-spreadsheet`}>
                              {t.export.spreadsheetId}
                            </Label>
                            <Input
                              id={`${itemKey}-spreadsheet`}
                              value={(item?.spreadsheetId as string) ?? ""}
                              onChange={event =>
                                handleUpdateImportItem(
                                  section,
                                  index,
                                  "spreadsheetId",
                                  event.target.value,
                                )
                              }
                              placeholder={t.settings.spreadsheetIdPlaceholder}
                            />
                          </div>
                          <div className="grid gap-2.5 sm:gap-3 md:grid-cols-2">
                            <div className="space-y-1.5 sm:space-y-2">
                              <Label htmlFor={`${itemKey}-date-format`}>
                                {t.settings.dateFormat}
                              </Label>
                              <Input
                                id={`${itemKey}-date-format`}
                                value={(item?.dateFormat as string) ?? ""}
                                onChange={event =>
                                  handleUpdateImportItem(
                                    section,
                                    index,
                                    "dateFormat",
                                    event.target.value,
                                  )
                                }
                                placeholder={t.settings.dateFormatPlaceholder}
                              />
                            </div>
                            <div className="space-y-1.5 sm:space-y-2">
                              <Label htmlFor={`${itemKey}-datetime-format`}>
                                {t.settings.datetimeFormat}
                              </Label>
                              <Input
                                id={`${itemKey}-datetime-format`}
                                value={(item?.datetimeFormat as string) ?? ""}
                                onChange={event =>
                                  handleUpdateImportItem(
                                    section,
                                    index,
                                    "datetimeFormat",
                                    event.target.value,
                                  )
                                }
                                placeholder={
                                  t.settings.datetimeFormatPlaceholder
                                }
                              />
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                )
              })
            )}

            <div className="flex justify-start pt-1 sm:pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddImportItem(section)}
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                {addLabel}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  const renderImportDialog = () => {
    if (!showImportConfig || !importConfigDraft) {
      return null
    }

    const globalsError = importValidationErrors.importGlobals?.[0]
    const globals = (importConfigDraft.globals ?? {}) as Record<string, any>

    return (
      <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-1 sm:p-3 lg:p-6">
        <Card className="flex max-h-[90vh] w-full max-w-4xl flex-col">
          <CardContent className="flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
            <div className="space-y-1 pb-1">
              <h2 className="text-lg font-semibold">
                {t.export.googleSheetsImportDialogTitle}
              </h2>
            </div>
            <div className="space-y-2.5 rounded-lg border border-border/60 bg-muted/20 p-3 sm:space-y-3 sm:p-5">
              <div>
                <h3 className="text-sm font-semibold">{t.settings.globals}</h3>
                <p className="text-xs text-muted-foreground">
                  {t.export.importDescription}
                </p>
              </div>
              <div className="grid gap-2.5 sm:gap-3 md:grid-cols-2">
                <div className="space-y-1.5 sm:space-y-2 md:col-span-2">
                  <Label htmlFor="import-spreadsheet-id">
                    {t.export.spreadsheetId}
                  </Label>
                  <Input
                    id="import-spreadsheet-id"
                    value={(globals.spreadsheetId as string) ?? ""}
                    onChange={event =>
                      handleImportGlobalChange(
                        "spreadsheetId",
                        event.target.value,
                      )
                    }
                    className={cn(
                      globalsError
                        ? "border-red-500 focus-visible:ring-red-500"
                        : undefined,
                    )}
                    placeholder={t.settings.spreadsheetIdPlaceholder}
                  />
                  {globalsError ? (
                    <p className="text-xs text-red-500">{globalsError}</p>
                  ) : null}
                </div>
                <div className="space-y-1.5 sm:space-y-2">
                  <Label htmlFor="import-date-format">
                    {t.settings.dateFormat}
                  </Label>
                  <Input
                    id="import-date-format"
                    value={(globals.dateFormat as string) ?? ""}
                    onChange={event =>
                      handleImportGlobalChange("dateFormat", event.target.value)
                    }
                    placeholder={t.settings.dateFormatPlaceholder}
                  />
                </div>
                <div className="space-y-1.5 sm:space-y-2">
                  <Label htmlFor="import-datetime-format">
                    {t.settings.datetimeFormat}
                  </Label>
                  <Input
                    id="import-datetime-format"
                    value={(globals.datetimeFormat as string) ?? ""}
                    onChange={event =>
                      handleImportGlobalChange(
                        "datetimeFormat",
                        event.target.value,
                      )
                    }
                    placeholder={t.settings.datetimeFormatPlaceholder}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {IMPORT_SECTIONS.map(section => renderImportSection(section))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCloseImportConfig}
              disabled={isSavingImportConfig}
              className="inline-flex items-center gap-2"
            >
              <X className="h-4 w-4" />
              {t.common.cancel}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRevertImportConfig}
              disabled={isSavingImportConfig || isRevertingImportConfig}
              aria-label={t.common.discard}
            >
              {isRevertingImportConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isRevertingImportConfig ? t.common.loading : t.common.discard}
              </span>
            </Button>
            <Button
              size="icon"
              onClick={handleSaveImportConfig}
              disabled={isSavingImportConfig}
              aria-label={t.common.save}
            >
              {isSavingImportConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <SaveIcon className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isSavingImportConfig ? t.settings.saving : t.common.save}
              </span>
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  return (
    <motion.div
      className="space-y-8"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <Tabs
        value={activeTab}
        onValueChange={value => setActiveTab(value as "export" | "import")}
        className="space-y-6"
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <h1 className="text-3xl font-bold">{t.export.title}</h1>
          <TabsList className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-muted/40 p-1 backdrop-blur self-center shadow-sm md:ml-auto md:self-auto">
            <TabsTrigger
              value="export"
              className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-black data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:bg-white dark:data-[state=active]:text-black"
            >
              <FileUp className="mr-2 h-4 w-4" />
              {t.export.tabs.export}
            </TabsTrigger>
            <TabsTrigger
              value="import"
              className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-black data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:bg-white dark:data-[state=active]:text-black"
            >
              <Download className="mr-2 h-4 w-4" />
              {t.export.tabs.import}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="export" className="space-y-6">
          {renderTemplatesCard(TemplateType.EXPORT)}

          <Card>
            <CardHeader className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <FileSpreadsheet className="mr-2 h-5 w-5 text-green-600" />
                  <CardTitle>{t.export.googleSheetsTitle}</CardTitle>
                </div>
                {isGoogleSheetsIntegrationEnabled ? (
                  <Badge
                    className={cn(
                      sheetsConfigured
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                        : "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
                    )}
                  >
                    {sheetsConfigured
                      ? t.export.badges.configured
                      : t.export.badges.notConfigured}
                  </Badge>
                ) : (
                  <IntegrationRequiredBadge />
                )}
              </div>
            </CardHeader>
            {isGoogleSheetsIntegrationEnabled ? (
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 gap-3">
                  <div className="rounded-lg border p-3">
                    <div className="text-sm font-medium mb-2">
                      {t.export.configuredSections}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {hasSheetSections ? (
                        Object.entries(sectionCounts)
                          .filter(([, count]) => count > 0)
                          .map(([section, count]) => (
                            <Badge
                              key={section}
                              variant="secondary"
                              className="capitalize"
                            >
                              {t.settings[section as keyof typeof t.settings] ||
                                section}{" "}
                              ({count})
                            </Badge>
                          ))
                      ) : (
                        <Badge variant="secondary">
                          {t.export.noSectionsConfigured}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:items-center">
                  <Button
                    onClick={handleExport}
                    disabled={isExportDisabled}
                    className={cn(
                      "relative w-full sm:w-auto",
                      exportState.isExporting && "opacity-100",
                    )}
                  >
                    {exportState.isExporting && (
                      <LoadingSpinner className="mr-2 h-5 w-5" />
                    )}
                    {successAnimation ? (
                      <motion.div
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="flex items-center"
                      >
                        <Check className="mr-2 h-4 w-4" />
                        {t.common.exportSuccess}
                      </motion.div>
                    ) : (
                      <>
                        <FileUp className="mr-2 h-4 w-4" />
                        {t.common.export}
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={handleOpenExportConfig}
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    {t.common.configure}
                  </Button>
                </div>
              </CardContent>
            ) : (
              <CardContent className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t.export.integrationRequiredMessage}
                </p>
              </CardContent>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="import" className="space-y-6">
          {renderTemplatesCard(TemplateType.IMPORT)}

          <Card>
            <CardHeader className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <FileSpreadsheet className="mr-2 h-5 w-5 text-green-600" />
                  <CardTitle>{t.export.googleSheetsTitle}</CardTitle>
                </div>
                {isGoogleSheetsIntegrationEnabled ? (
                  <Badge
                    className={cn(
                      importConfigured
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                        : "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
                    )}
                  >
                    {importConfigured
                      ? t.export.badges.configured
                      : t.export.badges.notConfigured}
                  </Badge>
                ) : (
                  <IntegrationRequiredBadge />
                )}
              </div>
            </CardHeader>
            {isGoogleSheetsIntegrationEnabled ? (
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 gap-3">
                  <div className="rounded-lg border p-3">
                    <div className="text-sm font-medium mb-2">
                      {t.export.configuredSections}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {hasImportSections ? (
                        Object.entries(importSectionCounts)
                          .filter(([, count]) => count > 0)
                          .map(([section, count]) => (
                            <Badge
                              key={section}
                              variant="secondary"
                              className="capitalize"
                            >
                              {t.settings[section as keyof typeof t.settings] ||
                                section}{" "}
                              ({count})
                            </Badge>
                          ))
                      ) : (
                        <Badge variant="secondary">
                          {t.export.noSectionsConfigured}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-2 pt-2">
                  <Button
                    onClick={handleOpenImport}
                    disabled={isImportDisabled}
                    className="w-full sm:w-auto"
                  >
                    {isImporting ? (
                      <LoadingSpinner className="h-5 w-5 mr-2" />
                    ) : importSuccessAnimation ? (
                      <motion.div
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="flex items-center"
                      >
                        <Check className="mr-2 h-4 w-4" />
                        {t.common.importSuccess}
                      </motion.div>
                    ) : (
                      <>
                        <Download className="mr-2 h-4 w-4" />
                        {t.export.importButton}
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={handleOpenImportConfig}
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    {t.common.configure}
                  </Button>
                </div>
              </CardContent>
            ) : (
              <CardContent className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t.export.integrationRequiredMessage}
                </p>
              </CardContent>
            )}
          </Card>
        </TabsContent>
      </Tabs>

      {renderExportConfigDialog()}
      {renderImportDialog()}

      <TemplateManagerDialog
        isOpen={isTemplateDialogOpen}
        onClose={handleCloseTemplatesDialog}
        templates={templatesByType[templateDialogType] ?? []}
        templateType={templateDialogType}
        templateFields={templateFields}
        isLoadingTemplates={templatesLoading[templateDialogType]}
        isLoadingFields={isLoadingTemplateFields}
        onCreate={handleCreateTemplate}
        onUpdate={handleUpdateTemplate}
        onDelete={handleDeleteTemplate}
        featureLabels={featureLabels}
        productLabels={productTypeLabels}
        t={t}
      />

      <ConfirmationDialog
        isOpen={showImportConfirm}
        title={t.entities.confirmUserEntered}
        message={t.entities.confirmUserEnteredDescription}
        confirmText={t.common.confirm}
        cancelText={t.common.cancel}
        onConfirm={handleConfirmImport}
        onCancel={handleCancelImport}
        isLoading={isImporting}
      />

      <ErrorDetailsDialog
        isOpen={showErrorDetails}
        errors={importErrors || []}
        onClose={handleCloseErrorDetails}
      />
    </motion.div>
  )
}
