import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
} from "react"
import {
  getPositions,
  getContributions,
  getAllPeriodicFlows,
  getAllPendingFlows,
  getTransactions,
} from "@/services/api"
import { EntitiesPosition, PositionQueryRequest } from "@/types/position"
import {
  EntityContributions,
  ContributionQueryRequest,
} from "@/types/contributions"
import { PeriodicFlow, PendingFlow } from "@/types"
import { TransactionsResult } from "@/types/transactions"
import { useAppContext } from "./AppContext"
import { useEntityWorkflow } from "./EntityWorkflowContext"
import { EntityType } from "@/types"
import { getAllRealEstate } from "@/services/api"
import type { RealEstate } from "@/types"

interface FinancialDataContextType {
  positionsData: EntitiesPosition | null
  contributions: EntityContributions | null
  periodicFlows: PeriodicFlow[]
  pendingFlows: PendingFlow[]
  isLoading: boolean
  isInitialLoading: boolean
  error: string | null
  refreshData: () => Promise<void>
  refreshEntity: (entityId: string) => Promise<void>
  refreshFlows: () => Promise<void>
  realEstateList: RealEstate[]
  refreshRealEstate: () => Promise<void>
  cachedLastTransactions: TransactionsResult | null
  fetchCachedTransactions: () => Promise<void>
  invalidateTransactionsCache: () => void
}

const FinancialDataContext = createContext<
  FinancialDataContextType | undefined
>(undefined)

export function FinancialDataProvider({ children }: { children: ReactNode }) {
  const [positionsData, setPositionsData] = useState<EntitiesPosition | null>(
    null,
  )
  const [contributions, setContributions] =
    useState<EntityContributions | null>(null)
  const [periodicFlows, setPeriodicFlows] = useState<PeriodicFlow[]>([])
  const [pendingFlows, setPendingFlows] = useState<PendingFlow[]>([])
  const [realEstateList, setRealEstateList] = useState<RealEstate[]>([])
  const [cachedLastTransactions, setCachedLastTransactions] =
    useState<TransactionsResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const initialFetchDone = useRef(false)
  const realEstateFetchInFlight = useRef<Promise<void> | null>(null)
  const {
    entities,
    entitiesLoaded,
    updateEntityLastFetch,
    exchangeRates,
    exchangeRatesLoading,
  } = useAppContext()
  const { setOnScrapeCompleted } = useEntityWorkflow()

  const fetchFinancialData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [
        positionsResponse,
        contributionsData,
        periodicFlowsData,
        pendingFlowsData,
      ] = await Promise.all([
        getPositions(),
        getContributions(),
        getAllPeriodicFlows(),
        getAllPendingFlows(),
      ])

      setPositionsData(positionsResponse)
      setContributions(contributionsData)
      setPeriodicFlows(periodicFlowsData)
      setPendingFlows(pendingFlowsData)
    } catch (err) {
      console.error("Error fetching financial data:", err)
      setError("Failed to load financial data. Please try again.")
    } finally {
      setIsLoading(false)
      setIsInitialLoading(false)
    }
  }

  const refreshFlows = useCallback(async () => {
    try {
      const [periodicFlowsData, pendingFlowsData] = await Promise.all([
        getAllPeriodicFlows(),
        getAllPendingFlows(),
      ])
      setPeriodicFlows(periodicFlowsData)
      setPendingFlows(pendingFlowsData)
    } catch (err) {
      console.error("Error refreshing flows:", err)
      setError("Failed to refresh flows. Please try again.")
    }
  }, [])

  const refreshRealEstate = useCallback(async () => {
    if (realEstateFetchInFlight.current) {
      return realEstateFetchInFlight.current
    }
    const p = (async () => {
      try {
        const list = await getAllRealEstate()
        setRealEstateList(list)
      } catch (err) {
        console.error("Error refreshing real estate:", err)
        setError("Failed to refresh real estate. Please try again.")
      } finally {
        realEstateFetchInFlight.current = null
      }
    })()
    realEstateFetchInFlight.current = p
    return p
  }, [])

  const fetchCachedTransactions = useCallback(async () => {
    try {
      const result = await getTransactions({
        limit: 8,
      })
      setCachedLastTransactions(result)
    } catch (err) {
      console.error("Error fetching cached transactions:", err)
    }
  }, [])

  const invalidateTransactionsCache = useCallback(() => {
    setCachedLastTransactions(null)
  }, [])

  const refreshEntity = useCallback(
    async (entityId: string) => {
      setError(null)

      try {
        console.log(`Refreshing financial data for entity: ${entityId}`)

        let queryParams: { entities: string[] }

        if (entityId === "crypto") {
          const cryptoEntities =
            entities?.filter(
              entity => entity.type === EntityType.CRYPTO_WALLET,
            ) || []

          if (cryptoEntities.length === 0) {
            console.log("No crypto entities found")
            return
          }

          queryParams = { entities: cryptoEntities.map(entity => entity.id) }
          console.log(
            `Refreshing crypto entities: ${cryptoEntities.map(e => e.name).join(", ")}`,
          )
        } else {
          queryParams = { entities: [entityId] }
        }

        const [positionsResponse, contributionsData] = await Promise.all([
          getPositions(queryParams as PositionQueryRequest),
          getContributions(queryParams as ContributionQueryRequest),
        ])

        // Update only the specific entity's data in the existing state
        setPositionsData(prevPositions => {
          if (!prevPositions) return positionsResponse

          return {
            ...prevPositions,
            positions: {
              ...prevPositions.positions,
              ...positionsResponse.positions,
            },
          }
        })

        setContributions(prevContributions => {
          if (!prevContributions) return contributionsData
          return {
            ...prevContributions,
            ...contributionsData,
          }
        })

        console.log(
          `Successfully refreshed ${entityId === "crypto" ? "crypto entities" : `entity ${entityId}`}`,
        )

        // Invalidate cached transactions since new data may be available
        invalidateTransactionsCache()
      } catch (err) {
        console.error(
          `Error refreshing ${entityId === "crypto" ? "crypto entities" : `entity ${entityId}`}:`,
          err,
        )
        setError(`Failed to refresh entity. Please try again.`)
      }
    },
    [entities, invalidateTransactionsCache, updateEntityLastFetch],
  )

  useEffect(() => {
    // Only fetch financial data if entities are loaded, exchange rates are not loading and are available
    // and we haven't done the initial fetch yet
    if (
      entitiesLoaded &&
      !exchangeRatesLoading &&
      exchangeRates &&
      !initialFetchDone.current
    ) {
      fetchFinancialData()
      // Also fetch real estate list so dashboard distributions have it available
      refreshRealEstate()
      initialFetchDone.current = true
    } else if (!entitiesLoaded) {
      // Reset the flag when entities are not loaded (user logged out)
      initialFetchDone.current = false
    }
  }, [entitiesLoaded, exchangeRatesLoading, exchangeRates, refreshRealEstate])

  // Register the refreshEntity callback with AppContext
  useEffect(() => {
    setOnScrapeCompleted(refreshEntity)
    return () => {
      setOnScrapeCompleted(null)
    }
  }, [refreshEntity, setOnScrapeCompleted])

  return (
    <FinancialDataContext.Provider
      value={{
        positionsData,
        contributions,
        periodicFlows,
        pendingFlows,
        isLoading,
        isInitialLoading,
        error,
        refreshData: fetchFinancialData,
        refreshEntity,
        refreshFlows,
        realEstateList,
        refreshRealEstate,
        cachedLastTransactions,
        fetchCachedTransactions,
        invalidateTransactionsCache,
      }}
    >
      {children}
    </FinancialDataContext.Provider>
  )
}

export const useFinancialData = () => {
  const context = useContext(FinancialDataContext)
  if (!context) {
    throw new Error(
      "useFinancialData must be used within a FinancialDataProvider",
    )
  }
  return context
}
