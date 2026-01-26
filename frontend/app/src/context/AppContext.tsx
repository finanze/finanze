import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  useEffect,
  useRef,
  useCallback,
} from "react"
import {
  EntityStatus,
  AutoRefreshMode,
  AutoRefreshMaxOutdatedTime,
  type Entity,
  type ExchangeRates,
  type ExternalIntegration,
  type FeatureFlags,
  type DataConfig,
  type AutoRefresh,
} from "@/types"
import {
  getEntities,
  getSettings,
  saveSettings,
  getExchangeRates,
  getExternalIntegrations,
  updateQuotesManualPositions,
} from "@/services/api"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"
import { WeightUnit } from "@/types/position"
import {
  getFeatureFlags,
  subscribeFeatureFlags,
} from "@/context/featureFlagsStore"

export interface AppSettings {
  export?: {
    sheets?: {
      [key: string]: any
    }
  }
  importing?: {
    sheets?: {
      [key: string]: any
    }
  }
  general: {
    defaultCurrency: string
    defaultCommodityWeightUnit: string
  }
  assets: {
    crypto: {
      stablecoins: string[]
      hideUnknownTokens: boolean
    }
  }
  data?: DataConfig
}

export interface ExportState {
  isExporting: boolean
  lastExportTime: number | null
}

interface AppContextType {
  entities: Entity[]
  entitiesLoaded: boolean
  isLoadingEntities: boolean
  featureFlags: FeatureFlags
  toast: {
    message: string
    type: "success" | "error" | "warning" | null
  } | null
  settings: AppSettings
  isLoadingSettings: boolean
  exchangeRates: ExchangeRates
  exchangeRatesLoading: boolean
  exchangeRatesError: string | null
  externalIntegrations: ExternalIntegration[]
  externalIntegrationsLoading: boolean
  exportState: ExportState
  setExportState: (
    state: ExportState | ((prev: ExportState) => ExportState),
  ) => void
  fetchEntities: () => Promise<void>
  updateEntityStatus: (entityId: string, status: EntityStatus) => void
  updateEntityLastFetch: (entityId: string, features: string[]) => void
  showToast: (message: string, type: "success" | "error" | "warning") => void
  hideToast: () => void
  fetchSettings: () => Promise<void>
  saveSettings: (settings: AppSettings) => Promise<boolean>
  refreshExchangeRates: () => Promise<void>
  fetchExternalIntegrations: () => Promise<void>
}

const AppContext = createContext<AppContextType | undefined>(undefined)

const defaultSettings: AppSettings = {
  export: {
    sheets: {},
  },
  importing: {
    sheets: {},
  },
  general: {
    defaultCurrency: "EUR",
    defaultCommodityWeightUnit: WeightUnit.GRAM,
  },
  assets: {
    crypto: {
      stablecoins: [],
      hideUnknownTokens: false,
    },
  },
  data: {
    autoRefresh: {
      mode: AutoRefreshMode.OFF,
      max_outdated: AutoRefreshMaxOutdatedTime.TWELVE_HOURS,
      entities: [],
    },
  },
}

const defaultAutoRefresh: AutoRefresh = {
  mode: AutoRefreshMode.OFF,
  max_outdated: AutoRefreshMaxOutdatedTime.TWELVE_HOURS,
  entities: [],
}

const mergeSettingsWithDefaults = (
  incoming?: Partial<AppSettings>,
): AppSettings => {
  const mergedExportSheets = {
    ...(defaultSettings.export?.sheets ?? {}),
    ...(incoming?.export?.sheets ?? {}),
    globals: {
      ...(defaultSettings.export?.sheets?.globals ?? {}),
      ...(incoming?.export?.sheets?.globals ?? {}),
    },
  }

  const mergedImportingSheets = {
    ...(defaultSettings.importing?.sheets ?? {}),
    ...(incoming?.importing?.sheets ?? {}),
    globals: {
      ...(defaultSettings.importing?.sheets?.globals ?? {}),
      ...(incoming?.importing?.sheets?.globals ?? {}),
    },
  }

  const mergedAssets = {
    ...defaultSettings.assets,
    ...incoming?.assets,
    crypto: {
      ...defaultSettings.assets.crypto,
      ...incoming?.assets?.crypto,
      stablecoins:
        incoming?.assets?.crypto?.stablecoins ??
        defaultSettings.assets.crypto.stablecoins,
      hideUnknownTokens:
        incoming?.assets?.crypto?.hideUnknownTokens ??
        defaultSettings.assets.crypto.hideUnknownTokens,
    },
  }

  return {
    ...defaultSettings,
    ...incoming,
    general: {
      ...defaultSettings.general,
      ...(incoming?.general ?? {}),
    },
    export: defaultSettings.export
      ? {
          ...defaultSettings.export,
          ...(incoming?.export ?? {}),
          sheets: mergedExportSheets,
        }
      : incoming?.export,
    importing: defaultSettings.importing
      ? {
          ...defaultSettings.importing,
          ...(incoming?.importing ?? {}),
          sheets: mergedImportingSheets,
        }
      : incoming?.importing,
    assets: mergedAssets,
    data: {
      autoRefresh: {
        ...defaultAutoRefresh,
        ...incoming?.data?.autoRefresh,
        entities: incoming?.data?.autoRefresh?.entities ?? [],
      },
    },
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Entity[]>([])
  const [entitiesLoaded, setEntitiesLoaded] = useState(false)
  const [isLoadingEntities, setIsLoadingEntities] = useState(false)
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>(() =>
    getFeatureFlags(),
  )
  const [toast, setToast] = useState<{
    message: string
    type: "success" | "error" | "warning" | null
  } | null>(null)
  const [settings, setSettings] = useState<AppSettings>({ ...defaultSettings })
  const [isLoadingSettings, setIsLoadingSettings] = useState(false)
  const [exchangeRates, setExchangeRates] = useState<ExchangeRates>({})
  const [exchangeRatesLoading, setExchangeRatesLoading] = useState(false)
  const [exchangeRatesError, setExchangeRatesError] = useState<string | null>(
    null,
  )
  const [externalIntegrations, setExternalIntegrations] = useState<
    ExternalIntegration[]
  >([])
  const [externalIntegrationsLoading, setExternalIntegrationsLoading] =
    useState(false)
  const [exportState, setExportState] = useState<ExportState>({
    isExporting: false,
    lastExportTime: null,
  })

  const { t } = useI18n()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    return subscribeFeatureFlags(setFeatureFlags)
  }, [])

  const initialFetchDone = useRef(false)
  const exchangeRatesTimerRef = useRef<NodeJS.Timeout | null>(null)

  const LAST_UPDATE_QUOTES_KEY = "lastUpdateQuotesTime"
  const QUOTES_UPDATE_INTERVAL_MS = 6 * 60 * 60 * 1000
  const EXCHANGE_RATES_REFRESH_INTERVAL_MS = 10 * 60 * 1000

  const showToast = useCallback(
    (message: string, type: "success" | "error" | "warning") => {
      setToast({ message, type })
      setTimeout(
        () => {
          setToast(null)
        },
        type === "success" ? 3000 : 5000,
      )
    },
    [],
  )

  const hideToast = useCallback(() => {
    setToast(null)
  }, [])

  const fetchExchangeRatesSilently = useCallback(async () => {
    if (!isAuthenticated) return

    try {
      setExchangeRatesError(null)
      const rates = await getExchangeRates()
      setExchangeRates(rates)
    } catch (error) {
      console.error("Error fetching exchange rates silently:", error)
    }
  }, [isAuthenticated])

  const startExchangeRatesTimer = useCallback(() => {
    if (exchangeRatesTimerRef.current) {
      clearInterval(exchangeRatesTimerRef.current)
    }

    exchangeRatesTimerRef.current = setInterval(() => {
      if (isAuthenticated) {
        fetchExchangeRatesSilently()
      }
    }, EXCHANGE_RATES_REFRESH_INTERVAL_MS)
  }, [fetchExchangeRatesSilently, isAuthenticated])

  const stopExchangeRatesTimer = useCallback(() => {
    if (exchangeRatesTimerRef.current) {
      clearInterval(exchangeRatesTimerRef.current)
      exchangeRatesTimerRef.current = null
    }
  }, [])

  const fetchExchangeRates = useCallback(async () => {
    if (!isAuthenticated) return

    try {
      setExchangeRatesLoading(true)
      setExchangeRatesError(null)
      const rates = await getExchangeRates()
      setExchangeRates(rates)

      if (!exchangeRatesTimerRef.current) {
        startExchangeRatesTimer()
      }
    } catch (error) {
      console.error("Error fetching exchange rates:", error)
      setExchangeRatesError(t.common.fetchError)
    } finally {
      setExchangeRatesLoading(false)
    }
  }, [isAuthenticated, startExchangeRatesTimer, t])

  const refreshExchangeRates = useCallback(async () => {
    await fetchExchangeRates()
  }, [fetchExchangeRates])

  const fetchEntities = useCallback(async () => {
    if (!isAuthenticated) return

    try {
      setIsLoadingEntities(true)
      const data = await getEntities()
      setEntities(data.entities)
      setEntitiesLoaded(true)

      await fetchExchangeRates()
    } catch (error) {
      console.error("Error fetching entities:", error)
      showToast(t.common.fetchError, "error")
    } finally {
      setIsLoadingEntities(false)
    }
  }, [fetchExchangeRates, isAuthenticated, showToast, t])

  const fetchSettings = useCallback(async () => {
    try {
      setIsLoadingSettings(true)
      const data = await getSettings()
      setSettings(mergeSettingsWithDefaults(data))
    } catch (error) {
      console.error("Error fetching settings:", error)
      showToast(t.settings.fetchError, "error")
    } finally {
      setIsLoadingSettings(false)
    }
  }, [showToast, t])

  const saveSettingsData = useCallback(
    async (settingsData: AppSettings) => {
      try {
        await saveSettings(settingsData)
        setSettings(mergeSettingsWithDefaults(settingsData))
        showToast(t.settings.saveSuccess, "success")
        return true
      } catch (error) {
        console.error("Error saving settings:", error)
        showToast(t.settings.saveError, "error")
        return false
      }
    },
    [showToast, t],
  )

  const updateEntityStatus = useCallback(
    (entityId: string, status: EntityStatus) => {
      setEntities(prevEntities =>
        prevEntities.map(entity =>
          entity.id === entityId
            ? {
                ...entity,
                status,
              }
            : entity,
        ),
      )
    },
    [],
  )

  const updateEntityLastFetch = useCallback(
    (entityId: string, features: string[]) => {
      const now = new Date().toISOString()
      setEntities(prevEntities =>
        prevEntities.map(entity =>
          entity.id === entityId
            ? {
                ...entity,
                last_fetch: {
                  ...entity.last_fetch,
                  ...Object.fromEntries(features.map(f => [f, now])),
                },
              }
            : entity,
        ),
      )
    },
    [],
  )

  const fetchExternalIntegrations = useCallback(async () => {
    try {
      setExternalIntegrationsLoading(true)
      const data = await getExternalIntegrations()
      setExternalIntegrations(data.integrations)
    } catch (error) {
      console.error("Error fetching external integrations:", error)
    } finally {
      setExternalIntegrationsLoading(false)
    }
  }, [])

  const updateQuotesIfNeeded = useCallback(async () => {
    const now = Date.now()

    const lastCallTimeStr = localStorage.getItem(LAST_UPDATE_QUOTES_KEY)
    const lastCallTime = lastCallTimeStr ? parseInt(lastCallTimeStr, 10) : null

    if (
      lastCallTime === null ||
      now - lastCallTime >= QUOTES_UPDATE_INTERVAL_MS
    ) {
      try {
        await updateQuotesManualPositions()
        localStorage.setItem(LAST_UPDATE_QUOTES_KEY, now.toString())
      } catch (error) {
        console.error("Error updating manual positions quotes:", error)
      }
    }
  }, [LAST_UPDATE_QUOTES_KEY, QUOTES_UPDATE_INTERVAL_MS])

  useEffect(() => {
    if (isAuthenticated && !initialFetchDone.current) {
      fetchEntities()
      fetchSettings()
      fetchExternalIntegrations()
      updateQuotesIfNeeded()
      initialFetchDone.current = true
    } else if (!isAuthenticated) {
      stopExchangeRatesTimer()
      setEntitiesLoaded(false)
      initialFetchDone.current = false
    }
  }, [
    fetchEntities,
    fetchExternalIntegrations,
    fetchSettings,
    isAuthenticated,
    stopExchangeRatesTimer,
    updateQuotesIfNeeded,
  ])

  useEffect(() => {
    return () => {
      stopExchangeRatesTimer()
    }
  }, [stopExchangeRatesTimer])

  return (
    <AppContext.Provider
      value={{
        entities,
        entitiesLoaded,
        isLoadingEntities,
        featureFlags,
        toast,
        settings,
        isLoadingSettings,
        exchangeRates,
        exchangeRatesLoading,
        exchangeRatesError,
        externalIntegrations,
        externalIntegrationsLoading,
        exportState,
        setExportState,
        fetchEntities,
        updateEntityStatus,
        updateEntityLastFetch,
        showToast,
        hideToast,
        fetchSettings,
        saveSettings: saveSettingsData,
        refreshExchangeRates,
        fetchExternalIntegrations,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export const useAppContext = () => {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider")
  }
  return context
}
