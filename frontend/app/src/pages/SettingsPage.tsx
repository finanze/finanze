import { useState, useEffect, useCallback, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n, type Locale } from "@/i18n"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs"
import { Switch } from "@/components/ui/Switch"
import { MultiSelect, MultiSelectOption } from "@/components/ui/MultiSelect"
import { motion } from "framer-motion"
import {
  PlusCircle,
  Trash2,
  ChevronDown,
  ChevronUp,
  Save,
  RefreshCw,
  Info,
  Link2,
  Link2Off,
  AlertCircle,
  Settings,
  Coins,
  Edit2,
  X,
  Check,
} from "lucide-react"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { AppSettings, useAppContext } from "@/context/AppContext"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ProductType, WeightUnit } from "@/types/position"
import { setupIntegration, disableIntegration } from "@/services/api"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/lib/utils"
import {
  PlatformType,
  ExternalIntegrationStatus,
  type ExternalIntegration,
} from "@/types"

const isArray = (value: any): value is any[] => Array.isArray(value)

const cleanObject = (obj: any): any => {
  if (obj === null || obj === undefined) {
    return undefined
  }

  if (Array.isArray(obj)) {
    if (obj.length === 0) {
      return undefined
    }
    const cleanedArray = obj
      .map(item => cleanObject(item))
      .filter(item => item !== undefined)
    return cleanedArray.length > 0 ? cleanedArray : undefined
  }

  if (typeof obj === "object") {
    const cleanedObj: Record<string, any> = {}
    let hasValues = false

    for (const [key, value] of Object.entries(obj)) {
      const cleanedValue = cleanObject(value)
      if (cleanedValue !== undefined) {
        cleanedObj[key] = cleanedValue
        hasValues = true
      }
    }

    return hasValues ? cleanedObj : undefined
  }

  if (obj === null || obj === "") {
    return undefined
  }

  return obj
}

const STABLECOIN_ALLOWED_CHARS = /[^A-Z0-9.-]/g
const STABLECOIN_SYMBOL_REGEX = /^[A-Z0-9.-]{1,20}$/
const normalizeStablecoinSymbol = (value: string) =>
  value.toUpperCase().replace(STABLECOIN_ALLOWED_CHARS, "")

const APPLICATION_LOCALES: Locale[] = ["en-US", "es-ES"]

export default function SettingsPage() {
  const { t, locale, changeLocale } = useI18n()
  const [searchParams] = useSearchParams()
  const {
    showToast,
    fetchSettings,
    settings: storedSettings,
    saveSettings,
    isLoadingSettings,
    externalIntegrations,
    fetchExternalIntegrations,
    platform,
  } = useAppContext()
  const [settings, setSettings] = useState<AppSettings>(storedSettings)
  const [isSaving, setIsSaving] = useState(false)
  const [isSetupLoading, setIsSetupLoading] = useState<Record<string, boolean>>(
    {},
  )
  const [isDisableLoading, setIsDisableLoading] = useState<
    Record<string, boolean>
  >({})
  const [integrationPayloads, setIntegrationPayloads] = useState<
    Record<string, Record<string, string>>
  >({})
  const [integrationErrors, setIntegrationErrors] = useState<
    Record<string, Record<string, boolean>>
  >({})
  const [activeTab, setActiveTab] = useState(
    searchParams.get("tab") || "general",
  )
  const showRefreshButton = activeTab !== "application"
  const showSaveButton =
    activeTab !== "application" && activeTab !== "integrations"
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    assetsCrypto: false,
    position: false,
    contributions: false,
    transactions: false,
    historic: false,
    virtualPosition: false,
    virtualTransactions: false,
  })
  const [expandedIntegrations, setExpandedIntegrations] = useState<
    Record<string, boolean>
  >({})
  // Track which integration card should receive a temporary highlight
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const [validationErrors, setValidationErrors] = useState<
    Record<string, string[]>
  >({})

  const [newStablecoin, setNewStablecoin] = useState("")
  const [editingStablecoinIndex, setEditingStablecoinIndex] = useState<
    number | null
  >(null)
  const [stablecoinDraft, setStablecoinDraft] = useState("")
  const [isAddingStablecoin, setIsAddingStablecoin] = useState(false)
  const newStablecoinInputRef = useRef<HTMLInputElement | null>(null)
  const stablecoins = settings.assets?.crypto?.stablecoins ?? []
  const hideUnknownTokens = settings.assets?.crypto?.hideUnknownTokens ?? false

  const applicationLanguageOptions = APPLICATION_LOCALES.map(code => ({
    code,
    label: t.settings.applicationLanguageOptions[code],
  }))

  const resolveIntegrationCopy = useCallback(
    (integration: ExternalIntegration) => {
      let title = integration.name
      let description: string | undefined
      const settingsCopy = t.settings as any

      if (integration.id === "GOOGLE_SHEETS") {
        title = settingsCopy?.sheetsIntegration ?? title
        description = settingsCopy?.sheetsIntegrationDescription
      } else if (integration.id === "ETHERSCAN") {
        title = settingsCopy?.etherscanIntegration ?? title
        description = settingsCopy?.etherscanIntegrationDescription
      } else if (integration.id === "GOCARDLESS") {
        title = settingsCopy?.goCardlessIntegration ?? title
        description = settingsCopy?.goCardlessIntegrationDescription
      }

      return { title, description }
    },
    [t],
  )

  const formatIntegrationMessage = useCallback(
    (message: string, integrationName: string) =>
      message
        .replace(/\{entity\}/g, integrationName)
        .replace(/\{integration\}/g, integrationName),
    [],
  )

  const updateStablecoins = useCallback(
    (updater: (current: string[]) => string[]) => {
      setSettings(prev => ({
        ...prev,
        assets: {
          ...prev.assets,
          crypto: {
            ...prev.assets?.crypto,
            stablecoins: updater(prev.assets?.crypto?.stablecoins ?? []),
          },
        },
      }))
    },
    [setSettings],
  )

  const handleHideUnknownTokensChange = useCallback(
    (checked: boolean) => {
      setSettings(prev => ({
        ...prev,
        assets: {
          ...prev.assets,
          crypto: {
            ...prev.assets?.crypto,
            hideUnknownTokens: checked,
          },
        },
      }))
    },
    [setSettings],
  )

  const handleAddStablecoin = useCallback(() => {
    const value = normalizeStablecoinSymbol(newStablecoin.trim())

    if (!value || !STABLECOIN_SYMBOL_REGEX.test(value)) {
      showToast(t.settings.assets.crypto.invalidSymbol, "warning")
      return
    }

    if (stablecoins.includes(value)) {
      showToast(t.settings.assets.crypto.duplicateSymbol, "warning")
      return
    }

    updateStablecoins(prev => [...prev, value])
    setNewStablecoin("")
    requestAnimationFrame(() => {
      newStablecoinInputRef.current?.focus()
    })
  }, [
    newStablecoin,
    newStablecoinInputRef,
    showToast,
    stablecoins,
    t,
    updateStablecoins,
  ])

  const handleRemoveStablecoin = useCallback(
    (index: number) => {
      updateStablecoins(prev => prev.filter((_, i) => i !== index))

      if (editingStablecoinIndex === index) {
        setEditingStablecoinIndex(null)
        setStablecoinDraft("")
      }
    },
    [editingStablecoinIndex, updateStablecoins],
  )

  const handleStartEditStablecoin = useCallback(
    (index: number) => {
      setIsAddingStablecoin(false)
      setNewStablecoin("")
      setEditingStablecoinIndex(index)
      setStablecoinDraft(stablecoins[index] ?? "")
    },
    [stablecoins],
  )

  const handleConfirmEditStablecoin = useCallback(() => {
    if (editingStablecoinIndex === null) {
      return
    }

    const value = normalizeStablecoinSymbol(stablecoinDraft.trim())

    if (!value || !STABLECOIN_SYMBOL_REGEX.test(value)) {
      showToast(t.settings.assets.crypto.invalidSymbol, "warning")
      return
    }

    if (
      stablecoins.some(
        (coin, index) => index !== editingStablecoinIndex && coin === value,
      )
    ) {
      showToast(t.settings.assets.crypto.duplicateSymbol, "warning")
      return
    }

    updateStablecoins(prev =>
      prev.map((coin, index) =>
        index === editingStablecoinIndex ? value : coin,
      ),
    )

    setEditingStablecoinIndex(null)
    setStablecoinDraft("")
  }, [
    editingStablecoinIndex,
    showToast,
    stablecoinDraft,
    stablecoins,
    t,
    updateStablecoins,
  ])

  const handleCancelEditStablecoin = useCallback(() => {
    setEditingStablecoinIndex(null)
    setStablecoinDraft("")
  }, [])

  const handleCancelAddStablecoin = useCallback(() => {
    setIsAddingStablecoin(false)
    setNewStablecoin("")
  }, [])

  const handleStartAddStablecoin = useCallback(() => {
    setEditingStablecoinIndex(null)
    setStablecoinDraft("")
    setIsAddingStablecoin(true)
    setNewStablecoin("")
    requestAnimationFrame(() => {
      newStablecoinInputRef.current?.focus()
    })
  }, [])

  useEffect(() => {
    if (isAddingStablecoin && expandedSections.assetsCrypto) {
      requestAnimationFrame(() => {
        newStablecoinInputRef.current?.focus()
      })
    }
  }, [expandedSections.assetsCrypto, isAddingStablecoin])

  const availablePositionOptions = [
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
  ]

  // Helper function to check if Google Sheets integration is enabled
  const isGoogleSheetsIntegrationEnabled = () => {
    const googleIntegration = externalIntegrations.find(
      integration => integration.id === "GOOGLE_SHEETS",
    )
    return googleIntegration?.status === ExternalIntegrationStatus.ON
  }

  const getPositionDataOptions = (): MultiSelectOption[] => {
    const options: MultiSelectOption[] = []
    const productTypeOptions = (t.enums as any).productType || {}

    availablePositionOptions.forEach(productType => {
      if (productTypeOptions[productType]) {
        options.push({
          value: productType,
          label: productTypeOptions[productType] as string,
        })
      }
    })

    return options
  }

  const getContributionsDataOptions = (): MultiSelectOption[] => {
    const options: MultiSelectOption[] = []
    const contributionsDataOptions =
      (t.settings as any).contributionsDataOptions || {}

    Object.entries(contributionsDataOptions).forEach(([value, label]) => {
      options.push({ value, label: label as string })
    })

    return options
  }

  const getTransactionsDataOptions = (): MultiSelectOption[] => {
    const options: MultiSelectOption[] = []
    const transactionsDataOptions =
      (t.settings as any).transactionsDataOptions || {}

    Object.entries(transactionsDataOptions).forEach(([value, label]) => {
      options.push({ value, label: label as string })
    })

    return options
  }

  useEffect(() => {
    fetchSettings()
    fetchExternalIntegrations()
  }, [])

  useEffect(() => {
    setIntegrationPayloads(prev => {
      const next: Record<string, Record<string, string>> = {}

      externalIntegrations.forEach(integration => {
        const schema = integration.payload_schema ?? {}
        const existing = prev[integration.id] ?? {}
        const payload: Record<string, string> = {}

        Object.keys(schema).forEach(field => {
          payload[field] = existing[field] ?? ""
        })

        next[integration.id] = payload
      })

      return next
    })

    setIntegrationErrors(prev => {
      const next: Record<string, Record<string, boolean>> = {}

      externalIntegrations.forEach(integration => {
        const schemaFields = Object.keys(integration.payload_schema ?? {})
        const existingErrors = prev[integration.id]

        if (existingErrors) {
          const filtered: Record<string, boolean> = {}
          schemaFields.forEach(field => {
            if (existingErrors[field]) {
              filtered[field] = true
            }
          })

          if (Object.keys(filtered).length > 0) {
            next[integration.id] = filtered
          }
        }
      })

      return next
    })

    setExpandedIntegrations(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        next[integration.id] = prev[integration.id] ?? false
      })

      return next
    })

    setIsSetupLoading(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        if (prev[integration.id]) {
          next[integration.id] = prev[integration.id]
        }
      })

      return next
    })

    setIsDisableLoading(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        if (prev[integration.id]) {
          next[integration.id] = prev[integration.id]
        }
      })

      return next
    })
  }, [externalIntegrations])

  // When arriving with a focus query param expand and highlight integration card
  useEffect(() => {
    const focus = searchParams.get("focus")
    if (!focus) {
      return
    }

    const integrationId = focus.toUpperCase()
    const exists = externalIntegrations.some(
      integration => integration.id === integrationId,
    )

    if (!exists) {
      return
    }

    if (activeTab !== "integrations") {
      setActiveTab("integrations")
    }

    setExpandedIntegrations(prev => {
      if (prev[integrationId]) {
        return prev
      }

      return {
        ...prev,
        [integrationId]: true,
      }
    })
    setHighlighted(integrationId)

    const timer = setTimeout(() => setHighlighted(null), 3500)
    return () => clearTimeout(timer)
  }, [activeTab, externalIntegrations, searchParams])

  // Auto-disable export and virtual settings when Google Sheets integration is disabled
  useEffect(() => {
    if (!isGoogleSheetsIntegrationEnabled()) {
      setSettings(prev => ({
        ...prev,
        export: {
          ...prev.export,
          sheets: {
            ...prev.export?.sheets,
            enabled: false,
          },
        },
        fetch: {
          ...prev.fetch,
          virtual: {
            ...prev.fetch?.virtual,
            enabled: false,
          },
        },
      }))
    }
  }, [isGoogleSheetsIntegrationEnabled()])

  const toggleSection = (section: string) => {
    setExpandedSections({
      ...expandedSections,
      [section]: !expandedSections[section],
    })
  }

  const toggleIntegrationCard = (integrationId: string) => {
    setExpandedIntegrations(prev => ({
      ...prev,
      [integrationId]: !prev[integrationId],
    }))
  }

  const handleExportToggle = (enabled: boolean) => {
    // Don't allow enabling if Google Sheets integration is not enabled
    if (enabled && !isGoogleSheetsIntegrationEnabled()) {
      return
    }

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          enabled,
        },
      },
    })
  }

  const handleVirtualToggle = (enabled: boolean) => {
    // Don't allow enabling if Google Sheets integration is not enabled
    if (enabled && !isGoogleSheetsIntegrationEnabled()) {
      return
    }

    setSettings({
      ...settings,
      fetch: {
        ...settings.fetch,
        virtual: {
          ...settings.fetch.virtual,
          enabled,
        },
      },
    })
  }

  const handleCurrencyChange = (currency: string) => {
    setSettings({
      ...settings,
      general: {
        ...settings.general,
        defaultCurrency: currency,
      },
    })
  }

  const handleCommodityWeightUnitChange = (unit: string) => {
    setSettings({
      ...settings,
      general: {
        ...settings.general,
        defaultCommodityWeightUnit: unit,
      },
    })
  }

  const handleIntegrationFieldChange = useCallback(
    (integrationId: string, field: string, value: string) => {
      setIntegrationPayloads(prev => ({
        ...prev,
        [integrationId]: {
          ...(prev[integrationId] ?? {}),
          [field]: value,
        },
      }))

      setIntegrationErrors(prev => {
        const current = prev[integrationId]
        if (!current || !current[field]) {
          return prev
        }

        const updatedIntegrationErrors = { ...current, [field]: false }
        const next = { ...prev, [integrationId]: updatedIntegrationErrors }

        if (Object.values(updatedIntegrationErrors).every(error => !error)) {
          delete next[integrationId]
        }

        return next
      })
    },
    [],
  )

  const handleSetupIntegration = useCallback(
    async (integrationId: string) => {
      const integration = externalIntegrations.find(
        item => item.id === integrationId,
      )

      if (!integration) {
        return
      }

      const { title: integrationName } = resolveIntegrationCopy(integration)

      if (integrationId === "GOOGLE_SHEETS" && platform === PlatformType.WEB) {
        showToast(t.settings.googleSheetsWebDisabled, "warning")
        return
      }

      const schema = integration.payload_schema ?? {}
      const payload = integrationPayloads[integrationId] ?? {}

      const requiredFields = Object.keys(schema)
      const missingFields: Record<string, boolean> = {}

      requiredFields.forEach(field => {
        if (!payload[field] || payload[field].trim() === "") {
          missingFields[field] = true
        }
      })

      if (Object.keys(missingFields).length > 0) {
        setIntegrationErrors(prev => ({
          ...prev,
          [integrationId]: {
            ...(prev[integrationId] ?? {}),
            ...missingFields,
          },
        }))
        showToast(t.settings.validationError, "error")
        return
      }

      const sanitizedPayload: Record<string, string> = {}
      requiredFields.forEach(field => {
        if (payload[field] !== undefined) {
          sanitizedPayload[field] = payload[field].trim()
        }
      })

      setIsSetupLoading(prev => ({ ...prev, [integrationId]: true }))

      try {
        await setupIntegration(integrationId, sanitizedPayload)
        setIntegrationErrors(prev => {
          if (!prev[integrationId]) {
            return prev
          }

          const rest = { ...prev }
          delete rest[integrationId]
          return rest
        })
        const successMessage = formatIntegrationMessage(
          t.settings.integrationEnabledSuccess,
          integrationName,
        )
        showToast(successMessage, "success")
        await fetchExternalIntegrations()
      } catch (error) {
        console.error(error)
        const code = (error as any)?.code
        const translated = (code && (t.errors as any)?.[code]) || t.common.error
        const formattedError = formatIntegrationMessage(
          translated,
          integrationName,
        )
        showToast(formattedError, "error")
      } finally {
        setIsSetupLoading(prev => ({ ...prev, [integrationId]: false }))
      }
    },
    [
      externalIntegrations,
      fetchExternalIntegrations,
      formatIntegrationMessage,
      integrationPayloads,
      platform,
      resolveIntegrationCopy,
      showToast,
      t,
    ],
  )

  const handleDisableIntegration = useCallback(
    async (integrationId: string) => {
      const integration = externalIntegrations.find(
        item => item.id === integrationId,
      )

      if (!integration) {
        return
      }

      const { title: integrationName } = resolveIntegrationCopy(integration)

      setIsDisableLoading(prev => ({ ...prev, [integrationId]: true }))

      try {
        await disableIntegration(integrationId)
        const successMessage = formatIntegrationMessage(
          t.settings.integrationDisabledSuccess,
          integrationName,
        )
        showToast(successMessage, "success")
        await fetchExternalIntegrations()
      } catch (error) {
        console.error(error)
        const code = (error as any)?.code
        const translated = (code && (t.errors as any)?.[code]) || t.common.error
        const formatted = formatIntegrationMessage(translated, integrationName)
        showToast(formatted, "error")
      } finally {
        setIsDisableLoading(prev => ({ ...prev, [integrationId]: false }))
      }
    },
    [
      externalIntegrations,
      fetchExternalIntegrations,
      formatIntegrationMessage,
      resolveIntegrationCopy,
      showToast,
      t,
    ],
  )

  const addConfigItem = (section: string) => {
    const newItem: any = { range: "" }

    if (
      section === "position" ||
      section === "transactions" ||
      section === "contributions"
    ) {
      newItem.data = []
    }

    if (
      section === "historic" ||
      section === "position" ||
      section === "contributions"
    ) {
      newItem.filters = []
    }

    setSettings({
      ...settings,
      export: {
        ...(settings.export || {}),
        sheets: {
          ...(settings.export?.sheets || {}),
          [section]: [
            ...((settings.export?.sheets?.[
              section as keyof typeof settings.export.sheets
            ] as any[]) || []),
            newItem,
          ],
        },
      },
    })
  }

  const removeConfigItem = (section: string, index: number) => {
    const newValidationErrors = { ...validationErrors }
    if (newValidationErrors[section]) {
      newValidationErrors[section] = newValidationErrors[section].filter(
        (_, i) => i !== index,
      )
      if (newValidationErrors[section].length === 0) {
        delete newValidationErrors[section]
      }
      setValidationErrors(newValidationErrors)
    }

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          [section]: (
            settings.export?.sheets?.[
              section as keyof typeof settings.export.sheets
            ] as any[]
          ).filter((_, i) => i !== index),
        },
      },
    })
  }

  const addVirtualConfigItem = (section: string) => {
    const newItem: any = { range: "" }

    if (section === "position" || section === "transactions") {
      newItem.data = ""
    }

    setSettings({
      ...settings,
      fetch: {
        ...(settings.fetch || {}),
        virtual: {
          ...(settings.fetch?.virtual || {}),
          [section]: [
            ...((settings.fetch?.virtual?.[
              section as keyof typeof settings.fetch.virtual
            ] as any[]) || []),
            newItem,
          ],
        },
      },
    })
  }

  const removeVirtualConfigItem = (section: string, index: number) => {
    const newValidationErrors = { ...validationErrors }
    const virtualKey = `virtual_${section}`
    if (newValidationErrors[virtualKey]) {
      newValidationErrors[virtualKey] = newValidationErrors[virtualKey].filter(
        (_, i) => i !== index,
      )
      if (newValidationErrors[virtualKey].length === 0) {
        delete newValidationErrors[virtualKey]
      }
      setValidationErrors(newValidationErrors)
    }

    setSettings({
      ...settings,
      fetch: {
        ...settings.fetch,
        virtual: {
          ...settings.fetch.virtual,
          [section]: (
            settings.fetch.virtual[
              section as keyof typeof settings.fetch.virtual
            ] as any[]
          ).filter((_, i) => i !== index),
        },
      },
    })
  }

  const addFilter = (section: string, itemIndex: number) => {
    const items = settings.export?.sheets?.[
      section as keyof typeof settings.export.sheets
    ] as any[]
    const updatedItems = [...items]

    if (!updatedItems[itemIndex].filters) {
      updatedItems[itemIndex].filters = []
    }

    updatedItems[itemIndex].filters.push({ field: "", values: "" })

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          [section]: updatedItems,
        },
      },
    })
  }

  const removeFilter = (
    section: string,
    itemIndex: number,
    filterIndex: number,
  ) => {
    const items = settings.export?.sheets?.[
      section as keyof typeof settings.export.sheets
    ] as any[]
    const updatedItems = [...items]

    updatedItems[itemIndex].filters = updatedItems[itemIndex].filters.filter(
      (_: any, i: number) => i !== filterIndex,
    )

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          [section]: updatedItems,
        },
      },
    })
  }

  const updateConfigItem = (
    section: string,
    index: number,
    field: string,
    value: any,
  ) => {
    const items = settings.export?.sheets?.[
      section as keyof typeof settings.export.sheets
    ] as any[]
    const updatedItems = [...items]

    updatedItems[index] = { ...updatedItems[index], [field]: value }

    if ((field === "range" || field === "data") && value && value.length > 0) {
      const newValidationErrors = { ...validationErrors }
      if (newValidationErrors[section] && newValidationErrors[section][index]) {
        newValidationErrors[section][index] = ""
        if (newValidationErrors[section].every(err => !err)) {
          delete newValidationErrors[section]
        }
        setValidationErrors(newValidationErrors)
      }
    }

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          [section]: updatedItems,
        },
      },
    })
  }

  const updateVirtualConfigItem = (
    section: string,
    index: number,
    field: string,
    value: any,
  ) => {
    const items = settings.fetch.virtual[
      section as keyof typeof settings.fetch.virtual
    ] as any[]
    const updatedItems = [...items]

    updatedItems[index] = { ...updatedItems[index], [field]: value }

    if ((field === "range" || field === "data") && value) {
      const virtualKey = `virtual_${section}`
      const newValidationErrors = { ...validationErrors }
      if (
        newValidationErrors[virtualKey] &&
        newValidationErrors[virtualKey][index]
      ) {
        newValidationErrors[virtualKey][index] = ""
        if (newValidationErrors[virtualKey].every(err => !err)) {
          delete newValidationErrors[virtualKey]
        }
        setValidationErrors(newValidationErrors)
      }
    }

    setSettings({
      ...settings,
      fetch: {
        ...settings.fetch,
        virtual: {
          ...settings.fetch.virtual,
          [section]: updatedItems,
        },
      },
    })
  }

  const updateFilter = (
    section: string,
    itemIndex: number,
    filterIndex: number,
    field: string,
    value: any,
  ) => {
    const items = settings.export?.sheets?.[
      section as keyof typeof settings.export.sheets
    ] as any[]
    const updatedItems = [...items]

    updatedItems[itemIndex].filters[filterIndex] = {
      ...updatedItems[itemIndex].filters[filterIndex],
      [field]: value,
    }

    setSettings({
      ...settings,
      export: {
        ...settings.export,
        sheets: {
          ...settings.export?.sheets,
          [section]: updatedItems,
        },
      },
    })
  }

  const validateSettings = () => {
    const errors: Record<string, string[]> = {}

    if (
      settings.export?.sheets?.enabled === true &&
      !settings.export.sheets?.globals?.spreadsheetId
    ) {
      errors.globals = [t.settings.errors.spreadsheetIdRequired]
    }

    Object.entries(settings.export?.sheets ?? {}).forEach(
      ([section, items]) => {
        if (
          section !== "globals" &&
          section !== "enabled" &&
          Array.isArray(items)
        ) {
          const sectionErrors: string[] = []

          items.forEach((item: any, index: number) => {
            if (!item.range) {
              if (!sectionErrors[index]) sectionErrors[index] = ""
              sectionErrors[index] += t.settings.errors.rangeRequired
            }

            if (
              (section === "position" ||
                section === "transactions" ||
                section === "contributions") &&
              (!item.data ||
                (Array.isArray(item.data) && item.data.length === 0))
            ) {
              if (!sectionErrors[index]) sectionErrors[index] = ""
              sectionErrors[index] += t.settings.errors.dataRequired
            }
          })

          if (sectionErrors.length > 0) {
            errors[section] = sectionErrors
          }
        }
      },
    )

    if (settings.fetch.virtual.enabled) {
      if (!settings.fetch.virtual?.globals?.spreadsheetId) {
        errors.virtualGlobals = [t.settings.errors.virtualSpreadsheetIdRequired]
      }

      Object.entries(settings.fetch.virtual).forEach(([section, items]) => {
        if (
          section !== "globals" &&
          section !== "enabled" &&
          Array.isArray(items)
        ) {
          const sectionErrors: string[] = []

          items.forEach((item: any, index: number) => {
            if (!item.range) {
              if (!sectionErrors[index]) sectionErrors[index] = ""
              sectionErrors[index] += t.settings.errors.rangeRequired
            }

            if (
              (section === "position" || section === "transactions") &&
              !item.data
            ) {
              if (!sectionErrors[index]) sectionErrors[index] = ""
              sectionErrors[index] += t.settings.errors.dataRequired
            }
          })

          if (sectionErrors.length > 0) {
            errors[`virtual_${section}`] = sectionErrors
          }
        }
      })
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const processDataFields = (settingsObj: any) => {
    const processed = { ...settingsObj }

    if (processed.export?.sheets) {
      Object.entries(processed.export.sheets).forEach(([section, items]) => {
        if (
          section !== "globals" &&
          section !== "enabled" &&
          Array.isArray(items)
        ) {
          ;(items as any[]).forEach(item => {
            // Skip processing data for position section as it's already an array from MultiSelect
            if (
              section !== "position" &&
              item.data &&
              typeof item.data === "string"
            ) {
              if (item.data.includes(",")) {
                item.data = item.data
                  .split(",")
                  .map((v: string) => v.trim())
                  .filter((v: string) => v !== "")
              } else if (item.data.trim() !== "") {
                item.data = [item.data.trim()]
              } else {
                item.data = []
              }
            }

            if (item.filters && Array.isArray(item.filters)) {
              item.filters.forEach((filter: any) => {
                if (filter.values && typeof filter.values === "string") {
                  if (filter.values.includes(",")) {
                    filter.values = filter.values
                      .split(",")
                      .map((v: string) => v.trim())
                      .filter((v: string) => v !== "")
                  } else if (filter.values.trim() !== "") {
                    filter.values = [filter.values.trim()]
                  } else {
                    filter.values = []
                  }
                }
              })
            }
          })
        }
      })
    }

    return processed
  }

  const handleSave = async () => {
    if (!validateSettings()) {
      showToast(t.settings.validationError, "error")
      return
    }

    try {
      setIsSaving(true)

      const sanitizedStablecoins = Array.from(
        new Set(
          (settings.assets?.crypto?.stablecoins ?? []).map(symbol =>
            symbol.trim().toUpperCase(),
          ),
        ),
      ).filter(Boolean)

      const settingsForSave: AppSettings = {
        ...settings,
        assets: {
          ...settings.assets,
          crypto: {
            ...settings.assets?.crypto,
            stablecoins: sanitizedStablecoins,
          },
        },
      }

      setSettings(settingsForSave)

      const processedSettings = processDataFields({ ...settingsForSave })

      const cleanedSettings = cleanObject(processedSettings)

      if (cleanedSettings.fetch && cleanedSettings.fetch.virtual) {
        cleanedSettings.fetch.virtual.enabled =
          !!cleanedSettings.fetch.virtual.enabled
      }
      if (cleanedSettings.export && cleanedSettings.export.sheets) {
        cleanedSettings.export.sheets.enabled =
          !!cleanedSettings.export.sheets.enabled
      }

      if (!cleanedSettings.assets) {
        cleanedSettings.assets = {
          crypto: {
            stablecoins: sanitizedStablecoins,
          },
        }
      } else {
        cleanedSettings.assets.crypto = cleanedSettings.assets.crypto || {
          stablecoins: [],
        }
        cleanedSettings.assets.crypto.stablecoins = sanitizedStablecoins
      }

      await saveSettings(cleanedSettings)
    } catch (error) {
      console.error("Error saving settings:", error)
      showToast(t.settings.saveError, "error")
    } finally {
      setIsSaving(false)
    }
  }

  const renderConfigSection = (section: string, items: any[]) => {
    const canHaveFilters =
      section === "transactions" ||
      section === "historic" ||
      section === "position" ||
      section === "contributions"

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3
            className="text-lg font-medium cursor-pointer flex items-center"
            onClick={() => toggleSection(section)}
          >
            {/* @ts-expect-error settings */}
            {t.settings[section]}
            {expandedSections[section] ? (
              <ChevronUp className="ml-2 h-4 w-4" />
            ) : (
              <ChevronDown className="ml-2 h-4 w-4" />
            )}
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => addConfigItem(section)}
            className="flex items-center"
          >
            <PlusCircle className="mr-1 h-4 w-4" />
            {t.common.add}
          </Button>
        </div>

        {expandedSections[section] && (
          <Card className="bg-gray-50 dark:bg-gray-900">
            <CardContent className="pt-4 space-y-4">
              {items.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {t.settings.noItems}
                </p>
              ) : (
                items.map((item, index) => (
                  <div
                    key={index}
                    className="grid grid-cols-1 gap-4 mb-4 pb-4 border-b border-gray-200 dark:border-gray-800 last:border-0 last:mb-0 last:pb-0"
                  >
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium">
                        {t.settings.configuration}
                      </h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeConfigItem(section, index)}
                        className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    {validationErrors[section] &&
                      validationErrors[section][index] && (
                        <div className="text-red-500 text-sm">
                          {validationErrors[section][index]}
                        </div>
                      )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t.settings.range} *</Label>
                        <Input
                          value={item.range || ""}
                          onChange={e =>
                            updateConfigItem(
                              section,
                              index,
                              "range",
                              e.target.value,
                            )
                          }
                          placeholder={t.settings.rangePlaceholder}
                          required
                          className={
                            validationErrors[section] &&
                            validationErrors[section][index] &&
                            !item.range
                              ? "border-red-500"
                              : ""
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>{t.settings.spreadsheetId}</Label>
                        <Input
                          value={item.spreadsheetId || ""}
                          onChange={e =>
                            updateConfigItem(
                              section,
                              index,
                              "spreadsheetId",
                              e.target.value,
                            )
                          }
                          placeholder={t.settings.optional}
                        />
                      </div>

                      {(section === "position" ||
                        section === "transactions" ||
                        section === "contributions") && (
                        <div className="space-y-2 md:col-span-2">
                          <Label>{t.settings.data} *</Label>
                          {section === "position" ? (
                            <MultiSelect
                              options={getPositionDataOptions()}
                              value={isArray(item.data) ? item.data : []}
                              onChange={selectedValues =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "data",
                                  selectedValues,
                                )
                              }
                              placeholder={t.settings.selectDataTypes}
                              className={
                                validationErrors[section] &&
                                validationErrors[section][index] &&
                                (!item.data ||
                                  (Array.isArray(item.data) &&
                                    item.data.length === 0))
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          ) : section === "contributions" ? (
                            <MultiSelect
                              options={getContributionsDataOptions()}
                              value={isArray(item.data) ? item.data : []}
                              onChange={selectedValues =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "data",
                                  selectedValues,
                                )
                              }
                              placeholder={t.settings.selectDataTypes}
                              className={
                                validationErrors[section] &&
                                validationErrors[section][index] &&
                                (!item.data ||
                                  (Array.isArray(item.data) &&
                                    item.data.length === 0))
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          ) : section === "transactions" ? (
                            <MultiSelect
                              options={getTransactionsDataOptions()}
                              value={isArray(item.data) ? item.data : []}
                              onChange={selectedValues =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "data",
                                  selectedValues,
                                )
                              }
                              placeholder={t.settings.selectDataTypes}
                              className={
                                validationErrors[section] &&
                                validationErrors[section][index] &&
                                (!item.data ||
                                  (Array.isArray(item.data) &&
                                    item.data.length === 0))
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          ) : (
                            <Input
                              value={
                                isArray(item.data)
                                  ? item.data.join(", ")
                                  : item.data || ""
                              }
                              onChange={e =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "data",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.dataPlaceholder}
                              required
                              className={
                                validationErrors[section] &&
                                validationErrors[section][index] &&
                                (!item.data ||
                                  (Array.isArray(item.data) &&
                                    item.data.length === 0))
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          )}
                        </div>
                      )}

                      {(section === "transactions" ||
                        section === "position") && (
                        <>
                          <div className="space-y-2">
                            <Label>{t.settings.dateFormat}</Label>
                            <Input
                              value={item.dateFormat || ""}
                              onChange={e =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "dateFormat",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.optional}
                            />
                          </div>

                          <div className="space-y-2">
                            <Label>{t.settings.datetimeFormat}</Label>
                            <Input
                              value={item.datetimeFormat || ""}
                              onChange={e =>
                                updateConfigItem(
                                  section,
                                  index,
                                  "datetimeFormat",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.optional}
                            />
                          </div>
                        </>
                      )}

                      {canHaveFilters && (
                        <div className="space-y-2 md:col-span-2">
                          <div className="flex items-center justify-between">
                            <Label>{t.settings.filters}</Label>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => addFilter(section, index)}
                              className="flex items-center"
                            >
                              <PlusCircle className="mr-1 h-4 w-4" />
                              {t.settings.addFilter}
                            </Button>
                          </div>

                          {item.filters && item.filters.length > 0 ? (
                            <div className="space-y-3 mt-2">
                              {item.filters.map(
                                (filter: any, filterIndex: number) => (
                                  <div
                                    key={filterIndex}
                                    className="grid grid-cols-1 md:grid-cols-2 gap-2 p-2 border border-gray-200 dark:border-gray-700 rounded-md"
                                  >
                                    <div className="flex items-center space-x-2">
                                      <Input
                                        value={filter.field || ""}
                                        onChange={e =>
                                          updateFilter(
                                            section,
                                            index,
                                            filterIndex,
                                            "field",
                                            e.target.value,
                                          )
                                        }
                                        placeholder={t.settings.field}
                                        className="flex-1"
                                      />
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() =>
                                          removeFilter(
                                            section,
                                            index,
                                            filterIndex,
                                          )
                                        }
                                        className="text-red-500 hover:text-red-600"
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </div>

                                    <Input
                                      value={
                                        isArray(filter.values)
                                          ? filter.values.join(", ")
                                          : filter.values || ""
                                      }
                                      onChange={e => {
                                        updateFilter(
                                          section,
                                          index,
                                          filterIndex,
                                          "values",
                                          e.target.value,
                                        )
                                      }}
                                      placeholder={t.settings.valuesPlaceholder}
                                    />
                                  </div>
                                ),
                              )}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              {t.settings.noFilters}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        )}
      </div>
    )
  }

  const renderVirtualConfigSection = (section: string, items: any[]) => {
    const virtualKey = `virtual_${section}`
    const virtualSectionKey = `virtual${section.charAt(0).toUpperCase() + section.slice(1)}`

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3
            className="text-lg font-medium cursor-pointer flex items-center"
            onClick={() => toggleSection(virtualSectionKey)}
          >
            {/* @ts-expect-error settings */}
            {t.settings[section]}
            {expandedSections[virtualSectionKey] ? (
              <ChevronUp className="ml-2 h-4 w-4" />
            ) : (
              <ChevronDown className="ml-2 h-4 w-4" />
            )}
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => addVirtualConfigItem(section)}
            className="flex items-center"
          >
            <PlusCircle className="mr-1 h-4 w-4" />
            {t.common.add}
          </Button>
        </div>

        {expandedSections[virtualSectionKey] && (
          <Card className="bg-gray-50 dark:bg-gray-900">
            <CardContent className="pt-4 space-y-4">
              {items.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {t.settings.noItems}
                </p>
              ) : (
                items.map((item, index) => (
                  <div
                    key={index}
                    className="grid grid-cols-1 gap-4 mb-4 pb-4 border-b border-gray-200 dark:border-gray-800 last:border-0 last:mb-0 last:pb-0"
                  >
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium">
                        {t.settings.configuration}
                      </h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeVirtualConfigItem(section, index)}
                        className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    {validationErrors[virtualKey] &&
                      validationErrors[virtualKey][index] && (
                        <div className="text-red-500 text-sm">
                          {validationErrors[virtualKey][index]}
                        </div>
                      )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t.settings.range} *</Label>
                        <Input
                          value={item.range || ""}
                          onChange={e =>
                            updateVirtualConfigItem(
                              section,
                              index,
                              "range",
                              e.target.value,
                            )
                          }
                          placeholder={t.settings.rangePlaceholder}
                          required
                          className={
                            validationErrors[virtualKey] &&
                            validationErrors[virtualKey][index] &&
                            !item.range
                              ? "border-red-500"
                              : ""
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>{t.settings.spreadsheetId}</Label>
                        <Input
                          value={item.spreadsheetId || ""}
                          onChange={e =>
                            updateVirtualConfigItem(
                              section,
                              index,
                              "spreadsheetId",
                              e.target.value,
                            )
                          }
                          placeholder={t.settings.optional}
                        />
                      </div>

                      {(section === "position" ||
                        section === "transactions") && (
                        <div className="space-y-2 md:col-span-2">
                          <Label>{t.settings.data} *</Label>
                          {section === "position" ? (
                            <MultiSelect
                              options={getPositionDataOptions()}
                              value={item.data ? [item.data] : []}
                              onChange={selectedValues => {
                                // For single-value mode: if multiple values, keep only the newest one
                                // If the current selection is different from what we have, it means a new selection was made
                                let newValue = ""
                                if (selectedValues.length > 0) {
                                  if (selectedValues.length === 1) {
                                    // Only one item selected
                                    newValue = selectedValues[0]
                                  } else {
                                    // Multiple items selected, find the new one (not the current value)
                                    const currentValue = item.data
                                    newValue =
                                      selectedValues.find(
                                        val => val !== currentValue,
                                      ) ||
                                      selectedValues[selectedValues.length - 1]
                                  }
                                }
                                updateVirtualConfigItem(
                                  section,
                                  index,
                                  "data",
                                  newValue,
                                )
                              }}
                              placeholder={t.settings.selectDataTypes}
                              className={
                                validationErrors[virtualKey] &&
                                validationErrors[virtualKey][index] &&
                                !item.data
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          ) : section === "transactions" ? (
                            <MultiSelect
                              options={getTransactionsDataOptions()}
                              value={item.data ? [item.data] : []}
                              onChange={selectedValues => {
                                // For single-value mode: if multiple values, keep only the newest one
                                // If the current selection is different from what we have, it means a new selection was made
                                let newValue = ""
                                if (selectedValues.length > 0) {
                                  if (selectedValues.length === 1) {
                                    // Only one item selected
                                    newValue = selectedValues[0]
                                  } else {
                                    // Multiple items selected, find the new one (not the current value)
                                    const currentValue = item.data
                                    newValue =
                                      selectedValues.find(
                                        val => val !== currentValue,
                                      ) ||
                                      selectedValues[selectedValues.length - 1]
                                  }
                                }
                                updateVirtualConfigItem(
                                  section,
                                  index,
                                  "data",
                                  newValue,
                                )
                              }}
                              placeholder={t.settings.selectDataTypes}
                              className={
                                validationErrors[virtualKey] &&
                                validationErrors[virtualKey][index] &&
                                !item.data
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          ) : (
                            <Input
                              value={item.data || ""}
                              onChange={e =>
                                updateVirtualConfigItem(
                                  section,
                                  index,
                                  "data",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.dataPlaceholder}
                              required
                              className={
                                validationErrors[virtualKey] &&
                                validationErrors[virtualKey][index] &&
                                !item.data
                                  ? "border-red-500"
                                  : ""
                              }
                            />
                          )}
                        </div>
                      )}

                      {(section === "position" ||
                        section === "transactions") && (
                        <>
                          <div className="space-y-2">
                            <Label>{t.settings.dateFormat}</Label>
                            <Input
                              value={item.dateFormat || ""}
                              onChange={e =>
                                updateVirtualConfigItem(
                                  section,
                                  index,
                                  "dateFormat",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.optional}
                            />
                          </div>

                          <div className="space-y-2">
                            <Label>{t.settings.datetimeFormat}</Label>
                            <Input
                              value={item.datetimeFormat || ""}
                              onChange={e =>
                                updateVirtualConfigItem(
                                  section,
                                  index,
                                  "datetimeFormat",
                                  e.target.value,
                                )
                              }
                              placeholder={t.settings.optional}
                            />
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        )}
      </div>
    )
  }

  const renderIntegrationCard = (integration: ExternalIntegration) => {
    const schemaEntries = Object.entries(integration.payload_schema ?? {})
    const payload = integrationPayloads[integration.id] ?? {}
    const errors = integrationErrors[integration.id] ?? {}
    const isExpanded = expandedIntegrations[integration.id] ?? false
    const isEnabled = integration.status === ExternalIntegrationStatus.ON
    const isLoading = !!isSetupLoading[integration.id]
    const disableLoading = !!isDisableLoading[integration.id]
    const disabledForPlatform =
      integration.id === "GOOGLE_SHEETS" && platform === PlatformType.WEB

    const settingsCopy = t.settings as any
    const { title, description } = resolveIntegrationCopy(integration)

    const hintContent = (() => {
      if (integration.id === "ETHERSCAN") {
        const prefix = settingsCopy?.etherscanApiInfoPrefix
        const linkText = settingsCopy?.etherscanApiInfoLinkText
        const suffix = settingsCopy?.etherscanApiInfoSuffix

        if (prefix && linkText && suffix) {
          return (
            <p className="text-sm">
              {prefix}
              <a
                href="https://docs.etherscan.io/etherscan-v2/getting-an-api-key"
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-primary"
              >
                {linkText}
              </a>
              {suffix}
            </p>
          )
        }
      }

      if (integration.id === "GOCARDLESS") {
        const prefix = settingsCopy?.goCardlessInfoPrefix
        const linkText = settingsCopy?.goCardlessInfoLinkText
        const middle = settingsCopy?.goCardlessInfoMiddle
        const userSecrets = settingsCopy?.goCardlessInfoUserSecrets
        const suffix = settingsCopy?.goCardlessInfoSuffix

        if (prefix && linkText && middle && userSecrets && suffix) {
          return (
            <p className="text-sm leading-relaxed">
              {prefix}
              <a
                href="https://bankaccountdata.gocardless.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-primary"
              >
                {linkText}
              </a>
              {middle}
              <a
                href="https://bankaccountdata.gocardless.com/user-secrets/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-primary"
              >
                {userSecrets}
              </a>
              {suffix}
            </p>
          )
        }
      }

      return null
    })()

    const hintButtonLabel =
      (integration.id === "GOCARDLESS" && settingsCopy?.goCardlessHelpButton) ??
      settingsCopy?.integrationHintButton ??
      t.common.help

    const hasHintLabel =
      typeof hintButtonLabel === "string" && hintButtonLabel.trim().length > 0

    const canSubmit =
      schemaEntries.length === 0 ||
      schemaEntries.every(([field]) => (payload[field] ?? "").trim() !== "")

    const iconSrc = `icons/external-integrations/${integration.id}.png`
    const isHighlighted = highlighted === integration.id

    return (
      <Card
        key={integration.id}
        className={cn(
          "self-start",
          isHighlighted ? "ring-2 ring-yellow-500 animate-pulse" : undefined,
        )}
      >
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div
              className="flex flex-1 items-center justify-between cursor-pointer"
              onClick={() => toggleIntegrationCard(integration.id)}
            >
              <div className="flex items-center gap-3">
                <img
                  src={iconSrc}
                  alt={title}
                  className="h-12 w-12 object-contain"
                />
                <div>
                  <CardTitle className="text-lg">{title}</CardTitle>
                </div>
              </div>
              <div className="flex items-center space-x-1">
                <Badge
                  className={cn(
                    isEnabled
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                  )}
                >
                  {isEnabled ? t.common.enabled : t.common.disabled}
                </Badge>
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </div>
            </div>
          </div>
          {description && (
            <CardDescription className="pt-2">{description}</CardDescription>
          )}
        </CardHeader>
        {isExpanded && (
          <CardContent className="space-y-4">
            {schemaEntries.length > 0 ? (
              schemaEntries.map(([field, label], index) => {
                const value = payload[field] ?? ""
                const hasError = !!errors[field]
                const inputType = /secret|password|token|key/i.test(field)
                  ? "password"
                  : "text"
                const showHintInline = hintContent && index === 0

                return (
                  <div key={field} className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <Label
                        htmlFor={`${integration.id}-${field}`}
                        className="leading-tight"
                      >
                        {label}
                      </Label>
                      {showHintInline && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              size={hasHintLabel ? "sm" : "icon"}
                              type="button"
                              aria-label={
                                hasHintLabel ? hintButtonLabel : t.common.help
                              }
                              className={cn(
                                "text-xs text-muted-foreground",
                                hasHintLabel
                                  ? "gap-1 h-auto px-2 py-1"
                                  : "h-8 w-8 p-0",
                              )}
                            >
                              <Info className="h-4 w-4" />
                              {hasHintLabel ? (
                                <span>{hintButtonLabel}</span>
                              ) : undefined}
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-80 p-3 space-y-2">
                            <h4 className="text-sm font-medium">{title}</h4>
                            {hintContent}
                          </PopoverContent>
                        </Popover>
                      )}
                    </div>
                    <Input
                      id={`${integration.id}-${field}`}
                      type={inputType}
                      value={value}
                      onChange={event =>
                        handleIntegrationFieldChange(
                          integration.id,
                          field,
                          event.target.value,
                        )
                      }
                      placeholder={String(label)}
                      className={cn(hasError ? "border-red-500" : undefined)}
                    />
                  </div>
                )
              })
            ) : (
              <p className="text-sm text-muted-foreground">
                {t.common.notAvailable}
              </p>
            )}

            <div className="flex items-center justify-end gap-2">
              {disabledForPlatform && (
                <span className="text-xs text-muted-foreground">
                  {`(${t.settings.googleSheetsWebDisabled})`}
                </span>
              )}
              {isEnabled && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDisableIntegration(integration.id)}
                  disabled={disableLoading}
                >
                  {disableLoading ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      {t.common.loading}
                    </>
                  ) : (
                    <>
                      <Link2Off className="mr-2 h-4 w-4" />
                      {t.entities.disconnect}
                    </>
                  )}
                </Button>
              )}
              <Button
                size="sm"
                onClick={() => handleSetupIntegration(integration.id)}
                disabled={isLoading || !canSubmit || disabledForPlatform}
              >
                {isLoading ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    {t.common.loading}
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    {t.common.setup}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    )
  }

  // Component for displaying integration requirement badge and popover
  const IntegrationRequiredBadge = ({
    integrationName = "Google Sheets",
  }: {
    integrationName?: string
  }) => {
    return (
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
              onClick={() => setActiveTab("integrations")}
            >
              <Settings className="mr-2 h-3 w-3" />
              {t.entities.goToSettings}
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    )
  }

  if (isLoadingSettings || !settings) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">{t.settings.title}</h1>
        <div className="flex space-x-2">
          {showRefreshButton ? (
            <Button
              variant="outline"
              size="icon"
              onClick={() => {
                fetchSettings()
                fetchExternalIntegrations()
              }}
              disabled={isLoadingSettings || isSaving}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          ) : null}
          {showSaveButton ? (
            <Button
              onClick={handleSave}
              disabled={isSaving || isLoadingSettings}
            >
              {isSaving ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  {t.common.saving}
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  {t.settings.save}
                </>
              )}
            </Button>
          ) : null}
        </div>
      </div>

      <Tabs
        defaultValue="general"
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full"
      >
        <div className="flex justify-center w-full">
          <TabsList className="grid w-full max-w-[800px] h-auto min-h-[3rem] grid-cols-2 sm:grid-cols-3 md:grid-cols-5">
            <TabsTrigger
              value="general"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.general}
            </TabsTrigger>
            <TabsTrigger
              value="application"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.application}
            </TabsTrigger>
            <TabsTrigger
              value="integrations"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.integrations}
            </TabsTrigger>
            <TabsTrigger
              value="export"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.export}
            </TabsTrigger>
            <TabsTrigger
              value="scrape"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.scrape}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="general" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <Card>
              <CardHeader>
                <CardTitle>{t.settings.general}</CardTitle>
                <CardDescription>
                  {t.settings.generalDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="default-currency">
                      {t.settings.defaultCurrency}
                    </Label>
                    <div className="relative">
                      <select
                        id="default-currency"
                        value={settings.general?.defaultCurrency || "EUR"}
                        onChange={e => handleCurrencyChange(e.target.value)}
                        className="flex h-10 w-full max-w-xs rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                      >
                        <option value="EUR">EUR - Euro</option>
                        <option value="USD">USD - US Dollar</option>
                      </select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="default-commodity-weight-unit">
                      {t.settings.defaultCommodityWeightUnit}
                    </Label>
                    <div className="relative">
                      <select
                        id="default-commodity-weight-unit"
                        value={
                          settings.general?.defaultCommodityWeightUnit ||
                          WeightUnit.GRAM
                        }
                        onChange={e =>
                          handleCommodityWeightUnitChange(e.target.value)
                        }
                        className="flex h-10 w-full max-w-xs rounded-md border border-input bg-background px-3 py-2 pr-8 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
                      >
                        <option value={WeightUnit.GRAM}>
                          {t.enums.weightUnit.GRAM} -{" "}
                          {t.enums.weightUnitName.GRAM}
                        </option>
                        <option value={WeightUnit.TROY_OUNCE}>
                          {t.enums.weightUnit.TROY_OUNCE} -{" "}
                          {t.enums.weightUnitName.TROY_OUNCE}
                        </option>
                      </select>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: 0.05 }}
          >
            <Card>
              <CardHeader onClick={() => toggleSection("assets")}>
                <CardTitle>{t.settings.assets.title}</CardTitle>
                <CardDescription>
                  {t.settings.assets.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div
                    className="flex cursor-pointer items-center justify-between rounded-md border border-border/50 bg-muted/20 px-3 py-2 transition-colors hover:bg-muted/30 dark:bg-muted/10 dark:hover:bg-muted/20"
                    onClick={() => toggleSection("assetsCrypto")}
                  >
                    <div className="flex items-start gap-3">
                      <Coins className="mt-0.5 h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">
                          {t.settings.assets.crypto.title}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t.settings.assets.crypto.description}
                        </p>
                      </div>
                    </div>
                    {expandedSections.assetsCrypto ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                  {expandedSections.assetsCrypto && (
                    <div className="space-y-4 rounded-md border border-dashed border-border/60 bg-background/60 p-4 dark:bg-muted/10">
                      <div className="space-y-1">
                        <Label htmlFor="assets-stablecoins">
                          {t.settings.assets.crypto.stablecoinsLabel}
                        </Label>
                        <p className="text-sm text-muted-foreground">
                          {t.settings.assets.crypto.stablecoinsDescription}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {stablecoins.map((coin, index) =>
                          editingStablecoinIndex === index ? (
                            <div
                              key={`stablecoin-edit-${index}`}
                              className="flex items-center gap-2 py-0.5"
                            >
                              <Input
                                autoFocus
                                value={stablecoinDraft}
                                onChange={event =>
                                  setStablecoinDraft(
                                    normalizeStablecoinSymbol(
                                      event.target.value,
                                    ),
                                  )
                                }
                                onKeyDown={event => {
                                  if (event.key === "Enter") {
                                    event.preventDefault()
                                    handleConfirmEditStablecoin()
                                  } else if (event.key === "Escape") {
                                    event.preventDefault()
                                    handleCancelEditStablecoin()
                                  }
                                }}
                                className="h-7 w-24 rounded-full border border-border/40 bg-background/40 px-3 text-xs uppercase focus:border-border/60 focus-visible:outline-none focus-visible:ring-0"
                              />
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                className="h-7 w-7 rounded-full p-0"
                                onClick={handleConfirmEditStablecoin}
                                aria-label={
                                  t.settings.assets.crypto.confirmEdit
                                }
                              >
                                <Check className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 rounded-full p-0"
                                onClick={handleCancelEditStablecoin}
                                aria-label={t.settings.assets.crypto.cancelEdit}
                              >
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          ) : (
                            <Badge
                              key={`stablecoin-${coin}-${index}`}
                              className="flex items-center gap-2 bg-primary/10 text-primary dark:bg-primary/20"
                            >
                              <span className="uppercase">{coin}</span>
                              <button
                                type="button"
                                onClick={() => handleStartEditStablecoin(index)}
                                className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-primary/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
                              >
                                <Edit2 className="h-3.5 w-3.5" />
                                <span className="sr-only">
                                  {t.settings.assets.crypto.editStablecoin}
                                </span>
                              </button>
                              <span
                                aria-hidden="true"
                                className="h-4 w-px bg-primary/30"
                              />
                              <button
                                type="button"
                                onClick={() => handleRemoveStablecoin(index)}
                                className="inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-primary/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
                              >
                                <X className="h-3.5 w-3.5" />
                                <span className="sr-only">
                                  {t.settings.assets.crypto.removeStablecoin}
                                </span>
                              </button>
                            </Badge>
                          ),
                        )}
                        {isAddingStablecoin ? (
                          <div className="flex items-center gap-2 py-0.5">
                            <Input
                              ref={newStablecoinInputRef}
                              id="assets-stablecoins"
                              value={newStablecoin}
                              onChange={event =>
                                setNewStablecoin(
                                  normalizeStablecoinSymbol(event.target.value),
                                )
                              }
                              onKeyDown={event => {
                                if (event.key === "Enter") {
                                  event.preventDefault()
                                  handleAddStablecoin()
                                } else if (event.key === "Escape") {
                                  event.preventDefault()
                                  handleCancelAddStablecoin()
                                }
                              }}
                              placeholder={
                                t.settings.assets.crypto
                                  .addStablecoinPlaceholder
                              }
                              className="h-7 w-24 rounded-full border border-border/40 bg-background/40 px-3 text-xs uppercase focus:border-border/60 focus-visible:outline-none focus-visible:ring-0"
                              autoCapitalize="characters"
                              autoComplete="off"
                            />
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              className="h-7 w-7 rounded-full p-0"
                              onClick={handleAddStablecoin}
                              disabled={!newStablecoin}
                              aria-label={
                                t.settings.assets.crypto.addStablecoin
                              }
                            >
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 rounded-full p-0"
                              onClick={handleCancelAddStablecoin}
                              aria-label={t.common.cancel}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={handleStartAddStablecoin}
                            className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-primary/50 px-2.5 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:ring-offset-0"
                            aria-label={t.settings.assets.crypto.addStablecoin}
                          >
                            <PlusCircle className="h-3 w-3" />
                            <span>
                              {t.settings.assets.crypto.addStablecoin}
                            </span>
                          </button>
                        )}
                      </div>
                      {stablecoins.length === 0 && !isAddingStablecoin && (
                        <p className="italic text-sm text-muted-foreground">
                          {t.settings.assets.crypto.emptyState}
                        </p>
                      )}
                      <div className="border-t border-border/50 pt-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="space-y-1">
                            <p className="text-sm font-medium">
                              {t.settings.assets.crypto.hideUnknownTokensLabel}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {
                                t.settings.assets.crypto
                                  .hideUnknownTokensDescription
                              }
                            </p>
                          </div>
                          <Switch
                            checked={hideUnknownTokens}
                            onCheckedChange={handleHideUnknownTokensChange}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
          <div className="flex justify-end">
            <p className="text-[0.6rem] text-gray-500 dark:text-gray-400">
              v{__APP_VERSION__} by marcosav
            </p>
          </div>
        </TabsContent>

        <TabsContent value="application" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {t.settings.applicationDisclaimerDescription}
              </p>
              <Card>
                <CardHeader>
                  <CardTitle>{t.settings.applicationLanguageTitle}</CardTitle>
                  <CardDescription>
                    {t.settings.applicationLanguageDescription}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Label htmlFor="application-language">
                      {t.settings.applicationLanguageTitle}
                    </Label>
                    <select
                      id="application-language"
                      value={locale}
                      aria-label={t.settings.applicationLanguageTitle}
                      onChange={event => {
                        const nextLocale = event.target.value as Locale
                        if (nextLocale !== locale) {
                          changeLocale(nextLocale)
                        }
                      }}
                      className="flex h-10 w-full max-w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {applicationLanguageOptions.map(option => (
                        <option key={option.code} value={option.code}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4"
          >
            {externalIntegrations.length === 0 ? (
              <Card className="col-span-full">
                <CardContent className="flex flex-col items-center gap-3 py-10">
                  <LoadingSpinner size="md" />
                  <p className="text-sm text-muted-foreground">
                    {t.common.loading}
                  </p>
                </CardContent>
              </Card>
            ) : (
              externalIntegrations.map(integration =>
                renderIntegrationCard(integration),
              )
            )}
          </motion.div>
        </TabsContent>

        <TabsContent value="export" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <Card>
              <CardHeader>
                <CardTitle>{t.settings.sheets}</CardTitle>
                <CardDescription>
                  {t.settings.sheetsDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="export-enabled">{t.settings.enabled}</Label>
                    {!isGoogleSheetsIntegrationEnabled() && (
                      <IntegrationRequiredBadge />
                    )}
                  </div>
                  <Switch
                    id="export-enabled"
                    checked={
                      isGoogleSheetsIntegrationEnabled() &&
                      settings.export?.sheets?.enabled === true
                    }
                    onCheckedChange={handleExportToggle}
                    disabled={!isGoogleSheetsIntegrationEnabled()}
                  />
                </div>

                {settings.export?.sheets?.enabled === true && (
                  <>
                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">
                        {t.settings.globals}
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="spreadsheetId">
                            {t.settings.spreadsheetId} *
                          </Label>
                          <Input
                            id="spreadsheetId"
                            value={
                              settings.export?.sheets?.globals?.spreadsheetId ||
                              ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                export: {
                                  ...(settings.export || {}),
                                  sheets: {
                                    ...(settings.export?.sheets || {}),
                                    globals: {
                                      ...(settings.export?.sheets?.globals ||
                                        {}),
                                      spreadsheetId: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.spreadsheetIdPlaceholder}
                            className={
                              validationErrors.globals ? "border-red-500" : ""
                            }
                          />
                          {validationErrors.globals && (
                            <div className="text-red-500 text-sm">
                              {validationErrors.globals[0]}
                            </div>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="datetimeFormat">
                            {t.settings.datetimeFormat}
                          </Label>
                          <Input
                            id="datetimeFormat"
                            value={
                              settings.export?.sheets?.globals
                                ?.datetimeFormat || ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                export: {
                                  ...(settings.export || {}),
                                  sheets: {
                                    ...(settings.export?.sheets || {}),
                                    globals: {
                                      ...(settings.export?.sheets?.globals ||
                                        {}),
                                      datetimeFormat: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.datetimeFormatPlaceholder}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="dateFormat">
                            {t.settings.dateFormat}
                          </Label>
                          <Input
                            id="dateFormat"
                            value={
                              settings.export?.sheets?.globals?.dateFormat || ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                export: {
                                  ...(settings.export || {}),
                                  sheets: {
                                    ...(settings.export?.sheets || {}),
                                    globals: {
                                      ...(settings.export?.sheets?.globals ||
                                        {}),
                                      dateFormat: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.dateFormatPlaceholder}
                          />
                        </div>
                      </div>
                    </div>

                    {renderConfigSection(
                      "position",
                      settings.export?.sheets?.position ?? [],
                    )}
                    {renderConfigSection(
                      "contributions",
                      settings.export?.sheets?.contributions ?? [],
                    )}
                    {renderConfigSection(
                      "transactions",
                      settings.export?.sheets?.transactions ?? [],
                    )}
                    {renderConfigSection(
                      "historic",
                      settings.export?.sheets?.historic ?? [],
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>

        <TabsContent value="scrape" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <Card>
              <CardHeader>
                <CardTitle>{t.settings.virtual}</CardTitle>
                <CardDescription>
                  {t.settings.virtualDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="virtual-enabled">
                      {t.settings.enabled}
                    </Label>
                    {!isGoogleSheetsIntegrationEnabled() && (
                      <IntegrationRequiredBadge />
                    )}
                  </div>
                  <Switch
                    id="virtual-enabled"
                    checked={
                      isGoogleSheetsIntegrationEnabled() &&
                      settings.fetch?.virtual?.enabled === true
                    }
                    onCheckedChange={handleVirtualToggle}
                    disabled={!isGoogleSheetsIntegrationEnabled()}
                  />
                </div>

                {settings.fetch.virtual.enabled === true && (
                  <div className="space-y-6 pt-4 border-t border-gray-200 dark:border-gray-800">
                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">
                        {t.settings.globals}
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="virtual-spreadsheetId">
                            {t.settings.spreadsheetId} *
                          </Label>
                          <Input
                            id="virtual-spreadsheetId"
                            value={
                              settings.fetch?.virtual?.globals?.spreadsheetId ||
                              ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                fetch: {
                                  ...(settings.fetch || {}),
                                  virtual: {
                                    ...(settings.fetch?.virtual || {}),
                                    globals: {
                                      ...(settings.fetch?.virtual?.globals ||
                                        {}),
                                      spreadsheetId: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.spreadsheetIdPlaceholder}
                            className={
                              validationErrors.virtualGlobals
                                ? "border-red-500"
                                : ""
                            }
                          />
                          {validationErrors.virtualGlobals && (
                            <div className="text-red-500 text-sm">
                              {validationErrors.virtualGlobals[0]}
                            </div>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="virtual-datetimeFormat">
                            {t.settings.datetimeFormat}
                          </Label>
                          <Input
                            id="virtual-datetimeFormat"
                            value={
                              settings.fetch?.virtual?.globals
                                ?.datetimeFormat || ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                fetch: {
                                  ...(settings.fetch || {}),
                                  virtual: {
                                    ...(settings.fetch?.virtual || {}),
                                    globals: {
                                      ...(settings.fetch?.virtual?.globals ||
                                        {}),
                                      datetimeFormat: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.datetimeFormatPlaceholder}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="virtual-dateFormat">
                            {t.settings.dateFormat}
                          </Label>
                          <Input
                            id="virtual-dateFormat"
                            value={
                              settings.fetch?.virtual?.globals?.dateFormat || ""
                            }
                            onChange={e =>
                              setSettings({
                                ...settings,
                                fetch: {
                                  ...(settings.fetch || {}),
                                  virtual: {
                                    ...(settings.fetch?.virtual || {}),
                                    globals: {
                                      ...(settings.fetch?.virtual?.globals ||
                                        {}),
                                      dateFormat: e.target.value || null,
                                    },
                                  },
                                },
                              })
                            }
                            placeholder={t.settings.dateFormatPlaceholder}
                          />
                        </div>
                      </div>
                    </div>

                    {renderVirtualConfigSection(
                      "position",
                      settings.fetch?.virtual?.position || [],
                    )}
                    {renderVirtualConfigSection(
                      "transactions",
                      settings.fetch?.virtual?.transactions || [],
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
