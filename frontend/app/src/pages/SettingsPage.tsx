import { useState, useEffect } from "react"
import { useI18n } from "@/i18n"
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
  FileSpreadsheet,
} from "lucide-react"
import { AppSettings, useAppContext } from "@/context/AppContext"
import { getExternalIntegrations } from "@/services/api"
import type { ExternalIntegration } from "@/types"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ProductType, WeightUnit } from "@/types/position"
import { setupGoogleIntegration } from "@/services/api"
import { Badge } from "@/components/ui/Badge"
import { cn } from "@/lib/utils"

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

export default function SettingsPage() {
  const { t } = useI18n()
  const {
    showToast,
    fetchSettings,
    settings: storedSettings,
    saveSettings,
    isLoading,
  } = useAppContext()
  const [settings, setSettings] = useState<AppSettings>(storedSettings)
  const [isSaving, setIsSaving] = useState(false)
  const [activeTab, setActiveTab] = useState("general")
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    position: false,
    contributions: false,
    transactions: false,
    historic: false,
    virtualPosition: false,
    virtualTransactions: false,
    googleSheets: false,
  })

  const [externalIntegrations, setExternalIntegrations] = useState<
    ExternalIntegration[]
  >([])
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string[]>
  >({})

  useEffect(() => {
    if (activeTab === "integrations") {
      getExternalIntegrations()
        .then(data => setExternalIntegrations(data.integrations))
        .catch(err =>
          console.error("Error loading external integrations:", err),
        )
    }
  }, [activeTab])

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
  }, [])

  const toggleSection = (section: string) => {
    setExpandedSections({
      ...expandedSections,
      [section]: !expandedSections[section],
    })
  }

  const handleUpdateCooldown = (value: string) => {
    setSettings({
      ...settings,
      fetch: {
        ...settings.fetch,
        updateCooldown: value === "" ? 60 : Number.parseInt(value) || 60,
      },
    })
  }

  const handleExportToggle = (enabled: boolean) => {
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

  const handleSetupGoogleIntegration = async () => {
    const clientId = settings?.integrations?.sheets?.credentials?.client_id
    const clientSecret =
      settings?.integrations?.sheets?.credentials?.client_secret
    if (!clientId || !clientSecret) {
      setValidationErrors(prev => ({
        ...prev,
        integrations: [
          t.settings.errors.clientIdRequired,
          t.settings.errors.clientSecretRequired,
        ],
      }))
      return
    }
    try {
      await setupGoogleIntegration({
        client_id: clientId,
        client_secret: clientSecret,
      })
      showToast(t.common.success, "success")
    } catch (error) {
      console.error(error)
      showToast(t.common.error, "error")
    }
  }

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

    // Validate integrations credentials
    const clientId = settings.integrations?.sheets?.credentials?.client_id
    const clientSecret =
      settings.integrations?.sheets?.credentials?.client_secret

    if (clientId || clientSecret) {
      const integrationErrors: string[] = []

      if (!clientId) {
        integrationErrors.push(
          t.settings.errors.clientIdRequired ||
            "Client ID is required when configuring Google Sheets integration",
        )
      }

      if (!clientSecret) {
        integrationErrors.push(
          t.settings.errors.clientSecretRequired ||
            "Client Secret is required when configuring Google Sheets integration",
        )
      }

      if (integrationErrors.length > 0) {
        errors.integrations = integrationErrors
      }
    }

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

      const processedSettings = processDataFields({ ...settings })

      const cleanedSettings = cleanObject(processedSettings)

      if (cleanedSettings.fetch && cleanedSettings.fetch.virtual) {
        cleanedSettings.fetch.virtual.enabled =
          !!cleanedSettings.fetch.virtual.enabled
      }
      if (cleanedSettings.export && cleanedSettings.export.sheets) {
        cleanedSettings.export.sheets.enabled =
          !!cleanedSettings.export.sheets.enabled
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

  if (isLoading || !settings) {
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
          <Button
            variant="outline"
            size="icon"
            onClick={fetchSettings}
            disabled={isLoading || isSaving}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleSave} disabled={isSaving || isLoading}>
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
        </div>
      </div>

      <Tabs
        defaultValue="general"
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full"
      >
        <div className="flex justify-center w-full">
          <TabsList className="grid grid-cols-4 w-full max-w-[800px] h-auto min-h-[3rem]">
            <TabsTrigger
              value="general"
              className="text-xs sm:text-sm px-1 sm:px-2 py-2 whitespace-normal text-center leading-tight min-h-[2.5rem] flex items-center justify-center"
            >
              {t.settings.general}
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
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4 mt-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="space-y-4"
          >
            {/* Google Sheets Integration */}
            <Card>
              <CardHeader>
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleSection("googleSheets")}
                >
                  <div className="flex items-center">
                    <FileSpreadsheet className="mr-2 h-5 w-5 text-green-600" />
                    <CardTitle>{t.settings.sheetsIntegration}</CardTitle>
                  </div>
                  <div className="flex items-center space-x-1">
                    {(() => {
                      const google = externalIntegrations.find(
                        i => i.id === "GOOGLE_SHEETS",
                      )
                      const on = google?.status === "ON"
                      return (
                        <Badge
                          className={cn(
                            on
                              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                              : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                          )}
                        >
                          {on ? t.common.enabled : t.common.disabled}
                        </Badge>
                      )
                    })()}
                    {expandedSections.googleSheets ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                </div>
                <CardDescription>
                  {t.settings.sheetsIntegrationDescription}
                </CardDescription>
              </CardHeader>
              {expandedSections.googleSheets && (
                <CardContent className="space-y-6">
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="client-id">{t.settings.clientId}</Label>
                      <Input
                        id="client-id"
                        type="text"
                        placeholder={t.settings.clientIdPlaceholder}
                        value={
                          settings?.integrations?.sheets?.credentials
                            ?.client_id || ""
                        }
                        onChange={e =>
                          setSettings({
                            ...settings,
                            integrations: {
                              ...settings.integrations,
                              sheets: {
                                ...settings.integrations?.sheets,
                                credentials: {
                                  ...settings.integrations?.sheets?.credentials,
                                  client_id: e.target.value,
                                },
                              },
                            },
                          })
                        }
                        className={
                          validationErrors.integrations &&
                          !settings?.integrations?.sheets?.credentials
                            ?.client_id
                            ? "border-red-500"
                            : ""
                        }
                      />
                      {validationErrors.integrations &&
                        !settings?.integrations?.sheets?.credentials
                          ?.client_id && (
                          <div className="text-red-500 text-sm">
                            {t.settings.errors.clientIdRequired}
                          </div>
                        )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="client-secret">
                        {t.settings.clientSecret}
                      </Label>
                      <Input
                        id="client-secret"
                        type="password"
                        placeholder={t.settings.clientSecretPlaceholder}
                        value={
                          settings?.integrations?.sheets?.credentials
                            ?.client_secret || ""
                        }
                        onChange={e =>
                          setSettings({
                            ...settings,
                            integrations: {
                              ...settings.integrations,
                              sheets: {
                                ...settings.integrations?.sheets,
                                credentials: {
                                  ...settings.integrations?.sheets?.credentials,
                                  client_secret: e.target.value,
                                },
                              },
                            },
                          })
                        }
                        className={
                          validationErrors.integrations &&
                          !settings?.integrations?.sheets?.credentials
                            ?.client_secret
                            ? "border-red-500"
                            : ""
                        }
                      />
                      {validationErrors.integrations &&
                        !settings?.integrations?.sheets?.credentials
                          ?.client_secret && (
                          <div className="text-red-500 text-sm">
                            {t.settings.errors.clientSecretRequired}
                          </div>
                        )}
                    </div>

                    {/* Add Setup button */}
                    <div className="flex justify-end">
                      <Button
                        onClick={handleSetupGoogleIntegration}
                        disabled={
                          !settings?.integrations?.sheets?.credentials
                            ?.client_id ||
                          !settings?.integrations?.sheets?.credentials
                            ?.client_secret
                        }
                      >
                        {t.common.setup}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
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
                  <Label htmlFor="export-enabled">{t.settings.enabled}</Label>
                  <Switch
                    id="export-enabled"
                    checked={settings.export?.sheets?.enabled === true}
                    onCheckedChange={handleExportToggle}
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
            <Card className="mb-4">
              <CardHeader>
                <CardTitle>{t.settings.scrapeSettings}</CardTitle>
                <CardDescription>
                  {t.settings.scrapeDescription}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Label htmlFor="updateCooldown">
                    {t.settings.updateCooldown}
                  </Label>
                  <Input
                    id="updateCooldown"
                    type="number"
                    value={settings.fetch?.updateCooldown ?? 60}
                    onChange={e => handleUpdateCooldown(e.target.value)}
                    placeholder="0"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t.settings.virtual}</CardTitle>
                <CardDescription>
                  {t.settings.virtualDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="virtual-enabled">{t.settings.enabled}</Label>
                  <Switch
                    id="virtual-enabled"
                    checked={settings.fetch?.virtual?.enabled === true}
                    onCheckedChange={handleVirtualToggle}
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
