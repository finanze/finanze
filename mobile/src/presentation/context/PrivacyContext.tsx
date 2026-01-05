import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import AsyncStorage from "@react-native-async-storage/async-storage"

interface PrivacyContextType {
  hideAmounts: boolean
  setHideAmounts: (value: boolean) => Promise<void>
}

const PrivacyContext = createContext<PrivacyContextType | undefined>(undefined)

const HIDE_AMOUNTS_KEY = "finanze.hideAmounts.v1"

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hideAmounts, setHideAmountsState] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const raw = await AsyncStorage.getItem(HIDE_AMOUNTS_KEY)
        if (raw != null) {
          setHideAmountsState(raw === "true")
        }
      } catch {
        // ignore
      } finally {
        setLoaded(true)
      }
    }
    load()
  }, [])

  const setHideAmounts = useCallback(async (value: boolean) => {
    try {
      await AsyncStorage.setItem(HIDE_AMOUNTS_KEY, value ? "true" : "false")
      setHideAmountsState(value)
    } catch {
      // ignore
    }
  }, [])

  if (!loaded) return null

  return (
    <PrivacyContext.Provider value={{ hideAmounts, setHideAmounts }}>
      {children}
    </PrivacyContext.Provider>
  )
}

export function usePrivacy(): PrivacyContextType {
  const ctx = useContext(PrivacyContext)
  if (!ctx) {
    throw new Error("usePrivacy must be used within a PrivacyProvider")
  }
  return ctx
}
