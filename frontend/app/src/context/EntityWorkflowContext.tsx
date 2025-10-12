import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  useRef,
  useEffect,
  useCallback,
} from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  CredentialType,
  type Entity,
  type Feature,
  FetchResultCode,
  LoginResultCode,
  EntityStatus,
  EntityType,
  EntityOrigin,
} from "@/types"
import {
  loginEntity,
  fetchFinancialEntity,
  fetchCryptoEntity,
  fetchExternalEntity,
  disconnectEntity,
} from "@/services/api"

export interface FetchOptions {
  deep?: boolean
  avoidNewLogin?: boolean
  code?: string
}

interface ResetStateOptions {
  preserveSelectedFeatures?: boolean
}

export interface VirtualFetchResult {
  gotData: boolean
  errors?: import("@/types").VirtualFetchError[]
}

export interface FetchingEntityState {
  fetchingEntityIds: string[]
}

interface EntityWorkflowContextValue {
  selectedEntity: Entity | null
  selectEntity: (entity: Entity) => void
  isLoggingIn: boolean
  processId: string | null
  pinRequired: boolean
  pinLength: number
  pinError: boolean
  clearPinError: () => void
  selectedFeatures: Feature[]
  setSelectedFeatures: (features: Feature[]) => void
  fetchOptions: FetchOptions
  setFetchOptions: (options: FetchOptions) => void
  currentAction: "login" | "scrape" | null
  storedCredentials: Record<string, string> | null
  view: "entities" | "login" | "features" | "external-login"
  setView: (view: "entities" | "login" | "features" | "external-login") => void
  login: (credentials: Record<string, string>, pin?: string) => Promise<void>
  scrape: (
    entity: Entity | null,
    features: Feature[],
    options?: FetchOptions,
  ) => Promise<void>
  resetState: (options?: ResetStateOptions) => void
  startExternalLogin: (
    entity?: Entity,
    credentials?: Record<string, string>,
  ) => Promise<void>
  disconnectEntity: (entityId: string) => Promise<void>
  fetchingEntityState: FetchingEntityState
  setFetchingEntityState: (
    state:
      | FetchingEntityState
      | ((prev: FetchingEntityState) => FetchingEntityState),
  ) => void
  setOnScrapeCompleted: (
    callback: ((entityId: string) => Promise<void>) | null,
  ) => void
}

const EntityWorkflowContext = createContext<
  EntityWorkflowContextValue | undefined
>(undefined)

const DEFAULT_FETCH_OPTIONS: FetchOptions = {
  deep: false,
}

export function EntityWorkflowProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const { showToast, updateEntityStatus, fetchEntities } = useAppContext()

  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [processId, setProcessId] = useState<string | null>(null)
  const [pinRequired, setPinRequired] = useState(false)
  const [pinLength, setPinLength] = useState(4)
  const [selectedFeatures, setSelectedFeatures] = useState<Feature[]>([])
  const [fetchOptions, setFetchOptions] = useState<FetchOptions>(
    DEFAULT_FETCH_OPTIONS,
  )
  const [currentAction, setCurrentAction] = useState<"login" | "scrape" | null>(
    null,
  )
  const [storedCredentials, setStoredCredentials] = useState<Record<
    string,
    string
  > | null>(null)
  const [view, setView] = useState<
    "entities" | "login" | "features" | "external-login"
  >("entities")
  const [pinError, setPinError] = useState(false)
  const [fetchingEntityState, setFetchingEntityState] =
    useState<FetchingEntityState>({
      fetchingEntityIds: [],
    })

  const scrapeManualLogin = useRef<{
    active: boolean
    features: Feature[]
    options: FetchOptions
  }>({
    active: false,
    features: [],
    options: DEFAULT_FETCH_OPTIONS,
  })

  const onScrapeCompletedRef = useRef<
    ((entityId: string) => Promise<void>) | null
  >(null)

  const resetState = useCallback((options: ResetStateOptions = {}) => {
    const { preserveSelectedFeatures = false } = options
    setPinRequired(false)

    if (!preserveSelectedFeatures) {
      setSelectedFeatures([])
      setFetchOptions({ ...DEFAULT_FETCH_OPTIONS })
      setProcessId(null)
    }

    setCurrentAction(null)
    setStoredCredentials(null)
    setPinError(false)
    scrapeManualLogin.current = {
      active: false,
      features: [],
      options: DEFAULT_FETCH_OPTIONS,
    }
  }, [])

  const selectEntity = useCallback(
    (entity: Entity) => {
      setSelectedEntity(entity)
      resetState()
    },
    [resetState],
  )

  const clearPinError = useCallback(() => {
    setPinError(false)
  }, [])

  const setOnScrapeCompleted = useCallback(
    (callback: ((entityId: string) => Promise<void>) | null) => {
      onScrapeCompletedRef.current = callback
    },
    [],
  )

  const startExternalLogin = useCallback(
    async (entityOverride?: Entity, credentials?: Record<string, string>) => {
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
        setView("external-login")

        const result = await window.ipcAPI.requestExternalLogin(
          entityToUse.id,
          {
            credentials,
          },
        )

        if (!result.success) {
          showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
          resetState()
          setView("entities")
        }
      } catch (error) {
        console.error("External login error:", error)
        showToast(t.errors.EXTERNAL_LOGIN_FAILED, "error")
        resetState()
        setView("entities")
      }
    },
    [resetState, selectedEntity, setView, showToast, t],
  )

  const login = useCallback(
    async (credentials: Record<string, string>, pin?: string) => {
      if (!selectedEntity) return

      try {
        setIsLoggingIn(true)
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
          showToast(
            `${t.common.loginSuccess}: ${selectedEntity.name}`,
            "success",
          )
          resetState()
          setView("entities")
        } else if (response.code === "INVALID_CODE") {
          setPinError(true)
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.loginError,
            "error",
          )
        } else {
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.loginError,
            "error",
          )
          resetState()
        }
      } catch {
        showToast(t.common.loginError, "error")
      } finally {
        setIsLoggingIn(false)
      }
    },
    [
      processId,
      resetState,
      selectedEntity,
      setView,
      showToast,
      storedCredentials,
      t,
      updateEntityStatus,
    ],
  )

  const formatCooldownTime = useCallback((seconds: number): string => {
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
  }, [])

  const scrape = useCallback(
    async (
      entity: Entity | null,
      features: Feature[],
      options: FetchOptions = DEFAULT_FETCH_OPTIONS,
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
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.fetchError,
            "error",
          )
        } else if (response.code === FetchResultCode.NOT_LOGGED) {
          navigate("/entities")
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.fetchError,
            "error",
          )
        } else if (response.code === FetchResultCode.LINK_EXPIRED) {
          showToast(t.errors.LINK_EXPIRED || t.errors.LOGIN_REQUIRED, "warning")
          if (entity) {
            updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
          }
          resetState({ preserveSelectedFeatures: true })
        } else if (response.code === FetchResultCode.REMOTE_FAILED) {
          showToast(t.errors.REMOTE_FAILED, "error")
          resetState({ preserveSelectedFeatures: true })
        } else {
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.fetchError,
            "error",
          )
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
    },
    [
      formatCooldownTime,
      navigate,
      processId,
      resetState,
      setView,
      showToast,
      startExternalLogin,
      t,
      updateEntityStatus,
    ],
  )

  const handleScrapeManualLoginCompletion = useCallback(
    async (credentials: Record<string, string>) => {
      if (!selectedEntity) return

      try {
        setIsLoggingIn(true)

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
            options: DEFAULT_FETCH_OPTIONS,
          }

          await scrape(selectedEntity, features, options)
        } else {
          showToast(
            t.errors[loginResponse.code as keyof typeof t.errors] ||
              t.common.loginError,
            "error",
          )
          resetState()
          setView("entities")
        }
      } catch (error) {
        console.error("Error handling manual login completion:", error)
        showToast(t.common.loginError, "error")
        resetState()
        setView("entities")
      } finally {
        setIsLoggingIn(false)
      }
    },
    [resetState, scrape, selectedEntity, setView, showToast, t],
  )

  useEffect(() => {
    if (typeof window === "undefined" || !window.ipcAPI) {
      return
    }

    const cleanupListener = window.ipcAPI.onCompletedExternalLogin(
      (id, result) => {
        console.debug("External login completed:", id)

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
  }, [
    handleScrapeManualLoginCompletion,
    login,
    resetState,
    selectedEntity,
    setView,
    showToast,
    t,
  ])

  const disconnectEntityHandler = useCallback(
    async (entityId: string) => {
      if (!isAuthenticated) return

      try {
        setIsLoggingIn(true)
        await disconnectEntity(entityId)

        updateEntityStatus(entityId, EntityStatus.DISCONNECTED)
        showToast(t.common.disconnectSuccess, "success")

        if (selectedEntity && selectedEntity.id === entityId) {
          setSelectedEntity(null)
          resetState()
        }

        await fetchEntities()
      } catch (error) {
        console.error("Error disconnecting entity:", error)
        showToast(t.common.disconnectError, "error")
      } finally {
        setIsLoggingIn(false)
      }
    },
    [
      fetchEntities,
      isAuthenticated,
      resetState,
      selectedEntity,
      showToast,
      t,
      updateEntityStatus,
    ],
  )

  return (
    <EntityWorkflowContext.Provider
      value={{
        selectedEntity,
        selectEntity,
        isLoggingIn,
        processId,
        pinRequired,
        pinLength,
        pinError,
        clearPinError,
        selectedFeatures,
        setSelectedFeatures,
        fetchOptions,
        setFetchOptions,
        currentAction,
        storedCredentials,
        view,
        setView,
        login,
        scrape,
        resetState,
        startExternalLogin,
        disconnectEntity: disconnectEntityHandler,
        fetchingEntityState,
        setFetchingEntityState,
        setOnScrapeCompleted,
      }}
    >
      {children}
    </EntityWorkflowContext.Provider>
  )
}

export const useEntityWorkflow = () => {
  const context = useContext(EntityWorkflowContext)
  if (!context) {
    throw new Error(
      "useEntityWorkflow must be used within an EntityWorkflowProvider",
    )
  }
  return context
}
