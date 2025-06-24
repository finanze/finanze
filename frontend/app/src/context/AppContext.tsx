import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  useEffect,
  useRef,
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
} from "@/services/api"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"
export interface AppSettings {
  integrations?: {
    sheets?: {
      credentials?: {
        client_id?: string
        client_secret?: string
      }
    }
  }
  export?: {
    sheets?: {
      enabled?: boolean
      [key: string]: any
    }
  }
  fetch: {
    updateCooldown: number
    virtual: {
      enabled: boolean
      [key: string]: any
    }
  }
  general: {
    defaultCurrency: string
  }
}

export interface ExportState {
  isExporting: boolean
  lastExportTime: number | null
}

export interface FetchingEntityState {
  fetchingEntityIds: string[]
}

interface AppContextType {
  entities: Entity[]
  inactiveEntities: Entity[]
  isLoading: boolean
  virtualEnabled: boolean
  selectedEntity: Entity | null
  processId: string | null
  pinRequired: boolean
  pinLength: number
  selectedFeatures: Feature[]
  setSelectedFeatures: (features: Feature[]) => void
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
  exchangeRates: ExchangeRates | null
  exchangeRatesLoading: boolean
  exchangeRatesError: string | null
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
    options?: object,
  ) => Promise<void>
  runVirtualScrape: () => Promise<void>
  resetState: () => void
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
}

const AppContext = createContext<AppContextType | undefined>(undefined)

const defaultSettings: AppSettings = {
  export: {
    sheets: {
      enabled: false,
    },
  },
  fetch: {
    updateCooldown: 60,
    virtual: {
      enabled: false,
    },
  },
  general: {
    defaultCurrency: "EUR",
  },
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Entity[]>([])
  const [inactiveEntities, setInactiveEntities] = useState<Entity[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [processId, setProcessId] = useState<string | null>(null)
  const [pinRequired, setPinRequired] = useState(false)
  const [pinLength, setPinLength] = useState(4)
  const [selectedFeatures, setSelectedFeatures] = useState<Feature[]>([])
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
  const [virtualEnabled, setVirtualEnabled] = useState(false)
  const [externalLoginInProgress, setExternalLoginInProgress] = useState(false)
  const [platform, setPlatform] = useState<PlatformType | null>(null)
  const [exchangeRates, setExchangeRates] = useState<ExchangeRates | null>(null)
  const [exchangeRatesLoading, setExchangeRatesLoading] = useState(false)
  const [exchangeRatesError, setExchangeRatesError] = useState<string | null>(
    null,
  )
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

  const scrapeManualLogin = useRef<{
    active: boolean
    features: Feature[]
  }>({
    active: false,
    features: [],
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
      setVirtualEnabled(data.virtual)
      setEntities(data.entities)
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

  const fetchExchangeRates = async () => {
    if (!isAuthenticated) return

    try {
      setExchangeRatesLoading(true)
      setExchangeRatesError(null)
      const rates = await getExchangeRates()
      setExchangeRates(rates)
    } catch (error) {
      console.error("Error fetching exchange rates:", error)
      setExchangeRatesError(t.common.fetchError)
    } finally {
      setExchangeRatesLoading(false)
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

        scrapeManualLogin.current = { active: false, features: [] }

        await scrape(selectedEntity, features)
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

  const scrape = async (
    entity: Entity | null,
    features: Feature[],
    options: object = {},
  ) => {
    try {
      setPinError(false)

      if (entity) {
        setFetchingEntityState(prev => ({
          ...prev,
          fetchingEntityIds: [...prev.fetchingEntityIds, entity.id],
        }))
      }

      const response =
        entity?.type === EntityType.FINANCIAL_INSTITUTION
          ? await fetchFinancialEntity({
              entity: entity?.id,
              features: features,
              processId: processId || undefined,
              ...options,
            })
          : await fetchCryptoEntity({
              entity: entity?.id,
              features: features,
              ...options,
            })

      if (response.code === FetchResultCode.CODE_REQUESTED) {
        setPinRequired(true)
        setProcessId(response.details?.processId || null)
        setPinLength(entity?.pin?.positions || 4)
        setCurrentAction("scrape")
      } else if (response.code === FetchResultCode.MANUAL_LOGIN) {
        if (response.details?.credentials && entity) {
          scrapeManualLogin.current = {
            active: true,
            features: features,
          }

          await startExternalLogin(entity, response.details.credentials)
        } else {
          console.debug("MANUAL_LOGIN response without credentials or entity")
          showToast(t.common.fetchError, "error")
          resetState()
        }
      } else if (response.code === FetchResultCode.LOGIN_REQUIRED) {
        showToast(t.errors.LOGIN_REQUIRED_SCRAPE, "warning")
        if (entity) {
          updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
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
      } else {
        handleScrapeError(response.code || "UNEXPECTED_ERROR")
        resetState()
      }
    } catch {
      showToast(t.common.fetchError, "error")
      resetState()
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

  const runVirtualScrape = async () => {
    try {
      const response = await virtualFetch()

      if (response.code === "COMPLETED") {
        showToast(t.common.virtualScrapeSuccess, "success")
      } else {
        handleScrapeError(response.code || "UNEXPECTED_ERROR")
      }
    } catch {
      showToast(t.common.virtualScrapeError, "error")
    }
  }

  const resetState = () => {
    setPinRequired(false)
    setProcessId(null)
    setSelectedFeatures([])
    setCurrentAction(null)
    setStoredCredentials(null)
    setPinError(false)
    setExternalLoginInProgress(false)
    scrapeManualLogin.current = { active: false, features: [] }
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

  useEffect(() => {
    if (isAuthenticated && !initialFetchDone.current) {
      fetchEntities()
      fetchSettings()
      fetchExchangeRates()
      initialFetchDone.current = true
    }
  }, [isAuthenticated])

  useEffect(() => {
    setInactiveEntities(
      entities.filter(entity => entity.status === EntityStatus.DISCONNECTED),
    )
  }, [entities])

  return (
    <AppContext.Provider
      value={{
        entities,
        inactiveEntities,
        isLoading,
        virtualEnabled,
        selectedEntity,
        processId,
        pinRequired,
        pinLength,
        selectedFeatures,
        setSelectedFeatures,
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
