import { createContext, useContext, useState, useEffect, type ReactNode } from "react"
import { checkLoginStatus, login as apiLogin, logout as apiLogout } from "@/services/api"

interface AuthContextType {
    isAuthenticated: boolean
    isLoading: boolean
    isInitializing: boolean
    login: (password: string) => Promise<boolean>
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [isInitializing, setIsInitializing] = useState(true)

    useEffect(() => {
        const checkAuth = async () => {
            const retryDelay = 1500

            while (true) {
                try {
                    const { status } = await checkLoginStatus()
                    setIsAuthenticated(status === "UNLOCKED")
                    setIsInitializing(false)
                    return
                } catch (error) {
                    await new Promise(resolve => setTimeout(resolve, retryDelay))
                }
            }
        }

        checkAuth()
    }, [])

    const login = async (password: string): Promise<boolean> => {
        setIsLoading(true)
        try {
            const { success } = await apiLogin(password)
            setIsAuthenticated(success)
            return success
        } catch (error) {
            console.error("Login error:", error)
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
        <AuthContext.Provider value={{ isAuthenticated, isLoading, isInitializing, login, logout }}>
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
