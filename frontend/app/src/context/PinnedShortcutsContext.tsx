import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react"

export type PinnedShortcutId =
  | "banking"
  | "stocks-etfs"
  | "funds"
  | "deposits"
  | "factoring"
  | "real-estate-cf"
  | "crypto"
  | "commodities"
  | "real-estate"
  | "management-recurring"
  | "management-pending"
  | "management-auto-contributions"

interface PinnedShortcutsContextType {
  pinnedShortcuts: PinnedShortcutId[]
  isPinned: (id: PinnedShortcutId) => boolean
  togglePin: (id: PinnedShortcutId) => void
  pin: (id: PinnedShortcutId) => void
  unpin: (id: PinnedShortcutId) => void
}

const STORAGE_KEY = "finanze-pinned-assets"
const KNOWN_SHORTCUT_IDS: PinnedShortcutId[] = [
  "banking",
  "stocks-etfs",
  "funds",
  "deposits",
  "factoring",
  "real-estate-cf",
  "crypto",
  "commodities",
  "real-estate",
  "management-recurring",
  "management-pending",
  "management-auto-contributions",
]
const DEFAULT_PINNED: PinnedShortcutId[] = ["banking"]

const PinnedShortcutsContext = createContext<
  PinnedShortcutsContextType | undefined
>(undefined)

function loadPinnedShortcuts(): PinnedShortcutId[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as string[]

      const valid = parsed.filter((id): id is PinnedShortcutId =>
        KNOWN_SHORTCUT_IDS.includes(id as PinnedShortcutId),
      )
      return valid.length ? valid : DEFAULT_PINNED
    }
    return DEFAULT_PINNED
  } catch {
    return DEFAULT_PINNED
  }
}

export const PinnedShortcutsProvider = ({
  children,
}: {
  children: React.ReactNode
}) => {
  const [pinnedShortcuts, setPinnedShortcuts] =
    useState<PinnedShortcutId[]>(loadPinnedShortcuts)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(pinnedShortcuts))
    } catch {
      /* ignore */
    }
  }, [pinnedShortcuts])

  const isPinned = useCallback(
    (id: PinnedShortcutId) => pinnedShortcuts.includes(id),
    [pinnedShortcuts],
  )

  const pin = useCallback((id: PinnedShortcutId) => {
    setPinnedShortcuts(prev => (prev.includes(id) ? prev : [...prev, id]))
  }, [])

  const unpin = useCallback((id: PinnedShortcutId) => {
    setPinnedShortcuts(prev => prev.filter(p => p !== id))
  }, [])

  const togglePin = useCallback((id: PinnedShortcutId) => {
    setPinnedShortcuts(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id],
    )
  }, [])

  return (
    <PinnedShortcutsContext.Provider
      value={{ pinnedShortcuts, isPinned, togglePin, pin, unpin }}
    >
      {children}
    </PinnedShortcutsContext.Provider>
  )
}

export const usePinnedShortcuts = () => {
  const ctx = useContext(PinnedShortcutsContext)
  if (!ctx)
    throw new Error(
      "usePinnedShortcuts must be used within PinnedShortcutsProvider",
    )
  return ctx
}
