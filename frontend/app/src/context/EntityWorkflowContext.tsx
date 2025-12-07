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
import {
  recordAutoRefreshSuccess,
  recordAutoRefreshFailure,
  getAutoRefreshCandidates,
} from "@/services/autoRefreshService"
import { AutoRefreshMode } from "@/types"

export interface FetchOptions {
  deep?: boolean
  avoidNewLogin?: boolean
  code?: string
  silent?: boolean
}

interface ResetStateOptions {
  preserveSelectedFeatures?: boolean
}

export interface ImportFetchResult {
  gotData: boolean
  errors?: import("@/types").ImportError[]
}

export interface FetchingEntityState {
  fetchingEntityIds: string[]
}

export interface PendingScrapeParams {
  entity: Entity
  features: Feature[]
  options: FetchOptions
  processId: string | null
  pinLength: number
  currentAction: "scrape" | "login"
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
  getPendingScrapeParams: (entityId: string) => PendingScrapeParams | undefined
  clearPendingScrapeParams: (entityId: string) => void
  pendingPinEntityIds: () => string[]
  switchActivePinEntity: (entityId: string) => void
  getPendingPinEntities: () => { id: string; name: string }[]
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
  const {
    showToast,
    updateEntityStatus,
    updateEntityLastFetch,
    fetchEntities,
    settings,
    entities,
    entitiesLoaded,
  } = useAppContext()

  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [processId, setProcessId] = useState<string | null>(null)
  const [pinRequired, setPinRequired] = useState(false)
  const [pinLength, setPinLength] = useState(4)
  const [activePinEntityId, setActivePinEntityId] = useState<string | null>(
    null,
  )
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

  const pendingScrapeParamsRef = useRef<Map<string, PendingScrapeParams>>(
    new Map(),
  )

  const activatePendingEntry = useCallback(
    (pending: PendingScrapeParams | undefined) => {
      if (!pending) return false
      setActivePinEntityId(pending.entity.id)
      setSelectedEntity(pending.entity)
      setSelectedFeatures(pending.features)
      setFetchOptions(current => ({
        ...current,
        deep: pending.options.deep ?? DEFAULT_FETCH_OPTIONS.deep,
        avoidNewLogin: pending.options.avoidNewLogin,
      }))
      setProcessId(pending.processId)
      setPinLength(pending.pinLength)
      setCurrentAction(pending.currentAction)
      setPinRequired(true)
      setPinError(false)
      return true
    },
    [],
  )

  const activateNextPending = useCallback(() => {
    const iterator = pendingScrapeParamsRef.current.values()
    const next = iterator.next()
    if (next.done) return false
    return activatePendingEntry(next.value)
  }, [activatePendingEntry])

  const onScrapeCompletedRef = useRef<
    ((entityId: string) => Promise<void>) | null
  >(null)

  const resetState = useCallback((options: ResetStateOptions = {}) => {
    const { preserveSelectedFeatures = false } = options
    setPinRequired(false)
    setActivePinEntityId(null)

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
    pendingScrapeParamsRef.current.clear()
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
          credentials: credentials,
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
            t.common.loginSuccessEntity.replace(
              "{entity}",
              selectedEntity.name,
            ),
            "success",
          )
          resetState()
          setView("entities")
        } else if (response.code === "INVALID_CODE") {
          setPinError(true)
          showToast(
            t.errors[response.code as keyof typeof t.errors] ||
              t.common.loginErrorEntity.replace(
                "{entity}",
                selectedEntity.name,
              ),
            "error",
          )
        } else {
          const errorMessage = t.errors[response.code as keyof typeof t.errors]
          let finalMessage: string
          if (errorMessage?.includes("{entity}")) {
            finalMessage = errorMessage.replace("{entity}", selectedEntity.name)
          } else if (errorMessage) {
            finalMessage = errorMessage
          } else {
            finalMessage = t.common.loginErrorEntity.replace(
              "{entity}",
              selectedEntity.name,
            )
          }
          showToast(finalMessage, "error")
          resetState()
        }
      } catch {
        showToast(
          t.common.loginErrorEntity.replace("{entity}", selectedEntity.name),
          "error",
        )
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
      const { silent = false } = options

      const notify = (
        message: string,
        type: "success" | "error" | "warning",
      ) => {
        if (!silent) {
          showToast(message, type)
        }
      }

      try {
        setPinError(false)

        if (entity) {
          setFetchingEntityState(prev => ({
            ...prev,
            fetchingEntityIds: [...prev.fetchingEntityIds, entity.id],
          }))
        }

        let response
        let httpError: number | undefined
        if (entity) {
          if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            try {
              response = await fetchExternalEntity(
                entity.external_entity_id || "",
              )
            } catch (e: any) {
              httpError = e?.status
              if (e?.status === 429) {
                const entityName = entity?.name || t.common.crypto
                const cooldownMsg = t.errors.COOLDOWN.replace(
                  "{entity}",
                  entityName,
                )
                notify(cooldownMsg, "warning")
                if (silent && entity) {
                  recordAutoRefreshFailure(entity.id, undefined, httpError)
                }
                throw e
              }
              throw e
            }
          } else if (entity.type === EntityType.FINANCIAL_INSTITUTION) {
            response = await fetchFinancialEntity({
              entity: entity.id,
              features: features,
              processId: processId || undefined,
              deep: options.deep,
              avoidNewLogin: options.avoidNewLogin,
              code: options.code,
            })
          } else {
            response = await fetchCryptoEntity({
              entity: entity.id,
              features: features,
              deep: options.deep,
              avoidNewLogin: options.avoidNewLogin,
              code: options.code,
            })
          }
        } else {
          response = await fetchCryptoEntity({
            entity: undefined,
            features: features,
            deep: options.deep,
            avoidNewLogin: options.avoidNewLogin,
            code: options.code,
          })
        }

        if (response.code === FetchResultCode.CODE_REQUESTED) {
          if (silent) {
            if (entity) {
              recordAutoRefreshFailure(entity.id, response)
            }
            return
          }
          if (entity) {
            const processIdValue = response.details?.processId || null
            const pinLen = entity.pin?.positions || 4
            const pendingPayload: PendingScrapeParams = {
              entity,
              features,
              options: {
                deep: options.deep,
                avoidNewLogin: options.avoidNewLogin,
              },
              processId: processIdValue,
              pinLength: pinLen,
              currentAction: "scrape",
            }

            const hadPendingBefore = pendingScrapeParamsRef.current.size > 0
            pendingScrapeParamsRef.current.set(entity.id, pendingPayload)

            if (!hadPendingBefore) {
              activatePendingEntry(pendingPayload)
            }
          }
        } else if (response.code === FetchResultCode.MANUAL_LOGIN) {
          if (silent) {
            if (entity) {
              recordAutoRefreshFailure(entity.id, response)
            }
            return
          }
          if (entity) {
            setSelectedEntity(entity)

            scrapeManualLogin.current = {
              active: true,
              features: features,
              options: options,
            }

            await startExternalLogin(entity, response.details?.credentials)
          } else {
            console.debug("MANUAL_LOGIN response without credentials or entity")
            notify(t.common.fetchError, "error")
            resetState({ preserveSelectedFeatures: true })
          }
        } else if (response.code === FetchResultCode.COOLDOWN) {
          const entityName = entity?.name || t.common.crypto
          const waitSeconds = response.details?.wait ?? null
          const cooldownMessage = waitSeconds
            ? t.errors.COOLDOWN_WITH_WAIT.replace(
                "{time}",
                formatCooldownTime(waitSeconds),
              ).replace("{entity}", entityName)
            : t.errors.COOLDOWN.replace("{entity}", entityName)
          notify(cooldownMessage, "warning")
          if (silent && entity) {
            recordAutoRefreshFailure(entity.id, response)
          }
          if (!silent) {
            resetState({ preserveSelectedFeatures: true })
          }
        } else if (response.code === FetchResultCode.LOGIN_REQUIRED) {
          notify(t.errors.LOGIN_REQUIRED_SCRAPE, "warning")
          if (entity) {
            updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
            if (silent) {
              recordAutoRefreshFailure(entity.id, response)
            }
          }
          if (!silent) {
            resetState({ preserveSelectedFeatures: true })
            setView("entities")
          }
        } else if (response.code === FetchResultCode.PARTIALLY_COMPLETED) {
          const entityName = entity?.name || t.common.crypto
          const warningMessage = t.errors.PARTIALLY_COMPLETED.replace(
            "{entity}",
            entityName,
          )
          notify(warningMessage, "warning")

          let advancedToNext = false

          if (entity) {
            updateEntityLastFetch(entity.id, features)
            pendingScrapeParamsRef.current.delete(entity.id)
            if (activePinEntityId === entity.id) {
              setActivePinEntityId(null)
            }
          }

          if (pendingScrapeParamsRef.current.size > 0) {
            advancedToNext = activateNextPending()
          }

          if (silent && entity) {
            recordAutoRefreshFailure(entity.id, response)
          }

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

          if (!silent) {
            if (!advancedToNext) {
              setSelectedEntity(currentSelected => {
                if (!currentSelected || currentSelected.id === entity?.id) {
                  resetState()
                  setView("entities")
                }
                return currentSelected
              })
            }
          }
        } else if (response.code === FetchResultCode.COMPLETED) {
          let successMessage: string
          let advancedToNext = false
          if (entity) {
            successMessage = t.common.fetchSuccessEntity.replace(
              "{entity}",
              entity.name,
            )
            recordAutoRefreshSuccess(entity.id)
            updateEntityLastFetch(entity.id, features)
            pendingScrapeParamsRef.current.delete(entity.id)
            if (activePinEntityId === entity.id) {
              setActivePinEntityId(null)
            }
            if (pendingScrapeParamsRef.current.size > 0) {
              advancedToNext = activateNextPending()
            }
          } else {
            successMessage = `${t.common.fetchSuccess}: ${t.common.crypto}`
          }
          notify(successMessage, "success")

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

          if (!silent) {
            if (!advancedToNext) {
              setSelectedEntity(currentSelected => {
                if (!currentSelected || currentSelected.id === entity?.id) {
                  resetState()
                  setView("entities")
                }
                return currentSelected
              })
            }
          }
        } else if (response.code === FetchResultCode.INVALID_CODE) {
          if (silent) {
            if (entity) {
              recordAutoRefreshFailure(entity.id, response)
            }
            return
          }
          setPinError(true)
          const entityName = entity?.name || t.common.crypto
          const errorMessage =
            t.errors[response.code as keyof typeof t.errors] ||
            t.common.fetchErrorEntity.replace("{entity}", entityName)
          notify(errorMessage, "error")
        } else if (response.code === FetchResultCode.NOT_LOGGED) {
          if (!silent) {
            navigate("/entities")
          }
          const entityName = entity?.name || t.common.crypto
          const errorMessage = (
            t.errors[response.code as keyof typeof t.errors] ||
            t.common.fetchErrorEntity
          )?.replace("{entity}", entityName)
          notify(errorMessage, "error")
          if (silent && entity) {
            recordAutoRefreshFailure(entity.id, response)
          }
        } else if (response.code === FetchResultCode.LINK_EXPIRED) {
          notify(t.errors.LINK_EXPIRED || t.errors.LOGIN_REQUIRED, "warning")
          if (entity) {
            updateEntityStatus(entity.id, EntityStatus.REQUIRES_LOGIN)
            if (silent) {
              recordAutoRefreshFailure(entity.id, response)
            }
          }
          if (!silent) {
            resetState({ preserveSelectedFeatures: true })
          }
        } else if (response.code === FetchResultCode.REMOTE_FAILED) {
          notify(t.errors.REMOTE_FAILED, "error")
          if (silent && entity) {
            recordAutoRefreshFailure(entity.id, response)
          }
          if (!silent) {
            resetState({ preserveSelectedFeatures: true })
          }
        } else {
          const entityName = entity?.name || t.common.crypto
          const errorMessage = t.errors[response.code as keyof typeof t.errors]
          let finalMessage: string
          if (errorMessage?.includes("{entity}")) {
            finalMessage = errorMessage.replace("{entity}", entityName)
          } else if (errorMessage) {
            finalMessage = errorMessage
          } else {
            finalMessage = t.common.fetchErrorEntity.replace(
              "{entity}",
              entityName,
            )
          }
          notify(finalMessage, "error")
          if (silent && entity) {
            recordAutoRefreshFailure(entity.id, response)
          }
          if (!silent) {
            resetState({ preserveSelectedFeatures: true })
          }
        }
      } catch (e: any) {
        notify(
          t.common.fetchErrorEntity.replace(
            "{entity}",
            entity?.name || t.common.crypto,
          ),
          "error",
        )
        if (silent && entity) {
          recordAutoRefreshFailure(entity.id, undefined, e?.status)
        }
        if (!silent) {
          resetState({ preserveSelectedFeatures: true })
        }
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
      setSelectedEntity,
      setSelectedFeatures,
      setFetchOptions,
      resetState,
      setView,
      showToast,
      startExternalLogin,
      t,
      updateEntityStatus,
      activatePendingEntry,
      activateNextPending,
      activePinEntityId,
      pinRequired,
      fetchingEntityState,
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

          try {
            await scrape(selectedEntity, features, options)
          } finally {
            setView("entities")
          }
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
      async (id, result) => {
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
              try {
                await login(result.credentials)
              } finally {
                setView("entities")
              }
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

  const autoRefreshExecutedRef = useRef(false)

  useEffect(() => {
    if (autoRefreshExecutedRef.current) return
    if (!entitiesLoaded || entities.length === 0) return

    const autoRefreshSettings = settings.data?.autoRefresh
    if (
      !autoRefreshSettings ||
      autoRefreshSettings.mode === AutoRefreshMode.OFF
    )
      return

    autoRefreshExecutedRef.current = true

    const candidates = getAutoRefreshCandidates(
      entities,
      autoRefreshSettings.max_outdated,
      autoRefreshSettings.entities,
    )

    if (candidates.length === 0) return

    const AUTO_REFRESH_DELAY_MS = 3000
    const timeoutId = setTimeout(() => {
      candidates.forEach(({ entity, features }) => {
        scrape(entity, features, { silent: true, avoidNewLogin: true })
      })
    }, AUTO_REFRESH_DELAY_MS)

    return () => clearTimeout(timeoutId)
  }, [entitiesLoaded, entities, settings, scrape])

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
        getPendingScrapeParams: (entityId: string) =>
          pendingScrapeParamsRef.current.get(entityId),
        clearPendingScrapeParams: (entityId: string) => {
          pendingScrapeParamsRef.current.delete(entityId)
        },
        pendingPinEntityIds: () =>
          Array.from(pendingScrapeParamsRef.current.keys()).filter(
            id => id !== activePinEntityId,
          ),
        switchActivePinEntity: (entityId: string) => {
          const pending = pendingScrapeParamsRef.current.get(entityId)
          if (!pending) return
          activatePendingEntry(pending)
        },
        getPendingPinEntities: () =>
          Array.from(pendingScrapeParamsRef.current.entries())
            .filter(([id]) => id !== activePinEntityId)
            .map(([, pending]) => ({
              id: pending.entity.id,
              name: pending.entity.name,
            })),
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
