import { useState, useEffect, useCallback, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n, type Locale } from "@/i18n"
import { Badge } from "@/components/ui/Badge"
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
  Coins,
  Edit2,
  X,
  Check,
  AlertTriangle,
} from "lucide-react"
import { AppSettings, useAppContext } from "@/context/AppContext"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { WeightUnit } from "@/types/position"
import { AdvancedSettingsForm } from "@/components/ui/AdvancedSettingsForm"
import { IntegrationsTab } from "@/components/settings/IntegrationsTab"

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
    fetchExternalIntegrations,
  } = useAppContext()
  const [settings, setSettings] = useState<AppSettings>(storedSettings)
  const [isSaving, setIsSaving] = useState(false)
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
    advancedSettings: false,
  })

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

  const isDesktopApp = typeof window !== "undefined" && !!window.ipcAPI

  const applicationLanguageOptions = APPLICATION_LOCALES.map(code => ({
    code,
    label: t.settings.applicationLanguageOptions[code],
  }))

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

  const toggleSection = (section: string) => {
    setExpandedSections({
      ...expandedSections,
      [section]: !expandedSections[section],
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
      errors.virtualGlobals = [t.settings.errors.importSpreadsheetIdRequired]
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

              {/* Advanced Settings Section (Desktop only) */}
              {isDesktopApp && (
                <Card>
                  <CardHeader
                    className="cursor-pointer select-none"
                    onClick={() => toggleSection("advancedSettings")}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{t.advancedSettings.title}</CardTitle>
                        <CardDescription>
                          {t.advancedSettings.subtitle}
                        </CardDescription>
                      </div>
                      {expandedSections.advancedSettings ? (
                        <ChevronUp className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </CardHeader>
                  {expandedSections.advancedSettings && (
                    <CardContent>
                      <div className="space-y-3">
                        <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                          {t.advancedSettings.restartWarning}
                        </p>
                        <AdvancedSettingsForm
                          idPrefix="settings"
                          onError={() =>
                            showToast(t.settings.saveError, "error")
                          }
                        />
                      </div>
                    </CardContent>
                  )}
                </Card>
              )}
            </div>
          </motion.div>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4 mt-4">
          <IntegrationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
