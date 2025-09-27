import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react"

// Asset identifiers (keep stable – used in localStorage)
export type AssetId =
  | "banking"
  | "stocks-etfs"
  | "funds"
  | "deposits"
  | "factoring"
  | "real-estate-cf"
  | "crypto"
  | "commodities"
  | "real-estate"

interface PinnedAssetsContextType {
  pinnedAssets: AssetId[]
  isPinned: (id: AssetId) => boolean
  togglePin: (id: AssetId) => void
  pin: (id: AssetId) => void
  unpin: (id: AssetId) => void
}

const STORAGE_KEY = "finanze-pinned-assets"
const DEFAULT_PINNED: AssetId[] = ["banking"]

const PinnedAssetsContext = createContext<PinnedAssetsContextType | undefined>(
  undefined,
)

export const PinnedAssetsProvider = ({
  children,
}: {
  children: React.ReactNode
}) => {
  const [pinnedAssets, setPinnedAssets] = useState<AssetId[]>(DEFAULT_PINNED)

  // Load
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as string[]
        // Filter unknown ids gracefully
        const valid = parsed.filter(id =>
          DEFAULT_PINNED.concat([
            "stocks-etfs",
            "funds",
            "deposits",
            "factoring",
            "real-estate-cf",
            "crypto",
            "commodities",
            "real-estate",
          ]).includes(id as AssetId),
        ) as AssetId[]
        setPinnedAssets(valid.length ? valid : DEFAULT_PINNED)
      } else {
        setPinnedAssets(DEFAULT_PINNED)
      }
    } catch {
      setPinnedAssets(DEFAULT_PINNED)
    }
  }, [])

  // Persist
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(pinnedAssets))
    } catch {
      /* ignore */
    }
  }, [pinnedAssets])

  const isPinned = useCallback(
    (id: AssetId) => pinnedAssets.includes(id),
    [pinnedAssets],
  )

  const pin = useCallback((id: AssetId) => {
    setPinnedAssets(prev => (prev.includes(id) ? prev : [...prev, id]))
  }, [])

  const unpin = useCallback((id: AssetId) => {
    setPinnedAssets(prev => prev.filter(p => p !== id))
  }, [])

  const togglePin = useCallback((id: AssetId) => {
    setPinnedAssets(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id],
    )
  }, [])

  return (
    <PinnedAssetsContext.Provider
      value={{ pinnedAssets, isPinned, togglePin, pin, unpin }}
    >
      {children}
    </PinnedAssetsContext.Provider>
  )
}

export const usePinnedAssets = () => {
  const ctx = useContext(PinnedAssetsContext)
  if (!ctx)
    throw new Error("usePinnedAssets must be used within PinnedAssetsProvider")
  return ctx
}
