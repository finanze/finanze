import { useState, useCallback, useRef } from "react"
import { useApplicationContainer } from "@/presentation/context/ApplicationContainerContext"
import {
  BaseTx,
  TransactionQueryRequest,
  TransactionsResult,
  ProductType,
  TxType,
  AvailableSources,
} from "@/domain"
import { TransactionFiltersState } from "@/presentation/components/transactions"

const ITEMS_PER_PAGE = 20

interface UseTransactionsResult {
  transactions: BaseTx[]
  isLoading: boolean
  isLoadingMore: boolean
  error: string | null
  currentPage: number
  totalPages: number
  hasMore: boolean
  entities: AvailableSources["entities"]

  filters: TransactionFiltersState
  setFilters: (filters: TransactionFiltersState) => void

  fetchTransactions: (
    page?: number,
    resetPage?: boolean,
    filtersOverride?: TransactionFiltersState,
  ) => Promise<void>
  loadMore: () => Promise<void>
  clearFilters: () => Promise<void>
  refresh: () => Promise<void>
}

const INITIAL_FILTERS: TransactionFiltersState = {
  entities: [],
  productTypes: [],
  txTypes: [],
  fromDate: "",
  toDate: "",
}

export function useTransactions(): UseTransactionsResult {
  const container = useApplicationContainer()

  const [transactions, setTransactions] = useState<BaseTx[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [entities, setEntities] = useState<AvailableSources["entities"]>([])
  const [filters, setFilters] =
    useState<TransactionFiltersState>(INITIAL_FILTERS)

  const latestFetchIdRef = useRef(0)

  const fetchTransactions = useCallback(
    async (
      page: number = 1,
      resetPage: boolean = false,
      filtersOverride?: TransactionFiltersState,
    ) => {
      const fetchId = ++latestFetchIdRef.current
      const isFirstPage = page === 1 || resetPage

      if (isFirstPage) {
        setIsLoading(true)
      } else {
        setIsLoadingMore(true)
      }
      setError(null)

      try {
        // Load entities if not loaded yet
        if (entities.length === 0) {
          try {
            const availableEntities =
              await container.getAvailableEntities.execute()
            setEntities(availableEntities.entities)
          } catch {
            // Ignore entity loading errors
          }
        }

        const queryParams: TransactionQueryRequest = {
          page: isFirstPage ? 1 : page,
          limit: ITEMS_PER_PAGE,
        }

        const effectiveFilters = filtersOverride ?? filters

        // Add filters
        if (effectiveFilters.entities.length > 0) {
          queryParams.entities = effectiveFilters.entities
        }
        if (effectiveFilters.productTypes.length > 0) {
          queryParams.productTypes = effectiveFilters.productTypes
        }
        if (effectiveFilters.txTypes.length > 0) {
          queryParams.types = effectiveFilters.txTypes
        }
        if (effectiveFilters.fromDate) {
          queryParams.fromDate = effectiveFilters.fromDate
        }
        if (effectiveFilters.toDate) {
          queryParams.toDate = effectiveFilters.toDate
        }

        const result: TransactionsResult =
          await container.getTransactions.execute(queryParams)

        // Check if this is still the latest fetch
        if (latestFetchIdRef.current !== fetchId) {
          return
        }

        const newTransactions = result.transactions

        if (isFirstPage) {
          setTransactions(newTransactions)
          setCurrentPage(1)
        } else {
          setTransactions(prev => [...prev, ...newTransactions])
          setCurrentPage(page)
        }

        // Determine if there are more pages
        const hasMoreItems = newTransactions.length === ITEMS_PER_PAGE
        setHasMore(hasMoreItems)

        // Estimate total pages (we don't have total count from API)
        if (!hasMoreItems) {
          setTotalPages(page)
        } else {
          setTotalPages(Math.max(page + 1, totalPages))
        }
      } catch (err: any) {
        if (latestFetchIdRef.current === fetchId) {
          console.error("Error fetching transactions:", err)
          setError(err.message || "Failed to load transactions")
        }
      } finally {
        if (latestFetchIdRef.current === fetchId) {
          setIsLoading(false)
          setIsLoadingMore(false)
        }
      }
    },
    [container, entities.length, filters, totalPages],
  )

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return
    await fetchTransactions(currentPage + 1, false)
  }, [currentPage, fetchTransactions, hasMore, isLoadingMore])

  const clearFilters = useCallback(async () => {
    setFilters(INITIAL_FILTERS)
    await fetchTransactions(1, true, INITIAL_FILTERS)
  }, [fetchTransactions])

  const refresh = useCallback(async () => {
    await fetchTransactions(1, true)
  }, [fetchTransactions])

  return {
    transactions,
    isLoading,
    isLoadingMore,
    error,
    currentPage,
    totalPages,
    hasMore,
    entities,
    filters,
    setFilters,
    fetchTransactions,
    loadMore,
    clearFilters,
    refresh,
  }
}
