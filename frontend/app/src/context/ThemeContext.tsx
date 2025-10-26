import { ThemeMode } from "@/types"
import {
  createContext,
  type ReactNode,
  useContext,
  useLayoutEffect,
  useEffect,
  useState,
  useCallback,
} from "react"

interface ThemeContextType {
  theme: ThemeMode
  setThemeMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Persisted selection (default to system so we respect user OS on fresh load)
  const [theme, setTheme] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") return "system"
    const saved = (localStorage.getItem("theme") as ThemeMode) || "system"
    return saved
  })

  // Apply (or re-apply) the actual theme class early in the commit phase to avoid flash
  useLayoutEffect(() => {
    if (typeof window === "undefined") return
    const resolved =
      theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : theme
    document.documentElement.classList.toggle("dark", resolved === "dark")
  }, [theme])

  // React to OS theme changes only while in system mode
  useEffect(() => {
    if (theme !== "system") return
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const sync = () => {
      document.documentElement.classList.toggle("dark", media.matches)
    }
    // Initial sync in case it changed between render and effect
    sync()
    // Add listener (use both APIs for broader compatibility)
    if (media.addEventListener) media.addEventListener("change", sync)
    else media.addListener(sync)
    return () => {
      if (media.removeEventListener) media.removeEventListener("change", sync)
      else media.removeListener(sync)
    }
  }, [theme])

  // Stable setter
  const setThemeMode = useCallback((mode: ThemeMode) => {
    localStorage.setItem("theme", mode)
    if (window.ipcAPI) {
      window.ipcAPI.changeThemeMode(mode)
    }
    setTheme(mode)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
