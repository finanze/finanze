import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react"
import { CloudUser, CloudSession } from "@/domain"
import { useApplicationContainer } from "@/presentation/context/ApplicationContainerContext"

interface AuthContextType {
  user: CloudUser | null
  session: CloudSession | null
  isLoading: boolean
  isInitialized: boolean
  error: string | null
  signInWithEmail: (email: string, password: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const container = useApplicationContainer()

  const [user, setUser] = useState<CloudUser | null>(null)
  const [session, setSession] = useState<CloudSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isInitialized, setIsInitialized] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let unsubscribe: (() => void) | undefined

    const initialize = async () => {
      try {
        await container.initializeAuth.execute()

        // Get initial session
        const initialSession = await container.getAuthSession.execute()
        if (initialSession) {
          setSession(initialSession)
          setUser(initialSession.user)
        }

        // Subscribe to auth state changes
        unsubscribe = container.observeAuthState.execute(newSession => {
          setSession(newSession)
          setUser(newSession?.user ?? null)
        })
      } catch (err) {
        console.error("Failed to initialize auth:", err)
      } finally {
        setIsInitialized(true)
      }
    }

    initialize()

    return () => {
      unsubscribe?.()
    }
  }, [container])

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      setIsLoading(true)
      setError(null)

      try {
        await container.signInWithEmail.execute(email, password)
      } catch (err: any) {
        const message = err.message || "Failed to sign in"
        setError(message)
        throw err
      } finally {
        setIsLoading(false)
      }
    },
    [container],
  )

  const signInWithGoogle = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      await container.signInWithGoogle.execute()
    } catch (err: any) {
      const message = err.message || "Failed to sign in with Google"
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [container])

  const signOut = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      await container.signOut.execute()
      setUser(null)
      setSession(null)
    } catch (err: any) {
      const message = err.message || "Failed to sign out"
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [container])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        isLoading,
        isInitialized,
        error,
        signInWithEmail,
        signInWithGoogle,
        signOut,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
