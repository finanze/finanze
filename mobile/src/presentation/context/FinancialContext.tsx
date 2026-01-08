import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  ReactNode,
} from "react"
import { useApplicationContainer } from "@/presentation/context/ApplicationContainerContext"
import { useExchangeRates } from "@/presentation/context/ExchangeRatesContext"
import {
  EntitiesPosition,
  BaseTx,
  RealEstate,
  PendingFlow,
  ExchangeRates,
} from "@/domain"

interface FinancialContextType {
  positions: EntitiesPosition | null
  recentTransactions: BaseTx[]
  realEstateList: RealEstate[]
  pendingFlows: PendingFlow[]
  exchangeRates: ExchangeRates
  targetCurrency: string

  isLoading: boolean
  error: string | null

  loadData: () => Promise<void>
  clearData: () => void
  clearError: () => void
}

const FinancialContext = createContext<FinancialContextType | undefined>(
  undefined,
)

interface FinancialProviderProps {
  children: ReactNode
}

export function FinancialProvider({ children }: FinancialProviderProps) {
  const container = useApplicationContainer()
  const { exchangeRates } = useExchangeRates()

  const [positions, setPositions] = useState<EntitiesPosition | null>(null)
  const [recentTransactions, setRecentTransactions] = useState<BaseTx[]>([])
  const [realEstateList, setRealEstateList] = useState<RealEstate[]>([])
  const [pendingFlows, setPendingFlows] = useState<PendingFlow[]>([])
  const [targetCurrency, setTargetCurrency] = useState("EUR")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // Load target currency from config
      try {
        const currency = await container.getDefaultCurrency.execute()
        setTargetCurrency(String(currency).toUpperCase())
      } catch {
        // Keep default
      }

      const [
        positionsData,
        recentTransactionsData,
        realEstateData,
        pendingFlowsData,
      ] = await Promise.all([
        container.getPosition.execute({}),
        container.getTransactions.execute({ limit: 10 }),
        container.listRealEstate.execute(),
        container.getPendingFlows.execute(),
      ])

      setPositions(positionsData)
      setRecentTransactions(recentTransactionsData.transactions)
      setRealEstateList(realEstateData)
      setPendingFlows(pendingFlowsData)
    } catch (err: any) {
      console.error("Error loading financial data:", err)
      setError(err.message || "Failed to load data")
    } finally {
      setIsLoading(false)
    }
  }, [container])

  // Auto-load data on mount if the database is already initialized (e.g., after hot reload).
  // This prevents the "No data available" screen from appearing after React state resets.
  useEffect(() => {
    if (positions !== null) return // Already have data

    const tryAutoLoad = async () => {
      try {
        const exists = await container.checkDatasourceExists.execute()
        if (exists) {
          await loadData()
        }
      } catch {
        // Database not ready, ignore - user will need to decrypt
      }
    }

    void tryAutoLoad()
  }, [container, loadData, positions])

  const clearData = useCallback(() => {
    setPositions(null)
    setRecentTransactions([])
    setRealEstateList([])
    setPendingFlows([])
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return (
    <FinancialContext.Provider
      value={{
        positions,
        recentTransactions,
        realEstateList,
        pendingFlows,
        exchangeRates,
        targetCurrency,
        isLoading,
        error,
        loadData,
        clearData,
        clearError,
      }}
    >
      {children}
    </FinancialContext.Provider>
  )
}

export function useFinancial(): FinancialContextType {
  const context = useContext(FinancialContext)
  if (context === undefined) {
    throw new Error("useFinancial must be used within a FinancialProvider")
  }
  return context
}
