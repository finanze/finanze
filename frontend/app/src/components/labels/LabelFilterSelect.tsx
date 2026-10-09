import { useEffect, useRef, useState, type ReactNode } from "react"
import { Ban, Check, ChevronDown, Tag, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"
import { useLabelOptions } from "./TransactionLabels"

export interface LabelFilterValue {
  included: string[]
  excluded: string[]
  unlabeled: boolean
}

interface LabelFilterSelectProps {
  value: LabelFilterValue
  onChange: (value: LabelFilterValue) => void
  placeholder?: string
  className?: string
}

type ChipKind = "unlabeled" | "included" | "excluded"

interface Chip {
  key: string
  kind: ChipKind
  value: string
  label: string
  icon?: ReactNode
}

export function LabelFilterSelect({
  value,
  onChange,
  placeholder,
  className,
}: LabelFilterSelectProps) {
  const { t } = useI18n()
  const options = useLabelOptions()
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
        setSearchTerm("")
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isOpen])

  const term = searchTerm.trim().toLowerCase()
  const filteredOptions = options.filter(option =>
    option.label.toLowerCase().includes(term),
  )
  const showUnlabeled = t.labels.unlabeled.toLowerCase().includes(term)

  const setLabelState = (
    labelId: string,
    state: "included" | "excluded" | null,
  ) => {
    const included = value.included.filter(id => id !== labelId)
    const excluded = value.excluded.filter(id => id !== labelId)
    if (state === "included") included.push(labelId)
    if (state === "excluded") excluded.push(labelId)
    onChange({ included, excluded, unlabeled: false })
  }

  const toggleUnlabeled = () => {
    onChange(
      value.unlabeled
        ? { ...value, unlabeled: false }
        : { included: [], excluded: [], unlabeled: true },
    )
  }

  const optionById = new Map(options.map(option => [option.value, option]))
  const chips: Chip[] = [
    ...(value.unlabeled
      ? [
          {
            key: "unlabeled",
            kind: "unlabeled" as const,
            value: "",
            label: t.labels.unlabeled,
          },
        ]
      : []),
    ...value.included.flatMap(id => {
      const option = optionById.get(id)
      return option
        ? [
            {
              key: `in-${id}`,
              kind: "included" as const,
              value: id,
              label: option.label,
              icon: option.icon as ReactNode,
            },
          ]
        : []
    }),
    ...value.excluded.flatMap(id => {
      const option = optionById.get(id)
      return option
        ? [
            {
              key: `ex-${id}`,
              kind: "excluded" as const,
              value: id,
              label: option.label,
            },
          ]
        : []
    }),
  ]

  const removeChip = (chip: Chip) => {
    if (chip.kind === "unlabeled") {
      onChange({ ...value, unlabeled: false })
    } else {
      setLabelState(chip.value, null)
    }
  }

  const renderChip = (chip: Chip) => (
    <div
      key={chip.key}
      className={cn(
        "flex max-w-[180px] items-center gap-1 rounded px-1.5 py-0.5 text-xs",
        chip.kind === "excluded"
          ? "bg-red-500/10 text-red-700 dark:text-red-300"
          : "bg-secondary text-secondary-foreground",
      )}
      title={
        chip.kind === "excluded"
          ? `${t.labels.excludeLabel}: ${chip.label}`
          : chip.label
      }
    >
      {chip.kind === "excluded" ? (
        <Ban className="h-3 w-3 shrink-0" />
      ) : chip.kind === "unlabeled" ? (
        <Tag className="h-3 w-3 shrink-0" />
      ) : (
        <span className="inline-flex shrink-0 [&_svg]:h-3 [&_svg]:w-3">
          {chip.icon}
        </span>
      )}
      <span
        className={cn("truncate", chip.kind === "excluded" && "line-through")}
      >
        {chip.label}
      </span>
      <button
        type="button"
        className="flex-shrink-0 rounded-full p-0.5 hover:bg-secondary-foreground/10"
        onClick={event => {
          event.stopPropagation()
          removeChip(chip)
        }}
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  )

  const stateButtonClass =
    "inline-flex h-6 w-6 items-center justify-center rounded-md border transition-colors"

  return (
    <div
      className={cn("relative", className)}
      ref={containerRef}
      data-testid="label-filter"
    >
      <div
        className={cn(
          "flex h-10 w-full cursor-pointer rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background",
          isOpen && "ring-2 ring-ring ring-offset-2",
        )}
        onClick={() => setIsOpen(open => !open)}
      >
        <div className="flex flex-1 flex-wrap items-center gap-1 overflow-hidden">
          {chips.length === 0 ? (
            <span className="text-muted-foreground">
              {placeholder ?? t.labels.anyLabel}
            </span>
          ) : chips.length > 2 ? (
            <>
              {renderChip(chips[0])}
              <div className="flex items-center rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
                +{chips.length - 1}
              </div>
            </>
          ) : (
            chips.map(renderChip)
          )}
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 transition-transform",
            isOpen && "rotate-180",
          )}
        />
      </div>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full min-w-[220px] rounded-md border border-input bg-background shadow-lg">
          <div className="border-b p-2">
            <input
              type="text"
              placeholder={t.common.searchOptions}
              className="w-full rounded border border-input bg-background px-2 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              value={searchTerm}
              onChange={event => setSearchTerm(event.target.value)}
              onClick={event => event.stopPropagation()}
            />
          </div>
          <div className="max-h-60 overflow-auto">
            {showUnlabeled && (
              <div
                className={cn(
                  "flex cursor-pointer items-center justify-between px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground",
                  value.unlabeled && "bg-accent text-accent-foreground",
                )}
                onClick={toggleUnlabeled}
                data-testid="label-filter-unlabeled"
              >
                <span className="flex items-center gap-2">
                  <Tag className="h-4 w-4 text-muted-foreground" />
                  {t.labels.unlabeled}
                </span>
                {value.unlabeled && <Check className="h-4 w-4" />}
              </div>
            )}
            {filteredOptions.length === 0 && !showUnlabeled ? (
              <div className="p-2 text-center text-sm text-muted-foreground">
                {t.common.noOptionsFound}
              </div>
            ) : (
              filteredOptions.map(option => {
                const included = value.included.includes(option.value)
                const excluded = value.excluded.includes(option.value)
                return (
                  <div
                    key={option.value}
                    className={cn(
                      "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground",
                      (included || excluded) &&
                        "bg-accent text-accent-foreground",
                    )}
                    onClick={() =>
                      setLabelState(option.value, included ? null : "included")
                    }
                    data-testid={`label-filter-option-${option.value}`}
                  >
                    <span
                      className={cn(
                        "flex min-w-0 items-center gap-2",
                        excluded && "text-muted-foreground line-through",
                      )}
                    >
                      {option.icon as ReactNode}
                      <span className="truncate">{option.label}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        title={t.labels.includeLabel}
                        aria-label={t.labels.includeLabel}
                        aria-pressed={included}
                        onClick={event => {
                          event.stopPropagation()
                          setLabelState(
                            option.value,
                            included ? null : "included",
                          )
                        }}
                        className={cn(
                          stateButtonClass,
                          included
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-transparent text-muted-foreground hover:border-input",
                        )}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        title={t.labels.excludeLabel}
                        aria-label={t.labels.excludeLabel}
                        aria-pressed={excluded}
                        onClick={event => {
                          event.stopPropagation()
                          setLabelState(
                            option.value,
                            excluded ? null : "excluded",
                          )
                        }}
                        data-testid={`label-filter-exclude-${option.value}`}
                        className={cn(
                          stateButtonClass,
                          excluded
                            ? "border-red-500 bg-red-500 text-white"
                            : "border-transparent text-muted-foreground hover:border-input",
                        )}
                      >
                        <Ban className="h-3.5 w-3.5" />
                      </button>
                    </span>
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
