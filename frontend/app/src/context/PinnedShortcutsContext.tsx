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
  | "market-forecast"
  | "commodities"
  | "real-estate"
  | "management-recurring"
  | "management-pending"
  | "management-cashflow"

interface PinnedShortcutsContextType {
  pinnedShortcuts: PinnedShortcutId[]
  isPinned: (id: PinnedShortcutId) => boolean
  togglePin: (id: PinnedShortcutId) => void
  pin: (id: PinnedShortcutId) => void
  unpin: (id: PinnedShortcutId) => void
}

const STORAGE_KEY = "finanze-pinned-assets"
const CASHFLOW_PIN_MIGRATION_KEY = "finanze-pinned-assets-cashflow-default-v1"
const DEFAULT_CASHFLOW_SHORTCUT: PinnedShortcutId = "management-cashflow"
export const KNOWN_SHORTCUT_IDS: PinnedShortcutId[] = [
  "banking",
  "stocks-etfs",
  "funds",
  "deposits",
  "factoring",
  "real-estate-cf",
  "crypto",
  "market-forecast",
  "commodities",
  "real-estate",
  "management-recurring",
  "management-pending",
  "management-cashflow",
]
const LEGACY_SHORTCUT_IDS: Record<string, PinnedShortcutId> = {
  "management-auto-contributions": "management-recurring",
  "management-labels": "management-cashflow",
}
const DEFAULT_PINNED: PinnedShortcutId[] = ["banking", "management-cashflow"]

const PinnedShortcutsContext = createContext<
  PinnedShortcutsContextType | undefined
>(undefined)

function loadPinnedShortcuts(): PinnedShortcutId[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const migrationComplete =
      localStorage.getItem(CASHFLOW_PIN_MIGRATION_KEY) === "true"
    if (raw) {
      const parsed = JSON.parse(raw) as string[]
      const valid = parsed
        .map(id => LEGACY_SHORTCUT_IDS[id] ?? id)
        .filter(
          (id, index, ids): id is PinnedShortcutId =>
            KNOWN_SHORTCUT_IDS.includes(id as PinnedShortcutId) &&
            ids.indexOf(id) === index,
        )
      const shortcuts = valid.length ? valid : DEFAULT_PINNED
      if (migrationComplete) return shortcuts

      const migrated = shortcuts.includes(DEFAULT_CASHFLOW_SHORTCUT)
        ? shortcuts
        : [...shortcuts, DEFAULT_CASHFLOW_SHORTCUT]
      if (migrated !== shortcuts) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
      }
      localStorage.setItem(CASHFLOW_PIN_MIGRATION_KEY, "true")
      return migrated
    }
    if (!migrationComplete) {
      localStorage.setItem(CASHFLOW_PIN_MIGRATION_KEY, "true")
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
