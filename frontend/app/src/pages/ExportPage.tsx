import {
  useEffect,
  useMemo,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeftRight,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  FileSpreadsheet,
  FileText,
  FileUp,
  Info,
  Plus,
  PlusCircle,
  RotateCcw,
  Save as SaveIcon,
  Settings,
  LayoutTemplate,
  Sparkles,
  Trash2,
  TrendingUp,
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
  exportFile,
  suggestTemplateFields,
} from "@/services/api"
import { useFileImportJob } from "@/context/FileImportJobContext"
import { AIImportSettingsCard } from "@/components/import/AIImportSettingsCard"
import { CollapsibleNotes } from "@/components/import/CollapsibleNotes"
import {
  NATIVE_IMAGE_EXTENSIONS,
  isImageFile,
  prepareAIImageUpload,
} from "@/lib/aiImageUpload"
import { isNativeMobile } from "@/lib/platform"
import {
  EntityType,
  ExternalIntegrationStatus,
  FileFormat,
  ImportResultCode,
  NumberFormat,
  TemplateType,
  type AIImportMetadata,
  type Feature,
  type ImportError,
  ImportErrorType,
  type Template,
  type TemplateCreatePayload,
  type TemplateFieldsSuggestion,
  type TemplateUpdatePayload,
  type TemplateFeatureDefinition,
  type EphemeralTemplateFieldPayload,
  type FileExportRequest,
  type FileImportRequest,
  type ImportedData,
} from "@/types"
import { ApiErrorException } from "@/utils/apiErrors"
import { cn } from "@/lib/utils"
import { getIntegrationName } from "@/lib/integrations"
import { saveBlobToDevice } from "@/lib/mobile"
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
import { DatePicker } from "@/components/ui/DatePicker"
import { PageTabs, type PageTab } from "@/components/ui/PageTabs"
import { Tabs, TabsContent } from "@/components/ui/Tabs"
import { format, subDays, subMonths } from "date-fns"
import { EntitySelector } from "@/components/EntitySelector"
import { cleanObject, processDataFields } from "@/lib/settingsUtils"
import { ProductType, type EntitiesPosition } from "@/types/position"
import {
  getIconForAssetType,
  getIconForProductType,
} from "@/utils/dashboardUtils"
import {
  TemplateManagerDialog,
  featureIcons,
  type TemplateCreatePreset,
} from "@/components/templates/TemplateManagerDialog"
import {
  FileImportPreviewDialog,
  type FileImportPreviewStrings,
} from "@/components/FileImportPreviewDialog"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"

const EXPORT_SECTIONS = [
  "position",
  "contributions",
  "transactions",
  "historic",
] as const

type ExportSectionKey = (typeof EXPORT_SECTIONS)[number]

const IMPORT_SECTIONS = ["position", "transactions"] as const

const EDGE_CARD =
  "-mx-6 rounded-none border-x-0 md:mx-0 md:rounded-lg md:border-x"

type ImportSectionKey = (typeof IMPORT_SECTIONS)[number]

const SECTION_FEATURE_MAP: Record<ExportSectionKey, Feature> = {
  position: "POSITION",
  contributions: "AUTO_CONTRIBUTIONS",
  transactions: "TRANSACTIONS",
  historic: "HISTORIC",
}

const PRIMARY_FILE_EXPORT_FEATURES: Feature[] = ["TRANSACTIONS", "POSITION"]
const SECONDARY_FILE_EXPORT_FEATURES: Feature[] = [
  "AUTO_CONTRIBUTIONS",
  "HISTORIC",
]
const FILE_EXPORT_FEATURES: Feature[] = [
  ...PRIMARY_FILE_EXPORT_FEATURES,
  ...SECONDARY_FILE_EXPORT_FEATURES,
]

const getDefaultTransactionsExportRange = (referenceDate = new Date()) => ({
  from: format(subMonths(referenceDate, 6), "yyyy-MM-dd"),
  to: format(referenceDate, "yyyy-MM-dd"),
})

const FILE_IMPORT_FEATURES: Feature[] = ["TRANSACTIONS", "POSITION"]

const NUMBER_FORMAT_OPTIONS: NumberFormat[] = [
  NumberFormat.ENGLISH,
  NumberFormat.EUROPEAN,
]

type SheetsConfigDraft = NonNullable<
  NonNullable<AppSettings["export"]>["sheets"]
>

type ImportConfigDraft = NonNullable<
  NonNullable<AppSettings["importing"]>["sheets"]
>

type ImportErrorsContext = "preview" | "import"

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
  ProductType.CRYPTO,
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
  ProductType.CRYPTO,
] as const

const FEATURE_PRODUCT_MAP: Record<Feature, readonly ProductType[]> = {
  POSITION: AVAILABLE_POSITION_OPTIONS,
  AUTO_CONTRIBUTIONS: [],
  TRANSACTIONS: AVAILABLE_TRANSACTION_PRODUCTS,
  HISTORIC: AVAILABLE_HISTORIC_PRODUCTS,
}

const getImportEntityTypes = (product?: string | null): EntityType[] =>
  product === ProductType.CRYPTO
    ? [EntityType.FINANCIAL_INSTITUTION, EntityType.CRYPTO_EXCHANGE]
    : [EntityType.FINANCIAL_INSTITUTION]

const FILE_EXPORT_FORMATS: FileFormat[] = [
  FileFormat.CSV,
  FileFormat.TSV,
  FileFormat.XLSX,
]

type FileExportDateFormatPresetKey =
  "ISO" | "DMY_SLASH" | "MDY_SLASH" | "DMY_DASH"

type FileExportDateFormatPreset = FileExportDateFormatPresetKey | "CUSTOM"

const FILE_EXPORT_DATE_FORMAT_PRESETS: ReadonlyArray<{
  key: FileExportDateFormatPresetKey
  labelKey: "iso" | "dmySlash" | "mdySlash" | "dmyDash"
  value: string
}> = [
  { key: "ISO", labelKey: "iso", value: "" },
  { key: "DMY_SLASH", labelKey: "dmySlash", value: "%d/%m/%Y" },
  { key: "MDY_SLASH", labelKey: "mdySlash", value: "%m/%d/%Y" },
  { key: "DMY_DASH", labelKey: "dmyDash", value: "%d-%m-%Y" },
]

type FileExportDatetimeFormatPresetKey =
  "ISO" | "YMD_SPACE" | "DMY_SLASH" | "MDY_SLASH" | "DMY_DASH"

type FileExportDatetimeFormatPreset =
  FileExportDatetimeFormatPresetKey | "CUSTOM"

const FILE_EXPORT_DATETIME_FORMAT_PRESETS: ReadonlyArray<{
  key: FileExportDatetimeFormatPresetKey
  labelKey: "iso" | "ymdSpace" | "dmySlash" | "mdySlash" | "dmyDash"
  value: string
}> = [
  { key: "ISO", labelKey: "iso", value: "" },
  { key: "YMD_SPACE", labelKey: "ymdSpace", value: "%Y-%m-%d %H:%M:%S" },
  { key: "DMY_SLASH", labelKey: "dmySlash", value: "%d/%m/%Y %H:%M:%S" },
  { key: "MDY_SLASH", labelKey: "mdySlash", value: "%m/%d/%Y %H:%M:%S" },
  { key: "DMY_DASH", labelKey: "dmyDash", value: "%d-%m-%Y %H:%M:%S" },
]

const POSITION_DATE_FIELDS_BY_PRODUCT: Partial<
  Record<ProductType, readonly string[]>
> = {
  [ProductType.LOAN]: ["creation", "maturity", "next_payment_date"],
  [ProductType.DEPOSIT]: ["maturity"],
  [ProductType.FACTORING]: ["maturity"],
  [ProductType.REAL_ESTATE_CF]: ["maturity", "extended_maturity"],
}

const POSITION_DATETIME_FIELDS_BY_PRODUCT: Partial<
  Record<ProductType, readonly string[]>
> = {
  [ProductType.DEPOSIT]: ["creation"],
  [ProductType.FACTORING]: ["start", "last_invest_date"],
  [ProductType.REAL_ESTATE_CF]: ["start", "last_invest_date"],
}

const HISTORIC_DATE_FIELDS_BY_PRODUCT: Partial<
  Record<ProductType, readonly string[]>
> = {
  [ProductType.FACTORING]: ["maturity"],
  [ProductType.REAL_ESTATE_CF]: ["maturity", "extended_maturity"],
}

const HISTORIC_DATETIME_FIELDS = [
  "last_invest_date",
  "last_tx_date",
  "effective_maturity",
] as const

const TRANSACTION_DATETIME_FIELDS_BY_PRODUCT: Partial<
  Record<ProductType, readonly string[]>
> = {
  [ProductType.STOCK_ETF]: ["date", "order_date"],
  [ProductType.FUND]: ["date", "order_date"],
  [ProductType.CRYPTO]: ["date", "order_date"],
  [ProductType.ACCOUNT]: ["date"],
  [ProductType.FUND_PORTFOLIO]: ["date"],
  [ProductType.FACTORING]: ["date"],
  [ProductType.REAL_ESTATE_CF]: ["date"],
  [ProductType.DEPOSIT]: ["date"],
}

const AUTO_CONTRIBUTION_DATE_FIELDS = ["since", "until", "next_date"] as const

const getExportTemporalCapabilities = (
  feature: Feature | null,
  products: readonly ProductType[],
  selectedTemplate: Template | null,
): { hasDate: boolean; hasDatetime: boolean } => {
  if (!feature) {
    return { hasDate: true, hasDatetime: true }
  }
  const templateFieldSet = selectedTemplate?.fields?.length
    ? new Set(selectedTemplate.fields.map(item => item.field))
    : null
  const matchesField = (fields: readonly string[]) =>
    fields.some(field => !templateFieldSet || templateFieldSet.has(field))

  if (feature === "AUTO_CONTRIBUTIONS") {
    return {
      hasDate: matchesField(AUTO_CONTRIBUTION_DATE_FIELDS),
      hasDatetime: false,
    }
  }

  const activeProducts =
    products.length > 0 ? products : FEATURE_PRODUCT_MAP[feature]

  if (feature === "TRANSACTIONS") {
    return {
      hasDate: false,
      hasDatetime: activeProducts.some(product =>
        matchesField(TRANSACTION_DATETIME_FIELDS_BY_PRODUCT[product] ?? []),
      ),
    }
  }

  if (feature === "HISTORIC") {
    return {
      hasDate: activeProducts.some(product =>
        matchesField(HISTORIC_DATE_FIELDS_BY_PRODUCT[product] ?? []),
      ),
      hasDatetime: matchesField(HISTORIC_DATETIME_FIELDS),
    }
  }

  return {
    hasDate: activeProducts.some(product =>
      matchesField(POSITION_DATE_FIELDS_BY_PRODUCT[product] ?? []),
    ),
    hasDatetime: activeProducts.some(product =>
      matchesField(POSITION_DATETIME_FIELDS_BY_PRODUCT[product] ?? []),
    ),
  }
}

const QUICK_EXPORT_POSITION_PRIORITY: readonly ProductType[] = [
  ProductType.STOCK_ETF,
  ProductType.FUND,
  ProductType.ACCOUNT,
  ProductType.CRYPTO,
  ProductType.DEPOSIT,
  ProductType.REAL_ESTATE_CF,
  ProductType.FACTORING,
  ProductType.LOAN,
  ProductType.CARD,
]

interface QuickExportPreset {
  key: string
  label: string
  icon: ReactNode
  feature: Feature
  products: ProductType[]
}

const extractHeldProductTypes = (
  positionsData: EntitiesPosition | null,
): Set<ProductType> => {
  const held = new Set<ProductType>()
  if (!positionsData?.positions) {
    return held
  }
  Object.values(positionsData.positions).forEach(entityPositions => {
    if (!Array.isArray(entityPositions)) return
    entityPositions.forEach(globalPos => {
      const products = globalPos?.products
      if (!products || typeof products !== "object") return
      Object.entries(products).forEach(([productType, productData]) => {
        const entries = (productData as { entries?: any[] })?.entries
        if (!Array.isArray(entries) || entries.length === 0) return
        if (productType === ProductType.CRYPTO) {
          const hasAssets = entries.some(wallet =>
            Array.isArray(wallet?.assets) ? wallet.assets.length > 0 : true,
          )
          if (!hasAssets) return
        }
        held.add(productType as ProductType)
      })
    })
  })
  return held
}

const IMPORT_FIELD_LABEL_KEY_ALIASES: Record<string, string> = {
  ref: "reference",
  portfolio_name: "portfolio",
  avg_balance: "average_balance",
}

const hasImportedContent = (data: ImportedData | null): boolean => {
  if (!data) {
    return false
  }

  const positionList = Array.isArray(data.positions)
    ? data.positions
    : data.positions
      ? Object.values(data.positions as Record<string, any>)
      : []
  const hasPositions = positionList.some(position => {
    const products = position?.products ?? {}
    return Object.values(products).some(product => {
      const entries = (product as { entries?: any[] })?.entries
      return Array.isArray(entries) && entries.length > 0
    })
  })

  const accountTransactions = data.transactions?.account ?? []
  const investmentTransactions = data.transactions?.investment ?? []
  const hasTransactions = [accountTransactions, investmentTransactions].some(
    list => Array.isArray(list) && list.length > 0,
  )

  return hasPositions || hasTransactions
}

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

const formatDetectedDatePattern = (pattern: string) =>
  pattern === "ISO"
    ? "YYYY-MM-DD"
    : pattern
        .replace(/%d/g, "DD")
        .replace(/%m/g, "MM")
        .replace(/%Y/g, "YYYY")
        .replace(/%y/g, "YY")
        .replace(/%H/g, "HH")
        .replace(/%M/g, "mm")
        .replace(/%S/g, "ss")

const isTemplateForProduct = (template: Template, product: ProductType) =>
  !template.products?.length || template.products.includes(product)

const uniqueTemplateName = (fileName: string, templates: Template[]) => {
  const base = fileName.replace(/\.[^.]+$/, "").trim() || fileName
  const taken = new Set(templates.map(template => template.name.toLowerCase()))
  let name = base
  for (let suffix = 2; taken.has(name.toLowerCase()); suffix++) {
    name = `${base} ${suffix}`
  }
  return name
}

type FileImportAnalysisError =
  "unsupported" | "pdf_no_text" | "no_table" | "failed"

interface ManualImportResult {
  gotData: boolean
  errors?: ImportError[]
}

const CREATE_IMPORT_TEMPLATE_OPTION = "__create_import_template__"
const FILE_IMPORT_ACCEPT = [
  ".csv,.tsv,.xls,.xlsx,.html,.htm,.pdf,.txt,.png,.jpg,.jpeg,.webp,.gif",
  ...(isNativeMobile() ? NATIVE_IMAGE_EXTENSIONS : []),
].join(",")
const AI_ONLY_EXTENSIONS = [".txt"]

const isAiOnlyImportFile = (file: File) =>
  isImageFile(file) ||
  AI_ONLY_EXTENSIONS.some(extension =>
    file.name.toLowerCase().endsWith(extension),
  )

type TemplateSelectionPayload<TParams = Record<string, string> | null> = {
  id: string
  params: TParams
}

type FileExportFormErrors = Partial<
  Record<"feature" | "products" | "dateRange", string>
>

type FileImportFormErrors = Partial<
  Record<"feature" | "product" | "template" | "file" | "entity", string>
>

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
  const { t, locale } = useI18n()
  const defaultNumberFormat = useMemo(
    () => (locale === "en-US" ? NumberFormat.ENGLISH : NumberFormat.EUROPEAN),
    [locale],
  )
  const navigate = useNavigate()
  const {
    settings,
    exportState,
    setExportState,
    showToast,
    fetchEntities,
    entities,
    externalIntegrations,
    fetchExternalIntegrations,
    saveSettings,
    fetchSettings,
  } = useAppContext()
  const { positionsData, refreshData, invalidateTransactionsCache } =
    useFinancialData()
  const [activeTab, setActiveTab] = useState<"export" | "import">("export")
  const pageTabs: PageTab<"export" | "import">[] = [
    { key: "export", label: t.export.tabs.export, Icon: FileUp },
    { key: "import", label: t.export.tabs.import, Icon: Download },
  ]
  const [successAnimation, setSuccessAnimation] = useState(false)
  const [showImportConfirm, setShowImportConfirm] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [importSuccessAnimation, setImportSuccessAnimation] = useState(false)
  const [importErrors, setImportErrors] = useState<ImportError[] | null>(null)
  const [importErrorsContext, setImportErrorsContext] =
    useState<ImportErrorsContext | null>(null)
  const [importInfoWarnings, setImportInfoWarnings] = useState<
    ImportError[] | null
  >(null)
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
  const [isFileExportDialogOpen, setIsFileExportDialogOpen] = useState(false)
  const [fileExportFeature, setFileExportFeature] = useState<Feature | null>(
    null,
  )
  const [fileExportProducts, setFileExportProducts] = useState<ProductType[]>(
    [],
  )
  const [fileExportTemplateId, setFileExportTemplateId] = useState<
    string | null
  >(null)
  const [fileExportFromDate, setFileExportFromDate] = useState("")
  const [fileExportToDate, setFileExportToDate] = useState("")
  const [showMoreFileExportFeatures, setShowMoreFileExportFeatures] =
    useState(false)
  const [fileExportDateFormatPreset, setFileExportDateFormatPreset] =
    useState<FileExportDateFormatPreset>("ISO")
  const [fileExportDatetimeFormatPreset, setFileExportDatetimeFormatPreset] =
    useState<FileExportDatetimeFormatPreset>("ISO")
  const [fileExportDateFormat, setFileExportDateFormat] = useState("")
  const [fileExportDatetimeFormat, setFileExportDatetimeFormat] = useState("")
  const [fileExportErrors, setFileExportErrors] =
    useState<FileExportFormErrors>({})
  const [isFileExporting, setIsFileExporting] = useState(false)
  const [fileExportFormat, setFileExportFormat] = useState<FileFormat>(
    FileFormat.CSV,
  )
  const [fileExportNumberFormat, setFileExportNumberFormat] =
    useState<NumberFormat>(defaultNumberFormat)
  const [isFileImportDialogOpen, setIsFileImportDialogOpen] = useState(false)
  const [fileImportFeature, setFileImportFeature] = useState<Feature | null>(
    null,
  )
  const [fileImportProduct, setFileImportProduct] =
    useState<ProductType | null>(null)
  const [fileImportTemplate, setFileImportTemplate] =
    useState<TemplateSelectionPayload<Record<string, string>> | null>(null)
  const [fileImportNumberFormat, setFileImportNumberFormat] =
    useState<NumberFormat>(defaultNumberFormat)
  const [fileImportDateFormat, setFileImportDateFormat] = useState("")
  const [fileImportDatetimeFormat, setFileImportDatetimeFormat] = useState("")
  const [fileImportFile, setFileImportFile] = useState<File | null>(null)
  const [fileImportErrors, setFileImportErrors] =
    useState<FileImportFormErrors>({})
  const [isFileImporting, setIsFileImporting] = useState(false)
  const [fileImportEntityMode, setFileImportEntityMode] = useState<
    "select" | "new"
  >("select")
  const [fileImportSelectedEntity, setFileImportSelectedEntity] = useState("")
  const [fileImportCustomEntity, setFileImportCustomEntity] = useState("")
  const fileImportInputRef = useRef<HTMLInputElement | null>(null)
  const fileImportCardInputRef = useRef<HTMLInputElement | null>(null)
  const [isDraggingFile, setIsDraggingFile] = useState(false)
  const [isDraggingCardFile, setIsDraggingCardFile] = useState(false)
  const defaultCurrency = settings.general?.defaultCurrency || "EUR"
  const [fileImportAutoCurrency, setFileImportAutoCurrency] =
    useState<string>(defaultCurrency)
  const currencyOptions = useMemo(() => {
    if (typeof Intl?.supportedValuesOf === "function") {
      try {
        return Array.from(
          new Set(
            Intl.supportedValuesOf("currency").map(code => code.toUpperCase()),
          ),
        ).sort()
      } catch {
        // fallback below
      }
    }
    return ["EUR", "USD", "GBP", "CHF", "JPY"]
  }, [])
  const [fileImportAnalysis, setFileImportAnalysis] =
    useState<TemplateFieldsSuggestion | null>(null)
  const [isAnalyzingImportFile, setIsAnalyzingImportFile] = useState(false)
  const [fileImportAnalysisError, setFileImportAnalysisError] =
    useState<FileImportAnalysisError | null>(null)
  const fileImportAnalysisRequestRef = useRef(0)
  const [showFileImportFormatOptions, setShowFileImportFormatOptions] =
    useState(false)
  const [templateCreatePreset, setTemplateCreatePreset] =
    useState<TemplateCreatePreset | null>(null)
  const templateManagerFromImportRef = useRef(false)
  const [pendingImportTemplateName, setPendingImportTemplateName] = useState<
    string | null
  >(null)
  const [importPreviewData, setImportPreviewData] =
    useState<ImportedData | null>(null)
  const [showImportPreviewDialog, setShowImportPreviewDialog] = useState(false)
  const [fileImportUseAi, setFileImportUseAi] = useState(false)
  const [fileImportAiInstructions, setFileImportAiInstructions] = useState("")
  const [aiPreview, setAiPreview] = useState<{
    token: string
    request: FileImportRequest
    ai: AIImportMetadata | null
  } | null>(null)
  const fileImportJob = useFileImportJob()

  useModalBackHandler(isTemplateDialogOpen, () =>
    setIsTemplateDialogOpen(false),
  )
  useModalBackHandler(showImportPreviewDialog, () =>
    setShowImportPreviewDialog(false),
  )
  useModalBackHandler(showImportConfirm, () => setShowImportConfirm(false))
  useModalBackHandler(showErrorDetails, () => setShowErrorDetails(false))
  useModalBackHandler(showExportConfig, () => setShowExportConfig(false))
  useModalBackHandler(showImportConfig, () => setShowImportConfig(false))
  useModalBackHandler(isFileExportDialogOpen, () =>
    setIsFileExportDialogOpen(false),
  )
  useModalBackHandler(isFileImportDialogOpen, () =>
    setIsFileImportDialogOpen(false),
  )

  useEffect(() => {
    setFileExportNumberFormat(defaultNumberFormat)
    setFileImportNumberFormat(defaultNumberFormat)
  }, [defaultNumberFormat])

  useEffect(() => {
    fetchExternalIntegrations()
  }, [fetchExternalIntegrations])

  const renderFileExportFeatureSelector = () => {
    const showSecondaryOnNarrow =
      showMoreFileExportFeatures ||
      (fileExportFeature !== null &&
        SECONDARY_FILE_EXPORT_FEATURES.includes(fileExportFeature))

    return (
      <div className="space-y-2">
        <Label className="text-sm font-medium text-foreground">
          {t.export.file.featureLabel}
          <span className="ml-1 text-red-500">*</span>
        </Label>
        <div className="flex flex-wrap gap-2">
          {FILE_EXPORT_FEATURES.map(feature => {
            const isSecondary = SECONDARY_FILE_EXPORT_FEATURES.includes(feature)
            return (
              <button
                key={feature}
                type="button"
                onClick={() => {
                  if (fileExportFeature === feature) return
                  if (feature === "TRANSACTIONS") {
                    const defaultRange = getDefaultTransactionsExportRange()
                    setFileExportFromDate(defaultRange.from)
                    setFileExportToDate(defaultRange.to)
                  } else {
                    setFileExportFromDate("")
                    setFileExportToDate("")
                  }
                  clearFileExportError("dateRange")
                  setFileExportFeature(feature)
                  clearFileExportError("feature")
                }}
                className={cn(
                  "items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                  isSecondary && !showSecondaryOnNarrow
                    ? "hidden sm:inline-flex"
                    : "inline-flex",
                  fileExportFeature === feature
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted",
                )}
              >
                {featureIcons[feature]}
                <span>{featureLabels[feature]}</span>
              </button>
            )
          })}
          {!showSecondaryOnNarrow ? (
            <button
              type="button"
              aria-label={t.common.more}
              title={t.common.more}
              data-testid="file-export-more-features"
              onClick={() => setShowMoreFileExportFeatures(true)}
              className="inline-flex items-center justify-center rounded-full border border-dashed border-border bg-muted/40 px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:hidden"
            >
              <Plus className="h-4 w-4" />
            </button>
          ) : null}
        </div>
        {fileExportErrors.feature ? (
          <p className="text-xs text-red-500">{fileExportErrors.feature}</p>
        ) : null}
      </div>
    )
  }

  const renderFileImportFeatureSelector = () => {
    return (
      <div className="space-y-2">
        <Label className="text-sm font-medium text-foreground">
          {t.export.fileImport.featureLabel}
          <span className="ml-1 text-red-500">*</span>
        </Label>
        <div className="flex flex-wrap gap-2">
          {FILE_IMPORT_FEATURES.map(feature => (
            <button
              key={feature}
              type="button"
              onClick={() => {
                if (fileImportFeature === feature) return
                setFileImportFeature(feature)
                setFileImportProduct(null)
                setFileImportTemplate(null)
                setFileImportEntityMode("select")
                setFileImportSelectedEntity("")
                setFileImportCustomEntity("")
                clearFileImportError("feature")
                clearFileImportError("template")
                clearFileImportError("product")
              }}
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                fileImportFeature === feature
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-muted/40 text-muted-foreground hover:bg-muted",
              )}
            >
              {featureIcons[feature]}
              <span>{featureLabels[feature]}</span>
            </button>
          ))}
        </div>
        {fileImportErrors.feature ? (
          <p className="text-xs text-red-500">{fileImportErrors.feature}</p>
        ) : null}
      </div>
    )
  }

  const renderProductPills = (
    options: MultiSelectOption[],
    isSelected: (product: ProductType) => boolean,
    onSelect: (product: ProductType) => void,
    hasError: boolean,
  ) => (
    <div className="flex flex-wrap gap-2">
      {options.map(option => {
        const product = option.value as ProductType
        const selected = isSelected(product)
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(product)}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : hasError
                  ? "border-red-500/70 bg-muted/40 text-muted-foreground hover:bg-muted"
                  : "border-border bg-muted/40 text-muted-foreground hover:bg-muted",
            )}
          >
            {getIconForProductType(product, "h-3.5 w-3.5")}
            <span>{option.label}</span>
          </button>
        )
      })}
    </div>
  )

  const handleOpenFileExportDialog = (preset?: {
    feature: Feature
    products?: ProductType[]
  }) => {
    resetFileExportForm()
    if (preset) {
      setFileExportFeature(preset.feature)
      setFileExportProducts(preset.products ?? [])
      if (preset.feature === "TRANSACTIONS") {
        const defaultRange = getDefaultTransactionsExportRange()
        setFileExportFromDate(defaultRange.from)
        setFileExportToDate(defaultRange.to)
      }
    }
    setIsFileExportDialogOpen(true)
    if (!templatesLoaded[TemplateType.EXPORT]) {
      loadTemplates(TemplateType.EXPORT)
    }
  }

  const handleCloseFileExportDialog = () => {
    setIsFileExportDialogOpen(false)
    resetFileExportForm()
  }

  const validateFileExportForm = useCallback(() => {
    const errors: FileExportFormErrors = {}
    if (!fileExportFeature) {
      errors.feature = t.export.file.errors.featureRequired
    }
    const requiresProducts =
      fileExportFeature &&
      (FEATURE_PRODUCT_MAP[fileExportFeature]?.length ?? 0) > 0
    if (requiresProducts && fileExportProducts.length === 0) {
      errors.products = t.settings.errors.dataRequired.trim()
    }
    if (
      fileExportFeature === "TRANSACTIONS" &&
      fileExportFromDate &&
      fileExportToDate &&
      fileExportFromDate > fileExportToDate
    ) {
      errors.dateRange = t.export.file.errors.invalidDateRange
    }
    setFileExportErrors(errors)
    return Object.keys(errors).length === 0
  }, [
    fileExportFeature,
    fileExportProducts,
    fileExportFromDate,
    fileExportToDate,
    t,
  ])

  const handleFileExport = async () => {
    const isValid = validateFileExportForm()
    if (!isValid || !fileExportFeature) {
      return
    }

    const isTransactionsExport = fileExportFeature === "TRANSACTIONS"
    const selectedExportTemplate = fileExportTemplateId
      ? ((templatesByType[TemplateType.EXPORT] ?? []).find(
          template => template.id === fileExportTemplateId,
        ) ?? null)
      : null
    const temporalCapabilities = getExportTemporalCapabilities(
      fileExportFeature,
      fileExportProducts,
      selectedExportTemplate,
    )
    const payload: FileExportRequest = {
      format: fileExportFormat,
      number_format: fileExportNumberFormat,
      feature: fileExportFeature,
      data: fileExportProducts.length ? fileExportProducts : null,
      date_format: temporalCapabilities.hasDate
        ? fileExportDateFormat.trim() || null
        : null,
      datetime_format: temporalCapabilities.hasDatetime
        ? fileExportDatetimeFormat.trim() || null
        : null,
      from_date:
        isTransactionsExport && fileExportFromDate ? fileExportFromDate : null,
      to_date:
        isTransactionsExport && fileExportToDate ? fileExportToDate : null,
      template: fileExportTemplateId
        ? { id: fileExportTemplateId, params: null }
        : null,
    }

    setIsFileExporting(true)
    try {
      const result = await exportFile(payload)
      const filename = result.filename ?? "export"
      const saved = await saveBlobToDevice({
        blob: result.blob,
        filename,
        contentType: result.contentType,
      })
      if (!saved) {
        const blobUrl = URL.createObjectURL(result.blob)
        const anchor = document.createElement("a")
        anchor.href = blobUrl
        anchor.download = filename
        document.body.appendChild(anchor)
        anchor.click()
        document.body.removeChild(anchor)
        URL.revokeObjectURL(blobUrl)
      }
      showToast(t.export.file.toast.success, "success")
      setIsFileExportDialogOpen(false)
      resetFileExportForm()
    } catch (error) {
      console.error("File export error:", error)
      let message = t.export.file.toast.error
      if (error instanceof ApiErrorException) {
        const code = error.code as keyof typeof t.errors
        const translated = (t.errors as Record<string, string>)[code]
        if (translated && !translated.includes("{entity}")) {
          message = translated
        }
      }
      showToast(message, "error")
    } finally {
      setIsFileExporting(false)
    }
  }

  const resetFileExportForm = useCallback(() => {
    setFileExportFeature(null)
    setFileExportProducts([])
    setFileExportTemplateId(null)
    setFileExportNumberFormat(defaultNumberFormat)
    setFileExportDateFormatPreset("ISO")
    setFileExportDatetimeFormatPreset("ISO")
    setFileExportDateFormat("")
    setFileExportDatetimeFormat("")
    setFileExportFromDate("")
    setFileExportToDate("")
    setShowMoreFileExportFeatures(false)
    setFileExportErrors({})
  }, [defaultNumberFormat])

  const clearFileExportError = useCallback(
    (field: keyof FileExportFormErrors) => {
      setFileExportErrors(prev => {
        if (!prev[field]) {
          return prev
        }
        const next = { ...prev }
        delete next[field]
        return next
      })
    },
    [],
  )

  const missingFromSuggestion = useMemo(
    () => fileImportAnalysis?.missing_required_fields ?? [],
    [fileImportAnalysis],
  )
  const unresolvableMissingFields = useMemo(
    () => missingFromSuggestion.filter(field => field !== "currency"),
    [missingFromSuggestion],
  )
  const needsAutoCurrencyFallback = useMemo(
    () => missingFromSuggestion.includes("currency"),
    [missingFromSuggestion],
  )
  const canAutoImportWithoutTemplate = Boolean(
    fileImportAnalysis &&
    !fileImportAnalysisError &&
    fileImportAnalysis.fields.length > 0 &&
    unresolvableMissingFields.length === 0,
  )

  const resetFileImportForm = useCallback(() => {
    setFileImportFeature(null)
    setFileImportProduct(null)
    setFileImportTemplate(null)
    setFileImportNumberFormat(defaultNumberFormat)
    setFileImportAutoCurrency(defaultCurrency)
    setFileImportDateFormat("")
    setFileImportDatetimeFormat("")
    setFileImportFile(null)
    setFileImportErrors({})
    setFileImportEntityMode("select")
    setFileImportSelectedEntity("")
    setFileImportCustomEntity("")
    setImportInfoWarnings(null)
    setImportPreviewData(null)
    setShowImportPreviewDialog(false)
    setShowFileImportFormatOptions(false)
    setPendingImportTemplateName(null)
    setFileImportUseAi(false)
    setFileImportAiInstructions("")
    setAiPreview(null)
    if (fileImportInputRef.current) {
      fileImportInputRef.current.value = ""
    }
  }, [defaultNumberFormat, defaultCurrency])

  const handleOpenFileImportDialog = (initialFile?: File | null) => {
    resetFileImportForm()
    if (initialFile) {
      setFileImportFile(initialFile)
      setFileImportUseAi(isAiOnlyImportFile(initialFile))
    }
    setIsFileImportDialogOpen(true)
    if (!templatesLoaded[TemplateType.IMPORT]) {
      loadTemplates(TemplateType.IMPORT)
    }
  }

  const handleCloseFileImportDialog = () => {
    setIsFileImportDialogOpen(false)
    resetFileImportForm()
  }

  const clearFileImportError = useCallback(
    (field: keyof FileImportFormErrors) => {
      setFileImportErrors(prev => {
        if (!prev[field]) {
          return prev
        }
        const next = { ...prev }
        delete next[field]
        return next
      })
    },
    [],
  )

  const validateFileImportForm = useCallback(() => {
    const errors: FileImportFormErrors = {}
    if (!fileImportFeature) {
      errors.feature = t.export.fileImport.errors.featureRequired
    }
    const requiresProduct =
      fileImportFeature &&
      (FEATURE_PRODUCT_MAP[fileImportFeature]?.length ?? 0) > 0
    if (requiresProduct && !fileImportProduct) {
      errors.product = t.export.fileImport.errors.productRequired
    }
    if (
      !fileImportUseAi &&
      !fileImportTemplate &&
      !canAutoImportWithoutTemplate
    ) {
      errors.template = t.export.templates.templateSelectRequired
    }
    if (!fileImportFile) {
      errors.file = t.export.fileImport.errors.fileRequired
    }
    const entityParam =
      fileImportEntityMode === "new"
        ? fileImportCustomEntity.trim()
        : fileImportSelectedEntity.trim()
    if (fileImportUseAi && !entityParam) {
      errors.entity = t.export.import.entityRequired
    }
    if (
      !entityParam &&
      !fileImportTemplate &&
      canAutoImportWithoutTemplate &&
      fileImportAnalysis &&
      !fileImportAnalysis.fields.some(f => f.field === "entity")
    ) {
      errors.entity = t.export.import.entityRequired
    }
    setFileImportErrors(errors)
    return Object.keys(errors).length === 0
  }, [
    fileImportFeature,
    fileImportProduct,
    fileImportTemplate,
    fileImportUseAi,
    canAutoImportWithoutTemplate,
    fileImportFile,
    fileImportEntityMode,
    fileImportCustomEntity,
    fileImportSelectedEntity,
    fileImportAnalysis,
    t,
  ])

  const handleFileImport = async (options?: { preview?: boolean }) => {
    const isPreviewRequest = options?.preview !== false
    const confirmingAiPreview = !isPreviewRequest && aiPreview !== null
    if (confirmingAiPreview) {
      await executeFileImport(
        {
          ...aiPreview.request,
          preview: false,
          previewToken: aiPreview.token,
        },
        null,
        false,
      )
      return
    }

    const isValid = validateFileImportForm()
    if (
      !isValid ||
      !fileImportFeature ||
      !fileImportProduct ||
      (!fileImportUseAi &&
        !fileImportTemplate &&
        !canAutoImportWithoutTemplate) ||
      !fileImportFile
    ) {
      return
    }

    const entityParam =
      fileImportEntityMode === "new"
        ? fileImportCustomEntity.trim()
        : fileImportSelectedEntity

    if (fileImportUseAi) {
      await executeFileImport(
        {
          feature: fileImportFeature,
          number_format: fileImportNumberFormat,
          product: fileImportProduct,
          templateParams: entityParam ? { entity: entityParam } : null,
          useAi: true,
          aiInstructions: fileImportAiInstructions.trim() || null,
        },
        await prepareAIImageUpload(fileImportFile),
        isPreviewRequest,
      )
      return
    }

    const templateParams = {
      ...(fileImportTemplate?.params ?? {}),
    }
    if (entityParam) {
      templateParams.entity = entityParam
    } else {
      delete templateParams.entity
    }

    const sanitizedTemplateParams =
      Object.keys(templateParams).length > 0 ? templateParams : null

    const dateFormatValue = fileImportDateFormat.trim()
    const datetimeFormatValue = fileImportDatetimeFormat.trim()

    let ephemeralFields: EphemeralTemplateFieldPayload[] | null = null
    if (!fileImportTemplate && fileImportAnalysis) {
      ephemeralFields = fileImportAnalysis.fields.map(field => ({
        field: field.field,
        name: field.name,
      }))
      if (needsAutoCurrencyFallback) {
        ephemeralFields.push({
          field: "currency",
          name: "currency",
          default: fileImportAutoCurrency || defaultCurrency,
        })
      }
    }

    const payload: FileImportRequest = {
      feature: fileImportFeature,
      number_format: fileImportNumberFormat,
      product: fileImportProduct,
      templateId: fileImportTemplate?.id ?? null,
      templateFields: ephemeralFields,
      templateParams: sanitizedTemplateParams,
    }

    if (dateFormatValue) {
      payload.date_format = dateFormatValue
    }
    if (datetimeFormatValue) {
      payload.datetime_format = datetimeFormatValue
    }
    if (!isPreviewRequest) {
      payload.preview = false
    }

    await executeFileImport(payload, fileImportFile, isPreviewRequest)
  }

  const executeFileImport = async (
    payload: FileImportRequest,
    file: File | null,
    isPreviewRequest: boolean,
  ) => {
    setIsFileImporting(true)
    try {
      const result = await fileImportJob.run(payload, file)
      if (result === null) {
        setIsFileImportDialogOpen(false)
        resetFileImportForm()
        return
      }
      const resultErrors = result.errors ?? []
      const infoWarnings = resultErrors.filter(
        error => error.type === ImportErrorType.UNEXPECTED_COLUMN,
      )
      const blockingErrors = resultErrors.filter(
        error => error.type !== ImportErrorType.UNEXPECTED_COLUMN,
      )

      setImportInfoWarnings(infoWarnings.length > 0 ? infoWarnings : null)

      if (blockingErrors.length > 0) {
        setImportErrors(resultErrors)
        setImportErrorsContext(isPreviewRequest ? "preview" : "import")
        setShowErrorDetails(true)
      } else {
        setImportErrors(null)
        setImportErrorsContext(null)
        setShowErrorDetails(false)
      }

      if (result.code !== "COMPLETED") {
        if (result.code === ImportResultCode.PREVIEW_EXPIRED) {
          setAiPreview(null)
          setShowImportPreviewDialog(false)
          setImportPreviewData(null)
        }
        const code = result.code as keyof typeof t.errors
        const translated = (t.errors as Record<string, string>)[code]
        const message =
          translated && !translated.includes("{entity}")
            ? translated
            : t.export.fileImport.toast.error
        showToast(message, "error")
        return
      }

      const importData = (result.data as ImportedData) ?? null

      if (isPreviewRequest) {
        setAiPreview(
          result.previewToken
            ? {
                token: result.previewToken,
                request: payload,
                ai: result.ai ?? null,
              }
            : null,
        )
        setImportPreviewData(importData)
        setShowImportPreviewDialog(true)
        return
      }

      if (hasImportedContent(importData)) {
        showToast(t.export.fileImport.toast.success, "success")
      } else {
        showToast(t.export.fileImport.toast.empty, "warning")
      }
      setIsFileImportDialogOpen(false)
      setShowImportPreviewDialog(false)
      setImportPreviewData(null)
      resetFileImportForm()
      invalidateTransactionsCache()
      await Promise.all([fetchEntities(), refreshData()])
    } catch (error) {
      console.error("File import error:", error)
      let message = t.export.fileImport.toast.error
      if (error instanceof ApiErrorException) {
        const code = error.code as keyof typeof t.errors
        const translated = (t.errors as Record<string, string>)[code]
        if (translated && !translated.includes("{entity}")) {
          message = translated
        }
      }
      showToast(message, "error")
    } finally {
      setIsFileImporting(false)
    }
  }

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

    const entityTypeByName = new Map(
      (entities ?? [])
        .filter(entity => entity.name && entity.id)
        .map(entity => [entity.name.trim(), entity.type] as const),
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
          const entityType = entityValue
            ? entityTypeByName.get(entityValue)
            : undefined
          if (
            entityValue &&
            (!entityType ||
              !getImportEntityTypes(item?.data).includes(entityType)) &&
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
    return {
      POSITION: t.features.POSITION,
      AUTO_CONTRIBUTIONS: t.features.AUTO_CONTRIBUTIONS,
      TRANSACTIONS: t.features.TRANSACTIONS,
      HISTORIC: t.features.HISTORIC,
    }
  }, [t])

  const previewStrings = useMemo(
    () => t.export.fileImport.preview as FileImportPreviewStrings,
    [t],
  )

  const previewWarningStrings = useMemo(
    () => ({
      title: t.importErrors.unexpectedColumn,
      description: t.importErrors.unexpectedColumnMessage,
    }),
    [t],
  )

  const templateFieldLabels = useMemo(
    () => (t.export?.templates?.fieldLabels ?? {}) as Record<string, string>,
    [t],
  )

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

  const fileExportProductOptions = useMemo(() => {
    if (fileExportFeature === "POSITION") {
      return positionOptions
    }
    if (fileExportFeature === "TRANSACTIONS") {
      return transactionProductOptions
    }
    if (fileExportFeature === "HISTORIC") {
      return historicProductOptions
    }
    return []
  }, [
    fileExportFeature,
    positionOptions,
    transactionProductOptions,
    historicProductOptions,
  ])

  const quickExportPresets = useMemo<QuickExportPreset[]>(() => {
    const held = extractHeldProductTypes(positionsData)
    const presetTexts = t.export.file.quickPresets

    const positionPreset = (productType: ProductType): QuickExportPreset => ({
      key: `pos-${productType}`,
      label: productTypeLabels[productType] ?? productType,
      icon: getIconForAssetType(productType, "h-3.5 w-3.5"),
      feature: "POSITION",
      products: [productType],
    })

    if (held.size === 0) {
      return [
        positionPreset(ProductType.ACCOUNT),
        positionPreset(ProductType.STOCK_ETF),
        {
          key: "tx-account",
          label: presetTexts.accountMovements,
          icon: <ArrowLeftRight className="h-3.5 w-3.5 text-emerald-500" />,
          feature: "TRANSACTIONS",
          products: [ProductType.ACCOUNT],
        },
        {
          key: "tx-investments",
          label: presetTexts.fundAndStockOrders,
          icon: <TrendingUp className="h-3.5 w-3.5 text-blue-500" />,
          feature: "TRANSACTIONS",
          products: [ProductType.FUND, ProductType.STOCK_ETF],
        },
      ]
    }

    const heldPositionPresets = QUICK_EXPORT_POSITION_PRIORITY.filter(product =>
      held.has(product),
    )
      .slice(0, 4)
      .map(positionPreset)

    const txPresets: QuickExportPreset[] = []
    if (held.has(ProductType.ACCOUNT)) {
      txPresets.push({
        key: "tx-account",
        label: presetTexts.accountMovements,
        icon: <ArrowLeftRight className="h-3.5 w-3.5 text-emerald-500" />,
        feature: "TRANSACTIONS",
        products: [ProductType.ACCOUNT],
      })
    }
    if (held.has(ProductType.STOCK_ETF) && held.has(ProductType.FUND)) {
      txPresets.push({
        key: "tx-investments",
        label: presetTexts.fundAndStockOrders,
        icon: <TrendingUp className="h-3.5 w-3.5 text-blue-500" />,
        feature: "TRANSACTIONS",
        products: [ProductType.FUND, ProductType.STOCK_ETF],
      })
    } else if (held.has(ProductType.STOCK_ETF)) {
      txPresets.push({
        key: "tx-stocks",
        label: presetTexts.stockOrders,
        icon: <TrendingUp className="h-3.5 w-3.5 text-blue-500" />,
        feature: "TRANSACTIONS",
        products: [ProductType.STOCK_ETF],
      })
    } else if (held.has(ProductType.FUND)) {
      txPresets.push({
        key: "tx-funds",
        label: presetTexts.fundOrders,
        icon: <TrendingUp className="h-3.5 w-3.5 text-cyan-500" />,
        feature: "TRANSACTIONS",
        products: [ProductType.FUND],
      })
    }
    if (held.has(ProductType.CRYPTO) && txPresets.length < 2) {
      txPresets.push({
        key: "tx-crypto",
        label: presetTexts.cryptoMovements,
        icon: <ArrowLeftRight className="h-3.5 w-3.5 text-orange-500" />,
        feature: "TRANSACTIONS",
        products: [ProductType.CRYPTO],
      })
    }

    return [...heldPositionPresets, ...txPresets]
  }, [positionsData, productTypeLabels, t])

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
      showToast(t.settings.validationError, "error", { reportable: false })
      return
    }

    try {
      setIsSavingExportConfig(true)

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

      const settingsForSave: Partial<AppSettings> = {
        export: {
          ...(settings.export ?? {}),
          sheets: exportSheets,
        },
      }

      const processedSettings = processDataFields({ ...settingsForSave })
      const cleanedSettings = cleanObject(processedSettings) as
        Partial<AppSettings> | undefined

      const wasSaved = await saveSettings({
        export: cleanedSettings?.export ?? {},
      })
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
      showToast(t.settings.validationError, "error", { reportable: false })
      return
    }

    try {
      setIsSavingImportConfig(true)

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

      const settingsForSave: Partial<AppSettings> = {
        importing: {
          ...(settings.importing ?? {}),
          sheets: importConfig,
        },
      }

      const processedSettings = processDataFields({ ...settingsForSave })
      const cleanedSettings = cleanObject(processedSettings) as
        Partial<AppSettings> | undefined

      const wasSaved = await saveSettings({
        importing: cleanedSettings?.importing ?? {},
      })
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
      await fetchSettings(["export"])
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
      await fetchSettings(["importing"])
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
  const isGoogleSheetsIntegrationAvailable =
    googleSheetsIntegration?.available ?? true
  const canExport = isGoogleSheetsIntegrationEnabled && hasSheetSections
  const canImport = isGoogleSheetsIntegrationEnabled && hasImportSections
  const sheetsConfigured = hasSheetSections
  const importConfigured = hasImportSections

  const isExportDisabled =
    !canExport || exportState.isExporting || successAnimation
  const isImportDisabled = !canImport || isImporting || importSuccessAnimation

  const goToProviders = () => navigate("/entities?tab=providers")

  const IntegrationRequiredBadge = ({
    integrationName = getIntegrationName(
      t,
      "GOOGLE_SHEETS",
      googleSheetsIntegration,
    ),
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
          <Button size="sm" className="w-full mt-8" onClick={goToProviders}>
            <Settings className="mr-2 h-3 w-3" />
            {t.entities.goToProviders}
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
            { reportable: false },
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
        const importData = (response.data as ImportedData) ?? null
        const gotData = hasImportedContent(importData)
        if (gotData) {
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
    let result: ManualImportResult | null

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
        setImportErrorsContext("import")
        setShowErrorDetails(true)
      } else {
        setImportErrors(null)
        setImportErrorsContext(null)
      }

      if (gotData) {
        setImportSuccessAnimation(true)
      }

      invalidateTransactionsCache()
      try {
        await Promise.all([fetchEntities(), refreshData()])
      } finally {
        if (gotData) {
          setTimeout(() => {
            setImportSuccessAnimation(false)
          }, 2000)
        }
      }
    }
  }

  const handleOpenImport = () => {
    setImportErrors(null)
    setImportErrorsContext(null)
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
    setImportErrorsContext(null)
  }

  const handleCloseImportPreviewDialog = () => {
    if (isFileImporting) {
      return
    }
    setShowImportPreviewDialog(false)
    setImportPreviewData(null)
    setAiPreview(null)
  }

  const handleConfirmImportPreview = () => {
    if (isFileImporting) {
      return
    }
    void handleFileImport({ preview: false })
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

  const fileImportProductOptions = useMemo(() => {
    if (fileImportFeature === "POSITION") {
      return importPositionOptions
    }
    if (fileImportFeature === "TRANSACTIONS") {
      return importTransactionProductOptions
    }
    return []
  }, [
    fileImportFeature,
    importPositionOptions,
    importTransactionProductOptions,
  ])

  const previewUnnamedEntry = t.export.fileImport.preview.unnamedEntry

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
        if (
          templateManagerFromImportRef.current &&
          payload.type === TemplateType.IMPORT
        ) {
          templateManagerFromImportRef.current = false
          setTemplateCreatePreset(null)
          setIsTemplateDialogOpen(false)
          setPendingImportTemplateName(payload.name)
        }
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
    templateManagerFromImportRef.current = false
    setTemplateCreatePreset(null)
    setTemplateDialogType(type)
    setIsTemplateDialogOpen(true)
    if (!templatesLoaded[type]) {
      loadTemplates(type)
    }
    fetchTemplateFields()
  }

  const handleCloseTemplatesDialog = () => {
    templateManagerFromImportRef.current = false
    setTemplateCreatePreset(null)
    setIsTemplateDialogOpen(false)
  }

  const openImportTemplateManager = (preset: TemplateCreatePreset | null) => {
    handleOpenTemplatesDialog(TemplateType.IMPORT)
    templateManagerFromImportRef.current = true
    setTemplateCreatePreset(preset)
  }

  const handleCreateTemplateFromFile = () => {
    if (
      !fileImportAnalysis ||
      !fileImportFeature ||
      !fileImportProduct ||
      !fileImportFile
    ) {
      openImportTemplateManager(null)
      return
    }
    openImportTemplateManager({
      name: uniqueTemplateName(
        fileImportFile.name,
        templatesByType[TemplateType.IMPORT] ?? [],
      ),
      feature: fileImportFeature,
      product: fileImportProduct,
      fileName: fileImportFile.name,
      suggestion: fileImportAnalysis,
    })
  }

  const selectFileImportTemplate = useCallback(
    (templateId: string | null) => {
      setFileImportTemplate(
        templateId
          ? { id: templateId, params: {} as Record<string, string> }
          : null,
      )
      clearFileImportError("template")
    },
    [clearFileImportError],
  )

  const selectFileImportProduct = (product: ProductType) => {
    if (fileImportProduct === product) return
    setFileImportProduct(product)
    clearFileImportError("product")
    setFileImportEntityMode("select")
    setFileImportSelectedEntity("")
    setFileImportCustomEntity("")
    clearFileImportError("entity")
    const currentTemplate = fileImportTemplate
      ? (templatesByType[TemplateType.IMPORT] ?? []).find(
          template => template.id === fileImportTemplate.id,
        )
      : null
    if (
      fileImportTemplate &&
      !(currentTemplate && isTemplateForProduct(currentTemplate, product))
    ) {
      selectFileImportTemplate(null)
    }
  }

  const importTemplates = templatesByType[TemplateType.IMPORT]

  useEffect(() => {
    if (fileImportProductOptions.length === 1 && !fileImportProduct) {
      setFileImportProduct(fileImportProductOptions[0].value as ProductType)
    }
  }, [fileImportProductOptions, fileImportProduct])

  useEffect(() => {
    const requestId = ++fileImportAnalysisRequestRef.current
    setFileImportAnalysis(null)
    setFileImportAnalysisError(null)
    if (
      !isFileImportDialogOpen ||
      !fileImportFeature ||
      !fileImportProduct ||
      !fileImportFile ||
      fileImportUseAi
    ) {
      setIsAnalyzingImportFile(false)
      return
    }
    setIsAnalyzingImportFile(true)
    suggestTemplateFields(fileImportFile, fileImportFeature, fileImportProduct)
      .then(suggestion => {
        if (requestId !== fileImportAnalysisRequestRef.current) return
        setFileImportAnalysis(suggestion)
        if (suggestion.number_format) {
          setFileImportNumberFormat(suggestion.number_format)
        }
        setFileImportAutoCurrency(
          suggestion.detected_currency || defaultCurrency,
        )
        const bestMatch = suggestion.matching_templates?.[0]
        if (bestMatch) {
          setFileImportTemplate(
            prev =>
              prev ?? { id: bestMatch, params: {} as Record<string, string> },
          )
          clearFileImportError("template")
        } else {
          const missingNonCurrency = (
            suggestion.missing_required_fields ?? []
          ).filter(field => field !== "currency")
          if (suggestion.fields.length > 0 && missingNonCurrency.length === 0) {
            clearFileImportError("template")
          }
        }
      })
      .catch(error => {
        if (requestId !== fileImportAnalysisRequestRef.current) return
        const code =
          typeof error === "object" && error && "code" in error
            ? (error as { code?: unknown }).code
            : undefined
        setFileImportAnalysisError(
          code === "PDF_NO_TEXT_LAYER"
            ? "pdf_no_text"
            : code === "NO_TABLE_FOUND"
              ? "no_table"
              : code === "UNSUPPORTED_FILE_FORMAT"
                ? "unsupported"
                : "failed",
        )
      })
      .finally(() => {
        if (requestId === fileImportAnalysisRequestRef.current) {
          setIsAnalyzingImportFile(false)
        }
      })
  }, [
    isFileImportDialogOpen,
    fileImportFeature,
    fileImportProduct,
    fileImportFile,
    fileImportUseAi,
    importTemplates,
    defaultCurrency,
    clearFileImportError,
  ])

  const { job: currentImportJob, discard: discardImportJob } = fileImportJob
  useEffect(() => {
    const { status, reviewRequested, result, request } = currentImportJob
    if (status !== "ready" || !reviewRequested || !result || !request) return
    discardImportJob()
    setAiPreview(
      result.previewToken
        ? { token: result.previewToken, request, ai: result.ai ?? null }
        : null,
    )
    const resultErrors = result.errors ?? []
    const infoWarnings = resultErrors.filter(
      error => error.type === ImportErrorType.UNEXPECTED_COLUMN,
    )
    setImportInfoWarnings(infoWarnings.length > 0 ? infoWarnings : null)
    if (resultErrors.length > infoWarnings.length) {
      setImportErrors(resultErrors)
      setImportErrorsContext("preview")
      setShowErrorDetails(true)
    }
    setImportPreviewData((result.data as ImportedData) ?? null)
    setShowImportPreviewDialog(true)
  }, [currentImportJob, discardImportJob])

  useEffect(() => {
    if (!pendingImportTemplateName) return
    const created = (importTemplates ?? []).find(
      template => template.id && template.name === pendingImportTemplateName,
    )
    if (!created?.id) return
    setPendingImportTemplateName(null)
    if (
      created.feature === fileImportFeature &&
      (!fileImportProduct || isTemplateForProduct(created, fileImportProduct))
    ) {
      selectFileImportTemplate(created.id)
    }
  }, [
    pendingImportTemplateName,
    importTemplates,
    fileImportFeature,
    fileImportProduct,
    selectFileImportTemplate,
  ])

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

  useEffect(() => {
    if (!fileExportFeature) {
      setFileExportProducts([])
      return
    }
    const allowedProducts = FEATURE_PRODUCT_MAP[fileExportFeature] ?? []
    if (allowedProducts.length === 0) {
      setFileExportProducts([])
      return
    }
    setFileExportProducts(prev => {
      const filtered = prev.filter(product => allowedProducts.includes(product))
      if (filtered.length === prev.length) {
        return prev
      }
      return filtered
    })
  }, [fileExportFeature])

  useEffect(() => {
    if (!fileExportFeature || !fileExportTemplateId) {
      return
    }
    const templates = templatesByType[TemplateType.EXPORT] ?? []
    const matchesFeature = templates.some(
      template =>
        template.id === fileExportTemplateId &&
        template.feature === fileExportFeature,
    )
    if (!matchesFeature) {
      setFileExportTemplateId(null)
    }
  }, [fileExportFeature, fileExportTemplateId, templatesByType])

  const renderTemplatesCard = (type: TemplateType) => {
    const templateTexts = t.export.templates
    const templates = templatesByType[type] ?? []
    const isLoading = templatesLoading[type]
    const cardTitle = templateTexts.cardTitle[type]
    const countLabel =
      templates.length === 0
        ? templateTexts.cardNotConfigured
        : templateTexts.cardCountLabel.replace(
            "{count}",
            String(templates.length),
          )

    return (
      <Card
        key={`templates-${type}`}
        className={EDGE_CARD}
        data-testid={`templates-card-${type}`}
      >
        <CardContent className="flex items-center gap-3 px-4 py-3 sm:px-6">
          <LayoutTemplate className="h-5 w-5 shrink-0 text-primary" />
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
            <CardTitle className="text-base">{cardTitle}</CardTitle>
            <Badge variant="outline" className="text-center">
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
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={() => handleOpenTemplatesDialog(type)}
          >
            <LayoutTemplate className="mr-2 h-4 w-4" />
            {templateTexts.manageButton}
          </Button>
        </CardContent>
      </Card>
    )
  }

  const renderFileExportCard = () => (
    <Card className={EDGE_CARD}>
      <CardHeader className="space-y-3 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <FileText className="mr-2 h-5 w-5 text-primary" />
            <CardTitle>{t.export.file.cardTitle}</CardTitle>
          </div>
          <Badge variant="secondary" className="text-center">
            {t.export.file.singleRunBadge}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {t.export.file.cardDescription}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="-mx-6 border-y border-border/60 bg-muted/20 px-6 py-3.5">
          <div className="mb-2.5 text-xs font-medium text-muted-foreground">
            {t.export.file.quickPickLabel}
          </div>
          <div className="flex flex-wrap gap-2">
            {quickExportPresets.map(preset => (
              <button
                key={preset.key}
                type="button"
                onClick={() =>
                  handleOpenFileExportDialog({
                    feature: preset.feature,
                    products: preset.products,
                  })
                }
                className="inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-background/80 px-3 py-1 text-xs font-medium text-foreground shadow-sm transition-colors hover:border-primary/50 hover:bg-muted"
              >
                {preset.icon}
                <span>{preset.label}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="flex justify-end">
          <Button
            onClick={() => handleOpenFileExportDialog()}
            className="w-full sm:w-auto"
          >
            <Download className="mr-2 h-4 w-4" />
            {t.export.file.exportButton}
          </Button>
        </div>
      </CardContent>
    </Card>
  )

  const renderGoogleSheetsCard = () => (
    <Card
      className={cn(
        EDGE_CARD,
        !isGoogleSheetsIntegrationAvailable && "opacity-60",
      )}
    >
      <CardHeader className="space-y-4 pb-4">
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
      {isGoogleSheetsIntegrationAvailable &&
      isGoogleSheetsIntegrationEnabled ? (
        <CardContent className="space-y-4">
          <div className="-mx-6 border-y border-border/60 bg-muted/20 px-6 py-3.5">
            <div className="mb-2.5 text-xs font-medium text-muted-foreground">
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

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button
              onClick={handleExport}
              disabled={isExportDisabled}
              className={cn(
                "relative w-full sm:w-auto",
                exportState.isExporting && "opacity-100",
              )}
            >
              {exportState.isExporting && (
                <LoadingSpinner className="mr-2 h-5 w-5 text-current" />
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
            {isGoogleSheetsIntegrationAvailable
              ? t.export.integrationRequiredMessage
              : t.common.notAvailableOnPlatform}
          </p>
        </CardContent>
      )}
    </Card>
  )

  const renderGoogleSheetsImportCard = () => (
    <Card
      className={cn(
        EDGE_CARD,
        !isGoogleSheetsIntegrationAvailable && "opacity-60",
      )}
    >
      <CardHeader className="space-y-4 pb-4">
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
      {isGoogleSheetsIntegrationAvailable &&
      isGoogleSheetsIntegrationEnabled ? (
        <CardContent className="space-y-4">
          <div className="-mx-6 border-y border-border/60 bg-muted/20 px-6 py-3.5">
            <div className="mb-2.5 text-xs font-medium text-muted-foreground">
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

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <Button
              onClick={handleOpenImport}
              disabled={isImportDisabled}
              className="w-full sm:w-auto"
            >
              {isImporting ? (
                <LoadingSpinner className="mr-2 h-5 w-5 text-current" />
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
            {isGoogleSheetsIntegrationAvailable
              ? t.export.integrationRequiredMessage
              : t.common.notAvailableOnPlatform}
          </p>
        </CardContent>
      )}
    </Card>
  )

  const renderFileImportCard = () => (
    <Card className={EDGE_CARD}>
      <CardHeader className="space-y-3 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <FileUp className="mr-2 h-5 w-5 text-primary" />
            <CardTitle>{t.export.fileImport.cardTitle}</CardTitle>
          </div>
          <Badge variant="secondary" className="text-center">
            {t.export.fileImport.singleRunBadge}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {t.export.fileImport.cardDescription}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <input
          ref={fileImportCardInputRef}
          id="file-import-card-input"
          type="file"
          accept={FILE_IMPORT_ACCEPT}
          className="hidden"
          onChange={event => {
            const nextFile = event.target.files?.[0] ?? null
            event.target.value = ""
            if (nextFile) {
              handleOpenFileImportDialog(nextFile)
            }
          }}
        />
        <div
          role="button"
          tabIndex={0}
          onClick={() => fileImportCardInputRef.current?.click()}
          onKeyDown={event => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              fileImportCardInputRef.current?.click()
            }
          }}
          onDragEnter={event => {
            event.preventDefault()
            event.stopPropagation()
            setIsDraggingCardFile(true)
          }}
          onDragOver={event => {
            event.preventDefault()
            event.stopPropagation()
            setIsDraggingCardFile(true)
          }}
          onDragLeave={event => {
            event.preventDefault()
            event.stopPropagation()
            const next = event.relatedTarget as Node | null
            if (next && event.currentTarget.contains(next)) return
            setIsDraggingCardFile(false)
          }}
          onDrop={event => {
            event.preventDefault()
            event.stopPropagation()
            setIsDraggingCardFile(false)
            const droppedFile = event.dataTransfer.files?.[0] ?? null
            if (droppedFile) {
              handleOpenFileImportDialog(droppedFile)
            }
          }}
          className={cn(
            "group -mx-6 flex cursor-pointer items-center gap-3 border-y border-dashed px-6 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
            isDraggingCardFile
              ? "border-primary bg-primary/5"
              : "border-border/70 bg-muted/20 hover:border-primary/50 hover:bg-muted/40",
          )}
        >
          <div
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-md border transition-colors",
              isDraggingCardFile
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border/60 bg-background text-muted-foreground group-hover:text-foreground",
            )}
          >
            <FileUp className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground">
              {isDraggingCardFile
                ? t.export.fileImport.cardDropActive
                : t.export.fileImport.cardDropTitle}
            </p>
            <p className="text-xs text-muted-foreground">
              {t.export.fileImport.cardDropSubtitle}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          {fileImportJob.job.status === "running" &&
          fileImportJob.job.background ? (
            <span
              data-testid="file-import-running"
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <LoadingSpinner className="h-3.5 w-3.5" />
              {t.export.fileImport.background.running}
            </span>
          ) : null}
          {fileImportJob.job.status === "ready" ? (
            <Button
              variant="outline"
              className="w-full sm:w-auto"
              onClick={fileImportJob.requestReview}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {t.export.fileImport.background.review}
            </Button>
          ) : null}
          {fileImportJob.job.status === "running" &&
          fileImportJob.job.background ? null : (
            <Button
              onClick={() => handleOpenFileImportDialog()}
              disabled={fileImportJob.job.status === "running"}
              className="w-full sm:w-auto"
            >
              <FileUp className="mr-2 h-4 w-4" />
              {t.export.fileImport.importButton}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )

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
    const globalsError = exportValidationErrors.globals?.[0]
    const globals = exportConfigDraft
      ? ((exportConfigDraft.globals ?? {}) as Record<string, any>)
      : {}

    return (
      <AnimatePresence>
        {showExportConfig && exportConfigDraft && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-1 sm:p-3 lg:p-6"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-5xl"
            >
              <Card className="flex max-h-[90vh] flex-col">
                <CardContent className="flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
                  <div className="space-y-1 pb-1">
                    <h2 className="text-lg font-semibold">
                      {t.export.googleSheetsExportDialogTitle}
                    </h2>
                  </div>
                  <div className="space-y-2.5 rounded-lg border border-border/60 bg-muted/20 p-3 sm:space-y-3 sm:p-5">
                    <div>
                      <h3 className="text-sm font-semibold">
                        {t.settings.globals}
                      </h3>
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
                            handleExportGlobalChange(
                              "dateFormat",
                              event.target.value,
                            )
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
                    {EXPORT_SECTIONS.map(section =>
                      renderExportSection(section),
                    )}
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
                      {isRevertingExportConfig
                        ? t.common.loading
                        : t.common.discard}
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
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
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

                const allowedEntityTypes = getImportEntityTypes(
                  item?.data as string | undefined,
                )
                const importEntities = (entities ?? []).filter(
                  entity =>
                    entity.name &&
                    entity.id &&
                    allowedEntityTypes.includes(entity.type),
                )
                const entityValue =
                  (
                    item?.template?.params?.entity as string | undefined
                  )?.trim() ?? ""
                const isKnownEntity = importEntities.some(
                  entity => entity.name === entityValue,
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
                              <EntitySelector
                                id={`${itemKey}-entity`}
                                entities={importEntities}
                                selectedEntityIds={importEntities
                                  .filter(
                                    entity => entity.name === selectedEntity,
                                  )
                                  .map(entity => entity.id)}
                                onSelectionChange={ids => {
                                  const normalized =
                                    normalizeImportTemplateValue(item.template)
                                  if (!normalized?.id) {
                                    return
                                  }
                                  const nextParams = {
                                    ...(normalized.params ?? {}),
                                  }
                                  const entityName = importEntities.find(
                                    entity => entity.id === ids[0],
                                  )?.name
                                  if (entityName) {
                                    nextParams.entity = entityName
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
                                singleSelect
                                placeholder={t.export.import.entityPlaceholder}
                                className={cn(
                                  "max-w-none",
                                  entityError
                                    ? "border-red-500 ring-red-500/50"
                                    : undefined,
                                )}
                              />
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
    const globalsError = importValidationErrors.importGlobals?.[0]
    const globals = importConfigDraft
      ? ((importConfigDraft.globals ?? {}) as Record<string, any>)
      : {}

    return (
      <AnimatePresence>
        {showImportConfig && importConfigDraft && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-1 sm:p-3 lg:p-6"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-4xl"
            >
              <Card className="flex max-h-[90vh] flex-col">
                <CardContent className="flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
                  <div className="space-y-1 pb-1">
                    <h2 className="text-lg font-semibold">
                      {t.export.googleSheetsImportDialogTitle}
                    </h2>
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-yellow-600 dark:text-yellow-500" />
                      <p className="text-xs italic text-muted-foreground">
                        {t.export.googleSheetsImportDisclaimer}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2.5 rounded-lg border border-border/60 bg-muted/20 p-3 sm:space-y-3 sm:p-5">
                    <div>
                      <h3 className="text-sm font-semibold">
                        {t.settings.globals}
                      </h3>
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
                            handleImportGlobalChange(
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
                    {IMPORT_SECTIONS.map(section =>
                      renderImportSection(section),
                    )}
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
                      {isRevertingImportConfig
                        ? t.common.loading
                        : t.common.discard}
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
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    )
  }

  const renderImportPreviewDialog = () => (
    <FileImportPreviewDialog
      isOpen={showImportPreviewDialog}
      isLoading={isFileImporting}
      locale={locale}
      previewStrings={previewStrings}
      loadingLabel={t.common.loading}
      productTypeLabels={productTypeLabels}
      importData={importPreviewData}
      templateFieldLabels={templateFieldLabels ?? {}}
      previewUnnamedEntry={previewUnnamedEntry}
      warningStrings={previewWarningStrings}
      infoWarnings={importInfoWarnings}
      aiNotice={
        aiPreview?.ai
          ? t.export.fileImport.ai.extractedBy.replace(
              "{model}",
              aiPreview.ai.model,
            )
          : null
      }
      onClose={handleCloseImportPreviewDialog}
      onConfirm={handleConfirmImportPreview}
    />
  )

  const renderFileExportDialog = () => {
    const requiresProducts =
      fileExportFeature &&
      (FEATURE_PRODUCT_MAP[fileExportFeature]?.length ?? 0) > 0
    const exportTemplates = templatesByType[TemplateType.EXPORT] ?? []
    const filteredTemplates = exportTemplates.filter(template => {
      if (!template.id) {
        return false
      }
      if (!fileExportFeature) {
        return true
      }
      return template.feature === fileExportFeature
    })
    const templateOptions = [
      ...filteredTemplates.map(template => ({
        value: String(template.id),
        label: template.name,
      })),
      {
        value: CREATE_IMPORT_TEMPLATE_OPTION,
        label: t.export.templates.templateCreateOption,
        icon: PlusCircle,
      },
    ]
    const hasTemplateOptions = filteredTemplates.length > 0
    const selectedTemplateValues = fileExportTemplateId
      ? [fileExportTemplateId]
      : []
    const selectedExportTemplate = fileExportTemplateId
      ? (exportTemplates.find(
          template => template.id === fileExportTemplateId,
        ) ?? null)
      : null
    const exportTemporalCapabilities = getExportTemporalCapabilities(
      fileExportFeature,
      fileExportProducts,
      selectedExportTemplate,
    )

    const today = new Date()
    const todayIso = format(today, "yyyy-MM-dd")
    const currentYear = today.getFullYear()
    const lastYear = currentYear - 1
    const dateRangeTexts = t.export.file.dateRange
    const dateRangePresets = [
      {
        key: "allTime",
        label: dateRangeTexts.presets.allTime,
        from: "",
        to: "",
      },
      {
        key: "last30Days",
        label: dateRangeTexts.presets.last30Days,
        from: format(subDays(today, 30), "yyyy-MM-dd"),
        to: todayIso,
      },
      {
        key: "last3Months",
        label: dateRangeTexts.presets.last3Months,
        from: format(subMonths(today, 3), "yyyy-MM-dd"),
        to: todayIso,
      },
      {
        key: "last6Months",
        label: dateRangeTexts.presets.last6Months,
        from: format(subMonths(today, 6), "yyyy-MM-dd"),
        to: todayIso,
      },
      {
        key: "thisYear",
        label: dateRangeTexts.presets.thisYear,
        from: `${currentYear}-01-01`,
        to: todayIso,
      },
      {
        key: "lastYear",
        label: dateRangeTexts.presets.lastYear,
        from: `${lastYear}-01-01`,
        to: `${lastYear}-12-31`,
      },
    ]

    return (
      <AnimatePresence>
        {isFileExportDialogOpen && (
          <motion.div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-2 sm:p-3 lg:p-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-3xl min-w-0"
            >
              <Card className="flex max-h-[90vh] w-full min-w-0 flex-col overflow-hidden">
                <CardContent className="min-w-0 flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
                  <div className="space-y-1">
                    <h2 className="text-lg font-semibold">
                      {t.export.file.dialogTitle}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t.export.file.dialogDescription}
                    </p>
                  </div>

                  <div className="space-y-4">
                    {renderFileExportFeatureSelector()}

                    {requiresProducts ? (
                      <div className="space-y-1.5 sm:space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                          <Label className="mb-0">
                            {t.export.file.productsLabel}
                            <span className="ml-1 text-red-500">*</span>
                          </Label>
                          <span className="text-xs text-muted-foreground">
                            {t.export.file.productsHint}
                          </span>
                        </div>
                        {renderProductPills(
                          fileExportProductOptions,
                          product => fileExportProducts.includes(product),
                          product => {
                            setFileExportProducts(prev =>
                              prev.includes(product)
                                ? prev.filter(item => item !== product)
                                : [...prev, product],
                            )
                            clearFileExportError("products")
                          },
                          Boolean(fileExportErrors.products),
                        )}
                        {fileExportErrors.products ? (
                          <p className="text-xs text-red-500">
                            {fileExportErrors.products}
                          </p>
                        ) : null}
                      </div>
                    ) : fileExportFeature ? (
                      <p className="text-xs text-muted-foreground">
                        {t.export.file.productsInfo}
                      </p>
                    ) : null}

                    {fileExportFeature === "TRANSACTIONS" ? (
                      <div className="space-y-2">
                        <Label>{dateRangeTexts.label}</Label>
                        <div className="flex flex-wrap gap-1.5">
                          {dateRangePresets.map(preset => {
                            const isSelected =
                              fileExportFromDate === preset.from &&
                              fileExportToDate === preset.to
                            return (
                              <button
                                key={preset.key}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() => {
                                  setFileExportFromDate(preset.from)
                                  setFileExportToDate(preset.to)
                                  clearFileExportError("dateRange")
                                }}
                                className={cn(
                                  "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                                  isSelected
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {preset.label}
                              </button>
                            )
                          })}
                        </div>
                        <div className="grid gap-2.5 sm:grid-cols-2">
                          <DatePicker
                            id="file-export-from-date"
                            value={fileExportFromDate}
                            onChange={value => {
                              setFileExportFromDate(value)
                              clearFileExportError("dateRange")
                            }}
                            placeholder={dateRangeTexts.fromPlaceholder}
                            className={cn(
                              fileExportErrors.dateRange
                                ? "border-red-500"
                                : undefined,
                            )}
                          />
                          <DatePicker
                            id="file-export-to-date"
                            value={fileExportToDate}
                            onChange={value => {
                              setFileExportToDate(value)
                              clearFileExportError("dateRange")
                            }}
                            placeholder={dateRangeTexts.toPlaceholder}
                            className={cn(
                              fileExportErrors.dateRange
                                ? "border-red-500"
                                : undefined,
                            )}
                          />
                        </div>
                        {fileExportErrors.dateRange ? (
                          <p className="text-xs text-red-500">
                            {fileExportErrors.dateRange}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="space-y-1.5 sm:space-y-2">
                      <div className="flex items-center gap-2">
                        <Label className="mb-0" htmlFor="file-export-template">
                          {t.export.file.templateLabel}
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
                        options={templateOptions}
                        value={selectedTemplateValues}
                        onChange={value => {
                          const nextValue = value[value.length - 1] ?? null
                          if (nextValue === CREATE_IMPORT_TEMPLATE_OPTION) {
                            handleOpenTemplatesDialog(TemplateType.EXPORT)
                            return
                          }
                          setFileExportTemplateId(nextValue ?? null)
                        }}
                        placeholder={t.export.file.templatePlaceholder}
                        disabled={!fileExportFeature}
                        closeOnSelect
                      />
                      {!fileExportFeature ? (
                        <p className="text-xs text-muted-foreground">
                          {t.export.file.templateFeatureHint}
                        </p>
                      ) : !hasTemplateOptions ? (
                        <p className="text-xs text-muted-foreground">
                          {t.export.templates.templateSelectNoOptions}
                        </p>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          {t.export.file.templateInfo}
                        </p>
                      )}
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>{t.export.file.formatLabel}</Label>
                        <div className="flex flex-wrap gap-2">
                          {FILE_EXPORT_FORMATS.map(formatOption => {
                            const isSelected = fileExportFormat === formatOption
                            return (
                              <button
                                key={formatOption}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() =>
                                  setFileExportFormat(formatOption)
                                }
                                className={cn(
                                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                                  isSelected
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {t.export.file.formats[formatOption]}
                              </button>
                            )
                          })}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Label className="mb-0">
                            {t.export.file.numberFormatLabel}
                          </Label>
                          <Popover>
                            <PopoverTrigger asChild>
                              <button
                                type="button"
                                className="inline-flex rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                aria-label={t.export.file.numberFormatHint}
                              >
                                <Info className="h-3.5 w-3.5" />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent side="right" className="w-64">
                              <p className="text-sm">
                                {t.export.file.numberFormatHint}
                              </p>
                            </PopoverContent>
                          </Popover>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {NUMBER_FORMAT_OPTIONS.map(formatOption => {
                            const isSelected =
                              fileExportNumberFormat === formatOption
                            return (
                              <button
                                key={formatOption}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() =>
                                  setFileExportNumberFormat(formatOption)
                                }
                                className={cn(
                                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                                  isSelected
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {t.export.file.numberFormats[formatOption]}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    </div>

                    {exportTemporalCapabilities.hasDate ? (
                      <div className="space-y-2">
                        <Label>{t.settings.dateFormat}</Label>
                        <div
                          role="group"
                          aria-label={t.settings.dateFormat}
                          className="flex flex-wrap gap-2"
                        >
                          {FILE_EXPORT_DATE_FORMAT_PRESETS.map(preset => {
                            const isSelected =
                              fileExportDateFormatPreset === preset.key
                            return (
                              <button
                                key={preset.key}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() => {
                                  setFileExportDateFormatPreset(preset.key)
                                  setFileExportDateFormat(preset.value)
                                }}
                                className={cn(
                                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                                  isSelected
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {
                                  t.export.file.dateFormats.presets[
                                    preset.labelKey
                                  ]
                                }
                              </button>
                            )
                          })}
                          <button
                            type="button"
                            data-testid="file-export-date-format-custom"
                            aria-pressed={
                              fileExportDateFormatPreset === "CUSTOM"
                            }
                            onClick={() =>
                              setFileExportDateFormatPreset("CUSTOM")
                            }
                            className={cn(
                              "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                              fileExportDateFormatPreset === "CUSTOM"
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                            )}
                          >
                            {t.export.file.dateFormats.presets.custom}
                          </button>
                        </div>
                        {fileExportDateFormatPreset === "CUSTOM" ? (
                          <div className="space-y-1.5 pt-1">
                            <Input
                              id="file-export-date-format"
                              value={fileExportDateFormat}
                              onChange={event =>
                                setFileExportDateFormat(event.target.value)
                              }
                              placeholder={t.settings.dateFormatPlaceholder}
                            />
                            <p className="text-xs text-muted-foreground">
                              {t.export.file.dateFormats.customHint}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {exportTemporalCapabilities.hasDatetime ? (
                      <div className="space-y-2">
                        <Label>{t.settings.datetimeFormat}</Label>
                        <div
                          role="group"
                          aria-label={t.settings.datetimeFormat}
                          className="flex flex-wrap gap-2"
                        >
                          {FILE_EXPORT_DATETIME_FORMAT_PRESETS.map(preset => {
                            const isSelected =
                              fileExportDatetimeFormatPreset === preset.key
                            return (
                              <button
                                key={preset.key}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() => {
                                  setFileExportDatetimeFormatPreset(preset.key)
                                  setFileExportDatetimeFormat(preset.value)
                                }}
                                className={cn(
                                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                                  isSelected
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                {
                                  t.export.file.datetimeFormats.presets[
                                    preset.labelKey
                                  ]
                                }
                              </button>
                            )
                          })}
                          <button
                            type="button"
                            data-testid="file-export-datetime-format-custom"
                            aria-pressed={
                              fileExportDatetimeFormatPreset === "CUSTOM"
                            }
                            onClick={() =>
                              setFileExportDatetimeFormatPreset("CUSTOM")
                            }
                            className={cn(
                              "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                              fileExportDatetimeFormatPreset === "CUSTOM"
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
                            )}
                          >
                            {t.export.file.datetimeFormats.presets.custom}
                          </button>
                        </div>
                        {fileExportDatetimeFormatPreset === "CUSTOM" ? (
                          <div className="space-y-1.5 pt-1">
                            <Input
                              id="file-export-datetime-format"
                              value={fileExportDatetimeFormat}
                              onChange={event =>
                                setFileExportDatetimeFormat(event.target.value)
                              }
                              placeholder={t.settings.datetimeFormatPlaceholder}
                            />
                            <p className="text-xs text-muted-foreground">
                              {t.export.file.datetimeFormats.customHint}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </CardContent>
                <CardFooter className="flex items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCloseFileExportDialog}
                    disabled={isFileExporting}
                    className="inline-flex items-center gap-2"
                  >
                    <X className="h-4 w-4" />
                    {t.common.cancel}
                  </Button>
                  <Button
                    onClick={handleFileExport}
                    disabled={isFileExporting}
                    className="whitespace-nowrap"
                  >
                    {isFileExporting ? (
                      <LoadingSpinner className="mr-2 h-4 w-4" />
                    ) : (
                      <FileUp className="mr-2 h-4 w-4" />
                    )}
                    {isFileExporting
                      ? t.common.loading
                      : t.export.file.exportAction}
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    )
  }

  const renderFileImportDialog = () => {
    const requiresProducts =
      fileImportFeature &&
      (FEATURE_PRODUCT_MAP[fileImportFeature]?.length ?? 0) > 0
    const availableImportTemplates = importTemplates ?? []
    const filteredTemplates = availableImportTemplates.filter(template => {
      if (!template.id) {
        return false
      }
      if (!fileImportFeature) {
        return true
      }
      return (
        template.feature === fileImportFeature &&
        (!fileImportProduct ||
          isTemplateForProduct(template, fileImportProduct))
      )
    })
    const templateOptions = [
      ...filteredTemplates.map(template => ({
        value: String(template.id),
        label: template.name,
      })),
      {
        value: CREATE_IMPORT_TEMPLATE_OPTION,
        label: t.export.templates.templateCreateOption,
        icon: PlusCircle,
      },
    ]
    const hasTemplateOptions = filteredTemplates.length > 0
    const selectedTemplateValues = fileImportTemplate
      ? [fileImportTemplate.id]
      : []

    const allowedEntityTypes = getImportEntityTypes(fileImportProduct)
    const importEntities = (entities ?? []).filter(
      entity =>
        entity.name && entity.id && allowedEntityTypes.includes(entity.type),
    )
    const selectedImportEntityId = importEntities.find(
      entity => entity.name === fileImportSelectedEntity,
    )?.id

    const showEntitySelector =
      Boolean(
        fileImportUseAi || fileImportTemplate || canAutoImportWithoutTemplate,
      ) &&
      (fileImportFeature === "POSITION" || fileImportFeature === "TRANSACTIONS")
    const isCreatingEntity = fileImportEntityMode === "new"

    const analysisTexts = t.export.fileImport.analysis
    const formatTexts = t.export.fileImport.formatOptions
    const getImportFieldLabel = (fieldKey: string) => {
      const lookupKey = IMPORT_FIELD_LABEL_KEY_ALIASES[fieldKey] ?? fieldKey
      return templateFieldLabels[lookupKey] ?? fieldKey
    }
    const matchingTemplateIds = fileImportAnalysis?.matching_templates ?? []
    const bestMatchTemplate = matchingTemplateIds
      .map(id => filteredTemplates.find(template => template.id === id))
      .find(template => template !== undefined)
    const selectedImportTemplate = fileImportTemplate
      ? (availableImportTemplates.find(
          template => template.id === fileImportTemplate.id,
        ) ?? null)
      : null
    const selectedTemplateMatches =
      !!selectedImportTemplate?.id &&
      matchingTemplateIds.includes(selectedImportTemplate.id)
    const detectedDateFormat = fileImportAnalysis?.date_format || null
    const typedDateFormat =
      fileImportDateFormat.trim() || fileImportDatetimeFormat.trim()
    const dateFormatSummary =
      typedDateFormat ||
      (detectedDateFormat
        ? formatDetectedDatePattern(detectedDateFormat)
        : formatTexts.automatic)
    const formatsDetected =
      (!typedDateFormat && !!detectedDateFormat) ||
      !!fileImportAnalysis?.number_format
    const datePlaceholder =
      detectedDateFormat && detectedDateFormat !== "ISO"
        ? detectedDateFormat
        : t.settings.dateFormatPlaceholder

    const renderFileImportAnalysis = () => {
      if (!fileImportFile || !fileImportProduct) return null
      if (isAnalyzingImportFile) {
        return (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <LoadingSpinner className="h-3.5 w-3.5" />
            {analysisTexts.analyzing}
          </div>
        )
      }
      if (fileImportAnalysisError) {
        const errorMessage =
          fileImportAnalysisError === "pdf_no_text"
            ? t.errors.PDF_NO_TEXT_LAYER
            : fileImportAnalysisError === "no_table"
              ? t.errors.NO_TABLE_FOUND
              : fileImportAnalysisError === "unsupported"
                ? t.errors.UNSUPPORTED_FILE_FORMAT
                : analysisTexts.error
        return <p className="text-xs text-red-500">{errorMessage}</p>
      }
      if (!fileImportAnalysis) return null
      if (selectedImportTemplate && selectedTemplateMatches) {
        return (
          <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400">
            <Check className="h-4 w-4 shrink-0" />
            <span>
              {analysisTexts.matched.replace(
                "{template}",
                selectedImportTemplate.name,
              )}
            </span>
          </div>
        )
      }
      const createFromFileButton = (
        <Button
          type="button"
          size="sm"
          variant={
            selectedImportTemplate || canAutoImportWithoutTemplate
              ? "outline"
              : "default"
          }
          onClick={handleCreateTemplateFromFile}
        >
          <Sparkles className="mr-2 h-4 w-4" />
          {analysisTexts.createFromFile}
        </Button>
      )
      if (selectedImportTemplate) {
        return (
          <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
            <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {analysisTexts.mismatch.replace(
                  "{template}",
                  selectedImportTemplate.name,
                )}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {bestMatchTemplate?.id ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() =>
                    selectFileImportTemplate(bestMatchTemplate.id ?? null)
                  }
                >
                  {analysisTexts.useTemplate.replace(
                    "{template}",
                    bestMatchTemplate.name,
                  )}
                </Button>
              ) : canAutoImportWithoutTemplate ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => selectFileImportTemplate(null)}
                >
                  {analysisTexts.useAutoDetect}
                </Button>
              ) : null}
              {createFromFileButton}
            </div>
          </div>
        )
      }
      if (canAutoImportWithoutTemplate) {
        return (
          <div className="space-y-2.5 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-0.5 text-xs">
                <p className="flex items-center gap-1.5 font-medium text-emerald-700 dark:text-emerald-400">
                  <Check className="h-4 w-4 shrink-0" />
                  <span>{analysisTexts.autoReady}</span>
                </p>
                <p className="text-muted-foreground">
                  {analysisTexts.recognized
                    .replace(
                      "{count}",
                      String(fileImportAnalysis.fields.length),
                    )
                    .replace(
                      "{total}",
                      String(fileImportAnalysis.headers.length),
                    )}
                </p>
              </div>
              {createFromFileButton}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {fileImportAnalysis.fields.map(item => (
                <span
                  key={item.field}
                  className="inline-flex max-w-full min-w-0 items-center gap-1 rounded-full border border-border/70 bg-background/80 px-2 py-0.5 text-[11px] text-foreground"
                >
                  <span className="shrink-0 font-medium">
                    {getImportFieldLabel(item.field)}
                  </span>
                  <span className="truncate text-muted-foreground">
                    ← {item.name}
                  </span>
                </span>
              ))}
            </div>
            {needsAutoCurrencyFallback ? (
              <div className="flex flex-wrap items-center gap-2 border-t border-emerald-500/20 pt-2 text-xs">
                <Label
                  htmlFor="file-import-currency"
                  className="mb-0 text-xs font-medium"
                >
                  {analysisTexts.currencyLabel}
                </Label>
                <select
                  id="file-import-currency"
                  value={fileImportAutoCurrency}
                  onChange={event =>
                    setFileImportAutoCurrency(event.target.value)
                  }
                  className="h-7 rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {currencyOptions.map(code => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
                <span className="text-muted-foreground">
                  {fileImportAnalysis.detected_currency
                    ? analysisTexts.currencyDetectedHint
                    : analysisTexts.currencyDefaultHint}
                </span>
              </div>
            ) : null}
          </div>
        )
      }
      const missingLabels = unresolvableMissingFields
        .map(getImportFieldLabel)
        .join(", ")
      return (
        <div className="flex flex-col gap-3 rounded-md border border-primary/30 bg-primary/5 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-0.5 text-xs">
            <p className="font-medium text-foreground">
              {analysisTexts.noMatch}
            </p>
            <p className="text-muted-foreground">
              {analysisTexts.recognized
                .replace("{count}", String(fileImportAnalysis.fields.length))
                .replace("{total}", String(fileImportAnalysis.headers.length))}
            </p>
            {missingLabels ? (
              <p className="text-amber-600 dark:text-amber-400">
                {analysisTexts.missingRequired.replace(
                  "{fields}",
                  missingLabels,
                )}
              </p>
            ) : null}
          </div>
          {createFromFileButton}
        </div>
      )
    }

    const aiTexts = t.export.fileImport.ai
    const renderFileImportAi = () => {
      if (!fileImportFeature) return null
      const suggestAi =
        !fileImportUseAi &&
        (fileImportAnalysisError === "pdf_no_text" ||
          fileImportAnalysisError === "no_table" ||
          unresolvableMissingFields.length > 0)
      return (
        <div
          className={cn(
            "space-y-3 rounded-md border px-3 py-3",
            fileImportUseAi
              ? "border-primary/40 bg-primary/5"
              : "border-border/60",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <Label
              htmlFor="file-import-use-ai"
              className="mb-0 flex flex-col space-y-1"
            >
              <span className="flex items-center gap-1.5 font-medium">
                <Sparkles className="h-4 w-4 text-primary" />
                {aiTexts.toggle}
              </span>
              <span className="text-xs font-normal text-muted-foreground">
                {suggestAi ? aiTexts.suggest : aiTexts.hint}
              </span>
            </Label>
            <Switch
              id="file-import-use-ai"
              checked={fileImportUseAi}
              onCheckedChange={checked => {
                setFileImportUseAi(checked)
                clearFileImportError("template")
              }}
            />
          </div>
          {fileImportUseAi ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                {aiTexts.disclosure}
              </p>
              <CollapsibleNotes
                id="file-import-ai-instructions"
                label={aiTexts.instructionsLabel}
                value={fileImportAiInstructions}
                maxLength={1000}
                rows={2}
                placeholder={aiTexts.instructionsPlaceholder}
                onChange={setFileImportAiInstructions}
              />
            </div>
          ) : null}
        </div>
      )
    }

    return (
      <AnimatePresence>
        {isFileImportDialogOpen && (
          <motion.div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 p-2 sm:p-3 lg:p-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-3xl min-w-0"
            >
              <Card className="flex max-h-[90vh] w-full min-w-0 flex-col overflow-hidden">
                <CardContent className="min-w-0 flex-1 space-y-4 overflow-y-auto px-3 py-3 sm:space-y-6 sm:px-6 sm:py-5">
                  <div className="space-y-1">
                    <h2 className="text-lg font-semibold">
                      {t.export.fileImport.dialogTitle}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t.export.fileImport.dialogDescription}
                    </p>
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-yellow-600 dark:text-yellow-500" />
                      <p className="text-xs italic text-muted-foreground">
                        {t.export.fileImport.additiveDisclaimer}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {renderFileImportFeatureSelector()}

                    {requiresProducts ? (
                      <div className="space-y-1.5 sm:space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                          <Label className="mb-0">
                            {t.export.fileImport.productsLabel}
                            <span className="ml-1 text-red-500">*</span>
                          </Label>
                          <span className="text-xs text-muted-foreground">
                            {t.export.fileImport.productsHint}
                          </span>
                        </div>
                        {renderProductPills(
                          fileImportProductOptions,
                          product => fileImportProduct === product,
                          selectFileImportProduct,
                          Boolean(fileImportErrors.product),
                        )}
                        {fileImportErrors.product ? (
                          <p className="text-xs text-red-500">
                            {fileImportErrors.product}
                          </p>
                        ) : null}
                      </div>
                    ) : fileImportFeature ? (
                      <p className="text-xs text-muted-foreground">
                        {t.export.fileImport.productsInfo}
                      </p>
                    ) : null}

                    <div className="space-y-1.5 sm:space-y-2">
                      <Label htmlFor="file-import-input">
                        {t.export.fileImport.fileLabel}
                        <span className="ml-1 text-red-500">*</span>
                      </Label>
                      <input
                        ref={fileImportInputRef}
                        id="file-import-input"
                        type="file"
                        accept={FILE_IMPORT_ACCEPT}
                        className="hidden"
                        onChange={event => {
                          const nextFile = event.target.files?.[0] ?? null
                          setFileImportFile(nextFile)
                          if (nextFile && isAiOnlyImportFile(nextFile)) {
                            setFileImportUseAi(true)
                          }
                          clearFileImportError("file")
                        }}
                      />
                      <div
                        className={cn(
                          "flex min-w-0 flex-col gap-3 rounded-md border border-dashed border-border/70 bg-muted/30 px-4 py-3 text-sm transition-colors sm:flex-row sm:items-center sm:justify-between",
                          isDraggingFile
                            ? "border-primary bg-primary/5"
                            : fileImportErrors.file
                              ? "border-red-500 bg-red-500/5"
                              : "hover:border-border",
                        )}
                        onDragOver={event => {
                          event.preventDefault()
                          event.stopPropagation()
                          setIsDraggingFile(true)
                        }}
                        onDragEnter={event => {
                          event.preventDefault()
                          event.stopPropagation()
                          setIsDraggingFile(true)
                        }}
                        onDragLeave={event => {
                          event.preventDefault()
                          event.stopPropagation()
                          setIsDraggingFile(false)
                        }}
                        onDrop={event => {
                          event.preventDefault()
                          event.stopPropagation()
                          setIsDraggingFile(false)
                          const droppedFile =
                            event.dataTransfer.files?.[0] ?? null
                          if (droppedFile) {
                            setFileImportFile(droppedFile)
                            if (isAiOnlyImportFile(droppedFile)) {
                              setFileImportUseAi(true)
                            }
                            clearFileImportError("file")
                          }
                        }}
                      >
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full shrink-0 sm:w-auto"
                          onClick={() => fileImportInputRef.current?.click()}
                        >
                          <FileUp className="mr-2 h-4 w-4" />
                          {fileImportFile
                            ? t.export.fileImport.fileButtonChange
                            : t.export.fileImport.fileButton}
                        </Button>
                        <div className="flex min-w-0 flex-1 flex-col text-left sm:text-right">
                          <span
                            className={cn(
                              "truncate text-sm",
                              fileImportFile
                                ? "text-foreground"
                                : "text-muted-foreground",
                            )}
                          >
                            {fileImportFile
                              ? fileImportFile.name
                              : t.export.fileImport.filePlaceholder}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {fileImportFile
                              ? t.export.fileImport.fileHintSelected
                              : t.export.fileImport.fileHint}
                          </span>
                        </div>
                      </div>
                      {fileImportErrors.file ? (
                        <p className="text-xs text-red-500">
                          {fileImportErrors.file}
                        </p>
                      ) : null}
                      {fileImportUseAi ? null : renderFileImportAnalysis()}
                    </div>

                    {renderFileImportAi()}

                    {fileImportUseAi ? null : (
                      <div className="space-y-1.5 sm:space-y-2">
                        <div className="flex items-center gap-2">
                          <Label
                            className="mb-0"
                            htmlFor="file-import-template"
                          >
                            {t.export.fileImport.templateLabel}
                          </Label>
                          <Popover>
                            <PopoverTrigger asChild>
                              <button
                                className="inline-flex rounded text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                aria-label={
                                  t.export.templates.templateSelectInfo
                                }
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
                          value={selectedTemplateValues}
                          onChange={value => {
                            const nextValue = value[value.length - 1] ?? null
                            if (nextValue === CREATE_IMPORT_TEMPLATE_OPTION) {
                              handleCreateTemplateFromFile()
                              return
                            }
                            selectFileImportTemplate(nextValue)
                          }}
                          placeholder={t.export.fileImport.templatePlaceholder}
                          disabled={!fileImportFeature}
                          closeOnSelect
                          className={cn(
                            fileImportErrors.template
                              ? "[&>div:first-child]:border-red-500 [&>div:first-child]:ring-red-500/50"
                              : undefined,
                          )}
                        />
                        {fileImportErrors.template ? (
                          <p className="text-xs text-red-500">
                            {fileImportErrors.template}
                          </p>
                        ) : !fileImportFeature ? (
                          <p className="text-xs text-muted-foreground">
                            {t.export.fileImport.templateFeatureHint}
                          </p>
                        ) : !fileImportTemplate &&
                          canAutoImportWithoutTemplate ? (
                          <p className="text-xs text-muted-foreground">
                            {t.export.fileImport.templateOptionalHint}
                          </p>
                        ) : !hasTemplateOptions ? (
                          <p className="text-xs text-muted-foreground">
                            {t.export.templates.templateSelectNoOptions}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            {t.export.fileImport.templateInfo}
                          </p>
                        )}
                      </div>
                    )}

                    {showEntitySelector ? (
                      <div className="space-y-1.5 sm:space-y-2">
                        <div className="flex items-center gap-2">
                          <Label htmlFor="file-import-entity" className="mb-0">
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
                          <div className="min-w-0 flex-1">
                            {isCreatingEntity ? (
                              <Input
                                id="file-import-entity-input"
                                value={fileImportCustomEntity}
                                placeholder={t.export.import.entityPlaceholder}
                                onChange={event => {
                                  setFileImportCustomEntity(event.target.value)
                                  clearFileImportError("entity")
                                }}
                                className={cn(
                                  fileImportErrors.entity
                                    ? "border-red-500 focus-visible:ring-red-500"
                                    : undefined,
                                )}
                              />
                            ) : (
                              <EntitySelector
                                id="file-import-entity"
                                entities={importEntities}
                                selectedEntityIds={
                                  selectedImportEntityId
                                    ? [selectedImportEntityId]
                                    : []
                                }
                                onSelectionChange={ids => {
                                  setFileImportSelectedEntity(
                                    importEntities.find(
                                      entity => entity.id === ids[0],
                                    )?.name ?? "",
                                  )
                                  clearFileImportError("entity")
                                }}
                                singleSelect
                                placeholder={t.export.import.entityPlaceholder}
                                className={cn(
                                  "max-w-none",
                                  fileImportErrors.entity
                                    ? "border-red-500 ring-red-500/50"
                                    : undefined,
                                )}
                              />
                            )}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            onClick={() => {
                              clearFileImportError("entity")
                              if (isCreatingEntity) {
                                setFileImportEntityMode("select")
                                setFileImportCustomEntity("")
                              } else {
                                setFileImportEntityMode("new")
                                setFileImportSelectedEntity("")
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
                        {fileImportErrors.entity ? (
                          <p className="text-xs text-red-500">
                            {fileImportErrors.entity}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            {t.export.import.entityInfo}
                          </p>
                        )}
                      </div>
                    ) : null}

                    {fileImportUseAi ? null : (
                      <div className="min-w-0 rounded-md border border-border/60">
                        <button
                          type="button"
                          aria-expanded={showFileImportFormatOptions}
                          onClick={() =>
                            setShowFileImportFormatOptions(prev => !prev)
                          }
                          className="flex w-full min-w-0 items-center justify-between gap-3 px-3 py-2 text-left text-sm"
                        >
                          <span className="shrink-0 font-medium">
                            {formatTexts.title}
                          </span>
                          <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                            {formatsDetected ? (
                              <span title={formatTexts.detected}>
                                <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" />
                              </span>
                            ) : null}
                            <span className="truncate">
                              {formatTexts.dates}: {dateFormatSummary} ·{" "}
                              {formatTexts.decimals}:{" "}
                              {
                                t.export.fileImport.numberFormats[
                                  fileImportNumberFormat
                                ]
                              }
                            </span>
                            {showFileImportFormatOptions ? (
                              <ChevronUp className="h-4 w-4 shrink-0" />
                            ) : (
                              <ChevronDown className="h-4 w-4 shrink-0" />
                            )}
                          </span>
                        </button>
                        {showFileImportFormatOptions ? (
                          <div className="space-y-3 border-t border-border/60 px-3 py-3">
                            <div className="grid gap-2.5 sm:gap-3 lg:grid-cols-3">
                              <div className="space-y-1.5 sm:space-y-2">
                                <Label htmlFor="file-import-date-format">
                                  {t.settings.dateFormat}
                                </Label>
                                <Input
                                  id="file-import-date-format"
                                  value={fileImportDateFormat}
                                  onChange={event =>
                                    setFileImportDateFormat(event.target.value)
                                  }
                                  placeholder={datePlaceholder}
                                />
                              </div>
                              <div className="space-y-1.5 sm:space-y-2">
                                <Label htmlFor="file-import-datetime-format">
                                  {t.settings.datetimeFormat}
                                </Label>
                                <Input
                                  id="file-import-datetime-format"
                                  value={fileImportDatetimeFormat}
                                  onChange={event =>
                                    setFileImportDatetimeFormat(
                                      event.target.value,
                                    )
                                  }
                                  placeholder={
                                    t.settings.datetimeFormatPlaceholder
                                  }
                                />
                              </div>
                              <div className="space-y-1.5 sm:space-y-2">
                                <Label>
                                  {t.export.fileImport.numberFormatLabel}
                                </Label>
                                <div className="grid grid-cols-2 gap-2">
                                  {NUMBER_FORMAT_OPTIONS.map(formatOption => (
                                    <button
                                      key={formatOption}
                                      type="button"
                                      onClick={() =>
                                        setFileImportNumberFormat(formatOption)
                                      }
                                      className={cn(
                                        "rounded-md border px-3 py-2 text-sm font-medium transition-colors",
                                        fileImportNumberFormat === formatOption
                                          ? "border-primary bg-primary text-primary-foreground shadow-sm"
                                          : "border-border/70 text-muted-foreground hover:border-border hover:text-foreground",
                                      )}
                                    >
                                      {
                                        t.export.fileImport.numberFormats[
                                          formatOption
                                        ]
                                      }
                                    </button>
                                  ))}
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  {t.export.fileImport.numberFormatHint}
                                </p>
                              </div>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {t.export.fileImport.datetimeHint}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>
                </CardContent>
                <CardFooter className="flex items-center justify-end gap-2 border-t border-border/60 px-3 py-3 sm:px-6 sm:py-4">
                  {isFileImporting &&
                  fileImportJob.job.status === "running" &&
                  fileImportJob.job.useAi ? (
                    <Button
                      variant="outline"
                      size="sm"
                      data-testid="file-import-background"
                      onClick={fileImportJob.sendToBackground}
                    >
                      {t.export.fileImport.background.continue}
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCloseFileImportDialog}
                    disabled={isFileImporting}
                    className="inline-flex items-center gap-2"
                  >
                    <X className="h-4 w-4" />
                    {t.common.cancel}
                  </Button>
                  <Button
                    onClick={() => handleFileImport()}
                    disabled={isFileImporting}
                    className="whitespace-nowrap"
                  >
                    {isFileImporting ? (
                      <LoadingSpinner className="mr-2 h-4 w-4 text-current" />
                    ) : (
                      <FileUp className="mr-2 h-4 w-4" />
                    )}
                    {isFileImporting
                      ? t.common.loading
                      : t.export.fileImport.importAction}
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    )
  }

  return (
    <>
      <motion.div
        className="space-y-8"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <Tabs value={activeTab} className="space-y-6">
          <div className="space-y-4">
            <h1 className="text-3xl font-bold">{t.export.title}</h1>
            <PageTabs
              tabs={pageTabs}
              active={activeTab}
              onChange={setActiveTab}
              layoutId="export-import-tabs"
            />
          </div>

          <TabsContent value="export" className="space-y-6">
            <div className="grid items-start gap-4 lg:grid-cols-2">
              {renderFileExportCard()}
              {renderGoogleSheetsCard()}
            </div>
            {renderTemplatesCard(TemplateType.EXPORT)}
          </TabsContent>

          <TabsContent value="import" className="space-y-6">
            <div className="grid items-start gap-4 lg:grid-cols-2">
              {renderFileImportCard()}
              {renderGoogleSheetsImportCard()}
            </div>
            {renderTemplatesCard(TemplateType.IMPORT)}
            <AIImportSettingsCard className={EDGE_CARD} />
          </TabsContent>
        </Tabs>
      </motion.div>

      {renderFileExportDialog()}
      {renderFileImportDialog()}
      {renderExportConfigDialog()}
      {renderImportDialog()}
      {renderImportPreviewDialog()}

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
        onSuggestFields={suggestTemplateFields}
        createPreset={templateCreatePreset}
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
        description={
          importErrorsContext === "preview"
            ? t.importErrors.previewDescription
            : t.importErrors.description
        }
      />
    </>
  )
}
