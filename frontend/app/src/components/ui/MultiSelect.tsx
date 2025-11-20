import { useState, useRef, useEffect } from "react"
import { Check, ChevronDown, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"
import type { LucideIcon } from "lucide-react"

export interface MultiSelectOption {
  value: string
  label: string
  icon?: LucideIcon
}

interface MultiSelectProps {
  options: MultiSelectOption[]
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}

export function MultiSelect({
  options,
  value,
  onChange,
  placeholder,
  className,
  disabled = false,
}: MultiSelectProps) {
  const { t } = useI18n()
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const defaultPlaceholder = placeholder || t.common.selectOptions

  const filteredOptions = options.filter(option =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  const selectedOptions = options.filter(option => value.includes(option.value))

  const toggleOption = (optionValue: string) => {
    if (value.includes(optionValue)) {
      onChange(value.filter(v => v !== optionValue))
    } else {
      onChange([...value, optionValue])
    }
  }

  const removeOption = (optionValue: string) => {
    onChange(value.filter(v => v !== optionValue))
  }

  const handleClickOutside = (event: MouseEvent) => {
    if (
      dropdownRef.current &&
      !dropdownRef.current.contains(event.target as Node)
    ) {
      setIsOpen(false)
      setSearchTerm("")
    }
  }

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside)
    } else {
      document.removeEventListener("mousedown", handleClickOutside)
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [isOpen])

  return (
    <div className={cn("relative", className)} ref={dropdownRef}>
      <div
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background cursor-pointer",
          "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
          disabled && "cursor-not-allowed opacity-50",
          isOpen && "ring-2 ring-ring ring-offset-2",
        )}
        onClick={() => !disabled && setIsOpen(!isOpen)}
      >
        <div className="flex flex-wrap gap-1 flex-1 items-center overflow-hidden">
          {selectedOptions.length === 0 ? (
            <span className="text-muted-foreground">{defaultPlaceholder}</span>
          ) : selectedOptions.length > 3 ? (
            <>
              {selectedOptions.slice(0, 2).map(option => (
                <div
                  key={option.value}
                  className="flex items-center gap-1 bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-xs max-w-[120px]"
                >
                  <span className="truncate">{option.label}</span>
                  <button
                    type="button"
                    className="hover:bg-secondary-foreground/10 rounded-full p-0.5 flex-shrink-0"
                    onClick={e => {
                      e.stopPropagation()
                      removeOption(option.value)
                    }}
                    disabled={disabled}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
              <div className="flex items-center bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-xs">
                +{selectedOptions.length - 2}
              </div>
            </>
          ) : (
            selectedOptions.map(option => (
              <div
                key={option.value}
                className="flex items-center gap-1 bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-xs max-w-[120px]"
              >
                <span className="truncate">{option.label}</span>
                <button
                  type="button"
                  className="hover:bg-secondary-foreground/10 rounded-full p-0.5 flex-shrink-0"
                  onClick={e => {
                    e.stopPropagation()
                    removeOption(option.value)
                  }}
                  disabled={disabled}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))
          )}
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 transition-transform",
            isOpen && "rotate-180",
          )}
        />
      </div>

      {isOpen && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-background border border-input rounded-md shadow-lg">
          <div className="p-2 border-b">
            <input
              ref={inputRef}
              type="text"
              placeholder={t.common.searchOptions}
              className="w-full px-2 py-1 text-sm border border-input rounded bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              onClick={e => e.stopPropagation()}
            />
          </div>
          <div className="max-h-60 overflow-auto">
            {filteredOptions.length === 0 ? (
              <div className="p-2 text-sm text-muted-foreground text-center">
                {t.common.noOptionsFound}
              </div>
            ) : (
              filteredOptions.map(option => {
                const OptionIcon = option.icon
                return (
                  <div
                    key={option.value}
                    className={cn(
                      "flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground",
                      value.includes(option.value) &&
                        "bg-accent text-accent-foreground",
                      option.icon && "italic",
                    )}
                    onClick={() => toggleOption(option.value)}
                  >
                    <span className="flex items-center gap-2">
                      {OptionIcon && <OptionIcon className="h-4 w-4" />}
                      {option.label}
                    </span>
                    {value.includes(option.value) && (
                      <Check className="h-4 w-4" />
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
