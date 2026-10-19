import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"
import {
  KNOWN_SHORTCUT_IDS,
  type PinnedShortcutId,
} from "@/context/PinnedShortcutsContext"

const ROOT_IDS = [
  "dashboard",
  "investments",
  "transactions",
  "calculations",
  "management",
  "entities",
  "settings",
  "export",
] as const

export type BottomNavItemId = (typeof ROOT_IDS)[number] | PinnedShortcutId
export const MIN_BAR_ITEMS = 4
export const MAX_BAR_ITEMS = 6
const STORAGE_KEY = "finanze-bottom-nav"
const DEFAULT_BAR: BottomNavItemId[] = [...ROOT_IDS.slice(0, 6)]
const DEFAULT_MENU: BottomNavItemId[] = ["settings", "export"]

export const BOTTOM_NAV_SHORTCUTS = KNOWN_SHORTCUT_IDS.filter(
  id => __CONNECTIONS__ || id !== "market-forecast",
)
const KNOWN_IDS: readonly string[] = [...ROOT_IDS, ...BOTTOM_NAV_SHORTCUTS]

interface NavLayout {
  bar: BottomNavItemId[]
  menu: BottomNavItemId[]
}

interface BottomNavContextValue extends NavLayout {
  isCustomizing: boolean
  setIsCustomizing: (value: boolean) => void
  moveToMenu: (id: BottomNavItemId) => void
  moveToBar: (id: BottomNavItemId) => void
  reorderBar: (ids: BottomNavItemId[]) => void
  reorderMenu: (ids: BottomNavItemId[]) => void
  addShortcut: (id: PinnedShortcutId) => void
  removeShortcut: (id: BottomNavItemId) => void
  isCustomized: boolean
  reset: () => void
}

const defaults = (): NavLayout => ({
  bar: [...DEFAULT_BAR],
  menu: [...DEFAULT_MENU],
})

function loadLayout(): NavLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults()
    const saved = JSON.parse(raw)
    if (
      saved?.version !== 1 ||
      !Array.isArray(saved.bar) ||
      !Array.isArray(saved.menu)
    ) {
      return defaults()
    }
    const seen = new Set<string>()
    const sanitize = (ids: unknown[]): BottomNavItemId[] =>
      ids.filter((id): id is BottomNavItemId => {
        if (typeof id !== "string" || !KNOWN_IDS.includes(id) || seen.has(id))
          return false
        seen.add(id)
        return true
      })
    const bar = sanitize(saved.bar)
    const menu = [...bar.splice(MAX_BAR_ITEMS), ...sanitize(saved.menu)]
    ROOT_IDS.forEach(id => {
      if (!seen.has(id)) menu.push(id)
    })
    bar.push(...menu.splice(0, Math.max(0, MIN_BAR_ITEMS - bar.length)))
    return { bar, menu }
  } catch {
    return defaults()
  }
}

const BottomNavContext = createContext<BottomNavContextValue | undefined>(
  undefined,
)

export function BottomNavProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState(loadLayout)
  const [isCustomizing, setIsCustomizing] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: 1, ...layout }),
      )
    } catch {
      return
    }
  }, [layout])

  const moveToMenu = (id: BottomNavItemId) =>
    setLayout(prev => {
      if (prev.bar.length <= MIN_BAR_ITEMS || !prev.bar.includes(id))
        return prev
      return {
        bar: prev.bar.filter(item => item !== id),
        menu: [...prev.menu, id],
      }
    })

  const moveToBar = (id: BottomNavItemId) =>
    setLayout(prev => {
      if (prev.bar.length >= MAX_BAR_ITEMS || !prev.menu.includes(id))
        return prev
      return {
        bar: [...prev.bar, id],
        menu: prev.menu.filter(item => item !== id),
      }
    })

  const reorder = (list: keyof NavLayout, ids: BottomNavItemId[]) =>
    setLayout(prev => {
      if (
        ids.length !== prev[list].length ||
        new Set(ids).size !== ids.length ||
        !ids.every(id => prev[list].includes(id))
      )
        return prev
      return { ...prev, [list]: [...ids] }
    })

  const addShortcut = (id: PinnedShortcutId) =>
    setLayout(prev => {
      if (
        !BOTTOM_NAV_SHORTCUTS.includes(id) ||
        prev.bar.includes(id) ||
        prev.menu.includes(id)
      )
        return prev
      return prev.bar.length < MAX_BAR_ITEMS
        ? { ...prev, bar: [...prev.bar, id] }
        : { ...prev, menu: [...prev.menu, id] }
    })

  const removeShortcut = (id: BottomNavItemId) =>
    setLayout(prev => {
      if (
        !BOTTOM_NAV_SHORTCUTS.includes(id as PinnedShortcutId) ||
        !prev.menu.includes(id)
      )
        return prev
      return { ...prev, menu: prev.menu.filter(item => item !== id) }
    })

  return (
    <BottomNavContext.Provider
      value={{
        ...layout,
        isCustomizing,
        setIsCustomizing,
        moveToMenu,
        moveToBar,
        reorderBar: ids => reorder("bar", ids),
        reorderMenu: ids => reorder("menu", ids),
        addShortcut,
        removeShortcut,
        isCustomized: JSON.stringify(layout) !== JSON.stringify(defaults()),
        reset: () => setLayout(defaults()),
      }}
    >
      {children}
    </BottomNavContext.Provider>
  )
}

export function useBottomNav() {
  const context = useContext(BottomNavContext)
  if (!context)
    throw new Error("useBottomNav must be used within BottomNavProvider")
  return context
}
