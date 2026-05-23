import React, { useMemo, useState, useCallback, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { formatCurrency } from "@/lib/formatters"
import { Sensitive } from "@/components/ui/Sensitive"
import { cn } from "@/lib/utils"
import { shouldInvertIcon } from "@/utils/iconAnalysis"

const RADIAN = Math.PI / 180
const BUBBLE_SIZE = 32
const BUBBLE_OFFSET = 20
const SMALL_SLICE_EXTRA_OFFSET = 44

export interface OrbitBubbleItem {
  name: string
  value: number
  color: string
  percentage: number
  iconUrl?: string | null
  fallbackIconUrl?: string | null
  initials?: string
}

interface DonutOrbitBubblesProps {
  data: OrbitBubbleItem[]
  outerRadius: number
  chartWidth: number
  chartHeight: number
  locale?: string
  currency?: string
  onBubbleClick?: (item: OrbitBubbleItem) => void
  hoveredIndex: number | null
  onHoverIndex: (index: number | null) => void
  minPercentage?: number
  collapsedHidden?: boolean
}

function getInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

export const DonutOrbitBubbles: React.FC<DonutOrbitBubblesProps> = ({
  data,
  outerRadius,
  chartWidth,
  chartHeight,
  locale = "en",
  currency = "USD",
  onBubbleClick,
  hoveredIndex,
  onHoverIndex,
  minPercentage = 2,
  collapsedHidden = false,
}) => {
  const [failedIcons, setFailedIcons] = useState<Set<number>>(new Set())
  const [usingFallback, setUsingFallback] = useState<Set<number>>(new Set())
  const [invertMap, setInvertMap] = useState<Record<number, boolean>>({})
  const imgRefs = useRef<Record<number, HTMLImageElement | null>>({})
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [expandedOffset, setExpandedOffset] = useState(0)

  useEffect(() => {
    const root = document.documentElement
    const update = () => setIsDarkMode(root.classList.contains("dark"))
    update()
    const observer = new MutationObserver(update)
    observer.observe(root, { attributes: true, attributeFilter: ["class"] })
    return () => observer.disconnect()
  }, [])

  const handleIconError = useCallback(
    (index: number) => {
      const bubble = data[index]
      if (bubble?.fallbackIconUrl && !usingFallback.has(index)) {
        setUsingFallback(prev => {
          const next = new Set(prev)
          next.add(index)
          return next
        })
        return
      }
      setFailedIcons(prev => {
        const next = new Set(prev)
        next.add(index)
        return next
      })
    },
    [data, usingFallback],
  )

  const handleIconLoad = useCallback(
    (index: number, img: HTMLImageElement) => {
      imgRefs.current[index] = img
      if (img.naturalWidth <= 1 || img.naturalHeight <= 1) {
        handleIconError(index)
        return
      }
      setInvertMap(prev => ({
        ...prev,
        [index]: shouldInvertIcon(img, isDarkMode),
      }))
    },
    [isDarkMode, handleIconError],
  )

  useEffect(() => {
    const next: Record<number, boolean> = {}
    let changed = false
    for (const [key, img] of Object.entries(imgRefs.current)) {
      if (!img) continue
      const idx = Number(key)
      const val = shouldInvertIcon(img, isDarkMode)
      next[idx] = val
      if (invertMap[idx] !== val) changed = true
    }
    if (changed) setInvertMap(prev => ({ ...prev, ...next }))
  }, [isDarkMode])

  useEffect(() => {
    setExpandedOffset(0)
  }, [hoveredIndex])

  const expandedRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return
    setTimeout(() => {
      const rect = node.getBoundingClientRect()
      const margin = 8
      let offset = 0
      if (rect.right > window.innerWidth - margin) {
        offset = window.innerWidth - margin - rect.right
      } else if (rect.left < margin) {
        offset = margin - rect.left
      }
      if (offset !== 0) setExpandedOffset(offset)
    }, 120)
  }, [])

  const bubbles = useMemo(() => {
    const cx = chartWidth / 2
    const cy = chartHeight / 2

    const n = data.length
    const paddingAngle = n > 1 ? 1 : 0
    const totalPadding = n * paddingAngle
    const availableDegrees = 360 - totalPadding

    let accumulated = 0
    return data.map((item, index) => {
      const sweep = (item.percentage / 100) * availableDegrees
      const midAngle = accumulated + paddingAngle / 2 + sweep / 2
      accumulated += sweep + paddingAngle

      const isBelowMin = item.percentage < minPercentage
      const r =
        outerRadius +
        BUBBLE_OFFSET +
        (isBelowMin ? SMALL_SLICE_EXTRA_OFFSET : 0)
      const angleRad = midAngle * RADIAN
      const x = cx + r * Math.cos(angleRad)
      const y = cy - r * Math.sin(angleRad)
      const isRightSide = x > cx

      return { ...item, x, y, index, isBelowMin, isRightSide }
    })
  }, [data, outerRadius, chartWidth, chartHeight, minPercentage])

  if (bubbles.length === 0) return null

  const renderIcon = (
    bubble: (typeof bubbles)[number],
    size: string,
    textClass: string,
  ) => {
    const isFallback = usingFallback.has(bubble.index)
    const iconSrc = isFallback ? bubble.fallbackIconUrl : bubble.iconUrl
    const hasValidIcon = iconSrc && !failedIcons.has(bubble.index)
    if (hasValidIcon) {
      return (
        <img
          key={isFallback ? "fb" : "primary"}
          src={iconSrc!}
          alt=""
          draggable={false}
          className={cn(
            size,
            "rounded-full object-contain shrink-0 pointer-events-none select-none",
            invertMap[bubble.index] && "invert",
          )}
          style={
            {
              WebkitUserSelect: "none",
              WebkitTouchCallout: "none",
            } as React.CSSProperties
          }
          onLoad={e => handleIconLoad(bubble.index, e.currentTarget)}
          onError={() => handleIconError(bubble.index)}
        />
      )
    }
    return (
      <span
        className={cn(
          "rounded-full flex items-center justify-center shrink-0 font-bold pointer-events-none select-none",
          size,
          textClass,
        )}
        style={
          {
            backgroundColor: bubble.color,
            WebkitUserSelect: "none",
            WebkitTouchCallout: "none",
          } as React.CSSProperties
        }
      >
        {!collapsedHidden && (bubble.initials || getInitials(bubble.name))}
      </span>
    )
  }

  return (
    <div
      className={cn(
        "absolute inset-0 pointer-events-none",
        hoveredIndex !== null ? "z-20" : "z-[5]",
      )}
    >
      <AnimatePresence>
        {bubbles.map(bubble => {
          const isHovered = hoveredIndex === bubble.index
          const isFaded = hoveredIndex !== null && !isHovered
          const isHidden = (bubble.isBelowMin || collapsedHidden) && !isHovered

          if (isHidden) return null

          return (
            <motion.div
              key={bubble.index}
              className="absolute pointer-events-auto"
              style={{
                left: bubble.x,
                top: bubble.y,
                zIndex: isHovered ? 30 : 10,
              }}
              initial={{
                opacity: 0,
                scale: bubble.isBelowMin ? 0.9 : 0.5,
                x: "-50%",
                y: "-50%",
              }}
              animate={{
                opacity: isFaded ? 0.35 : 1,
                scale: 1,
                x: "-50%",
                y: "-50%",
              }}
              exit={{
                opacity: 0,
                scale: bubble.isBelowMin ? 0.9 : 0.5,
                x: "-50%",
                y: "-50%",
              }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              onMouseEnter={() => onHoverIndex(bubble.index)}
              onMouseLeave={() => onHoverIndex(null)}
              onClick={() => onBubbleClick?.(bubble)}
            >
              <AnimatePresence mode="wait" initial={false}>
                {isHovered ? (
                  <motion.div
                    key="expanded"
                    ref={expandedRef}
                    className={cn(
                      "cursor-pointer select-none shadow-lg w-max",
                      "flex items-center gap-2 px-3 py-2",
                      "bg-popover border border-border rounded-xl",
                      bubble.isRightSide && "flex-row-reverse",
                    )}
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1, x: expandedOffset }}
                    exit={{ opacity: 0, scale: 0.85 }}
                    transition={{ duration: 0.1 }}
                  >
                    {renderIcon(bubble, "h-6 w-6", "text-[11px] text-white")}
                    <div className="flex flex-col leading-tight">
                      <span className="text-xs font-semibold text-popover-foreground max-w-[200px]">
                        {bubble.name}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        <Sensitive>
                          {bubble.percentage.toFixed(1)}% ·{" "}
                          {formatCurrency(bubble.value, locale, currency)}
                        </Sensitive>
                      </span>
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key="collapsed"
                    className={cn(
                      "cursor-pointer select-none border border-border shadow-sm rounded-full",
                      "flex items-center justify-center bg-popover",
                    )}
                    style={{
                      width: BUBBLE_SIZE,
                      height: BUBBLE_SIZE,
                    }}
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.85 }}
                    transition={{ duration: 0.1 }}
                  >
                    {renderIcon(bubble, "h-6 w-6", "text-[10px] text-white")}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
