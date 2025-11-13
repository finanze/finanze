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
import { motion } from "framer-motion"
import {
  PlusCircle,
  ChevronDown,
  ChevronUp,
  Save,
  RefreshCw,
  Info,
  Link2,
  Link2Off,
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
import { WeightUnit } from "@/types/position"
import { setupIntegration, disableIntegration } from "@/services/api"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/lib/utils"
import {
  PlatformType,
  ExternalIntegrationStatus,
  type ExternalIntegration,
} from "@/types"

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

type IntegrationHintPart =
  | { type: "text"; value: string }
  | { type: "link"; label: string; url: string }

const parseIntegrationHintParts = (
  rawParts: unknown,
): IntegrationHintPart[] | undefined => {
  if (!Array.isArray(rawParts)) {
    return undefined
  }

  const parsed = rawParts
    .map(part => {
      if (typeof part === "string") {
        return part.trim() ? ({ type: "text", value: part } as const) : null
      }

      if (!part || typeof part !== "object") {
        return null
      }

      const data = part as Record<string, unknown>
      const type = typeof data.type === "string" ? data.type : undefined

      if (type === "link") {
        const label = typeof data.label === "string" ? data.label.trim() : ""
        const url = typeof data.url === "string" ? data.url.trim() : ""
        return label && url ? ({ type: "link", label, url } as const) : null
      }

      const value = typeof data.value === "string" ? data.value : undefined

      return value && value.trim() ? ({ type: "text", value } as const) : null
    })
    .filter(Boolean) as IntegrationHintPart[]

  return parsed.length > 0 ? parsed : undefined
}

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

  const [, setValidationErrors] = useState<Record<string, string[]>>({})

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

  const getIntegrationCopy = useCallback(
    (integration: ExternalIntegration) => {
      const translations =
        (
          ((t.settings as unknown as Record<string, unknown>)?.integration ??
            {}) as Record<string, unknown>
        )[integration.id] ?? {}

      const copy = translations as Record<string, unknown>

      const descriptionRaw =
        typeof copy.description === "string" ? copy.description.trim() : ""
      const helpRaw = typeof copy.help === "string" ? copy.help.trim() : ""
      const hintRaw =
        typeof copy.hint === "object" && copy.hint !== null
          ? (copy.hint as Record<string, unknown>)
          : undefined

      const hintText =
        typeof hintRaw?.text === "string" ? hintRaw.text.trim() : ""
      const hintTitleRaw =
        typeof hintRaw?.title === "string" ? hintRaw.title.trim() : ""
      const hintParts = parseIntegrationHintParts(hintRaw?.parts)

      const hint =
        hintParts || hintText
          ? {
              title: hintTitleRaw || integration.name,
              text: hintText || undefined,
              parts: hintParts,
            }
          : undefined

      return {
        title: integration.name,
        description: descriptionRaw || undefined,
        helpLabel: helpRaw || undefined,
        hint,
      }
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

      const { title: integrationName } = getIntegrationCopy(integration)

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
      getIntegrationCopy,
      integrationPayloads,
      platform,
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

      const { title: integrationName } = getIntegrationCopy(integration)

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
      getIntegrationCopy,
      showToast,
      t,
    ],
  )

  const validateSettings = () => {
    const errors: Record<string, string[]> = {}

    const exportSheets = settings.export?.sheets ?? {}
    const exportSectionsConfigured = Object.entries(exportSheets).some(
      ([section, items]) =>
        section !== "globals" && Array.isArray(items) && items.length > 0,
    )

    if (exportSectionsConfigured && !exportSheets?.globals?.spreadsheetId) {
      errors.globals = [t.settings.errors.spreadsheetIdRequired]
    }

    Object.entries(exportSheets).forEach(([section, items]) => {
      if (section === "globals" || !Array.isArray(items)) {
        return
      }

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
          (!item.data || (Array.isArray(item.data) && item.data.length === 0))
        ) {
          if (!sectionErrors[index]) sectionErrors[index] = ""
          sectionErrors[index] += t.settings.errors.dataRequired
        }
      })

      if (sectionErrors.length > 0) {
        errors[section] = sectionErrors
      }
    })

    const virtualConfig = settings.importing?.sheets ?? {}
    const virtualSectionsConfigured = Object.entries(virtualConfig).some(
      ([section, items]) =>
        section !== "globals" && Array.isArray(items) && items.length > 0,
    )

    if (virtualSectionsConfigured && !virtualConfig?.globals?.spreadsheetId) {
      errors.virtualGlobals = [t.settings.errors.virtualSpreadsheetIdRequired]
    }

    Object.entries(virtualConfig).forEach(([section, items]) => {
      if (section === "globals" || !Array.isArray(items)) {
        return
      }

      const sectionErrors: string[] = []

      items.forEach((item: any, index: number) => {
        if (!item.range) {
          if (!sectionErrors[index]) sectionErrors[index] = ""
          sectionErrors[index] += t.settings.errors.rangeRequired
        }

        if (
          (section === "position" || section === "transactions") &&
          (!item.data || (Array.isArray(item.data) && item.data.length === 0))
        ) {
          if (!sectionErrors[index]) sectionErrors[index] = ""
          sectionErrors[index] += t.settings.errors.dataRequired
        }
      })

      if (sectionErrors.length > 0) {
        errors[`virtual_${section}`] = sectionErrors
      }
    })

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const processDataFields = (settingsObj: any) => {
    const processed = { ...settingsObj }

    if (processed.export?.sheets) {
      Object.entries(processed.export.sheets).forEach(([section, items]) => {
        if (section !== "globals" && Array.isArray(items)) {
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

    if (processed.importing?.sheets) {
      Object.entries(processed.importing.sheets).forEach(([section, items]) => {
        if (section !== "globals" && Array.isArray(items)) {
          ;(items as any[]).forEach(item => {
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

    const { title, description, helpLabel, hint } =
      getIntegrationCopy(integration)

    const hintContent = (() => {
      if (!hint) {
        return null
      }

      if (hint.parts) {
        return (
          <p className="text-sm leading-relaxed">
            {hint.parts.map((part, index) => {
              if (part.type === "link") {
                return (
                  <a
                    key={`${integration.id}-hint-link-${index}`}
                    href={part.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline text-primary"
                  >
                    {part.label}
                  </a>
                )
              }

              return (
                <span key={`${integration.id}-hint-text-${index}`}>
                  {part.value}
                </span>
              )
            })}
          </p>
        )
      }

      if (hint.text) {
        return <p className="text-sm leading-relaxed">{hint.text}</p>
      }

      return null
    })()

    const hintButtonLabel =
      helpLabel ?? t.settings.integrationHintButton ?? t.common.help

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
                const showHintInline = Boolean(hintContent) && index === 0

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
                            <h4 className="text-sm font-medium">
                              {hint?.title ?? title}
                            </h4>
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
          <TabsList className="grid w-full max-w-[800px] h-auto min-h-[3rem] grid-cols-3 sm:grid-cols-3 md:grid-cols-3">
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
      </Tabs>
    </div>
  )
}
