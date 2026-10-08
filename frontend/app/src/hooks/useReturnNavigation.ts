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
    sessionStorage.removeItem(storageKey)
    if (scrollRootRef.current) scrollRootRef.current.scrollTop = Number(saved)
  }, [ready, scrollRootRef])
}
