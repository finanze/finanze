import React, { useMemo, useState, useEffect, useRef, ReactNode } from "react"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ChevronLeft, ChevronRight } from "lucide-react"

const formatDateKey = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export interface CalendarDay<T> {
  date: Date
  dateKey: string
  items: T[]
  isCurrentMonth: boolean
  isToday: boolean
  isPast: boolean
}

export interface BaseCalendarProps<T> {
  items: T[]
  getItemDateKey: (item: T) => string
  currentMonth: number
  currentYear: number
  onMonthChange: (month: number, year: number) => void
  loading?: boolean
  renderDayContent: (day: CalendarDay<T>, isMobile: boolean) => ReactNode
  onDayClick?: (day: CalendarDay<T>, index: number) => void
  onCalendarDaysChange?: (days: CalendarDay<T>[]) => void
  disablePastNavigation?: boolean
  minYear?: number
  maxYear?: number
  showTodayButton?: boolean
  todayButtonLabel?: string
}

export function BaseCalendar<T>({
  items,
  getItemDateKey,
  currentMonth,
  currentYear,
  onMonthChange,
  loading = false,
  renderDayContent,
  onDayClick,
  onCalendarDaysChange,
  disablePastNavigation = false,
  minYear,
  maxYear,
  showTodayButton = true,
  todayButtonLabel,
}: BaseCalendarProps<T>) {
  const { t, locale } = useI18n()
  const [showYearPicker, setShowYearPicker] = useState(false)

  const today = useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  const currentYearNow = today.getFullYear()
  const currentMonthNow = today.getMonth()

  const itemsByDate = useMemo(() => {
    const map = new Map<string, T[]>()
    items.forEach(item => {
      const dateKey = getItemDateKey(item)
      if (!map.has(dateKey)) {
        map.set(dateKey, [])
      }
      map.get(dateKey)!.push(item)
    })
    return map
  }, [items, getItemDateKey])

  const calendarDays = useMemo((): CalendarDay<T>[] => {
    const days: CalendarDay<T>[] = []
    const firstDayOfMonth = new Date(currentYear, currentMonth, 1)
    const lastDayOfMonth = new Date(currentYear, currentMonth + 1, 0)

    let startDay = firstDayOfMonth.getDay()
    startDay = startDay === 0 ? 6 : startDay - 1

    const prevMonthLastDay = new Date(currentYear, currentMonth, 0)
    for (let i = startDay - 1; i >= 0; i--) {
      const date = new Date(
        currentYear,
        currentMonth - 1,
        prevMonthLastDay.getDate() - i,
      )
      date.setHours(0, 0, 0, 0)
      const dateKey = formatDateKey(date)
      days.push({
        date,
        dateKey,
        items: itemsByDate.get(dateKey) || [],
        isCurrentMonth: false,
        isToday: date.getTime() === today.getTime(),
        isPast: date.getTime() < today.getTime(),
      })
    }

    for (let day = 1; day <= lastDayOfMonth.getDate(); day++) {
      const date = new Date(currentYear, currentMonth, day)
      date.setHours(0, 0, 0, 0)
      const dateKey = formatDateKey(date)
      days.push({
        date,
        dateKey,
        items: itemsByDate.get(dateKey) || [],
        isCurrentMonth: true,
        isToday: date.getTime() === today.getTime(),
        isPast: date.getTime() < today.getTime(),
      })
    }

    const remainingDays = 42 - days.length
    for (let day = 1; day <= remainingDays; day++) {
      const date = new Date(currentYear, currentMonth + 1, day)
      date.setHours(0, 0, 0, 0)
      const dateKey = formatDateKey(date)
      days.push({
        date,
        dateKey,
        items: itemsByDate.get(dateKey) || [],
        isCurrentMonth: false,
        isToday: date.getTime() === today.getTime(),
        isPast: date.getTime() < today.getTime(),
      })
    }

    return days
  }, [currentYear, currentMonth, itemsByDate, today])

  const lastEmittedDaysRef = useRef<CalendarDay<T>[] | null>(null)

  useEffect(() => {
    // Only emit if the calendar days have actually changed (by comparing stringified keys)
    const currentKey = `${currentYear}-${currentMonth}-${items.length}`
    const lastKey = lastEmittedDaysRef.current
      ? `${lastEmittedDaysRef.current[0]?.date.getFullYear()}-${lastEmittedDaysRef.current[0]?.date.getMonth()}-${items.length}`
      : null

    if (currentKey !== lastKey) {
      lastEmittedDaysRef.current = calendarDays
      onCalendarDaysChange?.(calendarDays)
    }
  }, [
    calendarDays,
    onCalendarDaysChange,
    currentYear,
    currentMonth,
    items.length,
  ])

  const canNavigatePrevMonth = useMemo(() => {
    if (!disablePastNavigation) return true
    if (currentYear > currentYearNow) return true
    if (currentYear === currentYearNow && currentMonth > currentMonthNow)
      return true
    return false
  }, [
    disablePastNavigation,
    currentYear,
    currentMonth,
    currentYearNow,
    currentMonthNow,
  ])

  const handlePrevMonth = () => {
    if (!canNavigatePrevMonth) return
    if (currentMonth === 0) {
      onMonthChange(11, currentYear - 1)
    } else {
      onMonthChange(currentMonth - 1, currentYear)
    }
  }

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      onMonthChange(0, currentYear + 1)
    } else {
      onMonthChange(currentMonth + 1, currentYear)
    }
  }

  const handleToday = () => {
    onMonthChange(currentMonthNow, currentYearNow)
  }

  const handleYearSelect = (year: number) => {
    if (disablePastNavigation && year < currentYearNow) {
      onMonthChange(currentMonthNow, currentYearNow)
    } else if (
      disablePastNavigation &&
      year === currentYearNow &&
      currentMonth < currentMonthNow
    ) {
      onMonthChange(currentMonthNow, year)
    } else {
      onMonthChange(currentMonth, year)
    }
    setShowYearPicker(false)
  }

  const yearOptions = useMemo(() => {
    const years: number[] = []
    const startYear = minYear ?? currentYearNow - 10
    const endYear = maxYear ?? currentYearNow + 5
    for (let y = startYear; y <= endYear; y++) {
      if (!disablePastNavigation || y >= currentYearNow) {
        years.push(y)
      }
    }
    return years
  }, [minYear, maxYear, currentYearNow, disablePastNavigation])

  const monthName = new Date(currentYear, currentMonth).toLocaleDateString(
    locale,
    { month: "long" },
  )

  const shortMonthName = new Date(currentYear, currentMonth).toLocaleDateString(
    locale,
    { month: "short" },
  )

  const weekdayLabels = useMemo(() => {
    const labels: { short: string; letter: string }[] = []
    const baseDate = new Date(2024, 0, 1)
    while (baseDate.getDay() !== 1) {
      baseDate.setDate(baseDate.getDate() + 1)
    }
    for (let i = 0; i < 7; i++) {
      const short = baseDate.toLocaleDateString(locale, { weekday: "short" })
      const narrow = baseDate.toLocaleDateString(locale, { weekday: "narrow" })
      labels.push({ short, letter: narrow })
      baseDate.setDate(baseDate.getDate() + 1)
    }
    return labels
  }, [locale])

  const isCurrentMonthAndYear =
    currentMonth === currentMonthNow && currentYear === currentYearNow

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between p-2 sm:p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <h2 className="text-base sm:text-xl font-semibold text-gray-900 dark:text-gray-100 capitalize">
            <span className="hidden sm:inline">{monthName}</span>
            <span className="sm:hidden">{shortMonthName}</span> {currentYear}
          </h2>
          {loading && <LoadingSpinner size="sm" />}
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrevMonth}
            disabled={!canNavigatePrevMonth}
            className="p-1.5 sm:p-2"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {showTodayButton && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleToday}
              disabled={isCurrentMonthAndYear}
              className="px-2 sm:px-3 text-xs sm:text-sm"
            >
              {todayButtonLabel ?? t.transactions.calendar.today}
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={handleNextMonth}
            className="p-1.5 sm:p-2"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          <div className="relative ml-1 sm:ml-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowYearPicker(!showYearPicker)}
              className="min-w-[60px] sm:min-w-[80px] text-xs sm:text-sm"
            >
              {currentYear}
            </Button>
            {showYearPicker && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-60 overflow-y-auto">
                {yearOptions.map(year => (
                  <button
                    key={year}
                    onClick={() => handleYearSelect(year)}
                    className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                      year === currentYear
                        ? "bg-gray-100 dark:bg-gray-700 font-medium"
                        : ""
                    }`}
                  >
                    {year}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-7">
        {weekdayLabels.map((day, index) => (
          <div
            key={index}
            className="py-2 sm:py-3 text-center text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700"
          >
            <span className="hidden sm:inline">{day.short}</span>
            <span className="sm:hidden">{day.letter}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {calendarDays.map((day, index) => {
          const hasItems = day.items.length > 0
          const isClickable = hasItems && onDayClick

          return (
            <div
              key={index}
              onClick={() => isClickable && onDayClick(day, index)}
              className={`min-h-[60px] sm:min-h-[100px] md:min-h-[120px] p-0.5 sm:p-1 md:p-2 border-b border-r border-gray-200 dark:border-gray-700 transition-colors ${
                day.isCurrentMonth
                  ? "bg-white dark:bg-gray-900"
                  : "bg-gray-50 dark:bg-gray-950"
              } ${isClickable ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800" : ""}`}
            >
              <div className="flex items-start justify-between mb-0.5 sm:mb-1">
                <span
                  className={`text-xs sm:text-sm font-medium ${
                    day.isToday
                      ? "w-5 h-5 sm:w-7 sm:h-7 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] sm:text-sm"
                      : day.isCurrentMonth
                        ? "text-gray-900 dark:text-gray-100"
                        : "text-gray-400 dark:text-gray-600"
                  }`}
                >
                  {day.date.getDate()}
                </span>
              </div>

              <div className="hidden sm:block">
                {renderDayContent(day, false)}
              </div>

              <div className="sm:hidden">{renderDayContent(day, true)}</div>
            </div>
          )
        })}
      </div>

      {showYearPicker && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowYearPicker(false)}
        />
      )}
    </Card>
  )
}

export { formatDateKey }
