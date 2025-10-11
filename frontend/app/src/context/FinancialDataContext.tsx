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
} from "@/services/api"
import { EntitiesPosition, PositionQueryRequest } from "@/types/position"
import {
  EntityContributions,
  ContributionQueryRequest,
} from "@/types/contributions"
import { PeriodicFlow, PendingFlow } from "@/types"
import { useAppContext } from "./AppContext"
import { EntityType } from "@/types"
import { getAllRealEstate } from "@/services/api"
import type { RealEstate } from "@/types"

interface FinancialDataContextType {
  positionsData: EntitiesPosition | null
  contributions: EntityContributions | null
  periodicFlows: PeriodicFlow[]
  pendingFlows: PendingFlow[]
  isLoading: boolean
  error: string | null
  refreshData: () => Promise<void>
  refreshEntity: (entityId: string) => Promise<void>
  refreshFlows: () => Promise<void>
  realEstateList: RealEstate[]
  refreshRealEstate: () => Promise<void>
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
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const initialFetchDone = useRef(false)
  const realEstateFetchInFlight = useRef<Promise<void> | null>(null)
  const {
    inactiveEntities,
    entities,
    entitiesLoaded,
    setOnScrapeCompleted,
    fetchEntities,
    exchangeRates,
    exchangeRatesLoading,
  } = useAppContext()

  const fetchFinancialData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const entityIds = inactiveEntities?.map(entity => entity.id) ?? []
      const baseQuery =
        entityIds.length > 0 ? { excluded_entities: entityIds } : undefined

      const [
        positionsResponse,
        contributionsData,
        periodicFlowsData,
        pendingFlowsData,
      ] = await Promise.all([
        getPositions(baseQuery as PositionQueryRequest | undefined),
        getContributions(baseQuery as ContributionQueryRequest | undefined),
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

  const refreshEntity = async (entityId: string) => {
    setIsLoading(true)
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

      // Refresh entities to get updated last_fetch data
      try {
        await fetchEntities()
        console.log("Entities refreshed to update last_fetch data")
      } catch (error) {
        console.error(
          "Error refreshing entities after financial data refresh:",
          error,
        )
      }
    } catch (err) {
      console.error(
        `Error refreshing ${entityId === "crypto" ? "crypto entities" : `entity ${entityId}`}:`,
        err,
      )
      setError(`Failed to refresh entity. Please try again.`)
    } finally {
      setIsLoading(false)
    }
  }

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

  // Separate effect for inactive entities changes that should trigger refetch
  useEffect(() => {
    // Only refetch if we've already done the initial fetch
    if (initialFetchDone.current) {
      fetchFinancialData()
      // Keep real estate list in sync when filters change
      refreshRealEstate()
    }
  }, [inactiveEntities, refreshRealEstate])

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
        error,
        refreshData: fetchFinancialData,
        refreshEntity,
        refreshFlows,
        realEstateList,
        refreshRealEstate,
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
