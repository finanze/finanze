import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { addDays, format, parseISO, startOfWeek } from "date-fns"
import { ArrowUpRight } from "lucide-react"
import { useI18n } from "@/i18n"
import { Sensitive } from "@/components/ui/Sensitive"
import { cn } from "@/lib/utils"
import type { CashflowPoint } from "@/types/cashflow"
import {
  HEATMAP_LEVELS,
  buildHeatmapWeeks,
  type HeatmapDay,
} from "@/utils/cashflowHeatmap"

const GAP = 3
const MIN_CELL = 12
const MAX_CELL = 26
const WEEKDAY_COLUMN = 16
const INCOME_RGB = "22, 163, 74"
const EXPENSE_RGB = "239, 68, 68"
const LEGEND_LEVELS = Array.from(
  { length: HEATMAP_LEVELS * 2 + 1 },
  (_, index) => index - HEATMAP_LEVELS,
)

const levelColor = (level: number) =>
  level === 0
    ? undefined
    : `rgba(${level > 0 ? INCOME_RGB : EXPENSE_RGB}, ${0.25 + (0.75 * (Math.abs(level) - 1)) / (HEATMAP_LEVELS - 1)})`

interface CashflowHeatmapProps {
  series: CashflowPoint[]
  fromDate: string
  toDate: string
  formatAmount: (value: number) => string
  onOpenDay: (date: string) => void
}

export function CashflowHeatmap({
  series,
  fromDate,
  toDate,
  formatAmount,
  onOpenDay,
}: CashflowHeatmapProps) {
  const { t, locale } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const pointerTypeRef = useRef("mouse")
  const [width, setWidth] = useState(0)
  const [fades, setFades] = useState({ start: false, end: false })
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const weeks = useMemo(
    () => buildHeatmapWeeks(series, fromDate, toDate),
    [series, fromDate, toDate],
  )

  const daysByDate = useMemo(() => {
    const map = new Map<string, HeatmapDay>()
    weeks.forEach(week =>
      week.days.forEach(day => day && map.set(day.date, day)),
    )
    return map
  }, [weeks])

  const cell = width
    ? Math.min(
        MAX_CELL,
        Math.max(
          MIN_CELL,
          Math.floor((width - WEEKDAY_COLUMN - 4) / weeks.length) - GAP,
        ),
      )
    : MIN_CELL

  const fillerWeeks = useMemo(() => {
    if (!width || !toDate) return []
    const columns = Math.floor(
      (width - WEEKDAY_COLUMN - 4 + GAP) / (cell + GAP),
    )
    const lastWeek = startOfWeek(parseISO(toDate), { weekStartsOn: 1 })
    return Array.from(
      { length: Math.max(0, columns - weeks.length) },
      (_, index) => {
        const start = addDays(lastWeek, 7 * (index + 1))
        const monthDay = Array.from({ length: 7 }, (_, day) =>
          addDays(start, day),
        ).find(date => date.getDate() === 1)
        return monthDay ? format(monthDay, "yyyy-MM-dd") : null
      },
    )
  }, [width, cell, toDate, weeks.length])
  const multiYear = fromDate.slice(0, 4) !== toDate.slice(0, 4)
  const today = format(new Date(), "yyyy-MM-dd")

  const weekdayLabels = useMemo(() => {
    const formatter = new Intl.DateTimeFormat(locale, { weekday: "narrow" })
    return Array.from({ length: 7 }, (_, index) =>
      index % 2 === 0 ? formatter.format(new Date(2024, 0, 1 + index)) : "",
    )
  }, [locale])

  const updateFades = () => {
    const element = scrollRef.current
    if (!element) return
    const start = element.scrollLeft > 1
    const end =
      element.scrollLeft + element.clientWidth < element.scrollWidth - 1
    setFades(current =>
      current.start === start && current.end === end ? current : { start, end },
    )
  }

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver(entries =>
      setWidth(entries[0].contentRect.width),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useLayoutEffect(() => {
    const element = scrollRef.current
    if (!element) return
    element.scrollLeft = element.scrollWidth
    updateFades()
  }, [weeks.length, cell])

  useEffect(() => {
    if (!selected) return
    const handlePointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node))
        setSelected(null)
    }
    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [selected])

  const handleDayClick = (day: HeatmapDay, keyboard: boolean) => {
    if (keyboard || pointerTypeRef.current === "mouse") {
      if (day.count > 0) onOpenDay(day.date)
      return
    }
    if (selected === day.date && day.count > 0) {
      onOpenDay(day.date)
      return
    }
    setSelected(day.date)
  }

  const formatLongDate = (date: string) =>
    new Intl.DateTimeFormat(locale, {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(parseISO(date))

  const formatMonth = (date: string) =>
    new Intl.DateTimeFormat(locale, {
      month: "short",
      ...(multiYear && (date === fromDate || date.slice(5, 7) === "01")
        ? { year: "2-digit" as const }
        : {}),
    }).format(parseISO(date))

  const activeDay = daysByDate.get(hovered ?? selected ?? "")

  return (
    <div ref={containerRef} data-testid="cashflow-heatmap">
      <div className="flex" style={{ gap: GAP }}>
        <div
          className="flex shrink-0 flex-col py-1 text-[10px] leading-none text-muted-foreground"
          style={{ gap: GAP, width: WEEKDAY_COLUMN - GAP }}
        >
          <div className="h-4" />
          {weekdayLabels.map((label, index) => (
            <div
              key={index}
              className="flex items-center"
              style={{ height: cell }}
            >
              {label}
            </div>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <div
            ref={scrollRef}
            onScroll={updateFades}
            className="no-scrollbar overflow-x-auto"
          >
            <div className="flex w-fit px-0.5 py-1" style={{ gap: GAP }}>
              {weeks.map((week, weekIndex) => (
                <div
                  key={weekIndex}
                  className="flex shrink-0 flex-col"
                  style={{ gap: GAP, width: cell }}
                >
                  <div className="h-4 overflow-visible whitespace-nowrap text-[10px] leading-4 text-muted-foreground">
                    {week.monthStart && formatMonth(week.monthStart)}
                  </div>
                  {Array.from({ length: 7 }, (_, dayIndex) => {
                    const day = week.days[dayIndex]
                    if (!day || day.date > today) {
                      const upcoming = day !== null
                      return (
                        <div
                          key={dayIndex}
                          data-testid={
                            upcoming ? "heatmap-upcoming-day" : undefined
                          }
                          className={cn(
                            upcoming && "rounded-[3px] border border-border/60",
                          )}
                          style={{ width: cell, height: cell }}
                        />
                      )
                    }
                    const isActive = selected === day.date
                    return (
                      <button
                        key={dayIndex}
                        type="button"
                        data-testid="heatmap-day"
                        data-date={day.date}
                        data-level={day.level}
                        aria-label={formatLongDate(day.date)}
                        aria-pressed={isActive}
                        className={cn(
                          "rounded-[3px] transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          day.level === 0 && "bg-muted",
                          day.count > 0 ? "cursor-pointer" : "cursor-default",
                          day.date === today &&
                            "outline outline-1 outline-offset-1 outline-foreground/60",
                          isActive && "ring-2 ring-primary",
                        )}
                        style={{
                          width: cell,
                          height: cell,
                          backgroundColor: levelColor(day.level),
                        }}
                        onPointerDown={event => {
                          pointerTypeRef.current = event.pointerType
                        }}
                        onPointerEnter={event => {
                          if (event.pointerType === "mouse")
                            setHovered(day.date)
                        }}
                        onPointerLeave={event => {
                          if (event.pointerType === "mouse") setHovered(null)
                        }}
                        onClick={event =>
                          handleDayClick(day, event.detail === 0)
                        }
                      />
                    )
                  })}
                </div>
              ))}
              {fillerWeeks.map((monthStart, index) => (
                <div
                  key={`filler-${index}`}
                  data-testid="heatmap-filler-week"
                  className="flex shrink-0 flex-col"
                  style={{ gap: GAP, width: cell }}
                >
                  <div className="h-4 overflow-visible whitespace-nowrap text-[10px] leading-4 text-muted-foreground/60">
                    {monthStart && formatMonth(monthStart)}
                  </div>
                  {Array.from({ length: 7 }, (_, dayIndex) => (
                    <div
                      key={dayIndex}
                      className="rounded-[3px] border border-border/60"
                      style={{ width: cell, height: cell }}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
          {fades.start && (
            <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-card to-transparent" />
          )}
          {fades.end && (
            <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-card to-transparent" />
          )}
        </div>
      </div>

      <div className="mt-3 flex min-h-[1.75rem] flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <div
          data-testid="heatmap-details"
          className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1"
        >
          {activeDay ? (
            <>
              <span className="font-medium text-foreground">
                {formatLongDate(activeDay.date)}
              </span>
              {activeDay.count === 0 ? (
                <span>{t.cashflow.heatmap.noMovements}</span>
              ) : (
                <>
                  {activeDay.expenses > 0 && (
                    <span className="font-medium tabular-nums text-red-600 dark:text-red-400">
                      <Sensitive>−{formatAmount(activeDay.expenses)}</Sensitive>
                    </span>
                  )}
                  {activeDay.income > 0 && (
                    <span className="font-medium tabular-nums text-green-600 dark:text-green-400">
                      <Sensitive>+{formatAmount(activeDay.income)}</Sensitive>
                    </span>
                  )}
                  <span>
                    {t.cashflow.movementsCount.replace(
                      "{count}",
                      `${activeDay.count}`,
                    )}
                  </span>
                  {!hovered && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 font-medium text-primary"
                      onClick={() => onOpenDay(activeDay.date)}
                    >
                      {t.cashflow.heatmap.view}
                      <ArrowUpRight className="h-3 w-3" />
                    </button>
                  )}
                </>
              )}
            </>
          ) : (
            <span>{t.cashflow.heatmap.hint}</span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <span>{t.cashflow.expenses}</span>
          {LEGEND_LEVELS.map(level => (
            <span
              key={level}
              className={cn(
                "h-2.5 w-2.5 rounded-[2px]",
                level === 0 && "bg-muted",
              )}
              style={{ backgroundColor: levelColor(level) }}
            />
          ))}
          <span>{t.cashflow.income}</span>
        </div>
      </div>
    </div>
  )
}
