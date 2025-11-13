import { useEffect, useMemo, useState } from "react"
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
  PlusCircle,
  RotateCcw,
  Save as SaveIcon,
  Settings,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext, type AppSettings } from "@/context/AppContext"
import { updateSheets, virtualFetch } from "@/services/api"
import {
  ExportTarget,
  ExternalIntegrationStatus,
  type ImportError,
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

const EXPORT_SECTIONS = [
  "position",
  "contributions",
  "transactions",
  "historic",
] as const

type ExportSectionKey = (typeof EXPORT_SECTIONS)[number]

const VIRTUAL_SECTIONS = ["position", "transactions"] as const

type VirtualSectionKey = (typeof VIRTUAL_SECTIONS)[number]

type SheetsConfigDraft = NonNullable<
  NonNullable<AppSettings["export"]>["sheets"]
>

type VirtualConfigDraft = NonNullable<
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
  ProductType.CROWDLENDING,
  ProductType.COMMODITY,
] as const

interface ManualImportResult {
  gotData: boolean
  errors?: ImportError[]
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
    externalIntegrations,
    saveSettings,
    fetchSettings,
  } = useAppContext()
  const [activeTab, setActiveTab] = useState<"export" | "import">("export")
  const [successAnimation, setSuccessAnimation] = useState(false)
  const [excludeNonReal, setExcludeNonReal] = useState(false)
  const [showImportConfirm, setShowImportConfirm] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [importSuccessAnimation, setImportSuccessAnimation] = useState(false)
  const [importErrors, setImportErrors] = useState<ImportError[] | null>(null)
  const [showErrorDetails, setShowErrorDetails] = useState(false)
  const [showExportConfig, setShowExportConfig] = useState(false)
  const [showImportConfig, setShowImportConfig] = useState(false)
  const [exportConfigDraft, setExportConfigDraft] =
    useState<SheetsConfigDraft | null>(null)
  const [virtualConfigDraft, setVirtualConfigDraft] =
    useState<VirtualConfigDraft | null>(null)
  const [exportValidationErrors, setExportValidationErrors] = useState<
    Record<string, string[]>
  >({})
  const [virtualValidationErrors, setVirtualValidationErrors] = useState<
    Record<string, string[]>
  >({})
  const [isSavingExportConfig, setIsSavingExportConfig] = useState(false)
  const [isSavingVirtualConfig, setIsSavingVirtualConfig] = useState(false)
  const [isRevertingExportConfig, setIsRevertingExportConfig] = useState(false)
  const [isRevertingVirtualConfig, setIsRevertingVirtualConfig] =
    useState(false)
  const [expandedExportSections, setExpandedExportSections] = useState<
    Record<string, boolean>
  >({})
  const [expandedVirtualSections, setExpandedVirtualSections] = useState<
    Record<string, boolean>
  >({})
  const [exportExtraSettingsExpanded, setExportExtraSettingsExpanded] =
    useState<Record<string, boolean>>({})
  const [virtualExtraSettingsExpanded, setVirtualExtraSettingsExpanded] =
    useState<Record<string, boolean>>({})
  const [resetExportDraftRequested, setResetExportDraftRequested] =
    useState(false)
  const [resetVirtualDraftRequested, setResetVirtualDraftRequested] =
    useState(false)

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
      draft[section] = Array.isArray(base[section]) ? [...base[section]] : []
    })

    return draft as SheetsConfigDraft
  }

  const createVirtualConfigDraft = (
    source?: VirtualConfigDraft | null,
  ): VirtualConfigDraft => {
    const base = JSON.parse(JSON.stringify(source ?? {})) as Record<string, any>

    const draft: Record<string, any> = {
      ...base,
      globals: {
        ...(base.globals ?? {}),
      },
    }

    delete draft.enabled

    VIRTUAL_SECTIONS.forEach(section => {
      draft[section] = Array.isArray(base[section]) ? [...base[section]] : []
    })

    return draft as VirtualConfigDraft
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
    if (showImportConfig && resetVirtualDraftRequested) {
      setVirtualConfigDraft(
        createVirtualConfigDraft(settings.importing?.sheets),
      )
      setVirtualValidationErrors({})
      setExpandedVirtualSections(
        VIRTUAL_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
          acc[section] = false
          return acc
        }, {}),
      )
      setVirtualExtraSettingsExpanded({})
      setResetVirtualDraftRequested(false)
    }
  }, [showImportConfig, resetVirtualDraftRequested, settings.importing])

  const positionOptions = useMemo<MultiSelectOption[]>(() => {
    const productTypeOptions =
      (((t.enums as Record<string, any>) ?? {}).productType as Record<
        string,
        string
      >) ?? {}

    return AVAILABLE_POSITION_OPTIONS.reduce<MultiSelectOption[]>(
      (acc, productType) => {
        const label = productTypeOptions[productType]
        if (label) {
          acc.push({ value: productType, label })
        }
        return acc
      },
      [],
    )
  }, [t])

  const contributionsOptions = useMemo<MultiSelectOption[]>(() => {
    const options =
      ((t.settings as Record<string, any>)?.contributionsDataOptions as Record<
        string,
        string
      >) ?? {}

    return Object.entries(options).map(([value, label]) => ({
      value,
      label,
    }))
  }, [t])

  const transactionsOptions = useMemo<MultiSelectOption[]>(() => {
    const options =
      ((t.settings as Record<string, any>)?.transactionsDataOptions as Record<
        string,
        string
      >) ?? {}

    return Object.entries(options).map(([value, label]) => ({
      value,
      label,
    }))
  }, [t])

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
  }

  const handleCloseExportConfig = () => {
    setShowExportConfig(false)
    setExportConfigDraft(null)
    setExportValidationErrors({})
    setExpandedExportSections({})
    setExportExtraSettingsExpanded({})
  }

  const handleOpenImportConfig = () => {
    setVirtualConfigDraft(createVirtualConfigDraft(settings.importing?.sheets))
    setVirtualValidationErrors({})
    setExpandedVirtualSections(() =>
      VIRTUAL_SECTIONS.reduce<Record<string, boolean>>((acc, section) => {
        acc[section] = false
        return acc
      }, {}),
    )
    setVirtualExtraSettingsExpanded({})
    setShowImportConfig(true)
  }

  const handleCloseImportConfig = () => {
    setShowImportConfig(false)
    setVirtualConfigDraft(null)
    setVirtualValidationErrors({})
    setExpandedVirtualSections({})
    setVirtualExtraSettingsExpanded({})
  }

  const toggleExportSection = (section: ExportSectionKey) => {
    setExpandedExportSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const toggleVirtualSection = (section: VirtualSectionKey) => {
    setExpandedVirtualSections(prev => ({
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

  const toggleVirtualExtraSettings = (itemKey: string) => {
    setVirtualExtraSettingsExpanded(prev => ({
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

  const clearVirtualGlobalsError = () => {
    setVirtualValidationErrors(prev => {
      if (!prev.virtualGlobals) {
        return prev
      }
      const next = { ...prev }
      delete next.virtualGlobals
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

  const clearVirtualItemError = (section: VirtualSectionKey, index: number) => {
    const errorKey = `virtual_${section}`
    setVirtualValidationErrors(prev => {
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

  const handleVirtualGlobalChange = (
    field: "spreadsheetId" | "dateFormat" | "datetimeFormat",
    value: string,
  ) => {
    setVirtualConfigDraft(prev => {
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
      clearVirtualGlobalsError()
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
      const newItem: Record<string, any> = { range: "" }

      if (["position", "transactions", "contributions"].includes(section)) {
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

  const handleAddVirtualItem = (section: VirtualSectionKey) => {
    setVirtualConfigDraft(prev => {
      if (!prev) {
        return prev
      }
      const items = Array.isArray((prev as Record<string, any>)[section])
        ? [...((prev as Record<string, any>)[section] as any[])]
        : []
      const newItem: Record<string, any> = { range: "" }

      if (["position", "transactions"].includes(section)) {
        newItem.data = ""
      }

      items.push(newItem)

      return {
        ...prev,
        [section]: items,
      }
    })

    setExpandedVirtualSections(prev => ({
      ...prev,
      [section]: true,
    }))
  }

  const handleRemoveVirtualItem = (
    section: VirtualSectionKey,
    index: number,
  ) => {
    setVirtualConfigDraft(prev => {
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

    setVirtualValidationErrors(prev => {
      const errorKey = `virtual_${section}`
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

    setVirtualExtraSettingsExpanded(prev => {
      const next: Record<string, boolean> = {}
      Object.entries(prev).forEach(([key, value]) => {
        if (!key.startsWith(`${section}-`)) {
          next[key] = value
        }
      })
      return next
    })
  }

  const handleUpdateVirtualItem = (
    section: VirtualSectionKey,
    index: number,
    field: string,
    value: any,
  ) => {
    setVirtualConfigDraft(prev => {
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
        clearVirtualItemError(section, index)
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

        if (["position", "transactions", "contributions"].includes(section)) {
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

  const runVirtualValidation = (config: VirtualConfigDraft | null) => {
    if (!config) {
      setVirtualValidationErrors({})
      return true
    }

    const errors: Record<string, string[]> = {}
    const configRecord = config as Record<string, any>

    const sectionsConfigured = VIRTUAL_SECTIONS.some(section => {
      const items = configRecord[section]
      return Array.isArray(items) && items.length > 0
    })

    if (sectionsConfigured) {
      const spreadsheetId =
        (configRecord.globals?.spreadsheetId as string | undefined)?.trim() ??
        ""
      if (!spreadsheetId) {
        errors.virtualGlobals = [t.settings.errors.virtualSpreadsheetIdRequired]
      }
    }

    VIRTUAL_SECTIONS.forEach(section => {
      const items = Array.isArray(configRecord[section])
        ? (configRecord[section] as any[])
        : []

      if (items.length === 0) {
        return
      }

      const sectionErrors: string[] = []
      const errorKey = `virtual_${section}`

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
        }

        if (entryErrors.length > 0) {
          sectionErrors[index] = entryErrors.join(" ")
        }
      })

      if (sectionErrors.length > 0) {
        errors[errorKey] = sectionErrors
      }
    })

    setVirtualValidationErrors(errors)
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

  const handleSaveVirtualConfig = async () => {
    if (!virtualConfigDraft) {
      return
    }

    const isValid = runVirtualValidation(virtualConfigDraft)
    if (!isValid) {
      showToast(t.settings.validationError, "error")
      return
    }

    try {
      setIsSavingVirtualConfig(true)

      const sanitizedStablecoins = sanitizeStablecoins(
        settings.assets?.crypto?.stablecoins,
      )

      const virtualConfig = JSON.parse(
        JSON.stringify(virtualConfigDraft),
      ) as VirtualConfigDraft

      delete (virtualConfig as Record<string, any>).enabled

      const settingsForSave: AppSettings = {
        ...settings,
        importing: {
          ...(settings.importing ?? {}),
          sheets: virtualConfig,
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
      setVirtualConfigDraft(null)
    } catch (error) {
      console.error("Error saving virtual config:", error)
      showToast(t.settings.saveError, "error")
    } finally {
      setIsSavingVirtualConfig(false)
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

  const handleRevertVirtualConfig = async () => {
    try {
      setIsRevertingVirtualConfig(true)
      await fetchSettings()
      setVirtualValidationErrors({})
      setResetVirtualDraftRequested(true)
    } catch (error) {
      console.error("Error reverting virtual config:", error)
      showToast(t.settings.fetchError, "error")
    } finally {
      setIsRevertingVirtualConfig(false)
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

  const virtualConfig = settings?.importing?.sheets
  const virtualSectionCounts = {
    position: virtualConfig?.position?.length || 0,
    transactions: virtualConfig?.transactions?.length || 0,
  }
  const hasVirtualSections = Object.values(virtualSectionCounts).some(
    count => count > 0,
  )

  const googleSheetsIntegration = externalIntegrations.find(
    integration => integration.id === "GOOGLE_SHEETS",
  )
  const isGoogleSheetsIntegrationEnabled =
    googleSheetsIntegration?.status === ExternalIntegrationStatus.ON
  const canExport = isGoogleSheetsIntegrationEnabled && hasSheetSections
  const canImport = isGoogleSheetsIntegrationEnabled && hasVirtualSections
  const sheetsConfigured = hasSheetSections
  const virtualConfigured = hasVirtualSections

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
      await updateSheets({
        target: ExportTarget.GOOGLE_SHEETS,
        options: { exclude_non_real: excludeNonReal ? true : null },
      })

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
      const response = await virtualFetch()

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
          showToast(t.common.virtualScrapeSuccess, "success")
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
      showToast(t.common.virtualScrapeError, "error")
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
          await fetchEntities()
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
    section === "contributions"

  const sectionSupportsFilters = (section: ExportSectionKey) =>
    section === "historic" ||
    section === "position" ||
    section === "contributions" ||
    section === "transactions"

  const getExportDataOptions = (section: ExportSectionKey) => {
    if (section === "position") {
      return positionOptions
    }
    if (section === "contributions") {
      return contributionsOptions
    }
    if (section === "transactions") {
      return transactionsOptions
    }
    return []
  }

  const getVirtualDataOptions = (section: VirtualSectionKey) => {
    if (section === "position") {
      return positionOptions
    }
    if (section === "transactions") {
      return transactionsOptions
    }
    return []
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
                      <div className="space-y-1.5 sm:space-y-2">
                        <Label htmlFor={`${itemKey}-data`}>
                          {t.settings.data}
                          <span className="ml-1 text-red-500">*</span>
                        </Label>
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
                    ) : null}

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

  const renderVirtualSection = (section: VirtualSectionKey) => {
    if (!virtualConfigDraft) {
      return null
    }

    const configRecord = virtualConfigDraft as Record<string, any>
    const items = Array.isArray(configRecord[section])
      ? (configRecord[section] as any[])
      : []
    const sectionLabel = (t.settings as Record<string, any>)[section] as string
    const isExpanded = expandedVirtualSections[section] ?? false
    const sectionErrors = virtualValidationErrors[`virtual_${section}`] ?? []
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
          onClick={() => toggleVirtualSection(section)}
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
                const itemKey = `${section}-virtual-${index}`
                const extraKey = `${itemKey}-extra`
                const extraExpanded =
                  virtualExtraSettingsExpanded[extraKey] ?? false

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
                          onClick={() =>
                            handleRemoveVirtualItem(section, index)
                          }
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
                          handleUpdateVirtualItem(
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
                      <div className="space-y-1.5 sm:space-y-2">
                        <Label htmlFor={`${itemKey}-data`}>
                          {t.settings.data}
                          <span className="ml-1 text-red-500">*</span>
                        </Label>
                        <MultiSelect
                          options={getVirtualDataOptions(section)}
                          value={
                            Array.isArray(item?.data)
                              ? (item.data as string[])
                              : item?.data
                                ? [item.data as string]
                                : []
                          }
                          onChange={value => {
                            const lastValue =
                              value.length > 0 ? value[value.length - 1] : null
                            handleUpdateVirtualItem(
                              section,
                              index,
                              "data",
                              lastValue ?? null,
                            )
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
                    ) : null}

                    <div className="rounded-md border border-border/50 bg-muted/10">
                      <button
                        type="button"
                        onClick={() => toggleVirtualExtraSettings(extraKey)}
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
                                handleUpdateVirtualItem(
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
                                  handleUpdateVirtualItem(
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
                                  handleUpdateVirtualItem(
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
                onClick={() => handleAddVirtualItem(section)}
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

  const renderImportConfigDialog = () => {
    if (!showImportConfig || !virtualConfigDraft) {
      return null
    }

    const globalsError = virtualValidationErrors.virtualGlobals?.[0]
    const globals = (virtualConfigDraft.globals ?? {}) as Record<string, any>

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
                      handleVirtualGlobalChange(
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
                      handleVirtualGlobalChange(
                        "dateFormat",
                        event.target.value,
                      )
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
                      handleVirtualGlobalChange(
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
              {VIRTUAL_SECTIONS.map(section => renderVirtualSection(section))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCloseImportConfig}
              disabled={isSavingVirtualConfig}
              className="inline-flex items-center gap-2"
            >
              <X className="h-4 w-4" />
              {t.common.cancel}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRevertVirtualConfig}
              disabled={isSavingVirtualConfig || isRevertingVirtualConfig}
              aria-label={t.common.discard}
            >
              {isRevertingVirtualConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isRevertingVirtualConfig ? t.common.loading : t.common.discard}
              </span>
            </Button>
            <Button
              size="icon"
              onClick={handleSaveVirtualConfig}
              disabled={isSavingVirtualConfig}
              aria-label={t.common.save}
            >
              {isSavingVirtualConfig ? (
                <LoadingSpinner className="h-4 w-4" />
              ) : (
                <SaveIcon className="h-4 w-4" />
              )}
              <span className="sr-only">
                {isSavingVirtualConfig ? t.settings.saving : t.common.save}
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
              className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-white data-[state=active]:text-slate-900 data-[state=active]:shadow-sm dark:data-[state=active]:bg-white"
            >
              <FileUp className="mr-2 h-4 w-4" />
              {t.export.tabs.export}
            </TabsTrigger>
            <TabsTrigger
              value="import"
              className="rounded-full px-5 py-2 text-sm font-medium text-muted-foreground transition-all data-[state=active]:bg-white data-[state=active]:text-slate-900 data-[state=active]:shadow-sm dark:data-[state=active]:bg-white"
            >
              <Download className="mr-2 h-4 w-4" />
              {t.export.tabs.import}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="export" className="space-y-6">
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
                  <div className="flex w-full sm:w-auto">
                    <Button
                      onClick={handleExport}
                      disabled={isExportDisabled}
                      className="relative flex-1 rounded-r-none"
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
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          size="icon"
                          className="-ml-px rounded-l-none border-l-2 border-white/30 dark:border-black/30"
                          aria-label={t.export.options}
                        >
                          <SlidersHorizontal className="h-4 w-4" />
                          <span className="sr-only">{t.export.options}</span>
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-80" align="center">
                        <div className="space-y-4">
                          <div className="flex items-center justify-between space-x-2">
                            <div className="flex-1">
                              <div className="text-sm font-medium">
                                {t.export.excludeManual}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {t.export.excludeManualDescription}
                              </div>
                            </div>
                            <Switch
                              checked={excludeNonReal}
                              onCheckedChange={setExcludeNonReal}
                            />
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  </div>
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
                      virtualConfigured
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                        : "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
                    )}
                  >
                    {virtualConfigured
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
                      {hasVirtualSections ? (
                        Object.entries(virtualSectionCounts)
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
                        {t.common.virtualScrapeSuccess}
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
      {renderImportConfigDialog()}

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
