import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react"
import { getPositions, getContributions } from "@/services/api"
import { EntitiesPosition, PositionQueryRequest } from "@/types/position"
import {
  EntityContributions,
  ContributionQueryRequest,
} from "@/types/contributions"
import { useAppContext } from "./AppContext"

interface FinancialDataContextType {
  positionsData: EntitiesPosition | null
  contributions: EntityContributions | null
  isLoading: boolean
  error: string | null
  refreshData: () => Promise<void>
  refreshEntity: (entityId: string) => Promise<void>
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
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { activeEntities } = useAppContext()

  const fetchFinancialData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      let queryParams:
        | PositionQueryRequest
        | ContributionQueryRequest
        | undefined = undefined
      if (activeEntities && activeEntities.length > 0) {
        const entityIds = activeEntities.map(entity => entity.id)
        queryParams = { entities: entityIds }
      }

      const [positionsResponse, contributionsData] = await Promise.all([
        getPositions(queryParams as PositionQueryRequest),
        getContributions(queryParams as ContributionQueryRequest),
      ])

      setPositionsData(positionsResponse)
      setContributions(contributionsData)
    } catch (err) {
      console.error("Error fetching financial data:", err)
      setError("Failed to load financial data. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const refreshEntity = async (entityId: string) => {
    setIsLoading(true)
    setError(null)

    try {
      console.log(
        `Refreshing financial data for entity: ${entityId} (triggers full refresh)`,
      )
      await fetchFinancialData()
    } catch (err) {
      console.error(`Error refreshing entity ${entityId}:`, err)
      setError(`Failed to refresh entity. Please try again.`)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchFinancialData()
  }, [activeEntities])

  return (
    <FinancialDataContext.Provider
      value={{
        positionsData,
        contributions,
        isLoading,
        error,
        refreshData: fetchFinancialData,
        refreshEntity,
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
