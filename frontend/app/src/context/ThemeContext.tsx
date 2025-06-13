import { ThemeMode } from "@/types"
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"

type Theme = "light" | "dark"

interface ThemeContextType {
  theme: ThemeMode
  setThemeMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeMode>("dark")

  const resolveTheme: () => Theme = () => {
    const system = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
    let targetTheme = system

    if (!window.ipcAPI) {
      const savedTheme = localStorage.getItem("theme") as ThemeMode
      if (savedTheme != "system") {
        targetTheme = savedTheme
      }
    }

    return targetTheme as Theme
  }

  useEffect(() => {
    const resolvedTheme = resolveTheme()
    setTheme(resolvedTheme)
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark")
  }, [])

  const setThemeMode = (mode: ThemeMode) => {
    if (!window.ipcAPI) {
      localStorage.setItem("theme", mode)
    }
    window.ipcAPI?.changeThemeMode(mode)
    setTheme(mode)

    setTimeout(() => {
      if (mode === "system") {
        mode = window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
      }
      document.documentElement.classList.toggle("dark", mode === "dark")
    }, 80)
  }

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
