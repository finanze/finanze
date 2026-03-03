import { useState, useCallback, useRef, useEffect } from "react"
import { getHistoric } from "@/services/api"
import type {
  BaseHistoricEntry,
  HistoricQueryRequest,
  HistoricSortBy,
  SortOrder,
} from "@/types/historic"
import type { ProductType } from "@/types/position"

const DEFAULT_LIMIT = 20

interface UseHistoricPaginationOptions {
  productType: ProductType
  selectedEntities: string[]
  isVisible: boolean
  limit?: number
}

interface UseHistoricPaginationResult {
  entries: BaseHistoricEntry[]
  isLoading: boolean
  isLoadingMore: boolean
  hasMore: boolean
  hasLoaded: boolean
  error: string | null
  sortBy: HistoricSortBy
  sortOrder: SortOrder
  setSortBy: (value: HistoricSortBy) => void
  setSortOrder: (value: SortOrder) => void
  reload: () => void
  sentinelRef: (node: HTMLDivElement | null) => void
}

export function useHistoricPagination({
  productType,
  selectedEntities,
  isVisible,
  limit = DEFAULT_LIMIT,
}: UseHistoricPaginationOptions): UseHistoricPaginationResult {
  const [entries, setEntries] = useState<BaseHistoricEntry[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sortBy, setSortByState] = useState<HistoricSortBy>("maturity")
  const [sortOrder, setSortOrderState] = useState<SortOrder>("desc")

  const pageRef = useRef(1)
  const loadingRef = useRef(false)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const sentinelNodeRef = useRef<HTMLDivElement | null>(null)
  const filterKeyRef = useRef("")
  const fetchIdRef = useRef(0)

  const buildFilterKey = useCallback(() => {
    const entityPart =
      selectedEntities.length > 0 ? selectedEntities.join("|") : "ALL"
    return `${entityPart}::${sortBy}::${sortOrder}`
  }, [selectedEntities, sortBy, sortOrder])

  const fetchPage = useCallback(
    async (page: number, append: boolean) => {
      if (loadingRef.current) return
      loadingRef.current = true

      const fetchId = ++fetchIdRef.current

      if (append) {
        setIsLoadingMore(true)
      } else {
        setIsLoading(true)
        setError(null)
        setHasLoaded(false)
      }

      try {
        const queryParams: HistoricQueryRequest = {
          product_types: [productType],
          entities: selectedEntities.length > 0 ? selectedEntities : undefined,
          page,
          limit,
          sort_by: sortBy,
          sort_order: sortOrder,
        }

        const response = await getHistoric(queryParams)

        if (fetchIdRef.current !== fetchId) return

        const newEntries = Array.isArray(response.entries)
          ? response.entries.filter(entry => entry.product_type === productType)
          : []

        if (append) {
          setEntries(prev => [...prev, ...newEntries])
        } else {
          setEntries(newEntries)
        }

        setHasMore(newEntries.length >= limit)
        pageRef.current = page
        filterKeyRef.current = buildFilterKey()
        setHasLoaded(true)
      } catch (err) {
        if (fetchIdRef.current !== fetchId) return
        const message =
          err instanceof Error ? err.message : "Failed to load historic"
        setError(message)
        filterKeyRef.current = buildFilterKey()
      } finally {
        if (fetchIdRef.current === fetchId) {
          setIsLoading(false)
          setIsLoadingMore(false)
          loadingRef.current = false
        }
      }
    },
    [productType, selectedEntities, limit, sortBy, sortOrder, buildFilterKey],
  )

  const loadMore = useCallback(() => {
    if (loadingRef.current || !hasMore) return
    fetchPage(pageRef.current + 1, true)
  }, [fetchPage, hasMore])

  const reload = useCallback(() => {
    pageRef.current = 1
    setEntries([])
    setHasMore(true)
    loadingRef.current = false
    fetchPage(1, false)
  }, [fetchPage])

  const setSortBy = useCallback(
    (value: HistoricSortBy) => {
      if (value === sortBy) return
      setSortByState(value)
    },
    [sortBy],
  )

  const setSortOrder = useCallback(
    (value: SortOrder) => {
      if (value === sortOrder) return
      setSortOrderState(value)
    },
    [sortOrder],
  )

  // Auto-fetch when section becomes visible or filters/sort change
  useEffect(() => {
    if (!isVisible) return
    if (loadingRef.current) return

    const currentKey = buildFilterKey()
    if (hasLoaded && currentKey === filterKeyRef.current) return
    if (error && currentKey === filterKeyRef.current) return

    pageRef.current = 1
    setEntries([])
    setHasMore(true)
    loadingRef.current = false
    fetchPage(1, false)
  }, [isVisible, buildFilterKey, hasLoaded, error, fetchPage])

  // IntersectionObserver callback for infinite scroll
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }

      sentinelNodeRef.current = node

      if (!node) return

      observerRef.current = new IntersectionObserver(
        entries => {
          if (entries[0]?.isIntersecting && !loadingRef.current && hasMore) {
            loadMore()
          }
        },
        { rootMargin: "200px" },
      )

      observerRef.current.observe(node)
    },
    [loadMore, hasMore],
  )

  // Cleanup observer on unmount
  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect()
      }
    }
  }, [])

  return {
    entries,
    isLoading,
    isLoadingMore,
    hasMore,
    hasLoaded,
    error,
    sortBy,
    sortOrder,
    setSortBy,
    setSortOrder,
    reload,
    sentinelRef,
  }
}
