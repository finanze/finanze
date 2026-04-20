import { DataDisplayMode } from "@/types"
import {
  createContext,
  type ReactNode,
  useContext,
  useState,
  useCallback,
} from "react"

interface DataDisplayModeContextType {
  mode: DataDisplayMode
  setMode: (mode: DataDisplayMode) => void
}

const DataDisplayModeContext = createContext<
  DataDisplayModeContextType | undefined
>(undefined)

export function DataDisplayModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DataDisplayMode>(() => {
    if (typeof window === "undefined") return DataDisplayMode.NONE
    const saved = localStorage.getItem("dataDisplayMode")
    if (
      saved &&
      Object.values(DataDisplayMode).includes(saved as DataDisplayMode)
    ) {
      return saved as DataDisplayMode
    }
    return DataDisplayMode.NONE
  })

  const setMode = useCallback((next: DataDisplayMode) => {
    localStorage.setItem("dataDisplayMode", next)
    setModeState(next)
  }, [])

  return (
    <DataDisplayModeContext.Provider value={{ mode, setMode }}>
      {children}
    </DataDisplayModeContext.Provider>
  )
}

export function useDataDisplayMode(): DataDisplayModeContextType {
  const ctx = useContext(DataDisplayModeContext)
  if (!ctx) {
    throw new Error(
      "useDataDisplayMode must be used within a DataDisplayModeProvider",
    )
  }
  return ctx
}
