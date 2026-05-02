import type React from "react"
import { useRef, useState, useEffect } from "react"
import { Sidebar } from "./Sidebar"
import { FloatingBottomNav } from "./FloatingBottomNav"
import { Toast } from "@/components/ui/Toast"
import { useAppContext } from "@/context/AppContext"
import { motion, AnimatePresence } from "framer-motion"
import { PlatformType } from "@/types"
import { useI18n } from "@/i18n"
import { useLocation, useNavigate } from "react-router-dom"
import {
  getPlatformType,
  isAndroid,
  isNativeMobile,
  isPWAStandalone,
} from "@/lib/platform"
import { StatusBarBlur } from "./StatusBarBlur"
import {
  LayoutScrollProvider,
  useLayoutScroll,
} from "@/context/LayoutScrollContext"
import { cn } from "@/lib/utils"
import { SwipeBackGesture } from "./SwipeBackGesture"
import { useModalRegistry } from "@/context/ModalRegistryContext"
import { canNavigateBack } from "@/lib/mobile/backNavigation"

interface LayoutProps {
  children: React.ReactNode
}

const NARROW_BREAKPOINT = 768

function BackButtonHandler() {
  const navigate = useNavigate()
  const location = useLocation()
  const { dismissTop, hasOpen } = useModalRegistry()
  const pathnameRef = useRef(location.pathname)
  pathnameRef.current = location.pathname
  const navigateRef = useRef(navigate)
  navigateRef.current = navigate
  const dismissTopRef = useRef(dismissTop)
  dismissTopRef.current = dismissTop
  const hasOpenRef = useRef(hasOpen)
  hasOpenRef.current = hasOpen

  useEffect(() => {
    if (!isAndroid()) return

    let cleanup: (() => void) | undefined
    let mounted = true

    import("@capacitor/app").then(({ App }) => {
      if (!mounted) return

      const listener = App.addListener("backButton", () => {
        if (hasOpenRef.current()) {
          dismissTopRef.current()
          return
        }
        if (canNavigateBack(pathnameRef.current)) {
          navigateRef.current(-1)
          return
        }
        App.minimizeApp()
      })

      cleanup = () => {
        listener.then(l => l.remove())
      }
    })

    return () => {
      mounted = false
      cleanup?.()
    }
  }, [])

  return null
}

function LayoutContent({ children }: LayoutProps) {
  const { toast, hideToast } = useAppContext()
  const { t } = useI18n()
  const location = useLocation()
  const prevPathnameRef = useRef(location.pathname)
  const platform = getPlatformType()
  const { handleScroll, resetScroll } = useLayoutScroll()
  const isMobilePlatform = isNativeMobile()
  const isMobileViewport = isMobilePlatform || isPWAStandalone()

  const [isNarrowView, setIsNarrowView] = useState(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth < NARROW_BREAKPOINT
    }
    return false
  })

  useEffect(() => {
    const handleResize = () => {
      if (typeof window === "undefined") return
      setIsNarrowView(window.innerWidth < NARROW_BREAKPOINT)
    }
    handleResize()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  const isRouteChange = prevPathnameRef.current !== location.pathname
  if (isRouteChange) {
    prevPathnameRef.current = location.pathname
    resetScroll()
  }

  return (
    <>
      <BackButtonHandler />
      <div className="flex h-screen h-[100svh] min-h-0 overflow-hidden bg-gray-50 dark:bg-black text-gray-900 dark:text-gray-100">
        {!isNarrowView && <Sidebar />}
        <main
          className={cn(
            "flex-1 min-h-0 overflow-auto",
            isMobileViewport && "pt-[max(12px,var(--safe-area-inset-top,0px))]",
            (platform === PlatformType.WINDOWS ||
              platform === PlatformType.LINUX) &&
              "pt-4",
          )}
          onScroll={isNarrowView ? handleScroll : undefined}
        >
          <SwipeBackGesture>
            <motion.div
              key={location.pathname}
              initial={isRouteChange ? { opacity: 0, y: 10 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn(
                "min-h-full",
                isMobileViewport ? "px-6" : "p-6",
                isNarrowView
                  ? "pb-[calc(64px+max(12px,var(--safe-area-inset-bottom,0px)))] sm:pb-[calc(64px+max(16px,var(--safe-area-inset-bottom,0px)))]"
                  : "pb-[max(1.5rem,var(--safe-area-inset-bottom,0px))]",
              )}
            >
              {children}
            </motion.div>
          </SwipeBackGesture>
        </main>
        {isNarrowView && <FloatingBottomNav />}
        {isNarrowView && <StatusBarBlur />}
      </div>

      <AnimatePresence>
        {toast && (
          <Toast
            isAnimating
            variant={
              toast.type === "error"
                ? "error"
                : toast.type === "warning"
                  ? "warning"
                  : "success"
            }
            bottomOffsetClassName={
              isNarrowView
                ? "bottom-[calc(64px+max(12px,var(--safe-area-inset-bottom,0px)))]"
                : undefined
            }
            onClose={hideToast}
          >
            <div className="font-medium">
              {toast.type === "success"
                ? t.toast.success
                : toast.type === "warning"
                  ? t.toast.warning
                  : t.toast.error}
            </div>
            <div className="text-sm mt-1">{toast.message}</div>
          </Toast>
        )}
      </AnimatePresence>
    </>
  )
}

export function Layout({ children }: LayoutProps) {
  return (
    <LayoutScrollProvider>
      <LayoutContent>{children}</LayoutContent>
    </LayoutScrollProvider>
  )
}
