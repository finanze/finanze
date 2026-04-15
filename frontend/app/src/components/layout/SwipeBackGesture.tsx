import { useRef, useState, useEffect, type ReactNode } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { isNativeMobile, isIOS } from "@/lib/platform"
import { canNavigateBack } from "@/lib/mobile/backNavigation"
import { useModalRegistry } from "@/context/ModalRegistryContext"

const EDGE_ZONE = 30
const THRESHOLD_RATIO = 0.3
const MIN_VELOCITY = 0.3
const DAMPEN_MAX = 0.25

let hapticsModule: typeof import("@capacitor/haptics") | null = null
let hapticsLoading = false

function triggerHaptic() {
  if (!isIOS()) return
  if (hapticsModule) {
    hapticsModule.Haptics.impact({
      style: hapticsModule.ImpactStyle.Light,
    }).catch(() => {})
    return
  }
  if (hapticsLoading) return
  hapticsLoading = true
  import("@capacitor/haptics")
    .then(mod => {
      hapticsModule = mod
      mod.Haptics.impact({ style: mod.ImpactStyle.Light }).catch(() => {})
    })
    .catch(() => {})
}

function rubberBand(raw: number, maxOffset: number): number {
  if (raw <= 0) return 0
  return maxOffset * Math.tanh(raw / maxOffset)
}

function isInsideHorizontalScroller(el: EventTarget | null): boolean {
  let node = el as HTMLElement | null
  while (node) {
    if (node.scrollWidth > node.clientWidth + 1) {
      const style = window.getComputedStyle(node)
      const overflow = style.overflowX
      if (overflow === "auto" || overflow === "scroll") return true
    }
    node = node.parentElement
  }
  return false
}

interface SwipeBackGestureProps {
  children: ReactNode
}

export function SwipeBackGesture({ children }: SwipeBackGestureProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { hasOpen } = useModalRegistry()
  const [offsetX, setOffsetX] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const tracking = useRef(false)
  const startX = useRef(0)
  const startY = useRef(0)
  const startTime = useRef(0)
  const directionLocked = useRef<"horizontal" | "vertical" | null>(null)
  const navigating = useRef(false)
  const hapticFired = useRef(false)
  const navigateRef = useRef(navigate)
  navigateRef.current = navigate

  const enabled = isNativeMobile() && canNavigateBack(location.pathname)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const hasOpenRef = useRef(hasOpen)
  hasOpenRef.current = hasOpen

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const onStart = (e: TouchEvent) => {
      if (!enabledRef.current || navigating.current) return
      if (hasOpenRef.current()) return
      const touch = e.touches[0]
      if (touch.clientX > EDGE_ZONE) return
      if (isInsideHorizontalScroller(e.target)) return
      tracking.current = true
      directionLocked.current = null
      hapticFired.current = false
      startX.current = touch.clientX
      startY.current = touch.clientY
      startTime.current = Date.now()
    }

    const onMove = (e: TouchEvent) => {
      if (!tracking.current) return
      const touch = e.touches[0]
      const dx = touch.clientX - startX.current
      const dy = touch.clientY - startY.current

      if (!directionLocked.current) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return
        directionLocked.current =
          Math.abs(dx) > Math.abs(dy) ? "horizontal" : "vertical"
        if (directionLocked.current === "vertical") {
          tracking.current = false
          return
        }
      }

      e.preventDefault()
      const maxOffset = window.innerWidth * DAMPEN_MAX
      const wouldPass = dx > window.innerWidth * THRESHOLD_RATIO
      if (wouldPass && !hapticFired.current) {
        hapticFired.current = true
        triggerHaptic()
      } else if (!wouldPass && hapticFired.current) {
        hapticFired.current = false
      }
      setOffsetX(rubberBand(dx, maxOffset))
    }

    const onEnd = (e: TouchEvent) => {
      if (!tracking.current) {
        setOffsetX(0)
        return
      }
      tracking.current = false
      const touch = e.changedTouches[0]
      const dx = touch.clientX - startX.current
      const elapsed = (Date.now() - startTime.current) / 1000
      const velocity = elapsed > 0 ? dx / elapsed / window.innerWidth : 0
      const passedThreshold =
        dx > window.innerWidth * THRESHOLD_RATIO || velocity > MIN_VELOCITY

      if (passedThreshold && dx > 0) {
        navigating.current = true
        triggerHaptic()
        setOffsetX(window.innerWidth)
        setTimeout(() => {
          navigateRef.current(-1)
          setOffsetX(0)
          navigating.current = false
        }, 150)
      } else {
        setOffsetX(0)
      }
    }

    el.addEventListener("touchstart", onStart, { passive: true })
    el.addEventListener("touchmove", onMove, { passive: false })
    el.addEventListener("touchend", onEnd, { passive: true })

    return () => {
      el.removeEventListener("touchstart", onStart)
      el.removeEventListener("touchmove", onMove)
      el.removeEventListener("touchend", onEnd)
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="relative"
      style={{ touchAction: "pan-y" }}
    >
      {enabled && offsetX > 0 && (
        <div
          className="fixed inset-0 bg-black pointer-events-none z-[1]"
          style={{
            opacity: Math.min(0.15, (offsetX / window.innerWidth) * 0.2),
          }}
        />
      )}
      <div
        style={{
          transform:
            enabled && offsetX > 0 ? `translateX(${offsetX}px)` : undefined,
          transition:
            enabled && !tracking.current && offsetX > 0
              ? "transform 150ms ease-out"
              : undefined,
          willChange: enabled && tracking.current ? "transform" : undefined,
        }}
      >
        {children}
      </div>
    </div>
  )
}
