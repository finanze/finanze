import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react"
import {
  checkStatus,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
  changePassword as apiChangePassword,
} from "@/services/api"
import { AuthResultCode, type User } from "@/types"
import { setFeatureFlags } from "@/context/featureFlagsStore"
import { hideSplashScreen } from "@/lib/mobile"

interface AuthContextType {
  isAuthenticated: boolean
  user: User | null
  isLoading: boolean
  isInitializing: boolean
  isChangingPassword: boolean
  lastLoggedUser: string | null
  pendingPasswordChangeUser: string | null
  login: (
    username: string,
    password: string,
  ) => Promise<{ code: AuthResultCode; message?: string }>
  signup: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  changePassword: (oldPassword: string, newPassword: string) => Promise<boolean>
  setIsChangingPassword: (isChanging: boolean) => void
  startPasswordChange: () => Promise<void>
  cancelPasswordChange: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [lastLoggedUser, setLastLoggedUser] = useState<string | null>(null)
  const [pendingPasswordChangeUser, setPendingPasswordChangeUser] = useState<
    string | null
  >(null)

  const syncStatus = async (): Promise<void> => {
    const {
      status,
      lastLogged: last_logged,
      features,
      user: statusUser,
    } = await checkStatus()

    setFeatureFlags(features)
    const isUnlocked = status === "UNLOCKED"
    setIsAuthenticated(isUnlocked)
    setUser(isUnlocked ? (statusUser ?? null) : null)
    setLastLoggedUser(last_logged || null)
  }

  useEffect(() => {
    const checkAuth = async () => {
      hideSplashScreen()
      const retryDelay = 1500

      while (true) {
        try {
          await syncStatus()
          setIsInitializing(false)
          return
        } catch {
          await new Promise(resolve => setTimeout(resolve, retryDelay))
        }
      }
    }

    checkAuth()
  }, [])

  const login = async (
    username: string,
    password: string,
  ): Promise<{ code: AuthResultCode; message?: string }> => {
    setIsLoading(true)
    try {
      const result = await apiLogin({ username, password })
      const isSuccess = result.code === AuthResultCode.SUCCESS
      setIsAuthenticated(isSuccess)
      if (isSuccess) {
        try {
          await syncStatus()
        } catch {
          setLastLoggedUser(username)
          setUser(null)
        }
      }
      return result
    } catch (error) {
      console.error("Login error:", error)
      setIsAuthenticated(false)
      setUser(null)
      return {
        code: AuthResultCode.UNEXPECTED_ERROR,
        message: error instanceof Error ? error.message : undefined,
      }
    } finally {
      setIsLoading(false)
    }
  }

  const signup = async (
    username: string,
    password: string,
  ): Promise<boolean> => {
    setIsLoading(true)
    try {
      const { success } = await apiSignup({ username, password })
      if (success) {
        // Signup automatically logs the user in, so set auth state
        try {
          await syncStatus()
        } catch {
          setIsAuthenticated(true)
          setLastLoggedUser(username)
          setUser(null)
        }
      }
      return success
    } catch (error) {
      console.error("Signup error:", error)
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async (): Promise<void> => {
    setIsLoading(true)
    try {
      await apiLogout()
      setIsAuthenticated(false)
      setUser(null)
      // Always preserve lastLoggedUser - it should only be cleared when a new user logs in
      // This ensures that after logout, the login page shows for the last logged user
    } catch (error) {
      console.error("Logout error:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const changePassword = async (
    oldPassword: string,
    newPassword: string,
  ): Promise<boolean> => {
    // Use pendingPasswordChangeUser if available, otherwise fall back to lastLoggedUser
    const username = pendingPasswordChangeUser || lastLoggedUser
    if (!username) {
      console.error("changePassword: No username available")
      return false
    }

    setIsLoading(true)
    try {
      await apiChangePassword({
        username,
        oldPassword,
        newPassword,
      })
      // After successful password change, reset the flow state and preserve the user for login
      setIsChangingPassword(false)
      setPendingPasswordChangeUser(null)
      setLastLoggedUser(username) // Ensure the user is set for normal login view
      return true
    } catch (error) {
      console.error("Change password error:", error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const startPasswordChange = async (): Promise<void> => {
    if (!lastLoggedUser) {
      console.error("startPasswordChange: No lastLoggedUser available")
      return
    }

    setPendingPasswordChangeUser(lastLoggedUser)
    setIsChangingPassword(true)
    await logout()
  }

  const cancelPasswordChange = (): void => {
    const userForLogin = pendingPasswordChangeUser || lastLoggedUser
    setIsChangingPassword(false)
    setPendingPasswordChangeUser(null)
    if (userForLogin) {
      setLastLoggedUser(userForLogin)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        isLoading,
        isInitializing,
        isChangingPassword,
        lastLoggedUser,
        pendingPasswordChangeUser,
        login,
        signup,
        logout,
        changePassword,
        setIsChangingPassword,
        startPasswordChange,
        cancelPasswordChange,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
