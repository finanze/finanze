import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react"

interface LayoutScrollContextType {
  scrolling: boolean
  atTop: boolean
  atBottom: boolean
  handleScroll: (event: React.UIEvent<HTMLElement>) => void
  resetScroll: () => void
}

const LayoutScrollContext = createContext<LayoutScrollContextType | undefined>(
  undefined,
)

const SCROLL_THRESHOLD = 10
const SCROLL_END_DELAY = 150
const COLLAPSE_COOLDOWN = 700

export function LayoutScrollProvider({ children }: { children: ReactNode }) {
  const [scrolling, setScrolling] = useState(false)
  const [atTop, setAtTop] = useState(true)
  const [atBottom, setAtBottom] = useState(false)

  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const collapseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastScrollTopRef = useRef(0)
  const lastAtEdgeRef = useRef(Date.now())
  const wasAtEdgeRef = useRef(true)

  const handleScroll = useCallback((event: React.UIEvent<HTMLElement>) => {
    const target = event.currentTarget
    const scrollTop = target.scrollTop
    const scrollHeight = target.scrollHeight
    const clientHeight = target.clientHeight

    const isAtTop = scrollTop <= SCROLL_THRESHOLD
    const isAtBottom =
      scrollTop + clientHeight >= scrollHeight - SCROLL_THRESHOLD
    const isAtEdge = isAtTop || isAtBottom

    setAtTop(isAtTop)
    setAtBottom(isAtBottom)

    const scrollDelta = Math.abs(scrollTop - lastScrollTopRef.current)
    lastScrollTopRef.current = scrollTop

    if (isAtEdge) {
      lastAtEdgeRef.current = Date.now()
      wasAtEdgeRef.current = true
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current)
        collapseTimeoutRef.current = null
      }
    }

    if (scrollDelta > 2 && !isAtEdge) {
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current)
        collapseTimeoutRef.current = null
      }

      const timeSinceEdge = Date.now() - lastAtEdgeRef.current
      if (wasAtEdgeRef.current && timeSinceEdge < COLLAPSE_COOLDOWN) {
        collapseTimeoutRef.current = setTimeout(() => {
          setScrolling(true)
          wasAtEdgeRef.current = false
        }, COLLAPSE_COOLDOWN - timeSinceEdge)
      } else {
        setScrolling(true)
        wasAtEdgeRef.current = false
      }
    }

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
    }

    scrollTimeoutRef.current = setTimeout(() => {
      setScrolling(false)
    }, SCROLL_END_DELAY)
  }, [])

  const resetScroll = useCallback(() => {
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current)
      scrollTimeoutRef.current = null
    }
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current)
      collapseTimeoutRef.current = null
    }
    setScrolling(false)
    setAtTop(true)
    setAtBottom(false)
    lastScrollTopRef.current = 0
    lastAtEdgeRef.current = Date.now()
    wasAtEdgeRef.current = true
  }, [])

  return (
    <LayoutScrollContext.Provider
      value={{ scrolling, atTop, atBottom, handleScroll, resetScroll }}
    >
      {children}
    </LayoutScrollContext.Provider>
  )
}

export function useLayoutScroll() {
  const context = useContext(LayoutScrollContext)
  if (context === undefined) {
    throw new Error(
      "useLayoutScroll must be used within a LayoutScrollProvider",
    )
  }
  return context
}
