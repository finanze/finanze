import React, {
  createContext,
  type ReactNode,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react"
import {
  useColorScheme as useSystemColorScheme,
  Appearance,
  View,
  ActivityIndicator,
  StyleSheet,
} from "react-native"
import AsyncStorage from "@react-native-async-storage/async-storage"

export type ThemeMode = "light" | "dark" | "system"

interface ThemeContextType {
  /** User's preference: 'light', 'dark', or 'system' */
  themeMode: ThemeMode
  /** Resolved theme to actually use for styling */
  resolvedTheme: "light" | "dark"
  /** Update the theme mode preference */
  setThemeMode: (mode: ThemeMode) => Promise<void>
}

const THEME_STORAGE_KEY = "theme_mode"

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const systemColorScheme = useSystemColorScheme()
  const [themeMode, setThemeModeState] = useState<ThemeMode>("system")
  const [isLoaded, setIsLoaded] = useState(false)

  // Load saved theme preference on mount
  useEffect(() => {
    const loadTheme = async () => {
      try {
        const saved = await AsyncStorage.getItem(THEME_STORAGE_KEY)
        if (saved && ["light", "dark", "system"].includes(saved)) {
          setThemeModeState(saved as ThemeMode)
        }
      } catch (error) {
        console.error("Failed to load theme preference:", error)
      } finally {
        setIsLoaded(true)
      }
    }
    loadTheme()
  }, [])

  // Listen for system theme changes when in 'system' mode
  useEffect(() => {
    if (themeMode !== "system") return

    const subscription = Appearance.addChangeListener(({ colorScheme }) => {
      // Force re-render when system theme changes
    })

    return () => subscription?.remove()
  }, [themeMode])

  // Resolve the actual theme to use
  const resolvedTheme: "light" | "dark" =
    themeMode === "system" ? (systemColorScheme ?? "dark") : themeMode

  const setThemeMode = useCallback(async (mode: ThemeMode) => {
    try {
      await AsyncStorage.setItem(THEME_STORAGE_KEY, mode)
      setThemeModeState(mode)
    } catch (error) {
      console.error("Failed to save theme preference:", error)
    }
  }, [])

  // Show minimal loading state while loading preference (prevents flash)
  if (!isLoaded) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="small" color="#3b82f6" />
      </View>
    )
  }

  return (
    <ThemeContext.Provider value={{ themeMode, resolvedTheme, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    backgroundColor: "#000000",
    justifyContent: "center",
    alignItems: "center",
  },
})

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
