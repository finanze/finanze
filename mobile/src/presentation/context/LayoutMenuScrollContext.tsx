import React from "react"
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native"

type LayoutMenuScrollContextValue = {
  scrolling: boolean
  atTop: boolean
  atBottom: boolean
  onScroll: (e: NativeSyntheticEvent<NativeScrollEvent>) => void
}

const LayoutMenuScrollContext = React.createContext<
  LayoutMenuScrollContextValue | undefined
>(undefined)

export function LayoutMenuScrollProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [scrolling, setScrolling] = React.useState(false)
  const [atTop, setAtTop] = React.useState(true)
  const [atBottom, setAtBottom] = React.useState(false)
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  const onScroll = React.useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent
      const y = contentOffset?.y ?? 0
      const visibleH = layoutMeasurement?.height ?? 0
      const contentH = contentSize?.height ?? 0

      // Use a small threshold to avoid flapping.
      const nextAtTop = y <= 1
      const nextAtBottom = y + visibleH >= contentH - 1

      if (nextAtTop !== atTop) setAtTop(nextAtTop)
      if (nextAtBottom !== atBottom) setAtBottom(nextAtBottom)

      if (!scrolling) setScrolling(true)

      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        setScrolling(false)
      }, 220)
    },
    [atBottom, atTop, scrolling],
  )

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <LayoutMenuScrollContext.Provider
      value={{ scrolling, atTop, atBottom, onScroll }}
    >
      {children}
    </LayoutMenuScrollContext.Provider>
  )
}

export function useLayoutMenuScroll(): LayoutMenuScrollContextValue {
  const ctx = React.useContext(LayoutMenuScrollContext)
  if (!ctx) {
    return {
      scrolling: false,
      atTop: true,
      atBottom: false,
      onScroll: () => {
        // noop
      },
    }
  }
  return ctx
}
