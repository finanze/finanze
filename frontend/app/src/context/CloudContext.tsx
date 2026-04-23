import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import { BackupMode, CloudRole, FFStatus } from "@/types"
import {
  cloudAuth,
  getCloudAuthToken,
  getApiServerInfo,
  getBackupSettings,
  updateBackupSettings,
} from "@/services/api"
import {
  CloudAuthProvider,
  CloudSession,
  CloudUser,
  SupabaseAuthProvider,
  type EmailPasswordSignUpResult,
} from "@/services/cloud"
import { useI18n } from "@/i18n"
import { useAuth } from "@/context/AuthContext"
import { useAppContext } from "@/context/AppContext"
import { isNativeMobile, isElectron } from "@/lib/platform"
import {
  signInWithGoogleMobile,
  signInWithAppleMobile,
} from "@/lib/mobile/socialLogin"
import { resetBackupStatusCache } from "@/hooks/useBackupStatus"

interface CloudContextType {
  user: CloudUser | null
  role: CloudRole | null
  permissions: string[]
  backupMode: BackupMode
  setBackupMode: (mode: BackupMode) => void
  isLoading: boolean
  isInitialized: boolean
  isPasswordRecoveryActive: boolean
  clearPasswordRecovery: () => void
  oauthError: string | null
  clearOAuthError: () => void
  signInWithGoogle: () => Promise<void>
  signInWithApple: () => Promise<void>
  signInWithEmail: (email: string, password: string) => Promise<void>
  signUpWithEmail: (
    email: string,
    password: string,
  ) => Promise<EmailPasswordSignUpResult>
  requestPasswordReset: (email: string) => Promise<void>
  updatePassword: (password: string) => Promise<void>
  signOut: () => Promise<void>
}

const CloudContext = createContext<CloudContextType | undefined>(undefined)

const createAuthProvider = (): CloudAuthProvider => {
  return new SupabaseAuthProvider()
}

export function CloudProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const navigate = useNavigate()
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
  const [isPasswordRecoveryActive, setIsPasswordRecoveryActive] =
    useState(false)
  const authProviderRef = useRef<CloudAuthProvider | null>(null)
  const lastSyncedTokenSignatureRef = useRef<string | null>(null)
  const lastBackupSettingsUserIdRef = useRef<string | null>(null)
  const clearBackendAuthInFlightRef = useRef(false)
  const syncInFlightRef = useRef(false)
  const pendingSyncRef = useRef<CloudSession | null | undefined>(undefined)
  const handleAuthStateChangeRef = useRef<
    ((session: CloudSession | null) => Promise<void>) | null
  >(null)
  const isExplicitSignOutRef = useRef(false)
  const recoveryAttemptedRef = useRef(false)

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

  const refreshSessionIfNeeded = useCallback(async (): Promise<void> => {
    try {
      const provider = getProvider()
      const session = await provider.getSession()
      if (session) {
        const now = Math.floor(Date.now() / 1000)
        const expiresAt = session.expiresAt
        const timeUntilExpiry = expiresAt - now
        const shouldRefresh = timeUntilExpiry < 300

        if (shouldRefresh) {
          await provider.refreshSession()
        }
      }
    } catch (error) {
      console.error("Failed to refresh session:", error)
    }
  }, [getProvider])

  const clearLocalCloudState = useCallback(() => {
    setUser(null)
    setRole(null)
    setPermissions([])
    setBackupModeState(BackupMode.OFF)
    lastSyncedTokenSignatureRef.current = null
    lastBackupSettingsUserIdRef.current = null
  }, [])

  const handleAuthStateChange = useCallback(
    async (session: CloudSession | null) => {
      if (session) {
        recoveryAttemptedRef.current = false
        setUser(session.user)
        try {
          await getProvider().setAutoRefreshEnabled(true)
        } catch (error) {
          console.error("Failed to enable auto-refresh:", error)
        }
        await syncRoleWithBackendIfNeeded(session)
        await refreshBackupModeForUser(session.user.id)
      } else if (isExplicitSignOutRef.current) {
        isExplicitSignOutRef.current = false
        await clearBackendCloudSession()
        clearLocalCloudState()
        try {
          await getProvider().setAutoRefreshEnabled(false)
        } catch (error) {
          console.error("Failed to disable auto-refresh:", error)
        }
      } else if (!recoveryAttemptedRef.current) {
        recoveryAttemptedRef.current = true
        try {
          const authData = await getCloudAuthToken()
          if (authData?.token) {
            const provider = getProvider()
            await provider.setSession(
              authData.token.access_token,
              authData.token.refresh_token,
            )
            const recovered = await provider.getSession()
            if (recovered) {
              await handleAuthStateChangeRef.current?.(recovered)
              return
            }
          }
        } catch (error) {
          console.error("Failed to recover cloud session:", error)
        }
        await clearBackendCloudSession()
        clearLocalCloudState()
        try {
          await getProvider().setAutoRefreshEnabled(false)
        } catch (error) {
          console.error("Failed to disable auto-refresh:", error)
        }
      } else {
        clearLocalCloudState()
        try {
          await getProvider().setAutoRefreshEnabled(false)
        } catch (error) {
          console.error("Failed to disable auto-refresh:", error)
        }
      }
    },
    [
      clearBackendCloudSession,
      clearLocalCloudState,
      getProvider,
      refreshBackupModeForUser,
      syncRoleWithBackendIfNeeded,
    ],
  )

  // Keep ref updated synchronously - not in an effect
  handleAuthStateChangeRef.current = handleAuthStateChange

  // Refresh session when app becomes visible after being hidden
  useEffect(() => {
    if (!isAuthenticated || !isCloudEnabled || !user) {
      return
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshSessionIfNeeded()
      }
    }

    document.addEventListener("visibilitychange", handleVisibilityChange)

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange)
    }
  }, [isAuthenticated, isCloudEnabled, user, refreshSessionIfNeeded])

  // Periodic session refresh check (every 5 minutes)
  useEffect(() => {
    if (!isAuthenticated || !isCloudEnabled || !user) {
      return
    }

    const intervalId = setInterval(
      () => {
        void refreshSessionIfNeeded()
      },
      5 * 60 * 1000,
    )

    return () => {
      clearInterval(intervalId)
    }
  }, [isAuthenticated, isCloudEnabled, user, refreshSessionIfNeeded])

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

    let cancelled = false
    let unsubscribe: (() => void) | undefined

    const initialize = async () => {
      try {
        const provider = getProvider()
        await provider.initialize()
        if (cancelled) return

        let session = await provider.getSession()
        if (cancelled) return

        try {
          const authData = await getCloudAuthToken()
          if (cancelled) return

          if (authData?.token) {
            try {
              await provider.setSession(
                authData.token.access_token,
                authData.token.refresh_token,
              )
              if (cancelled) return
              session = await provider.getSession()
              if (cancelled) return
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

        if (cancelled) return

        await provider.setAutoRefreshEnabled(!!session)
        if (cancelled) return

        if (session) {
          await handleAuthStateChangeRef.current?.(session)
        } else {
          setUser(null)
          setRole(null)
          setPermissions([])
          setBackupModeState(BackupMode.OFF)
          lastBackupSettingsUserIdRef.current = null
        }

        if (cancelled) return

        unsubscribe = provider.onAuthStateChange(changedSession => {
          void handleAuthStateChangeRef.current?.(changedSession)
        })
      } catch (error) {
        console.error("Failed to initialize cloud auth:", error)
      } finally {
        if (!cancelled) {
          setIsInitialized(true)
        }
      }
    }

    initialize()

    return () => {
      cancelled = true
      unsubscribe?.()
    }
  }, [getProvider, isAuthenticated, isCloudEnabled])

  useEffect(() => {
    if (!window.ipcAPI?.onOAuthCallbackUrl) {
      return
    }

    const unsubscribe = window.ipcAPI.onOAuthCallbackUrl(async payload => {
      try {
        const provider = getProvider()

        const urlObj = new URL(payload.url)
        const errorFromSearch = urlObj.searchParams.get("error")
        const errorCodeFromSearch = urlObj.searchParams.get("error_code")
        if (errorFromSearch) {
          const errorCode = errorCodeFromSearch ?? errorFromSearch ?? "unknown"
          const translatedError =
            t.settings.cloud.oauthErrors[
              errorCode as keyof typeof t.settings.cloud.oauthErrors
            ] ?? t.settings.cloud.oauthErrors.unknown

          const message = translatedError.replace("{error}", errorCode)
          setOauthError(message)
          navigate("/settings?tab=cloud")
          return
        }

        const hash = urlObj.hash.startsWith("#")
          ? urlObj.hash.substring(1)
          : urlObj.hash
        const hashParams = new URLSearchParams(hash)

        const errorFromHash = hashParams.get("error")
        if (errorFromHash) {
          const errorCodeFromHash = hashParams.get("error_code")
          const errorCode = errorCodeFromHash ?? errorFromHash ?? "unknown"

          const translatedError =
            t.settings.cloud.oauthErrors[
              errorCode as keyof typeof t.settings.cloud.oauthErrors
            ] ?? t.settings.cloud.oauthErrors.unknown

          const message = translatedError.replace("{error}", errorCode)
          setOauthError(message)
          navigate("/settings?tab=cloud")
          return
        }

        const typeFromSearch = urlObj.searchParams.get("type")
        const typeFromHash = hashParams.get("type")
        const type = typeFromSearch ?? typeFromHash

        const codeFromSearch = urlObj.searchParams.get("code")

        try {
          await provider.handleAuthCallbackUrl(payload.url)
        } catch (error) {
          // Some Supabase flows may return a PKCE code in the query string.
          // Prefer delegating to Supabase URL parsing, but fall back to direct
          // code exchange when needed.
          if (codeFromSearch) {
            await provider.exchangeCodeForSession(codeFromSearch)
          } else {
            throw error
          }
        }

        if (type === "recovery") {
          setIsPasswordRecoveryActive(true)
          navigate("/settings?tab=cloud")
          return
        }

        if (type === "signup" || type === "magiclink") {
          navigate("/settings?tab=cloud")
          return
        }

        // Some flows (notably magiclink and PKCE-based verify redirects)
        // may not preserve `type` in the final finanze:// callback.
        // If a session was established, route the user to the Cloud tab.
        const session = await provider.getSession()
        if (session) {
          navigate("/settings?tab=cloud")
          return
        }

        // Even if the link is invalid/expired, Supabase sometimes redirects
        // back without a session. Still route to Cloud so the user can see
        // the current state/error.
        if (
          urlObj.protocol === "finanze:" &&
          urlObj.hostname === "auth" &&
          urlObj.pathname === "/callback"
        ) {
          navigate("/settings?tab=cloud")
        }
      } catch (error) {
        console.error("Failed to set session from OAuth callback:", error)

        if (
          error instanceof Error &&
          /code verifier|pkce/i.test(error.message)
        ) {
          setOauthError(t.settings.cloud.oauthErrors.invalid_request)
          navigate("/settings?tab=cloud")
        }
      }
    })

    return () => {
      unsubscribe?.()
    }
  }, [getProvider, navigate])

  useEffect(() => {
    try {
      const provider = getProvider()
      const unsubscribe = provider.onAuthEvent(event => {
        if (event === "PASSWORD_RECOVERY") {
          setIsPasswordRecoveryActive(true)
          navigate("/settings?tab=cloud")
        }
      })

      return () => {
        unsubscribe?.()
      }
    } catch {
      return
    }
  }, [getProvider, navigate])

  const clearPasswordRecovery = useCallback(() => {
    setIsPasswordRecoveryActive(false)
  }, [])

  const updatePassword = useCallback(
    async (password: string) => {
      setIsLoading(true)
      try {
        const provider = getProvider()
        await provider.updatePassword(password)
      } finally {
        setIsLoading(false)
      }
    },
    [getProvider],
  )

  useEffect(() => {
    // Avoid handling the same callback through multiple IPC channels.
    // When the raw URL channel is available, it is the source of truth.
    if (
      window.ipcAPI?.onOAuthCallbackUrl ||
      !window.ipcAPI?.onOAuthCallbackCode
    ) {
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
    // Avoid handling the same callback through multiple IPC channels.
    // When the raw URL channel is available, it is the source of truth.
    if (
      window.ipcAPI?.onOAuthCallbackUrl ||
      !window.ipcAPI?.onOAuthCallbackError
    ) {
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
      navigate("/settings?tab=cloud")
    })

    return () => {
      unsubscribe?.()
    }
  }, [navigate, t.settings.cloud.oauthErrors])

  const signInWithGoogle = useCallback(async () => {
    setOauthError(null)
    setIsLoading(true)
    try {
      const provider = getProvider()

      if (isNativeMobile()) {
        const result = await signInWithGoogleMobile()
        if (!result.success) {
          throw new Error(result.error || "Google sign-in failed")
        }
        if (!result.idToken) {
          throw new Error("No ID token received from Google")
        }
        await provider.signInWithIdToken(
          "google",
          result.idToken,
          result.rawNonce,
        )
        return
      }

      if (!isElectron()) {
        throw new Error("Google sign-in is only available on desktop or mobile")
      }

      const serverInfo = await getApiServerInfo()
      const callbackUrl = `${serverInfo.baseUrl}/oauth/callback`
      await provider.signInWithGoogle(callbackUrl)
    } catch (error) {
      console.error("Google sign-in error:", error)

      let errorCode = "unknown"
      if (
        typeof error === "object" &&
        error &&
        "code" in error &&
        typeof (error as { code?: unknown }).code === "string"
      ) {
        errorCode = (error as { code: string }).code
      }

      const translatedError =
        t.settings.cloud.oauthErrors[
          errorCode as keyof typeof t.settings.cloud.oauthErrors
        ] ?? t.settings.cloud.oauthErrors.unknown

      const message = translatedError.replace("{error}", errorCode)

      setOauthError(message)
    } finally {
      setIsLoading(false)
    }
  }, [getProvider, t.settings.cloud.oauthErrors])

  const signInWithApple = useCallback(async () => {
    setOauthError(null)
    setIsLoading(true)
    try {
      const provider = getProvider()

      if (isNativeMobile()) {
        const result = await signInWithAppleMobile()
        if (!result.success) {
          throw new Error(result.error || "Apple sign-in failed")
        }
        if (!result.idToken) {
          throw new Error("No ID token received from Apple")
        }
        await provider.signInWithIdToken(
          "apple",
          result.idToken,
          result.rawNonce,
        )
        return
      }

      if (!isElectron()) {
        throw new Error("Apple sign-in is only available on desktop or mobile")
      }

      const serverInfo = await getApiServerInfo()
      const callbackUrl = `${serverInfo.baseUrl}/oauth/callback`
      await provider.signInWithApple(callbackUrl)
    } catch (error) {
      console.error("Apple sign-in error:", error)

      let errorCode = "unknown"
      if (
        typeof error === "object" &&
        error &&
        "code" in error &&
        typeof (error as { code?: unknown }).code === "string"
      ) {
        errorCode = (error as { code: string }).code
      }

      const translatedError =
        t.settings.cloud.oauthErrors[
          errorCode as keyof typeof t.settings.cloud.oauthErrors
        ] ?? t.settings.cloud.oauthErrors.unknown

      const message = translatedError.replace("{error}", errorCode)

      setOauthError(message)
    } finally {
      setIsLoading(false)
    }
  }, [getProvider, t.settings.cloud.oauthErrors])

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

  const signUpWithEmail = useCallback(
    async (email: string, password: string) => {
      setIsLoading(true)
      try {
        const provider = getProvider()
        const isElectron = typeof window !== "undefined" && !!window.ipcAPI
        const emailRedirectTo = isElectron
          ? "finanze://auth/callback?type=signup"
          : undefined
        return await provider.signUpWithEmail(email, password, {
          emailRedirectTo,
        })
      } finally {
        setIsLoading(false)
      }
    },
    [getProvider],
  )

  const requestPasswordReset = useCallback(
    async (email: string) => {
      setIsLoading(true)
      try {
        const provider = getProvider()
        const isElectron = typeof window !== "undefined" && !!window.ipcAPI
        const emailRedirectTo = isElectron
          ? "finanze://auth/callback?type=recovery"
          : undefined
        await provider.requestPasswordReset(email, {
          emailRedirectTo,
        })
      } finally {
        setIsLoading(false)
      }
    },
    [getProvider],
  )

  const signOut = useCallback(async () => {
    setIsLoading(true)
    try {
      isExplicitSignOutRef.current = true
      const provider = getProvider()
      try {
        await provider.signOut()
      } catch (error) {
        isExplicitSignOutRef.current = false
        throw error
      }
      resetBackupStatusCache()
    } finally {
      setIsLoading(false)
    }
  }, [getProvider])

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
        isPasswordRecoveryActive,
        clearPasswordRecovery,
        oauthError,
        clearOAuthError,
        signInWithGoogle,
        signInWithApple,
        signInWithEmail,
        signUpWithEmail,
        requestPasswordReset,
        updatePassword,
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
