import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from "react"
import { useApplicationContainer } from "@/presentation/context"
import {
  EntitiesPosition,
  BaseTx,
  RealEstate,
  PendingFlow,
  Dezimal,
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

const DEFAULT_EXCHANGE_RATES: ExchangeRates = {
  EUR: { EUR: Dezimal.fromString("1"), USD: Dezimal.fromString("1") },
  USD: { USD: Dezimal.fromString("1"), EUR: Dezimal.fromString("1") },
}

export function FinancialProvider({ children }: FinancialProviderProps) {
  const container = useApplicationContainer()

  const [positions, setPositions] = useState<EntitiesPosition | null>(null)
  const [recentTransactions, setRecentTransactions] = useState<BaseTx[]>([])
  const [realEstateList, setRealEstateList] = useState<RealEstate[]>([])
  const [pendingFlows, setPendingFlows] = useState<PendingFlow[]>([])
  const [exchangeRates, setExchangeRates] = useState<ExchangeRates>(
    DEFAULT_EXCHANGE_RATES,
  )
  const [targetCurrency, setTargetCurrency] = useState("EUR")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exchangeRatesInitialLoad = useRef(true)

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
        exchangeRatesData,
        positionsData,
        recentTransactionsData,
        realEstateData,
        pendingFlowsData,
      ] = await Promise.all([
        container.getExchangeRates.execute(exchangeRatesInitialLoad.current),
        container.getPosition.execute({}),
        container.getTransactions.execute({ limit: 10 }),
        container.listRealEstate.execute(),
        container.getPendingFlows.execute(),
      ])

      exchangeRatesInitialLoad.current = false
      setExchangeRates(prev => {
        return exchangeRatesData && Object.keys(exchangeRatesData).length
          ? exchangeRatesData
          : prev
      })

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
