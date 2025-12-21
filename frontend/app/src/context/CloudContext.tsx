import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react"
import { BackupMode, CloudRole, FFStatus } from "@/types"
import {
  cloudAuth,
  getCloudAuthToken,
  getApiBaseUrl,
  getBackupSettings,
  updateBackupSettings,
} from "@/services/api"
import {
  CloudAuthProvider,
  CloudSession,
  CloudUser,
  SupabaseAuthProvider,
} from "@/services/cloud"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"
import { useAppContext } from "@/context/AppContext"

interface CloudContextType {
  user: CloudUser | null
  role: CloudRole | null
  permissions: string[]
  backupMode: BackupMode
  setBackupMode: (mode: BackupMode) => void
  isLoading: boolean
  isInitialized: boolean
  oauthError: string | null
  clearOAuthError: () => void
  signInWithGoogle: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const CloudContext = createContext<CloudContextType | undefined>(undefined)

const createAuthProvider = (): CloudAuthProvider => {
  return new SupabaseAuthProvider()
}

export function CloudProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const { isAuthenticated } = useAuth()
  const { featureFlags } = useAppContext()

  const isCloudEnabled = featureFlags.CLOUD === FFStatus.ON

  const [user, setUser] = useState<CloudUser | null>(null)
  const [role, setRole] = useState<CloudRole | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [backupMode, setBackupModeState] = useState<BackupMode>(BackupMode.OFF)
  const [isLoading, setIsLoading] = useState(false)
  const [isInitialized, setIsInitialized] = useState(false)
  const [oauthError, setOauthError] = useState<string | null>(null)
  const authProviderRef = useRef<CloudAuthProvider | null>(null)
  const lastSyncedTokenSignatureRef = useRef<string | null>(null)
  const lastBackupSettingsUserIdRef = useRef<string | null>(null)
  const clearBackendAuthInFlightRef = useRef(false)
  const syncInFlightRef = useRef(false)
  const pendingSyncRef = useRef<CloudSession | null | undefined>(undefined)
  const handleAuthStateChangeRef = useRef<
    ((session: CloudSession | null) => Promise<void>) | null
  >(null)

  const getProvider = useCallback(() => {
    if (!authProviderRef.current) {
      authProviderRef.current = createAuthProvider()
    }
    return authProviderRef.current
  }, [])

  const refreshBackupMode = useCallback(async (): Promise<void> => {
    try {
      const settings = await getBackupSettings()
      if (
        settings?.mode === BackupMode.OFF ||
        settings?.mode === BackupMode.AUTO ||
        settings?.mode === BackupMode.MANUAL
      ) {
        setBackupModeState(settings.mode)
      } else {
        setBackupModeState(BackupMode.OFF)
      }
    } catch (error) {
      console.error("Failed to fetch backup settings:", error)
      setBackupModeState(BackupMode.OFF)
    }
  }, [])

  const refreshBackupModeForUser = useCallback(
    async (userId: string): Promise<void> => {
      if (lastBackupSettingsUserIdRef.current === userId) {
        return
      }

      lastBackupSettingsUserIdRef.current = userId
      await refreshBackupMode()
    },
    [refreshBackupMode],
  )

  const syncWithBackend = useCallback(
    async (
      session: CloudSession,
    ): Promise<{
      role: CloudRole | null
      permissions: string[]
    }> => {
      try {
        const response = await cloudAuth({
          token: {
            access_token: session.accessToken,
            refresh_token: session.refreshToken,
            token_type: session.tokenType,
            expires_at: session.expiresAt,
          },
        })
        return { role: response.role, permissions: response.permissions }
      } catch (error) {
        console.error("Failed to sync with backend:", error)
        return { role: null, permissions: [] }
      }
    },
    [],
  )

  const computeTokenSignature = (session: CloudSession): string => {
    return `${session.accessToken}|${session.refreshToken}|${session.tokenType}`
  }

  const clearBackendCloudSession = useCallback(async (): Promise<void> => {
    if (clearBackendAuthInFlightRef.current) {
      return
    }

    clearBackendAuthInFlightRef.current = true
    try {
      await cloudAuth({ token: null })
    } catch (error) {
      console.error("Failed to clear cloud session in backend:", error)
    } finally {
      clearBackendAuthInFlightRef.current = false
    }
  }, [])

  const syncRoleWithBackendIfNeeded = useCallback(
    async (session: CloudSession) => {
      const signature = computeTokenSignature(session)

      if (signature === lastSyncedTokenSignatureRef.current) {
        return
      }

      if (syncInFlightRef.current) {
        pendingSyncRef.current = session
        return
      }

      syncInFlightRef.current = true
      try {
        const { role: backendRole, permissions: backendPermissions } =
          await syncWithBackend(session)
        lastSyncedTokenSignatureRef.current = signature
        setRole(backendRole)
        setPermissions(backendPermissions)
      } finally {
        syncInFlightRef.current = false
        const pending = pendingSyncRef.current
        pendingSyncRef.current = undefined
        if (pending !== undefined) {
          if (pending) {
            void syncRoleWithBackendIfNeeded(pending)
          }
        }
      }
    },
    [syncWithBackend],
  )

  const handleAuthStateChange = useCallback(
    async (session: CloudSession | null) => {
      if (session) {
        setUser(session.user)
        // Enable auto-refresh when we have a session
        try {
          await getProvider().setAutoRefreshEnabled(true)
        } catch (error) {
          console.error("Failed to enable auto-refresh:", error)
        }
        await syncRoleWithBackendIfNeeded(session)
        await refreshBackupModeForUser(session.user.id)
      } else {
        await clearBackendCloudSession()
        setUser(null)
        setRole(null)
        setPermissions([])
        setBackupModeState(BackupMode.OFF)
        lastSyncedTokenSignatureRef.current = null
        lastBackupSettingsUserIdRef.current = null
        // Disable auto-refresh when signed out
        try {
          await getProvider().setAutoRefreshEnabled(false)
        } catch (error) {
          console.error("Failed to disable auto-refresh:", error)
        }
      }
    },
    [
      clearBackendCloudSession,
      getProvider,
      refreshBackupModeForUser,
      syncRoleWithBackendIfNeeded,
    ],
  )

  // Keep ref updated synchronously - not in an effect
  handleAuthStateChangeRef.current = handleAuthStateChange

  // When cloud feature is disabled, mark as initialized immediately
  useEffect(() => {
    if (!isCloudEnabled) {
      setUser(null)
      setRole(null)
      setPermissions([])
      setBackupModeState(BackupMode.OFF)
      lastBackupSettingsUserIdRef.current = null
      setIsInitialized(true)
    }
  }, [isCloudEnabled])

  useEffect(() => {
    if (!isAuthenticated || !isCloudEnabled) {
      return
    }

    let unsubscribe: (() => void) | undefined

    const initialize = async () => {
      try {
        const provider = getProvider()
        await provider.initialize()

        let session = await provider.getSession()

        try {
          const authData = await getCloudAuthToken()

          if (authData?.token) {
            try {
              await provider.setSession(
                authData.token.access_token,
                authData.token.refresh_token,
              )
              session = await provider.getSession()
              setRole(authData.role)
              setPermissions(authData.permissions)
            } catch (error) {
              console.error("Failed to set local session from backend:", error)
            }
          } else {
            if (session) {
              try {
                await provider.clearLocalSession()
              } catch (error) {
                console.error(
                  "Failed to clear local cloud session after backend returned null:",
                  error,
                )
              }
              session = null
            }
          }
        } catch (error) {
          console.error("Failed to fetch cloud session from backend:", error)
        }

        await provider.setAutoRefreshEnabled(!!session)

        if (session) {
          // Use handleAuthStateChangeRef to call the latest version
          await handleAuthStateChangeRef.current?.(session)
        } else {
          setUser(null)
          setRole(null)
          setPermissions([])
          setBackupModeState(BackupMode.OFF)
          lastBackupSettingsUserIdRef.current = null
        }

        // Subscribe using a stable wrapper that calls the ref
        unsubscribe = provider.onAuthStateChange(changedSession => {
          void handleAuthStateChangeRef.current?.(changedSession)
        })
      } catch (error) {
        console.error("Failed to initialize cloud auth:", error)
      } finally {
        setIsInitialized(true)
      }
    }

    initialize()

    return () => {
      unsubscribe?.()
    }
  }, [getProvider, isAuthenticated, isCloudEnabled])

  useEffect(() => {
    if (!window.ipcAPI?.onOAuthCallback) {
      return
    }

    const unsubscribe = window.ipcAPI.onOAuthCallback(async tokens => {
      try {
        const provider = getProvider()
        await provider.setSession(tokens.access_token, tokens.refresh_token)
      } catch (error) {
        console.error("Failed to set session from OAuth callback:", error)
      }
    })

    return () => {
      unsubscribe?.()
    }
  }, [getProvider])

  useEffect(() => {
    if (!window.ipcAPI?.onOAuthCallbackCode) {
      return
    }

    const unsubscribe = window.ipcAPI.onOAuthCallbackCode(async payload => {
      try {
        const provider = getProvider()
        await provider.exchangeCodeForSession(payload.code)
      } catch (error) {
        console.error("Failed to exchange OAuth code for session:", error)
        setOauthError(t.settings.cloud.loginError)
      }
    })

    return () => {
      unsubscribe?.()
    }
  }, [getProvider, t.settings.cloud.loginError])

  useEffect(() => {
    if (!window.ipcAPI?.onOAuthCallbackError) {
      return
    }

    const unsubscribe = window.ipcAPI.onOAuthCallbackError(payload => {
      console.error("OAuth callback error:", payload)

      const errorCode = payload.error ?? payload.error_code ?? "unknown"
      const translatedError =
        t.settings.cloud.oauthErrors[
          errorCode as keyof typeof t.settings.cloud.oauthErrors
        ] ?? t.settings.cloud.oauthErrors.unknown

      const message = translatedError.replace("{error}", errorCode)

      setOauthError(message)
    })

    return () => {
      unsubscribe?.()
    }
  }, [t.settings.cloud.oauthErrors])

  const signInWithGoogle = useCallback(async () => {
    setOauthError(null)
    setIsLoading(true)
    try {
      const provider = getProvider()
      const baseUrl = await getApiBaseUrl()
      const callbackUrl = `${baseUrl}/oauth/callback`
      await provider.signInWithGoogle(callbackUrl)
    } finally {
      setIsLoading(false)
    }
  }, [getProvider])

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      setIsLoading(true)
      try {
        const provider = getProvider()
        await provider.signInWithEmail(email, password)
      } finally {
        setIsLoading(false)
      }
    },
    [getProvider],
  )

  const signOut = useCallback(async () => {
    setIsLoading(true)
    try {
      const provider = getProvider()
      await provider.signOut()
      await clearBackendCloudSession()
      setUser(null)
      setRole(null)
      setPermissions([])
      setBackupModeState(BackupMode.OFF)
      lastBackupSettingsUserIdRef.current = null
    } finally {
      setIsLoading(false)
    }
  }, [clearBackendCloudSession, getProvider])

  const setBackupMode = useCallback(
    (mode: BackupMode) => {
      if (!user) {
        return
      }

      setBackupModeState(previousMode => {
        if (previousMode === mode) {
          return previousMode
        }

        void (async () => {
          try {
            await updateBackupSettings({ mode })
          } catch (error) {
            console.error("Failed to persist backup settings:", error)
            setBackupModeState(previousMode)
          }
        })()

        return mode
      })
    },
    [user],
  )

  const clearOAuthError = useCallback(() => {
    setOauthError(null)
  }, [])

  return (
    <CloudContext.Provider
      value={{
        user,
        role,
        permissions,
        backupMode,
        setBackupMode,
        isLoading,
        isInitialized,
        oauthError,
        clearOAuthError,
        signInWithGoogle,
        signInWithEmail,
        signOut,
      }}
    >
      {children}
    </CloudContext.Provider>
  )
}

export function useCloud(): CloudContextType {
  const context = useContext(CloudContext)
  if (context === undefined) {
    throw new Error("useCloud must be used within a CloudProvider")
  }
  return context
}
