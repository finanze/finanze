import { useCallback, useEffect, useRef } from "react"
import { useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export interface PageTab<K extends string> {
  key: K
  label: string
  Icon?: LucideIcon
  count?: number | null
}

interface PageTabsProps<K extends string> {
  tabs: PageTab<K>[]
  active: K
  onChange: (key: K) => void
  layoutId: string
  className?: string
}

export function useTabSearchParam<K extends string>(
  keys: readonly K[],
  fallback: K,
): [K, (next: K) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get("tab") as K | null
  const tab = raw && keys.includes(raw) ? raw : fallback

  const setTab = useCallback(
    (next: K) => {
      setSearchParams(
        params => {
          params.set("tab", next)
          return params
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  return [tab, setTab]
}

export function PageTabs<K extends string>({
  tabs,
  active,
  onChange,
  layoutId,
  className,
}: PageTabsProps<K>) {
  const navRef = useRef<HTMLElement>(null)
  const activeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const nav = navRef.current
    const button = activeRef.current
    if (!nav || !button || nav.scrollWidth <= nav.clientWidth) return
    const pad = parseFloat(getComputedStyle(nav).paddingLeft) || 0
    const left = button.offsetLeft - nav.offsetLeft - pad
    const right = button.offsetLeft - nav.offsetLeft + button.offsetWidth + pad
    if (left < nav.scrollLeft) {
      nav.scrollTo({ left, behavior: "smooth" })
    } else if (right > nav.scrollLeft + nav.clientWidth) {
      nav.scrollTo({ left: right - nav.clientWidth, behavior: "smooth" })
    }
  }, [active])

  return (
    <nav
      ref={navRef}
      className={cn(
        "no-scrollbar -mx-6 flex touch-pan-x gap-5 overflow-x-auto overflow-y-hidden border-b border-border px-6 sm:gap-6 md:mx-0 md:px-0",
        className,
      )}
      role="tablist"
    >
      {tabs.map(({ key, label, Icon, count }) => {
        const selected = active === key
        return (
          <button
            key={key}
            ref={selected ? activeRef : undefined}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(key)}
            className={cn(
              "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap pb-3 pt-1 text-sm font-medium transition-colors sm:gap-2",
              selected
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {Icon && <Icon className="h-4 w-4 shrink-0" />}
            <span>{label}</span>
            {count != null && (
              <span
                className={cn(
                  "shrink-0 rounded-full px-1.5 text-[11px] tabular-nums transition-colors",
                  selected
                    ? "bg-foreground text-background"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {count}
              </span>
            )}
            {selected && (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-foreground"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
          </button>
        )
      })}
    </nav>
  )
}
