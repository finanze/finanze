import { useCallback, useEffect, useRef } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { useLayoutScroll } from "@/context/LayoutScrollContext"
import { returnScrollKey } from "@/lib/returnTo"

export function useNavigateWithReturn(label: string) {
  const navigate = useNavigate()
  const location = useLocation()
  const { scrollRootRef } = useLayoutScroll()

  return useCallback(
    (to: string) => {
      sessionStorage.setItem(
        returnScrollKey(location.key),
        String(scrollRootRef.current?.scrollTop ?? 0),
      )
      navigate(to, {
        state: {
          returnTo: { path: `${location.pathname}${location.search}`, label },
        },
      })
    },
    [
      navigate,
      location.key,
      location.pathname,
      location.search,
      label,
      scrollRootRef,
    ],
  )
}

export function useRestoreReturnScroll(ready: boolean) {
  const location = useLocation()
  const { scrollRootRef } = useLayoutScroll()
  // URL syncing after mount changes the key, so keep the one we arrived with
  const arrivalKey = useRef(location.key)

  useEffect(() => {
    if (!ready) return
    const storageKey = returnScrollKey(arrivalKey.current)
    const saved = sessionStorage.getItem(storageKey)
    if (saved === null) return
    const scrollRoot = scrollRootRef.current
    if (!scrollRoot) return
    const savedOffset = Number(saved)
    let observer: ResizeObserver | null = null
    const restore = () => {
      scrollRoot.scrollTop = savedOffset
      if (Math.abs(scrollRoot.scrollTop - savedOffset) < 1) {
        sessionStorage.removeItem(storageKey)
        observer?.disconnect()
      }
    }
    restore()
    if (sessionStorage.getItem(storageKey) !== null) {
      observer = new ResizeObserver(restore)
      observer.observe(scrollRoot.firstElementChild ?? scrollRoot)
    }
    return () => observer?.disconnect()
  }, [ready, scrollRootRef])
}
