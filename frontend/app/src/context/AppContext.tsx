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
  CredentialType,
  type Entity,
  type Feature,
  FetchResultCode,
  LoginResultCode,
  EntityStatus,
  EntityType,
  PlatformType,
  type PlatformInfo,
  type ExchangeRates,
  type VirtualFetchError,
  type ExternalIntegration,
  EntityOrigin,
} from "@/types"
import {
  getEntities,
  loginEntity,
  fetchFinancialEntity,
  fetchCryptoEntity,
  virtualFetch,
  getSettings,
  saveSettings,
  disconnectEntity,
  getExchangeRates,
  getExternalIntegrations,
  fetchExternalEntity,
} from "@/services/api"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"
import { WeightUnit } from "@/types/position"
import { useNavigate } from "react-router-dom"

const DEFAULT_OPTIONS: FetchOptions = {
  deep: false,
}

export interface VirtualFetchResult {
  gotData: boolean
  errors?: VirtualFetchError[]
}

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

export interface FetchingEntityState {
  fetchingEntityIds: string[]
}

export interface FetchOptions {
  deep?: boolean
  avoidNewLogin?: boolean
  code?: string
}

interface ResetStateOptions {
  preserveSelectedFeatures?: boolean
}

interface AppContextType {
  entities: Entity[]
  entitiesLoaded: boolean
  inactiveEntities: Entity[]
  isLoading: boolean
  selectedEntity: Entity | null
  processId: string | null
  pinRequired: boolean
  pinLength: number
  selectedFeatures: Feature[]
  setSelectedFeatures: (features: Feature[]) => void
  fetchOptions: FetchOptions
  setFetchOptions: (options: FetchOptions) => void
  currentAction: "login" | "scrape" | null
  storedCredentials: Record<string, string> | null
  toast: {
    message: string
    type: "success" | "error" | "warning" | null
  } | null
  view: "entities" | "login" | "features" | "external-login"
  settings: AppSettings
  pinError: boolean
  externalLoginInProgress: boolean
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
  fetchingEntityState: FetchingEntityState
  setFetchingEntityState: (
    state:
      | FetchingEntityState
      | ((prev: FetchingEntityState) => FetchingEntityState),
  ) => void
  setView: (view: "entities" | "login" | "features" | "external-login") => void

  fetchEntities: () => Promise<void>
  selectEntity: (entity: Entity) => void
  login: (credentials: Record<string, string>, pin?: string) => Promise<void>
  scrape: (
    entity: Entity | null,
    features: Feature[],
    options?: FetchOptions,
  ) => Promise<void>
  runVirtualScrape: () => Promise<VirtualFetchResult | null>
  resetState: (options?: ResetStateOptions) => void
  updateEntityStatus: (entityId: string, status: EntityStatus) => void
  showToast: (message: string, type: "success" | "error" | "warning") => void
  hideToast: () => void
  fetchSettings: () => Promise<void>
  saveSettings: (settings: AppSettings) => Promise<void>
  clearPinError: () => void
  startExternalLogin: (
    entity?: Entity,
    credentials?: Record<string, string>,
  ) => Promise<void>
  disconnectEntity: (entityId: string) => Promise<void>
  setOnScrapeCompleted: (
    callback: ((entityId: string) => Promise<void>) | null,
  ) => void
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
  const [isLoading, setIsLoading] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [processId, setProcessId] = useState<string | null>(null)
  const [pinRequired, setPinRequired] = useState(false)
  const [pinLength, setPinLength] = useState(4)
  const [selectedFeatures, setSelectedFeatures] = useState<Feature[]>([])
  const [fetchOptions, setFetchOptions] =
    useState<FetchOptions>(DEFAULT_OPTIONS)
  const [currentAction, setCurrentAction] = useState<"login" | "scrape" | null>(
    null,
  )
  const [storedCredentials, setStoredCredentials] = useState<Record<
    string,
    string
  > | null>(null)
  const [toast, setToast] = useState<{
    message: string
    type: "success" | "error" | "warning" | null
  } | null>(null)
  const [view, setView] = useState<
    "entities" | "login" | "features" | "external-login"
  >("entities")
  const [settings, setSettings] = useState<AppSettings>({ ...defaultSettings })
  const [pinError, setPinError] = useState(false)
  const [externalLoginInProgress, setExternalLoginInProgress] = useState(false)
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
  const [fetchingEntityState, setFetchingEntityState] =
    useState<FetchingEntityState>({
      fetchingEntityIds: [],
    })
  const { t } = useI18n()
  const { isAuthenticated } = useAuth()

  const initialFetchDone = useRef(false)
  const exchangeRatesTimerRef = useRef<NodeJS.Timeout | null>(null)

  const navigate = useNavigate()

  const scrapeManualLogin = useRef<{
    active: boolean
    features: Feature[]
    options: FetchOptions
  }>({
    active: false,
    features: [],
    options: DEFAULT_OPTIONS,
  })

  const onScrapeCompletedRef = useRef<
    ((entityId: string) => Promise<void>) | null
  >(null)
  useEffect(() => {
    const getPlatform = async () => {
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
    getPlatform()
  }, [])

  const showToast = (
    message: string,
    type: "success" | "error" | "warning",
  ) => {
    setToast({ message, type })
    setTimeout(
      () => {
        setToast(null)
      },
      type === "success" ? 3000 : 5000,
    )
  }

  const hideToast = () => {
    setToast(null)
  }

  const clearPinError = () => {
    setPinError(false)
  }

  const setOnScrapeCompleted = (
    callback: ((entityId: string) => Promise<void>) | null,
  ) => {
    onScrapeCompletedRef.current = callback
  }

  const fetchEntities = async () => {
    if (!isAuthenticated) return

    try {
      setIsLoading(true)
      const data = await getEntities()
      setEntities(data.entities)
      setEntitiesLoaded(true)

      await fetchExchangeRates()
    } catch {
      showToast(t.common.fetchError, "error")
    } finally {
      setIsLoading(false)
    }
  }

  const fetchSettings = async () => {
    try {
      setIsLoading(true)
      const data = await getSettings()
      setSettings(data)
    } catch (error) {
      console.error("Error fetching settings:", error)
      showToast(t.settings.fetchError, "error")
    } finally {
      setIsLoading(false)
    }
  }

  const saveSettingsData = async (settingsData: AppSettings) => {
    try {
      await saveSettings(settingsData)
      setSettings(settingsData)
      showToast(t.settings.saveSuccess, "success")
    } catch (error) {
      console.error("Error saving settings:", error)
      showToast(t.settings.saveError, "error")
    }
  }

  const startExchangeRatesTimer = () => {
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
  }

  const stopExchangeRatesTimer = () => {
    if (exchangeRatesTimerRef.current) {
      clearInterval(exchangeRatesTimerRef.current)
      exchangeRatesTimerRef.current = null
    }
  }

  const fetchExchangeRates = async () => {
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
  }

  const fetchExchangeRatesSilently = async () => {
    if (!isAuthenticated) return

    try {
      setExchangeRatesError(null)
      const rates = await getExchangeRates()
      setExchangeRates(rates)
    } catch (error) {
      console.error("Error fetching exchange rates silently:", error)
    }
  }

  const refreshExchangeRates = async () => {
    await fetchExchangeRates()
  }

  const selectEntity = (entity: Entity) => {
    setSelectedEntity(entity)
    resetState()
  }

  const handleLoginError = (code: string) => {
    const errorMessage =
      t.errors[code as keyof typeof t.errors] || t.common.loginError
    showToast(errorMessage, "error")
  }

  const handleScrapeError = (code: string) => {
    const errorMessage =
      t.errors[code as keyof typeof t.errors] || t.common.fetchError
    showToast(errorMessage, "error")
  }

  useEffect(() => {
    if (typeof window !== "undefined" && window.ipcAPI) {
      const cleanupListener = window.ipcAPI.onCompletedExternalLogin(
        (id, result) => {
          console.debug("External login completed:", id)
          setExternalLoginInProgress(false)

          if (!selectedEntity) {
            console.error("No selected entity when external login completed")
            showToast(t.common.loginError, "error")
            resetState()
            setView("entities")
            return
          }

          if (result.success) {
            if (scrapeManualLogin.current.active) {
              handleScrapeManualLoginCompletion(result.credentials)
            } else {
              const visibleCredentials = Object.fromEntries(
                Object.entries(selectedEntity.credentials_template!).filter(
                  ([, type]) =>
                    type !== CredentialType.INTERNAL &&
                    type !== CredentialType.INTERNAL_TEMP,
                ),
              )

              const allCredentialsProvided = Object.keys(
                visibleCredentials,
              ).every(key => result.credentials[key])

              if (allCredentialsProvided) {
                login(result.credentials)
              } else {
                setStoredCredentials(result.credentials)
                setView("login")
              }
            }
          } else {
            showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
            resetState()
            setView("entities")
          }
        },
      )

      return cleanupListener
    }
  }, [selectedEntity])

  const handleScrapeManualLoginCompletion = async (
    credentials: Record<string, string>,
  ) => {
    if (!selectedEntity) return

    try {
      setIsLoading(true)

      const loginResponse = await loginEntity({
        entity: selectedEntity.id,
        credentials,
      })

      if (
        loginResponse.code === LoginResultCode.CREATED ||
        loginResponse.code === LoginResultCode.RESUMED
      ) {
        const features = scrapeManualLogin.current.features
        const options = scrapeManualLogin.current.options

        scrapeManualLogin.current = {
          active: false,
          features: [],
          options: DEFAULT_OPTIONS,
        }

        await scrape(selectedEntity, features, options)
      } else {
        handleLoginError(loginResponse.code)
        resetState()
        setView("entities")
      }
    } catch (error) {
      console.error("Error handling manual login completion:", error)
      showToast(t.common.loginError, "error")
      resetState()
      setView("entities")
    } finally {
      setIsLoading(false)
    }
  }

  const startExternalLogin = async (
    entityOverride?: Entity,
    credentials?: Record<string, string>,
  ) => {
    const entityToUse = entityOverride || selectedEntity

    if (!entityToUse) {
      console.error("No entity provided for external login")
      showToast(t.common.loginError, "error")
      return
    }

    if (!window.ipcAPI) {
      console.error("IPC API not available")
      showToast(t.common.incompatibleLoginPlatform, "error")
      return
    }

    try {
      setExternalLoginInProgress(true)
      setView("external-login")

      const result = await window.ipcAPI.requestExternalLogin(entityToUse.id, {
        credentials,
      })

      if (!result.success) {
        setExternalLoginInProgress(false)
        showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
        resetState()
        setView("entities")
      }
    } catch (error) {
      console.error("External login error:", error)
      setExternalLoginInProgress(false)
      showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
      resetState()
      setView("entities")
    }
  }

  const login = async (credentials: Record<string, string>, pin?: string) => {
    if (!selectedEntity) return

    try {
      setIsLoading(true)
      setPinError(false)

      if (!storedCredentials) {
        setStoredCredentials(credentials)
      }

      const response = await loginEntity({
        entity: selectedEntity.id,
        credentials: storedCredentials || credentials,
        code: pin,
        processId: processId || undefined,
      })

      if (response.code === "CODE_REQUESTED") {
        setPinRequired(true)
        setProcessId(response.processId || null)
        setPinLength(selectedEntity.pin?.positions || 4)
        setCurrentAction("login")
      } else if (response.code === "CREATED" || response.code === "RESUMED") {
        updateEntityStatus(selectedEntity.id, EntityStatus.CONNECTED)
        showToast(`${t.common.loginSuccess}: ${selectedEntity.name}`, "success")
        resetState()
        setView("entities")
      } else if (response.code === "INVALID_CODE") {
        setPinError(true)
        handleLoginError(response.code)
      } else {
        handleLoginError(response.code || "UNEXPECTED_ERROR")
        resetState()
      }
    } catch {
      showToast(t.common.loginError, "error")
      resetState()
    } finally {
      setIsLoading(false)
    }
  }

  const formatCooldownTime = (seconds: number): string => {
    if (!Number.isFinite(seconds) || seconds <= 0) {
      return "0s"
    }

    const units = [
      { label: "d", value: 86400 },
      { label: "h", value: 3600 },
      { label: "m", value: 60 },
      { label: "s", value: 1 },
    ]

    let remaining = Math.floor(seconds)
    const parts: string[] = []

    for (const unit of units) {
      if (remaining >= unit.value) {
        const amount = Math.floor(remaining / unit.value)
        parts.push(`${amount}${unit.label}`)
        remaining -= amount * unit.value
      }

      if (parts.length === 2) {
        break
      }
    }

    if (parts.length === 0) {
      return `${Math.max(Math.floor(seconds), 0)}s`
    }

    return parts.join(" ")
  }

  const scrape = async (
    entity: Entity | null,
    features: Feature[],
    options: FetchOptions = DEFAULT_OPTIONS,
  ) => {
    try {
      setPinError(false)

      if (entity) {
        setFetchingEntityState(prev => ({
          ...prev,
          fetchingEntityIds: [...prev.fetchingEntityIds, entity.id],
        }))
      }

      let response
      if (entity) {
        if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
          // For externally provided entities use external fetch endpoint
          try {
            response = await fetchExternalEntity(
              entity.external_entity_id || "",
            )
          } catch (e: any) {
            if (e?.status === 429) {
              showToast(t.errors.COOLDOWN, "warning")
              throw e
            }
            throw e
          }
        } else if (entity.type === EntityType.FINANCIAL_INSTITUTION) {
          response = await fetchFinancialEntity({
            entity: entity.id,
            features: features,
            processId: processId || undefined,
            ...options,
          })
        } else {
          response = await fetchCryptoEntity({
            entity: entity.id,
            features: features,
            ...options,
          })
        }
      } else {
        // Fallback (should not happen without entity)
        response = await fetchCryptoEntity({
          entity: undefined,
          features: features,
          ...options,
        })
      }

      if (response.code === FetchResultCode.CODE_REQUESTED) {
        setPinRequired(true)
        setProcessId(response.details?.processId || null)
        setPinLength(entity?.pin?.positions || 4)
        setCurrentAction("scrape")
      } else if (response.code === FetchResultCode.MANUAL_LOGIN) {
        if (entity) {
          scrapeManualLogin.current = {
            active: true,
            features: features,
            options: options,
          }

          await startExternalLogin(entity, response.details?.credentials)
        } else {
          console.debug("MANUAL_LOGIN response without credentials or entity")
          showToast(t.common.fetchError, "error")
          resetState({ preserveSelectedFeatures: true })
        }
      } else if (response.code === FetchResultCode.COOLDOWN) {
        const waitSeconds = response.details?.wait ?? null
        const cooldownMessage = waitSeconds
          ? t.errors.COOLDOWN_WITH_WAIT.replace(
              "{time}",
              formatCooldownTime(waitSeconds),
            )
          : t.errors.COOLDOWN
        showToast(cooldownMessage, "warning")
        resetState({ preserveSelectedFeatures: true })
      } else if (response.code === FetchResultCode.LOGIN_REQUIRED) {
        showToast(t.errors.LOGIN_REQUIRED_SCRAPE, "warning")
        if (entity) {
          updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
        }
        resetState({ preserveSelectedFeatures: true })
        setView("entities")
      } else if (response.code === FetchResultCode.PARTIALLY_COMPLETED) {
        const entityName = entity?.name || t.common.crypto
        const warningMessage = t.errors.PARTIALLY_COMPLETED.replace(
          "{entity}",
          entityName,
        )
        showToast(warningMessage, "warning")

        if (onScrapeCompletedRef.current) {
          try {
            await onScrapeCompletedRef.current(entity?.id || "crypto")
          } catch (error) {
            console.error(
              "Error refreshing financial data after partial scrape:",
              error,
            )
          }
        }

        resetState()
        setView("entities")
      } else if (response.code === FetchResultCode.COMPLETED) {
        const successMessage = entity
          ? `${t.common.fetchSuccess}: ${entity.name}`
          : `${t.common.fetchSuccess}: ${t.common.crypto}`
        showToast(successMessage, "success")

        if (onScrapeCompletedRef.current) {
          try {
            await onScrapeCompletedRef.current(entity?.id || "crypto")
          } catch (error) {
            console.error(
              "Error refreshing financial data after scrape:",
              error,
            )
          }
        }

        resetState()
        setView("entities")
      } else if (response.code === FetchResultCode.INVALID_CODE) {
        setPinError(true)
        handleScrapeError(response.code)
      } else if (response.code === FetchResultCode.NOT_LOGGED) {
        navigate("/entities")
        handleScrapeError(response.code)
      } else if (response.code === FetchResultCode.LINK_EXPIRED) {
        // Externally provided session expired
        showToast(t.errors.LINK_EXPIRED || t.errors.LOGIN_REQUIRED, "warning")
        if (entity) {
          updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
        }
        resetState({ preserveSelectedFeatures: true })
      } else if (response.code === FetchResultCode.REMOTE_FAILED) {
        showToast(t.errors.REMOTE_FAILED, "error")
        resetState({ preserveSelectedFeatures: true })
      } else {
        handleScrapeError(response.code || "UNEXPECTED_ERROR")
        resetState({ preserveSelectedFeatures: true })
      }
    } catch {
      showToast(t.common.fetchError, "error")
      resetState({ preserveSelectedFeatures: true })
    } finally {
      if (entity) {
        setFetchingEntityState(prev => ({
          ...prev,
          fetchingEntityIds: prev.fetchingEntityIds.filter(
            id => id !== entity.id,
          ),
        }))
      }
    }
  }

  const runVirtualScrape = async (): Promise<VirtualFetchResult | null> => {
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

        return { gotData: gotData, errors: response.errors }
      } else {
        handleScrapeError(response.code)
        return null
      }
    } catch {
      showToast(t.common.virtualScrapeError, "error")
      return null
    }
  }

  const resetState = (options: ResetStateOptions = {}) => {
    const { preserveSelectedFeatures = false } = options
    setPinRequired(false)
    setProcessId(null)
    if (!preserveSelectedFeatures) {
      setSelectedFeatures([])
    }
    setFetchOptions(DEFAULT_OPTIONS)
    setCurrentAction(null)
    setStoredCredentials(null)
    setPinError(false)
    setExternalLoginInProgress(false)
    scrapeManualLogin.current = {
      active: false,
      features: [],
      options: DEFAULT_OPTIONS,
    }
  }

  const updateEntityStatus = (entityId: string, status: EntityStatus) => {
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
  }

  const disconnectEntityHandler = async (entityId: string) => {
    if (!isAuthenticated) return

    try {
      setIsLoading(true)
      await disconnectEntity(entityId)

      updateEntityStatus(entityId, EntityStatus.DISCONNECTED)
      showToast(t.common.disconnectSuccess, "success")

      if (selectedEntity && selectedEntity.id === entityId) {
        setSelectedEntity(null)
        resetState()
      }
    } catch (error) {
      console.error("Error disconnecting entity:", error)
      showToast(t.common.disconnectError, "error")
    } finally {
      setIsLoading(false)
    }
  }

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

  useEffect(() => {
    if (isAuthenticated && !initialFetchDone.current) {
      fetchEntities()
      fetchSettings()
      fetchExternalIntegrations()
      initialFetchDone.current = true
    } else if (!isAuthenticated) {
      stopExchangeRatesTimer()
      setEntitiesLoaded(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    return () => {
      stopExchangeRatesTimer()
    }
  }, [])

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
        isLoading,
        selectedEntity,
        processId,
        pinRequired,
        pinLength,
        selectedFeatures,
        setSelectedFeatures,
        fetchOptions,
        setFetchOptions,
        currentAction,
        storedCredentials,
        toast,
        view,
        settings,
        pinError,
        externalLoginInProgress,
        platform,
        exchangeRates,
        exchangeRatesLoading,
        exchangeRatesError,
        externalIntegrations,
        externalIntegrationsLoading,
        exportState,
        setExportState,
        fetchingEntityState,
        setFetchingEntityState,
        setView,
        fetchEntities,
        selectEntity,
        login,
        scrape,
        runVirtualScrape,
        resetState,
        updateEntityStatus,
        showToast,
        hideToast,
        fetchSettings,
        saveSettings: saveSettingsData,
        clearPinError,
        startExternalLogin,
        disconnectEntity: disconnectEntityHandler,
        setOnScrapeCompleted,
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
