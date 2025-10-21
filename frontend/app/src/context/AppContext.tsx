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
  PlatformType,
  type Entity,
  type PlatformInfo,
  type ExchangeRates,
  type ExternalIntegration,
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

export interface AppSettings {
  integrations?: {
    sheets?: {
      credentials?: {
        client_id?: string
        client_secret?: string
      }
    }
    etherscan?: {
      api_key?: string
    }
    gocardless?: {
      secret_id: string
      secret_key: string
    }
  }
  export?: {
    sheets?: {
      enabled?: boolean
      [key: string]: any
    }
  }
  fetch: {
    virtual: {
      enabled: boolean
      [key: string]: any
    }
  }
  general: {
    defaultCurrency: string
    defaultCommodityWeightUnit: string
  }
}

export interface ExportState {
  isExporting: boolean
  lastExportTime: number | null
}

interface AppContextType {
  entities: Entity[]
  entitiesLoaded: boolean
  inactiveEntities: Entity[]
  isLoadingEntities: boolean
  toast: {
    message: string
    type: "success" | "error" | "warning" | null
  } | null
  settings: AppSettings
  isLoadingSettings: boolean
  platform: PlatformType | null
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
  showToast: (message: string, type: "success" | "error" | "warning") => void
  hideToast: () => void
  fetchSettings: () => Promise<void>
  saveSettings: (settings: AppSettings) => Promise<void>
  refreshExchangeRates: () => Promise<void>
  fetchExternalIntegrations: () => Promise<void>
}

const AppContext = createContext<AppContextType | undefined>(undefined)

const defaultSettings: AppSettings = {
  export: {
    sheets: {
      enabled: false,
    },
  },
  fetch: {
    virtual: {
      enabled: false,
    },
  },
  general: {
    defaultCurrency: "EUR",
    defaultCommodityWeightUnit: WeightUnit.GRAM,
  },
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Entity[]>([])
  const [entitiesLoaded, setEntitiesLoaded] = useState(false)
  const [inactiveEntities, setInactiveEntities] = useState<Entity[]>([])
  const [isLoadingEntities, setIsLoadingEntities] = useState(false)
  const [toast, setToast] = useState<{
    message: string
    type: "success" | "error" | "warning" | null
  } | null>(null)
  const [settings, setSettings] = useState<AppSettings>({ ...defaultSettings })
  const [isLoadingSettings, setIsLoadingSettings] = useState(false)
  const [platform, setPlatform] = useState<PlatformType | null>(null)
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

  const initialFetchDone = useRef(false)
  const exchangeRatesTimerRef = useRef<NodeJS.Timeout | null>(null)

  const LAST_UPDATE_QUOTES_KEY = "lastUpdateQuotesTime"
  const SIX_HOURS_MS = 6 * 60 * 60 * 1000

  useEffect(() => {
    const getPlatformInfo = async () => {
      if (window.ipcAPI && window.ipcAPI.platform) {
        try {
          const platformInfo: PlatformInfo = await window.ipcAPI.platform()
          setPlatform(platformInfo.type)
        } catch (error) {
          console.error("Failed to get platform info:", error)
          setPlatform(PlatformType.WEB)
        }
      } else {
        setPlatform(PlatformType.WEB)
      }
    }

    getPlatformInfo()
  }, [])

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

    exchangeRatesTimerRef.current = setInterval(
      () => {
        if (isAuthenticated) {
          fetchExchangeRatesSilently()
        }
      },
      5 * 60 * 1000,
    )
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
      setSettings(data)
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
        setSettings(settingsData)
        showToast(t.settings.saveSuccess, "success")
      } catch (error) {
        console.error("Error saving settings:", error)
        showToast(t.settings.saveError, "error")
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

    if (lastCallTime === null || now - lastCallTime >= SIX_HOURS_MS) {
      try {
        await updateQuotesManualPositions()
        localStorage.setItem(LAST_UPDATE_QUOTES_KEY, now.toString())
      } catch (error) {
        console.error("Error updating manual positions quotes:", error)
      }
    }
  }, [LAST_UPDATE_QUOTES_KEY, SIX_HOURS_MS])

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

  useEffect(() => {
    setInactiveEntities(
      entities.filter(entity => entity.status === EntityStatus.DISCONNECTED),
    )
  }, [entities])

  return (
    <AppContext.Provider
      value={{
        entities,
        entitiesLoaded,
        inactiveEntities,
        isLoadingEntities,
        toast,
        settings,
        isLoadingSettings,
        platform,
        exchangeRates,
        exchangeRatesLoading,
        exchangeRatesError,
        externalIntegrations,
        externalIntegrationsLoading,
        exportState,
        setExportState,
        fetchEntities,
        updateEntityStatus,
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
