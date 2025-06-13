import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react"
import {
  checkLoginStatus,
  login as apiLogin,
  logout as apiLogout,
  signup as apiSignup,
} from "@/services/api"

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  isInitializing: boolean
  lastLoggedUser: string | null
  login: (username: string, password: string) => Promise<boolean>
  signup: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [lastLoggedUser, setLastLoggedUser] = useState<string | null>(null)

  useEffect(() => {
    const checkAuth = async () => {
      const retryDelay = 1500

      while (true) {
        try {
          const { status, last_logged } = await checkLoginStatus()
          setIsAuthenticated(status === "UNLOCKED")
          setLastLoggedUser(last_logged || null)
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
  ): Promise<boolean> => {
    setIsLoading(true)
    try {
      const { success } = await apiLogin({ username, password })
      setIsAuthenticated(success)
      if (success) {
        setLastLoggedUser(username)
      }
      return success
    } catch (error) {
      console.error("Login error:", error)
      return false
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
        setIsAuthenticated(true)
        setLastLoggedUser(username)
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
    } catch (error) {
      console.error("Logout error:", error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        isInitializing,
        lastLoggedUser,
        login,
        signup,
        logout,
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
