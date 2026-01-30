import {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
  useLayoutEffect,
  type PointerEvent as ReactPointerEvent,
} from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import {
  LayoutDashboard,
  TrendingUp,
  ArrowLeftRight,
  Calculator,
  CalendarCog,
  Blocks,
  Settings,
  FileUp,
  MoreVertical,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"
import { useLayoutScroll } from "@/context/LayoutScrollContext"
import { useBackupAlert } from "@/context/BackupAlertContext"
import { createPortal } from "react-dom"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Button } from "@/components/ui/Button"

const PILL_HEIGHT = 48
const PILL_HEIGHT_COLLAPSED = 30
const INDICATOR_INSET = 2
const COLLAPSE_DURATION = 0.18
const DOT_SIZE = 6
const DOT_GAP = 5
const TAB_SIZE = 40
const TAB_GAP = 6
const EXPANDED_INSET = 8
const COLLAPSED_INSET = 12
const LONG_PRESS_DELAY = 450
const LONG_PRESS_MOVE_TOLERANCE = 8

type NavItem =
  | {
      kind: "route"
      key: string
      path: string
      label: string
      icon: React.ReactNode
    }
  | {
      kind: "more"
      key: string
      label: string
      icon: React.ReactNode
    }

export function FloatingBottomNav() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const { scrolling, atTop, atBottom } = useLayoutScroll()
  const { alertColor } = useBackupAlert()

  const [collapsed, setCollapsed] = useState(false)
  const [disableIndicatorAnim, setDisableIndicatorAnim] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [pressTip, setPressTip] = useState<{
    open: boolean
    label: string
    x: number
    y: number
  }>({ open: false, label: "", x: 0, y: 0 })
  const [navScale, setNavScale] = useState(1)

  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pressStartRef = useRef<{ x: number; y: number } | null>(null)
  const isPressingRef = useRef(false)
  const didLongPressRef = useRef(false)

  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }, [])

  const hidePressTip = useCallback(() => {
    setPressTip(prev => (prev.open ? { ...prev, open: false } : prev))
  }, [])

  const cancelPress = useCallback(() => {
    isPressingRef.current = false
    pressStartRef.current = null
    clearLongPressTimer()
    hidePressTip()
  }, [clearLongPressTimer, hidePressTip])

  const handleTabPointerDown = useCallback(
    (label: string) => (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (collapsed) return

      if (event.pointerType === "mouse" && event.button !== 0) return

      didLongPressRef.current = false
      isPressingRef.current = true
      pressStartRef.current = { x: event.clientX, y: event.clientY }
      clearLongPressTimer()

      const target = event.currentTarget
      longPressTimerRef.current = setTimeout(() => {
        if (!isPressingRef.current) return

        const rect = target.getBoundingClientRect()
        didLongPressRef.current = true
        setPressTip({
          open: true,
          label,
          x: rect.left + rect.width / 2,
          y: rect.top - 6,
        })
      }, LONG_PRESS_DELAY)
    },
    [clearLongPressTimer, collapsed],
  )

  const handleTabPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!isPressingRef.current) return
      const start = pressStartRef.current
      if (!start) return

      const dx = event.clientX - start.x
      const dy = event.clientY - start.y
      if (Math.hypot(dx, dy) > LONG_PRESS_MOVE_TOLERANCE) {
        cancelPress()
      }
    },
    [cancelPress],
  )

  useEffect(() => {
    setIndicatorReady(false)
    if (!collapsed) {
      setDisableIndicatorAnim(true)
    }
    if (collapsed) {
      setMoreOpen(false)
    }
  }, [collapsed])

  useEffect(() => {
    if (scrolling) setCollapsed(true)
  }, [scrolling])

  useEffect(() => {
    if (!scrolling && (atTop || atBottom)) setCollapsed(false)
  }, [atBottom, atTop, scrolling])

  useEffect(() => {
    cancelPress()
  }, [cancelPress, location.pathname, collapsed, scrolling, moreOpen])

  useEffect(() => {
    const updateScale = () => {
      if (typeof window === "undefined") return
      const width = window.innerWidth
      const nextScale = width < 335 ? 0.86 : width < 375 ? 0.92 : 1
      setNavScale(prev => (prev === nextScale ? prev : nextScale))
    }
    updateScale()
    window.addEventListener("resize", updateScale)
    return () => window.removeEventListener("resize", updateScale)
  }, [])

  const navItems: NavItem[] = useMemo(
    () => [
      {
        kind: "route",
        key: "dashboard",
        path: "/",
        label: t.common.dashboard,
        icon: <LayoutDashboard size={22} />,
      },
      {
        kind: "route",
        key: "investments",
        path: "/investments",
        label: t.common.investments,
        icon: <TrendingUp size={22} />,
      },
      {
        kind: "route",
        key: "transactions",
        path: "/transactions",
        label: t.common.transactions,
        icon: <ArrowLeftRight size={22} />,
      },
      {
        kind: "route",
        key: "calculations",
        path: "/calculations",
        label: t.calculations.title,
        icon: <Calculator size={22} />,
      },
      {
        kind: "route",
        key: "management",
        path: "/management",
        label: t.management.title,
        icon: <CalendarCog size={22} />,
      },
      {
        kind: "route",
        key: "integrations",
        path: "/entities",
        label: t.entities.title,
        icon: <Blocks size={22} />,
      },
      {
        kind: "more",
        key: "more",
        label: t.common.more ?? "More",
        icon: <MoreVertical size={22} />,
      },
    ],
    [t],
  )

  const getActiveIndex = useCallback(() => {
    const exactMatch = navItems.findIndex(item => {
      if (item.kind !== "route") return false
      return item.path === location.pathname
    })
    if (exactMatch !== -1) return exactMatch

    const prefixMatch = navItems.findIndex(item => {
      if (item.kind !== "route") return false
      return item.path !== "/" && location.pathname.startsWith(item.path)
    })
    if (prefixMatch !== -1) return prefixMatch

    const investmentsIndex = navItems.findIndex(
      item => item.kind === "route" && item.path === "/investments",
    )
    const investmentPrefixes = ["/banking", "/investments", "/real-estate"]
    if (
      investmentsIndex !== -1 &&
      investmentPrefixes.some(prefix => location.pathname.startsWith(prefix))
    ) {
      return investmentsIndex
    }

    const moreIndex = navItems.findIndex(item => item.kind === "more")
    if (moreIndex !== -1) {
      if (
        location.pathname.startsWith("/settings") ||
        location.pathname.startsWith("/export")
      ) {
        return moreIndex
      }
    }

    return moreIndex !== -1 ? moreIndex : 0
  }, [navItems, location.pathname])

  const activeIndex = getActiveIndex()

  const tabsContainerRef = useRef<HTMLDivElement>(null)
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [indicatorStyle, setIndicatorStyle] = useState({ x: 0, width: 0 })
  const [indicatorReady, setIndicatorReady] = useState(false)

  const measureAndUpdateIndicator = useCallback(() => {
    const container = tabsContainerRef.current
    const button = buttonRefs.current[activeIndex]
    if (!container || !button) return

    const activeItem = navItems[activeIndex]
    if (!activeItem) return

    const bubble = PILL_HEIGHT - INDICATOR_INSET * 2

    const centerX = button.offsetLeft + button.offsetWidth / 2
    const unclampedX = centerX - bubble / 2
    const maxX = Math.max(0, container.clientWidth - bubble)
    const x = Math.min(Math.max(0, unclampedX), maxX)

    setIndicatorStyle(prev => {
      if (prev.x === x && prev.width === bubble) return prev
      return { x, width: bubble }
    })

    setIndicatorReady(true)
  }, [activeIndex, navItems, navScale])

  useLayoutEffect(() => {
    if (!collapsed) {
      measureAndUpdateIndicator()
      requestAnimationFrame(() => setDisableIndicatorAnim(false))
    }
  }, [collapsed, activeIndex, measureAndUpdateIndicator])

  useLayoutEffect(() => {
    if (!collapsed) {
      measureAndUpdateIndicator()
    }
  }, [collapsed, navScale, measureAndUpdateIndicator])

  const handlePillPress = () => {
    if (collapsed) {
      setCollapsed(false)
    }
  }

  const handleNavigation = (path: string) => {
    if (collapsed) return
    if (didLongPressRef.current) {
      didLongPressRef.current = false
      return
    }
    navigate(path)
  }

  const collapsedDotsWidth =
    navItems.length * DOT_SIZE + (navItems.length - 1) * DOT_GAP

  const pillWidth = collapsed
    ? Math.max(PILL_HEIGHT_COLLAPSED, COLLAPSED_INSET * 2 + collapsedDotsWidth)
    : EXPANDED_INSET * 2 +
      navItems.length * TAB_SIZE +
      (navItems.length - 1) * TAB_GAP

  const content = (
    <div className="fixed bottom-0 left-0 right-0 flex justify-center pointer-events-none z-50 select-none pb-[max(12px,var(--safe-area-inset-bottom,0px))] sm:pb-[max(16px,var(--safe-area-inset-bottom,0px))]">
      <motion.div
        className="pointer-events-auto"
        onClick={handlePillPress}
        style={{ cursor: collapsed ? "pointer" : "default", scale: navScale }}
      >
        <motion.div
          className={cn(
            "relative flex items-center justify-center overflow-hidden",
            "rounded-full border border-gray-200 dark:border-gray-800",
            "bg-gray-100 dark:bg-gray-950",
            "shadow-lg",
          )}
          animate={{
            width: pillWidth,
            height: collapsed ? PILL_HEIGHT_COLLAPSED : PILL_HEIGHT,
          }}
          transition={{ duration: COLLAPSE_DURATION, ease: "easeInOut" }}
        >
          <AnimatePresence mode="wait">
            {collapsed ? (
              <motion.div
                key="dots"
                className="absolute inset-0 flex items-center justify-center gap-1.5 px-3"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ duration: COLLAPSE_DURATION }}
              >
                {navItems.map((_, index) => (
                  <div
                    key={index}
                    className={cn(
                      "rounded-full transition-colors shrink-0",
                      index === activeIndex
                        ? "bg-gray-900 dark:bg-gray-100"
                        : "bg-gray-400 dark:bg-gray-600",
                    )}
                    style={{
                      width: DOT_SIZE,
                      height: DOT_SIZE,
                      borderRadius: 9999,
                    }}
                  />
                ))}
              </motion.div>
            ) : (
              <motion.div
                key="tabs"
                ref={tabsContainerRef}
                className="relative flex items-center gap-1.5 px-2"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ duration: COLLAPSE_DURATION }}
                onAnimationComplete={measureAndUpdateIndicator}
              >
                {indicatorReady ? (
                  <motion.div
                    initial={false}
                    className={cn(
                      "absolute rounded-full",
                      "bg-gray-200 dark:bg-gray-800",
                      "border border-gray-300 dark:border-gray-700",
                    )}
                    style={{
                      top: INDICATOR_INSET,
                      bottom: INDICATOR_INSET,
                      left: 0,
                    }}
                    animate={{
                      x: indicatorStyle.x,
                      width: indicatorStyle.width,
                    }}
                    transition={
                      disableIndicatorAnim
                        ? { duration: 0 }
                        : {
                            type: "spring",
                            damping: 18,
                            stiffness: 200,
                            mass: 0.8,
                          }
                    }
                  />
                ) : null}
                {navItems.map((item, index) =>
                  item.kind === "more" ? (
                    <Popover
                      key={item.key}
                      open={moreOpen}
                      onOpenChange={setMoreOpen}
                    >
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          ref={el => {
                            buttonRefs.current[index] = el
                          }}
                          onPointerDown={handleTabPointerDown(item.label)}
                          onPointerMove={handleTabPointerMove}
                          onPointerUp={cancelPress}
                          onPointerCancel={cancelPress}
                          onPointerLeave={cancelPress}
                          onClick={event => {
                            if (!didLongPressRef.current) return
                            didLongPressRef.current = false
                            event.preventDefault()
                            event.stopPropagation()
                          }}
                          className={cn(
                            "relative z-10 flex items-center justify-center",
                            "w-10 h-10 rounded-full",
                            "transition-colors",
                            index === activeIndex
                              ? "text-gray-900 dark:text-gray-100"
                              : "text-gray-500 dark:text-gray-400",
                            "focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0",
                          )}
                          aria-label={item.label}
                          aria-current={
                            index === activeIndex ? "page" : undefined
                          }
                        >
                          {item.icon}
                          {alertColor && (
                            <span
                              className={cn(
                                "absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full",
                                alertColor === "dark-red"
                                  ? "bg-red-700"
                                  : alertColor === "red"
                                    ? "bg-red-500"
                                    : "bg-amber-500",
                              )}
                            />
                          )}
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        side="top"
                        align="end"
                        sideOffset={6}
                        className={cn(
                          "p-0.5 w-max select-none rounded-xl",
                          "relative more-popover",
                          "after:content-[''] after:absolute after:-bottom-[7px] after:right-3 after:h-4 after:w-4 after:rotate-45 after:scale-y-73 after:rounded-[4px] after:bg-popover after:border after:border-border after:border-t-0 after:border-l-0",
                        )}
                      >
                        <div className="relative z-20 flex flex-col gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="justify-start select-none focus-visible:ring-0 focus-visible:ring-offset-0 rounded-lg"
                            tabIndex={-1}
                            onMouseDown={event => event.preventDefault()}
                            onClick={() => {
                              setMoreOpen(false)
                              navigate("/settings")
                            }}
                          >
                            <Settings size={16} className="mr-2" />
                            {t.common.settings}
                            {alertColor && (
                              <span
                                className={cn(
                                  "ml-2 inline-block h-1.5 w-1.5 rounded-full",
                                  alertColor === "dark-red"
                                    ? "bg-red-700"
                                    : alertColor === "red"
                                      ? "bg-red-500"
                                      : "bg-amber-500",
                                )}
                              />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="justify-start select-none focus-visible:ring-0 focus-visible:ring-offset-0 rounded-lg"
                            tabIndex={-1}
                            onMouseDown={event => event.preventDefault()}
                            onClick={() => {
                              setMoreOpen(false)
                              navigate("/export")
                            }}
                          >
                            <FileUp size={16} className="mr-2" />
                            {t.export.title}
                          </Button>
                        </div>
                      </PopoverContent>
                    </Popover>
                  ) : (
                    <button
                      key={item.key}
                      type="button"
                      ref={el => {
                        buttonRefs.current[index] = el
                      }}
                      onClick={() => handleNavigation(item.path)}
                      onPointerDown={handleTabPointerDown(item.label)}
                      onPointerMove={handleTabPointerMove}
                      onPointerUp={cancelPress}
                      onPointerCancel={cancelPress}
                      onPointerLeave={cancelPress}
                      className={cn(
                        "relative z-10 flex items-center justify-center",
                        "w-10 h-10 rounded-full",
                        "transition-colors",
                        "focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0",
                        index === activeIndex
                          ? "text-gray-900 dark:text-gray-100"
                          : "text-gray-500 dark:text-gray-400",
                      )}
                      aria-label={item.label}
                      aria-current={index === activeIndex ? "page" : undefined}
                    >
                      {item.icon}
                    </button>
                  ),
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </motion.div>

      {pressTip.open ? (
        <div
          className="fixed z-[999999] pointer-events-none"
          style={{ left: pressTip.x, top: pressTip.y }}
        >
          <div className="rounded-md px-2 py-1 text-xs shadow-md bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 -translate-x-1/2 -translate-y-full">
            {pressTip.label}
          </div>
        </div>
      ) : null}
    </div>
  )

  if (typeof document === "undefined") {
    return content
  }

  return createPortal(content, document.body)
}
