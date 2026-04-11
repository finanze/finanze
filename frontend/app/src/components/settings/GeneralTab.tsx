import { useState, useEffect, useCallback, useRef } from "react"
import { useI18n } from "@/i18n"
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
import { Switch } from "@/components/ui/Switch"
import { motion } from "framer-motion"
import {
  PlusCircle,
  ChevronDown,
  ChevronUp,
  Coins,
  Edit2,
  X,
  Check,
  AlertTriangle,
  Database,
  User,
  LogOut,
  KeyRound,
} from "lucide-react"
import { AppSettings, useAppContext } from "@/context/AppContext"
import { useAuth } from "@/context/AuthContext"
import { WeightUnit } from "@/types/position"
import { AutoRefreshMaxOutdatedTime, AutoRefreshMode } from "@/types"
import { EntitySelector } from "@/components/EntitySelector"
import {
  getAutoRefreshCompatibleEntities,
  entityHasPin,
} from "@/utils/autoRefreshUtils"
import { copyToClipboard } from "@/lib/clipboard"

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

const AUTO_SAVE_DEBOUNCE_MS = 500

export function GeneralTab() {
  const { t } = useI18n()
  const {
    showToast,
    settings: storedSettings,
    saveSettings,
    entities,
  } = useAppContext()
  const { user, logout, startPasswordChange } = useAuth()

  const [settings, setSettings] = useState<AppSettings>(storedSettings)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isInitializedRef = useRef(false)
  const isSyncingFromContextRef = useRef(false)
  const persistRef = useRef<(s: AppSettings) => void>(() => {})

  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({
    dataAutoRefresh: false,
    assetsCrypto: false,
  })

  const [newStablecoin, setNewStablecoin] = useState("")
  const [editingStablecoinIndex, setEditingStablecoinIndex] = useState<
    number | null
  >(null)
  const [stablecoinDraft, setStablecoinDraft] = useState("")
  const [isAddingStablecoin, setIsAddingStablecoin] = useState(false)
  const newStablecoinInputRef = useRef<HTMLInputElement | null>(null)
  const stablecoins = settings.assets?.crypto?.stablecoins ?? []
  const hideUnknownTokens = settings.assets?.crypto?.hideUnknownTokens ?? false

  const autoRefreshEnabled =
    settings.data?.autoRefresh?.mode === AutoRefreshMode.NO_2FA
  const autoRefreshMaxOutdated =
    settings.data?.autoRefresh?.max_outdated ??
    AutoRefreshMaxOutdatedTime.TWELVE_HOURS
  const autoRefreshEntityIds = (settings.data?.autoRefresh?.entities ?? []).map(
    entry => entry.id,
  )

  useEffect(() => {
    if (isInitializedRef.current) {
      isSyncingFromContextRef.current = true
    }
    setSettings(storedSettings)
  }, [storedSettings])

  const persistSettings = useCallback(
    (nextSettings: AppSettings) => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(async () => {
        const sanitizedStablecoins = Array.from(
          new Set(
            (nextSettings.assets?.crypto?.stablecoins ?? []).map(symbol =>
              symbol.trim().toUpperCase(),
            ),
          ),
        ).filter(Boolean)

        const settingsForSave: AppSettings = {
          ...nextSettings,
          assets: {
            ...nextSettings.assets,
            crypto: {
              ...nextSettings.assets?.crypto,
              stablecoins: sanitizedStablecoins,
            },
          },
        }

        const cleanedSettings = cleanObject(settingsForSave)

        if (!cleanedSettings.assets) {
          cleanedSettings.assets = {
            crypto: { stablecoins: sanitizedStablecoins },
          }
        } else {
          cleanedSettings.assets.crypto = cleanedSettings.assets.crypto || {
            stablecoins: [],
          }
          cleanedSettings.assets.crypto.stablecoins = sanitizedStablecoins
        }

        if (settingsForSave.data?.autoRefresh) {
          cleanedSettings.data = cleanedSettings.data || {}
          cleanedSettings.data.autoRefresh = {
            ...settingsForSave.data.autoRefresh,
          }
        }

        await saveSettings(cleanedSettings, { silent: true })
      }, AUTO_SAVE_DEBOUNCE_MS)
    },
    [saveSettings],
  )

  persistRef.current = persistSettings

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!isInitializedRef.current) {
      isInitializedRef.current = true
      return
    }
    if (isSyncingFromContextRef.current) {
      isSyncingFromContextRef.current = false
      return
    }
    persistRef.current(settings)
  }, [settings])

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
    [],
  )

  const handleHideUnknownTokensChange = useCallback((checked: boolean) => {
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
  }, [])

  const handleAutoRefreshEnabledChange = useCallback((checked: boolean) => {
    setSettings(prev => ({
      ...prev,
      data: {
        ...prev.data,
        autoRefresh: {
          ...prev.data?.autoRefresh,
          mode: checked ? AutoRefreshMode.NO_2FA : AutoRefreshMode.OFF,
          max_outdated:
            prev.data?.autoRefresh?.max_outdated ??
            AutoRefreshMaxOutdatedTime.TWELVE_HOURS,
          entities: prev.data?.autoRefresh?.entities ?? [],
        },
      },
    }))
  }, [])

  const handleAutoRefreshMaxOutdatedChange = useCallback(
    (value: AutoRefreshMaxOutdatedTime) => {
      setSettings(prev => ({
        ...prev,
        data: {
          ...prev.data,
          autoRefresh: {
            ...prev.data?.autoRefresh,
            mode: prev.data?.autoRefresh?.mode ?? AutoRefreshMode.OFF,
            max_outdated: value,
            entities: prev.data?.autoRefresh?.entities ?? [],
          },
        },
      }))
    },
    [],
  )

  const handleAutoRefreshEntitiesChange = useCallback((entityIds: string[]) => {
    const mapped = entityIds.map(id => ({ id }))
    setSettings(prev => ({
      ...prev,
      data: {
        ...prev.data,
        autoRefresh: {
          ...prev.data?.autoRefresh,
          mode: prev.data?.autoRefresh?.mode ?? AutoRefreshMode.OFF,
          max_outdated:
            prev.data?.autoRefresh?.max_outdated ??
            AutoRefreshMaxOutdatedTime.TWELVE_HOURS,
          entities: mapped,
        },
      },
    }))
  }, [])

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
  }, [newStablecoin, showToast, stablecoins, t, updateStablecoins])

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

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const handleCurrencyChange = (currency: string) => {
    setSettings(prev => ({
      ...prev,
      general: {
        ...prev.general,
        defaultCurrency: currency,
      },
    }))
  }

  const handleCommodityWeightUnitChange = (unit: string) => {
    setSettings(prev => ({
      ...prev,
      general: {
        ...prev.general,
        defaultCommodityWeightUnit: unit,
      },
    }))
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>{t.settings.general}</CardTitle>
            <CardDescription>{t.settings.generalDescription}</CardDescription>
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
                      {t.enums.weightUnit.GRAM} - {t.enums.weightUnitName.GRAM}
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
          <CardHeader>
            <CardTitle>{t.settings.dataSettings.title}</CardTitle>
            <CardDescription>
              {t.settings.dataSettings.description}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div
                className="flex cursor-pointer items-center justify-between rounded-md border border-border/50 bg-muted/20 px-3 py-2 transition-colors hover:bg-muted/30 dark:bg-muted/10 dark:hover:bg-muted/20"
                onClick={() => toggleSection("dataAutoRefresh")}
              >
                <div className="flex items-start gap-3">
                  <Database className="mt-0.5 h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium">
                      {t.settings.dataSettings.autoRefresh.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t.settings.dataSettings.autoRefresh.description}
                    </p>
                  </div>
                </div>
                {expandedSections.dataAutoRefresh ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </div>
              {expandedSections.dataAutoRefresh && (
                <div className="space-y-4 rounded-md border border-dashed border-border/60 bg-background/60 p-4 dark:bg-muted/10">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {t.settings.dataSettings.autoRefresh.enableLabel}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t.settings.dataSettings.autoRefresh.enableDescription}
                      </p>
                    </div>
                    <Switch
                      checked={autoRefreshEnabled}
                      onCheckedChange={handleAutoRefreshEnabledChange}
                    />
                  </div>
                  {autoRefreshEnabled && (
                    <>
                      <div className="border-t border-border/50 pt-4">
                        <div className="space-y-3">
                          <div className="space-y-1">
                            <Label htmlFor="max-outdated">
                              {
                                t.settings.dataSettings.autoRefresh
                                  .maxOutdatedLabel
                              }
                            </Label>
                            <p className="text-xs text-muted-foreground">
                              {
                                t.settings.dataSettings.autoRefresh
                                  .maxOutdatedDescription
                              }
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {Object.values(AutoRefreshMaxOutdatedTime)
                              .filter(
                                option =>
                                  import.meta.env.DEV ||
                                  option !==
                                    AutoRefreshMaxOutdatedTime.THREE_HOURS,
                              )
                              .map(option => (
                                <button
                                  key={option}
                                  type="button"
                                  onClick={() =>
                                    handleAutoRefreshMaxOutdatedChange(option)
                                  }
                                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                                    autoRefreshMaxOutdated === option
                                      ? "bg-primary text-primary-foreground"
                                      : "bg-muted/50 text-muted-foreground hover:bg-muted"
                                  }`}
                                >
                                  {
                                    t.settings.dataSettings.autoRefresh
                                      .maxOutdatedOptions[option]
                                  }
                                </button>
                              ))}
                          </div>
                        </div>
                      </div>
                      <div className="border-t border-border/50 pt-4">
                        <div className="space-y-3">
                          <div className="space-y-1">
                            <Label>
                              {
                                t.settings.dataSettings.autoRefresh
                                  .entitiesLabel
                              }
                            </Label>
                            <p className="text-xs text-muted-foreground">
                              {
                                t.settings.dataSettings.autoRefresh
                                  .entitiesDescription
                              }
                            </p>
                          </div>
                          <EntitySelector
                            entities={getAutoRefreshCompatibleEntities(
                              entities,
                            )}
                            selectedEntityIds={autoRefreshEntityIds}
                            onSelectionChange={handleAutoRefreshEntitiesChange}
                            description={
                              t.settings.dataSettings.autoRefresh
                                .entitiesDescription
                            }
                            emptyMessage={
                              t.settings.dataSettings.autoRefresh
                                .noEntitiesAvailable
                            }
                            placeholder={
                              t.settings.dataSettings.autoRefresh
                                .entitiesPlaceholder
                            }
                            emptySelectionBadge={
                              t.settings.dataSettings.autoRefresh.allEntities
                            }
                            entityWarning={entityHasPin}
                            warningBanner={
                              getAutoRefreshCompatibleEntities(entities).some(
                                entityHasPin,
                              ) ? (
                                <div className="flex items-start gap-2 rounded-md bg-amber-500/10 p-2 m-1.5 text-xs">
                                  <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0 text-amber-500" />
                                  <p className="text-muted-foreground">
                                    {
                                      t.settings.dataSettings.autoRefresh
                                        .pinWarningTooltip
                                    }
                                  </p>
                                </div>
                              ) : undefined
                            }
                          />
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </motion.div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader onClick={() => toggleSection("assets")}>
            <CardTitle>{t.settings.assets.title}</CardTitle>
            <CardDescription>{t.settings.assets.description}</CardDescription>
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
                                normalizeStablecoinSymbol(event.target.value),
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
                            aria-label={t.settings.assets.crypto.confirmEdit}
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
                            t.settings.assets.crypto.addStablecoinPlaceholder
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
                          aria-label={t.settings.assets.crypto.addStablecoin}
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
                        <span>{t.settings.assets.crypto.addStablecoin}</span>
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
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.15 }}
      >
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <User className="h-5 w-5 text-primary" />
              <CardTitle>{t.settings.userTitle}</CardTitle>
            </div>
            <CardDescription>{t.settings.userDescription}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-center sm:gap-4">
              <Button
                variant="outline"
                className="justify-start"
                onClick={() => startPasswordChange()}
              >
                <KeyRound className="mr-2 h-4 w-4" />
                {t.login.changePassword}
              </Button>
              <Button
                variant="outline"
                className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 justify-start"
                onClick={async () => {
                  try {
                    await logout()
                  } catch (error) {
                    console.error("Logout failed:", error)
                  }
                }}
              >
                <LogOut className="mr-2 h-4 w-4" />
                {t.common.logout}
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
      <div className="flex justify-between items-center">
        <button
          type="button"
          className="text-[0.4rem] text-gray-500 dark:text-gray-400 text-left font-mono enabled:cursor-pointer"
          disabled={!user?.id}
          onClick={() => {
            if (user?.id) {
              copyToClipboard(user.id)
            }
          }}
        >
          {user?.id}
        </button>
        <button
          type="button"
          onClick={() => window.open(t.common.officialWebpageUrl, "_blank")}
          className="text-[0.5rem] text-primary hover:underline"
        >
          {t.common.officialWebpage}
        </button>
        <p className="text-[0.5rem] text-gray-500 dark:text-gray-400">
          v{__APP_VERSION__} by marcosav
        </p>
      </div>
    </>
  )
}
