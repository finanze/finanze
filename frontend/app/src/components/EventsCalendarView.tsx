import React, { useState, useMemo, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { MoneyEvent, MoneyEventType } from "@/types"
import { getMoneyEvents } from "@/services/api"
import { formatCurrency } from "@/lib/formatters"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { BaseCalendar, CalendarDay } from "@/components/ui/BaseCalendar"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { X, CalendarSync, HandCoins, PiggyBank, Landmark } from "lucide-react"

type EventTypeFilter = {
  [key in MoneyEventType]: boolean
}

interface EventsCalendarViewProps {
  onEventClick?: (event: MoneyEvent) => void
}

export function EventsCalendarView({ onEventClick }: EventsCalendarViewProps) {
  const { t } = useI18n()

  const today = useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])

  const [currentMonth, setCurrentMonth] = useState(today.getMonth())
  const [currentYear, setCurrentYear] = useState(today.getFullYear())
  const [events, setEvents] = useState<MoneyEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedDay, setSelectedDay] =
    useState<CalendarDay<MoneyEvent> | null>(null)
  const [eventTypeFilter, setEventTypeFilter] = useState<EventTypeFilter>({
    [MoneyEventType.CONTRIBUTION]: true,
    [MoneyEventType.PERIODIC_FLOW]: true,
    [MoneyEventType.PENDING_FLOW]: true,
    [MoneyEventType.MATURITY]: true,
  })

  const filteredEvents = useMemo(() => {
    return events.filter(event => eventTypeFilter[event.type])
  }, [events, eventTypeFilter])

  const toggleEventType = (type: MoneyEventType) => {
    setEventTypeFilter(prev => ({
      ...prev,
      [type]: !prev[type],
    }))
  }

  // Format date as YYYY-MM-DD without timezone conversion
  const formatDateStr = (d: Date) => {
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, "0")
    const dd = String(d.getDate()).padStart(2, "0")
    return `${yyyy}-${mm}-${dd}`
  }

  const fetchEvents = useCallback(async () => {
    // Calculate the visible date range in the calendar grid
    // The grid always shows 6 weeks (42 days) starting from Monday
    const firstDayOfMonth = new Date(currentYear, currentMonth, 1)
    let startDay = firstDayOfMonth.getDay()
    startDay = startDay === 0 ? 6 : startDay - 1 // Adjust for Monday start

    // First visible day (may be in previous month)
    const firstVisibleDay = new Date(currentYear, currentMonth, 1 - startDay)
    // Last visible day (42 days total in the grid)
    const lastVisibleDay = new Date(firstVisibleDay)
    lastVisibleDay.setDate(firstVisibleDay.getDate() + 41)

    // For events, we always start from tomorrow
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)

    // If tomorrow is after the last visible day, there's nothing to fetch
    if (tomorrow > lastVisibleDay) {
      setEvents([])
      return
    }

    // fromDate is tomorrow or first visible day, whichever is later
    const fromDate = tomorrow > firstVisibleDay ? tomorrow : firstVisibleDay
    const toDate = lastVisibleDay

    setLoading(true)
    try {
      const fromDateStr = formatDateStr(fromDate)
      const toDateStr = formatDateStr(toDate)

      const response = await getMoneyEvents({
        from_date: fromDateStr,
        to_date: toDateStr,
      })

      setEvents(response.events)
    } catch (error) {
      console.error("Failed to fetch events:", error)
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [currentMonth, currentYear, today])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  const handleMonthChange = (month: number, year: number) => {
    setCurrentMonth(month)
    setCurrentYear(year)
    setSelectedDay(null)
  }

  const getItemDateKey = (event: MoneyEvent): string => {
    return event.date.split("T")[0]
  }

  const getEventColor = (event: MoneyEvent): string => {
    const isEarning = event.amount > 0

    if (event.type === MoneyEventType.CONTRIBUTION) {
      return "bg-blue-500 dark:bg-blue-400"
    }
    if (event.type === MoneyEventType.MATURITY) {
      return "bg-green-500 dark:bg-green-400"
    }
    if (isEarning) {
      return "bg-green-500 dark:bg-green-400"
    }
    return "bg-red-500 dark:bg-red-400"
  }

  const getEventIcon = (
    event: MoneyEvent,
    size: string = "h-4 w-4",
    forceWhite: boolean = false,
  ) => {
    const isEarning = event.amount > 0
    const isRecurring =
      event.type === MoneyEventType.PERIODIC_FLOW ||
      event.type === MoneyEventType.CONTRIBUTION

    const colorClass = forceWhite
      ? "text-white"
      : event.type === MoneyEventType.CONTRIBUTION
        ? "text-blue-500"
        : isEarning
          ? "text-green-500"
          : "text-red-500"

    if (event.type === MoneyEventType.CONTRIBUTION) {
      return <PiggyBank className={`${size} ${colorClass}`} />
    }
    if (event.type === MoneyEventType.MATURITY && event.product_type) {
      return (
        <span className="flex-shrink-0">
          {getIconForAssetType(
            event.product_type,
            size,
            forceWhite ? "text-white" : null,
          )}
        </span>
      )
    }
    if (isRecurring) {
      return <CalendarSync className={`${size} ${colorClass}`} />
    }
    return <HandCoins className={`${size} ${colorClass}`} />
  }

  const renderDayContent = (
    day: CalendarDay<MoneyEvent>,
    isMobile: boolean,
  ) => {
    if (day.items.length === 0) return null

    if (isMobile) {
      return (
        <div className="flex flex-wrap gap-0.5 mt-0.5">
          {day.items.slice(0, 4).map((event, idx) => (
            <div
              key={event.id || idx}
              className={`w-2 h-2 rounded-sm ${getEventColor(event)} ${!day.isCurrentMonth ? "opacity-50" : ""}`}
              title={event.name}
            />
          ))}
          {day.items.length > 4 && (
            <span
              className={`text-[8px] text-gray-500 dark:text-gray-400 ${!day.isCurrentMonth ? "opacity-50" : ""}`}
            >
              +{day.items.length - 4}
            </span>
          )}
        </div>
      )
    }

    const previewEvents = day.items.slice(0, 3)
    const moreCount = day.items.length - 3

    return (
      <div className="space-y-0.5">
        {previewEvents.map((event, idx) => (
          <div
            key={event.id || idx}
            className={`text-xs truncate rounded px-1 py-0.5 ${getEventColor(event)} text-white flex items-center gap-1 ${!day.isCurrentMonth ? "opacity-50" : ""}`}
            title={event.name}
          >
            <span className="flex-shrink-0">
              {getEventIcon(event, "h-3 w-3", true)}
            </span>
            <span className="truncate">{event.name}</span>
          </div>
        ))}
        {moreCount > 0 && (
          <div
            className={`text-xs text-gray-500 dark:text-gray-400 pl-1 ${!day.isCurrentMonth ? "opacity-50" : ""}`}
          >
            +{moreCount} {t.transactions.calendar.more}
          </div>
        )}
      </div>
    )
  }

  const handleDayClick = (day: CalendarDay<MoneyEvent>) => {
    if (day.items.length > 0) {
      setSelectedDay(day)
    }
  }

  const filterButtons = [
    {
      type: MoneyEventType.CONTRIBUTION,
      label: t.management.autoContributions,
      icon: <PiggyBank className="h-3.5 w-3.5" />,
    },
    {
      type: MoneyEventType.PERIODIC_FLOW,
      label: t.management.recurringMoney,
      icon: <CalendarSync className="h-3.5 w-3.5" />,
    },
    {
      type: MoneyEventType.PENDING_FLOW,
      label: t.management.pendingMoney,
      icon: <HandCoins className="h-3.5 w-3.5" />,
    },
    {
      type: MoneyEventType.MATURITY,
      label: t.investments.maturity,
      icon: <Landmark className="h-3.5 w-3.5" />,
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 justify-center">
        {filterButtons.map(({ type, label, icon }) => (
          <Button
            key={type}
            variant="outline"
            size="sm"
            onClick={() => toggleEventType(type)}
            className={`inline-flex items-center gap-1.5 text-xs ${
              !eventTypeFilter[type] ? "opacity-50" : ""
            }`}
          >
            {icon}
            <span className="hidden sm:inline">{label}</span>
          </Button>
        ))}
      </div>

      <BaseCalendar
        items={filteredEvents}
        getItemDateKey={getItemDateKey}
        currentMonth={currentMonth}
        currentYear={currentYear}
        onMonthChange={handleMonthChange}
        loading={loading}
        renderDayContent={renderDayContent}
        onDayClick={handleDayClick}
        disablePastNavigation={true}
        showTodayButton={false}
      />

      <AnimatePresence>
        {selectedDay && (
          <EventDayDetailModal
            day={selectedDay}
            onClose={() => setSelectedDay(null)}
            getEventIcon={getEventIcon}
            onEventClick={onEventClick}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

interface EventDayDetailModalProps {
  day: CalendarDay<MoneyEvent>
  onClose: () => void
  getEventIcon: (
    event: MoneyEvent,
    size?: string,
    forceWhite?: boolean,
  ) => React.ReactNode
  onEventClick?: (event: MoneyEvent) => void
}

function EventDayDetailModal({
  day,
  onClose,
  getEventIcon,
  onEventClick,
}: EventDayDetailModalProps) {
  const { t, locale } = useI18n()

  const formattedDate = day.date.toLocaleDateString(locale, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })

  const shortFormattedDate = day.date.toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
  })

  const getAmountColor = (event: MoneyEvent): string => {
    if (event.type === MoneyEventType.CONTRIBUTION) {
      return "text-foreground"
    }
    if (event.type === MoneyEventType.MATURITY || event.amount > 0) {
      return "text-green-600"
    }
    return "text-red-600"
  }

  const getAmountPrefix = (event: MoneyEvent): string => {
    if (event.type === MoneyEventType.CONTRIBUTION) {
      return ""
    }
    if (event.type === MoneyEventType.MATURITY || event.amount > 0) {
      return "+"
    }
    return "-"
  }

  const getEventTypeLabel = (event: MoneyEvent): string => {
    switch (event.type) {
      case MoneyEventType.CONTRIBUTION:
        return t.management.autoContributions
      case MoneyEventType.PERIODIC_FLOW:
        return t.management.recurringMoney
      case MoneyEventType.PENDING_FLOW:
        return t.management.pendingMoney
      case MoneyEventType.MATURITY:
        return t.investments.maturity
      default:
        return ""
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={e => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="w-full max-w-lg"
      >
        <Card className="max-h-[80vh] overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-3 sm:p-4 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">
              <span className="hidden sm:inline">{formattedDate}</span>
              <span className="sm:hidden">{shortFormattedDate}</span>
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 flex-shrink-0"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          <div className="p-3 sm:p-4 overflow-y-auto space-y-2 sm:space-y-3">
            {day.items.map((event, idx) => (
              <div
                key={event.id || idx}
                className={`p-3 rounded-lg bg-muted/50 ${onEventClick ? "cursor-pointer hover:bg-muted/70 transition-colors" : ""}`}
                onClick={() => onEventClick?.(event)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    {getEventIcon(event, "h-5 w-5")}
                    <div className="min-w-0 flex-1">
                      <p
                        className="font-medium text-sm truncate"
                        title={event.name}
                      >
                        {event.name}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {getEventTypeLabel(event)}
                      </p>
                    </div>
                  </div>
                  <p
                    className={`font-mono text-sm font-semibold flex-shrink-0 ${getAmountColor(event)}`}
                  >
                    {getAmountPrefix(event)}
                    {formatCurrency(
                      Math.abs(event.amount),
                      locale,
                      event.currency,
                    )}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}
