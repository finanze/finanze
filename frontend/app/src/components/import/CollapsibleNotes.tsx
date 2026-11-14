import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

export function CollapsibleNotes({
  id,
  label,
  hint,
  value,
  placeholder,
  onChange,
  disabled = false,
  rows = 3,
  maxLength,
}: {
  id: string
  label: string
  hint?: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
  disabled?: boolean
  rows?: number
  maxLength?: number
}) {
  const [open, setOpen] = useState(() => value.trim().length > 0)

  return (
    <div className="space-y-1.5">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(current => !current)}
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        data-testid={`${id}-toggle`}
      >
        {label}
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      {open ? (
        <>
          <textarea
            id={id}
            aria-label={label}
            value={value}
            maxLength={maxLength}
            rows={rows}
            disabled={disabled}
            placeholder={placeholder}
            onChange={event => onChange(event.target.value)}
            className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {hint ? (
            <p className="text-xs text-muted-foreground">{hint}</p>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
