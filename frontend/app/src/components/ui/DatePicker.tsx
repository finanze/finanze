import * as React from "react"
import {
  CalendarIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  XIcon,
} from "lucide-react"
import { DayPicker } from "react-day-picker"
import { addMonths, format, parse } from "date-fns"
import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  type Transition,
} from "framer-motion"
import { enUS, es, it } from "date-fns/locale"
import { cn } from "@/lib/utils"
import { Button } from "./Button"
import { Popover, PopoverContent, PopoverTrigger } from "./Popover"
import { useI18n } from "@/i18n"

interface DatePickerProps {
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  contentClassName?: string
  id?: string
}

const localeMap = {
  "en-US": enUS,
  "es-ES": es,
  "it-IT": it,
}

type SwipeState = {
  x: number
  y: number
  time: number
  axis: "x" | "y" | null
}

const SWIPE_LOCK_DISTANCE = 8
const SWIPE_MIN_DISTANCE = 50
const SWIPE_COMMIT_RATIO = 0.25
const SWIPE_MIN_VELOCITY = 0.3
const SWIPE_TRANSITION: Transition = { duration: 0.2, ease: [0, 0, 0.58, 0.8] }

function DatePicker({
  value = "",
  onChange,
  placeholder = "Pick a date",
  disabled = false,
  className,
  contentClassName,
  id,
}: DatePickerProps) {
  const { locale, t } = useI18n()
  const [isOpen, setIsOpen] = React.useState(false)
  const [currentMonth, setCurrentMonth] = React.useState<Date>(() => {
    if (value) {
      return parse(value, "yyyy-MM-dd", new Date())
    }
    return new Date()
  })
  const [showYearPicker, setShowYearPicker] = React.useState(false)
  const dragX = useMotionValue(0)
  const gridRef = React.useRef<HTMLTableElement>(null)
  const swipe = React.useRef<SwipeState | null>(null)
  const isSliding = React.useRef(false)
  const reducedMotion = useReducedMotion()
  const swipeTransition: Transition = reducedMotion
    ? { duration: 0 }
    : SWIPE_TRANSITION
  const SwipeMonthGrid = React.useMemo(() => {
    /* eslint-disable react/prop-types */
    function SwipeGrid({
      role,
      className,
      style,
      children,
      "aria-label": ariaLabel,
      "aria-multiselectable": ariaMultiselectable,
    }: React.TableHTMLAttributes<HTMLTableElement>) {
      return (
        <motion.table
          ref={gridRef}
          role={role}
          aria-label={ariaLabel}
          aria-multiselectable={ariaMultiselectable}
          className={cn(className, "touch-pan-y")}
          style={{ ...style, x: dragX }}
        >
          {children}
        </motion.table>
      )
    }
    /* eslint-enable react/prop-types */
    return SwipeGrid
  }, [dragX])
  const dateLocale = localeMap[locale as keyof typeof localeMap] || enUS
  const selectedDate = value
    ? parse(value, "yyyy-MM-dd", new Date())
    : undefined

  const handleDateSelect = (date: Date | undefined) => {
    if (date) {
      const formattedDate = format(date, "yyyy-MM-dd")
      onChange?.(formattedDate)
      setIsOpen(false)
    }
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange?.("")
  }

  const handleYearSelect = (year: number) => {
    const newDate = new Date(currentMonth)
    newDate.setFullYear(year)
    setCurrentMonth(newDate)
    setShowYearPicker(false)
  }

  const slideMonth = async (step: number, width: number) => {
    await animate(dragX, -step * width, swipeTransition)
    setCurrentMonth(month => addMonths(month, step))
    dragX.set(step * width)
    await animate(dragX, 0, swipeTransition)
    isSliding.current = false
  }

  const handleSwipeStart = (e: React.TouchEvent) => {
    if (isSliding.current || !gridRef.current?.contains(e.target as Node))
      return
    const touch = e.touches[0]
    swipe.current = {
      x: touch.clientX,
      y: touch.clientY,
      time: Date.now(),
      axis: null,
    }
  }

  const handleSwipeMove = (e: React.TouchEvent) => {
    const start = swipe.current
    if (!start) return
    const touch = e.touches[0]
    const dx = touch.clientX - start.x
    const dy = touch.clientY - start.y
    if (!start.axis) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_LOCK_DISTANCE) return
      start.axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y"
    }
    if (start.axis === "x") dragX.set(dx)
  }

  const handleSwipeEnd = (e: React.TouchEvent) => {
    const start = swipe.current
    swipe.current = null
    if (start?.axis !== "x") return
    const dx = e.changedTouches[0].clientX - start.x
    const distance = Math.abs(dx)
    const width = gridRef.current?.offsetWidth ?? 0
    const velocity = distance / Math.max(Date.now() - start.time, 1)
    const commit =
      distance > width * SWIPE_COMMIT_RATIO ||
      (distance > SWIPE_MIN_DISTANCE && velocity > SWIPE_MIN_VELOCITY)
    if (commit) {
      isSliding.current = true
      slideMonth(dx < 0 ? 1 : -1, width)
    } else {
      animate(dragX, 0, swipeTransition)
    }
  }

  const handleSwipeCancel = () => {
    if (swipe.current?.axis === "x") animate(dragX, 0, swipeTransition)
    swipe.current = null
  }

  const generateYearRange = () => {
    const currentYear = currentMonth.getFullYear()
    const startYear = currentYear - 10
    const endYear = currentYear + 30
    const years: number[] = []
    for (let year = startYear; year <= endYear; year++) years.push(year)
    return years
  }

  const displayValue = selectedDate
    ? format(selectedDate, "PPP", { locale: dateLocale })
    : ""

  return (
    <div className="relative">
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-start text-left font-normal",
              !value && "text-muted-foreground",
              className,
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4 flex-shrink-0" />
            <span className={cn("flex-1 truncate", value && "pr-6")}>
              {displayValue || placeholder}
            </span>
          </Button>
        </PopoverTrigger>

        {value && !disabled && (
          <div
            className="absolute right-2 top-1/2 transform -translate-y-1/2 z-10 flex items-center justify-center"
            onClick={handleClear}
          >
            <XIcon className="h-4 w-4 hover:bg-muted hover:text-foreground rounded-sm p-0.5 cursor-pointer transition-colors duration-200" />
          </div>
        )}

        <PopoverContent
          className={cn(
            "z-[18000] w-auto overflow-hidden p-4",
            contentClassName,
          )}
          onTouchStart={handleSwipeStart}
          onTouchMove={handleSwipeMove}
          onTouchEnd={handleSwipeEnd}
          onTouchCancel={handleSwipeCancel}
        >
          {showYearPicker ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">
                  {t.datePicker.selectYear}
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowYearPicker(false)}
                  className="h-6 w-6 p-0"
                >
                  <XIcon className="h-4 w-4" />
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                {generateYearRange().map(year => (
                  <Button
                    key={year}
                    variant={
                      year === currentMonth.getFullYear() ? "default" : "ghost"
                    }
                    size="sm"
                    onClick={() => handleYearSelect(year)}
                    className="h-8 text-sm"
                  >
                    {year}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={handleDateSelect}
              month={currentMonth}
              onMonthChange={setCurrentMonth}
              locale={dateLocale}
              weekStartsOn={1}
              showOutsideDays={true}
              fixedWeeks={true}
              classNames={{
                nav: "absolute end-4 flex justify-between w-16 p-0.5",
                month_grid: "mt-4",
                caption_label:
                  "text-lg font-medium cursor-pointer hover:bg-muted rounded px-2 py-1",
                weekdays: "text-sm text-muted-foreground",
                weekday: "font-light",
                day_button: "cell h-9 w-9",
                selected:
                  "rounded-md bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
                today:
                  "[&>button]:font-bold [&>button]:underline [&>button]:underline-offset-2",
                outside: "text-muted-foreground opacity-50",
                disabled: "text-muted-foreground opacity-50",
              }}
              components={{
                MonthGrid: SwipeMonthGrid,
                // eslint-disable-next-line react/prop-types
                CaptionLabel: ({ children, ...props }) => (
                  <span
                    {...props}
                    onClick={() => setShowYearPicker(true)}
                    className="cursor-pointer hover:bg-muted rounded px-2 py-1 transition-colors"
                  >
                    {children}
                  </span>
                ),
                // eslint-disable-next-line react/prop-types
                Chevron: ({ orientation, ...props }) => {
                  switch (orientation) {
                    case "left":
                      return (
                        <ChevronLeftIcon {...props} className="h-full w-full" />
                      )
                    case "right":
                      return (
                        <ChevronRightIcon
                          {...props}
                          className="h-full w-full"
                        />
                      )
                    case "up":
                      return (
                        <ChevronUpIcon {...props} className="h-full w-full" />
                      )
                    case "down":
                      return (
                        <ChevronDownIcon {...props} className="h-full w-full" />
                      )
                    default:
                      return (
                        <ChevronRightIcon
                          {...props}
                          className="h-full w-full"
                        />
                      )
                  }
                },
              }}
            />
          )}
        </PopoverContent>
      </Popover>
    </div>
  )
}

export { DatePicker }
