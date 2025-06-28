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
import { format, parse } from "date-fns"
import { enUS, es } from "date-fns/locale"
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
  id?: string
}

const localeMap = {
  "en-US": enUS,
  "es-ES": es,
}

function DatePicker({
  value = "",
  onChange,
  placeholder = "Pick a date",
  disabled = false,
  className,
  id,
}: DatePickerProps) {
  const { locale } = useI18n()
  const [isOpen, setIsOpen] = React.useState(false)
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
            <CalendarIcon className="mr-2 h-4 w-4" />
            <span className={cn("flex-1", value && "pr-6")}>
              {displayValue || placeholder}
            </span>
          </Button>
        </PopoverTrigger>

        {value && (
          <div
            className="absolute right-2 top-1/2 transform -translate-y-1/2 z-10 flex items-center justify-center"
            onClick={handleClear}
          >
            <XIcon className="h-4 w-4 hover:bg-muted hover:text-foreground rounded-sm p-0.5 cursor-pointer transition-colors duration-200" />
          </div>
        )}

        <PopoverContent className="w-auto p-4">
          <DayPicker
            mode="single"
            selected={selectedDate}
            onSelect={handleDateSelect}
            locale={dateLocale}
            weekStartsOn={1}
            showOutsideDays={true}
            classNames={{
              nav: "absolute end-4 flex justify-between w-16 p-0.5",
              month_grid: "mt-4",
              caption_label: "text-lg font-medium",
              weekdays: "text-sm text-muted-foreground",
              weekday: "font-light",
              day_button: "cell h-9 w-9",
              selected:
                "rounded-md bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
              today: "font-bold",
              outside: "text-muted-foreground opacity-50",
              disabled: "text-muted-foreground opacity-50",
            }}
            components={{
              // eslint-disable-next-line react/prop-types
              Chevron: ({ orientation, ...props }) => {
                switch (orientation) {
                  case "left":
                    return (
                      <ChevronLeftIcon {...props} className="h-full w-full" />
                    )
                  case "right":
                    return (
                      <ChevronRightIcon {...props} className="h-full w-full" />
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
                      <ChevronRightIcon {...props} className="h-full w-full" />
                    )
                }
              },
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

export { DatePicker }
