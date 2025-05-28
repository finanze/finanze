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
  ExportTarget,
  type Entity,
  type Feature,
  ScrapeResultCode,
  LoginResultCode,
  EntityStatus,
} from "@/types"
import {
  getEntities,
  loginEntity,
  scrapeEntity,
  virtualScrape,
  updateSheets,
  getSettings,
  saveSettings,
  disconnectEntity,
} from "@/services/api"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"

// Types for settings
export interface AppSettings {
  export?: {
    sheets?: {
      enabled: boolean
      [key: string]: any
    }
  }
  scrape: {
    updateCooldown: number
    virtual: {
      enabled: boolean
      [key: string]: any
    }
  }
  mainCurrency: string
}

interface AppContextType {
  entities: Entity[]
  activeEntities: Entity[]
  isLoading: boolean
  virtualEnabled: boolean
  selectedEntity: Entity | null
  processId: string | null
  pinRequired: boolean
  pinLength: number
  selectedFeatures: Feature[]
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
  setView: (view: "entities" | "login" | "features" | "external-login") => void

  fetchEntities: () => Promise<void>
  selectEntity: (entity: Entity) => void
  login: (credentials: Record<string, string>, pin?: string) => Promise<void>
  scrape: (
    entity: Entity,
    features: Feature[],
    options?: object,
  ) => Promise<void>
  runVirtualScrape: () => Promise<void>
  exportToSheets: () => Promise<void>
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
}

const AppContext = createContext<AppContextType | undefined>(undefined)

const defaultSettings: AppSettings = {
  export: {
    sheets: {
      enabled: false,
    },
  },
  scrape: {
    updateCooldown: 60,
    virtual: {
      enabled: false,
    },
  },
  mainCurrency: "EUR",
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Entity[]>([])
  const [activeEntities, setActiveEntities] = useState<Entity[]>([])
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
  const { t } = useI18n()
  const { isAuthenticated } = useAuth()

  // Use a ref to track if initial fetch has been done
  const initialFetchDone = useRef(false)

  // Use a ref to track if we're in the middle of a scrape-triggered manual login
  const scrapeManualLogin = useRef<{
    active: boolean
    features: Feature[]
  }>({
    active: false,
    features: [],
  })

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
    ) // 3s for success, 5s for warnings and errors
  }

  const hideToast = () => {
    setToast(null)
  }

  const clearPinError = () => {
    setPinError(false)
  }

  const fetchEntities = async () => {
    // Don't fetch entities if not authenticated
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
    // Don't fetch settings if not authenticated
    if (!isAuthenticated) return

    try {
      setIsLoading(true)
      const data = await getSettings()
      data.mainCurrency = "EUR"
      setSettings(data)
    } catch (error) {
      console.error("Error fetching settings:", error)
      setSettings(defaultSettings)
    } finally {
      setIsLoading(false)
    }
  }

  const saveSettingsData = async (settingsData: AppSettings) => {
    // Don't save settings if not authenticated
    if (!isAuthenticated) return

    try {
      setIsLoading(true)
      await saveSettings(settingsData)
      setSettings(settingsData)
      showToast("Settings saved successfully", "success")
    } catch (error) {
      console.error("Error saving settings:", error)
      showToast("Failed to save settings", "error")
    } finally {
      setIsLoading(false)
    }
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

  // Setup external login completion handler
  useEffect(() => {
    if (typeof window !== "undefined" && window.ipcAPI) {
      // Set up the event listener and get the cleanup function
      const cleanupListener = window.ipcAPI.onCompletedExternalLogin(
        (id, result) => {
          console.debug("External login completed:", id)
          setExternalLoginInProgress(false)

          // Make sure we have a selected entity
          if (!selectedEntity) {
            console.error("No selected entity when external login completed")
            showToast(t.common.loginError, "error")
            resetState()
            setView("entities")
            return
          }

          if (result.success) {
            // Check if this was triggered during scraping
            if (scrapeManualLogin.current.active) {
              // Handle completion of manual login during scraping
              handleScrapeManualLoginCompletion(result.credentials)
            } else {
              // Regular login flow
              // Filter out INTERNAL and INTERNAL_TEMP credentials
              const visibleCredentials = Object.fromEntries(
                Object.entries(selectedEntity.credentials_template).filter(
                  ([, type]) =>
                    type !== CredentialType.INTERNAL &&
                    type !== CredentialType.INTERNAL_TEMP,
                ),
              )

              // Check if all required credentials are provided
              const allCredentialsProvided = Object.keys(
                visibleCredentials,
              ).every(key => result.credentials[key])

              if (allCredentialsProvided) {
                // If all credentials are provided, proceed with login
                login(result.credentials)
              } else {
                // If some credentials are missing, show the login form with pre-filled values
                setStoredCredentials(result.credentials)
                setView("login")
              }
            }
          } else {
            // If login failed, show error and reset
            showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
            resetState()
            setView("entities")
          }
        },
      )

      // Return the cleanup function
      return cleanupListener
    }
  }, [selectedEntity]) // Add selectedEntity as a dependency to re-establish the listener when it changes

  // Handle completion of manual login during scraping
  const handleScrapeManualLoginCompletion = async (
    credentials: Record<string, string>,
  ) => {
    if (!selectedEntity) return

    try {
      setIsLoading(true)

      // First, call login endpoint to set up the backend
      const loginResponse = await loginEntity({
        entity: selectedEntity.id,
        credentials,
      })

      if (
        loginResponse.code === LoginResultCode.CREATED ||
        loginResponse.code === LoginResultCode.RESUMED
      ) {
        // Login successful, now continue with scraping
        const features = scrapeManualLogin.current.features

        // Reset the scrapeManualLogin ref
        scrapeManualLogin.current = { active: false, features: [] }

        // Continue with scraping
        await scrape(selectedEntity, features)
      } else {
        // Handle login error
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
    // Use the provided entity or fall back to the selected entity
    const entityToUse = entityOverride || selectedEntity

    if (!entityToUse) {
      console.error("No entity provided for external login")
      showToast(t.common.loginError, "error")
      return
    }

    if (!window.ipcAPI) {
      console.error("IPC API not available")
      showToast(t.common.loginError, "error")
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
      // If successful, we wait for the onCompletedExternalLogin callback
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

      // If this is the first login attempt, store credentials
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
        // Login successful
        updateEntityStatus(selectedEntity.id, EntityStatus.CONNECTED)
        showToast(`${t.common.loginSuccess}: ${selectedEntity.name}`, "success")
        resetState()
        // Return to entities view after successful login
        setView("entities")
      } else if (response.code === "INVALID_CODE") {
        // Handle invalid PIN but stay in the PIN view
        setPinError(true)
        handleLoginError(response.code)
      } else {
        // Handle other response codes
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
    entity: Entity,
    features: Feature[],
    options: object = {},
  ) => {
    if (!entity) return

    try {
      setIsLoading(true)
      setPinError(false)

      const response = await scrapeEntity({
        entity: entity.id,
        features: features,
        processId: processId || undefined,
        ...options,
      })

      if (response.code === ScrapeResultCode.CODE_REQUESTED) {
        setPinRequired(true)
        setProcessId(response.details?.processId || null)
        setPinLength(entity.pin?.positions || 4)
        setCurrentAction("scrape")
      } else if (response.code === ScrapeResultCode.MANUAL_LOGIN) {
        if (response.details?.credentials) {
          scrapeManualLogin.current = {
            active: true,
            features: features,
          }

          await startExternalLogin(entity, response.details.credentials)
        } else {
          console.debug("MANUAL_LOGIN response without credentials")
          showToast(t.common.fetchError, "error")
          resetState()
        }
      } else if (response.code === ScrapeResultCode.LOGIN_REQUIRED) {
        // Handle LOGIN_REQUIRED - show a warning toast
        showToast(t.errors.LOGIN_REQUIRED_SCRAPE, "warning")
        // Update entity status to REQUIRES_LOGIN
        updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
        resetState()
        setView("entities")
      } else if (response.code === ScrapeResultCode.COMPLETED) {
        showToast(`${t.common.fetchSuccess}: ${entity.name}`, "success")
        resetState()
        // Return to entities view after successful scrape
        setView("entities")
      } else if (response.code === ScrapeResultCode.INVALID_CODE) {
        // Handle invalid PIN but stay in the PIN view
        setPinError(true)
        handleScrapeError(response.code)
      } else {
        // Handle other response codes
        handleScrapeError(response.code || "UNEXPECTED_ERROR")
        resetState()
      }
    } catch {
      showToast(t.common.fetchError, "error")
      resetState()
    } finally {
      setIsLoading(false)
    }
  }

  const runVirtualScrape = async () => {
    try {
      const response = await virtualScrape()

      if (response.code === "COMPLETED") {
        showToast(t.common.virtualScrapeSuccess, "success")
      } else {
        handleScrapeError(response.code || "UNEXPECTED_ERROR")
      }
    } catch {
      showToast(t.common.virtualScrapeError, "error")
    }
  }

  const exportToSheets = async () => {
    try {
      setIsLoading(true)
      await updateSheets({ target: ExportTarget.GOOGLE_SHEETS })

      showToast(t.common.exportSuccess, "success")
    } catch {
      showToast(t.common.exportError, "error")
    } finally {
      setIsLoading(false)
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

      // Update entity status to DISCONNECTED
      updateEntityStatus(entityId, EntityStatus.DISCONNECTED)
      showToast(t.common.disconnectSuccess, "success")

      // If the currently selected entity is the one being disconnected, reset the selection
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

  // Fetch entities and settings on component mount and when authentication status changes
  useEffect(() => {
    if (isAuthenticated && !initialFetchDone.current) {
      fetchEntities()
      fetchSettings()
      initialFetchDone.current = true
    }
  }, [isAuthenticated])

  useEffect(() => {
    setActiveEntities(
      entities.filter(entity => entity.status !== EntityStatus.DISCONNECTED),
    )
  }, [entities])

  return (
    <AppContext.Provider
      value={{
        entities,
        activeEntities,
        isLoading,
        virtualEnabled,
        selectedEntity,
        processId,
        pinRequired,
        pinLength,
        selectedFeatures,
        currentAction,
        storedCredentials,
        toast,
        view,
        settings,
        pinError,
        externalLoginInProgress,
        setView,
        fetchEntities,
        selectEntity,
        login,
        scrape,
        runVirtualScrape,
        exportToSheets,
        resetState,
        updateEntityStatus,
        showToast,
        hideToast,
        fetchSettings,
        saveSettings: saveSettingsData,
        clearPinError,
        startExternalLogin,
        disconnectEntity: disconnectEntityHandler,
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
