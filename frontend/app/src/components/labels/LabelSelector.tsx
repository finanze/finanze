import { useMemo, useState } from "react"
import { Check, Search } from "lucide-react"
import { useI18n } from "@/i18n"
import { useLabels } from "@/context/LabelsContext"
import { cn } from "@/lib/utils"
import { LabelIcon, getLabelColor, hexToRgba } from "./LabelChip"

interface LabelSelectorProps {
  value: string[]
  onChange: (value: string[]) => void
  disabled?: boolean
  className?: string
}

export function LabelSelector({
  value,
  onChange,
  disabled,
  className,
}: LabelSelectorProps) {
  const { t } = useI18n()
  const { labels, getLabelName } = useLabels()
  const [query, setQuery] = useState("")

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    if (!normalized) return labels
    return labels.filter(label =>
      getLabelName(label).toLocaleLowerCase().includes(normalized),
    )
  }, [labels, getLabelName, query])

  const toggle = (labelId: string) => {
    if (disabled) return
    onChange(
      value.includes(labelId)
        ? value.filter(id => id !== labelId)
        : [...value, labelId],
    )
  }

  return (
    <div className={cn("space-y-2", className)} data-testid="label-selector">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder={t.labels.searchLabels}
          disabled={disabled}
          className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
      <div className="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto py-0.5">
        {filtered.length === 0 && (
          <span className="text-xs text-muted-foreground">
            {t.common.noOptionsFound}
          </span>
        )}
        {filtered.map(label => {
          const selected = value.includes(label.id)
          const color = getLabelColor(label)
          return (
            <button
              key={label.id}
              type="button"
              onClick={() => toggle(label.id)}
              disabled={disabled}
              aria-pressed={selected}
              data-testid={`label-option-${label.key ?? label.id}`}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-all",
                selected ? "shadow-sm" : "opacity-70 hover:opacity-100",
              )}
              style={{
                backgroundColor: selected
                  ? hexToRgba(color, 0.18)
                  : "transparent",
                borderColor: hexToRgba(color, selected ? 0.6 : 0.3),
                color,
              }}
            >
              {selected ? (
                <Check className="h-3 w-3" />
              ) : (
                <LabelIcon label={label} className="h-3 w-3" />
              )}
              {getLabelName(label)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
