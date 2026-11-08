import { useRef, type ClipboardEvent, type KeyboardEvent } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export type TagSeparator = "Enter" | ","

interface TagInputProps {
  values: string[]
  onChange: (values: string[]) => void
  draft: string
  onDraftChange: (draft: string) => void
  removeLabel: (value: string) => string
  separators?: TagSeparator[]
  maxItems?: number
  maxLength?: number
  placeholder?: string
  disabled?: boolean
  mono?: boolean
  autoFocus?: boolean
  id?: string
  testId?: string
  className?: string
  "aria-describedby"?: string
}

const tagKey = (value: string) =>
  value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim()

export const mergeTags = (
  values: string[],
  additions: string[],
  maxItems = Infinity,
): string[] => {
  const result = [...values]
  const seen = new Set(values.map(tagKey))
  for (const raw of additions) {
    const value = raw.trim()
    const key = tagKey(value)
    if (!key || seen.has(key)) continue
    if (result.length >= maxItems) break
    seen.add(key)
    result.push(value)
  }
  return result
}

export function TagInput({
  values,
  onChange,
  draft,
  onDraftChange,
  removeLabel,
  separators = ["Enter", ","],
  maxItems,
  maxLength,
  placeholder,
  disabled,
  mono,
  autoFocus,
  id,
  testId,
  className,
  "aria-describedby": describedBy,
}: TagInputProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const splitOnComma = separators.includes(",")
  const splitOnEnter = separators.includes("Enter")
  const full = maxItems !== undefined && values.length >= maxItems

  const commit = (additions: string[], nextDraft = "") => {
    const next = mergeTags(values, additions, maxItems)
    if (next.length !== values.length) onChange(next)
    onDraftChange(
      maxItems !== undefined && next.length >= maxItems ? "" : nextDraft,
    )
  }

  const handleChange = (value: string) => {
    if (splitOnComma && value.includes(",")) {
      const parts = value.split(",")
      const rest = parts.pop() ?? ""
      commit(parts, rest.trimStart())
      return
    }
    onDraftChange(value)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return
    if (event.key === "Enter" && splitOnEnter) {
      if (!draft.trim()) return
      event.preventDefault()
      commit([draft])
    } else if (event.key === "Backspace" && !draft && values.length) {
      event.preventDefault()
      onChange(values.slice(0, -1))
    }
  }

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData("text")
    const pattern = splitOnComma ? /[\r\n,]+/ : /[\r\n]+/
    if (!pattern.test(text)) return
    event.preventDefault()
    commit([draft, ...text.split(pattern)])
  }

  const remove = (index: number) => {
    onChange(values.filter((_, i) => i !== index))
    inputRef.current?.focus()
  }

  return (
    <div
      className={cn(
        "flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
      onClick={event => {
        if (event.target === event.currentTarget) inputRef.current?.focus()
      }}
    >
      {values.map((value, index) => (
        <span
          key={`${value}-${index}`}
          data-testid="tag-chip"
          className={cn(
            "inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-muted/60 py-0.5 pl-2.5 pr-1 text-xs font-medium",
            mono && "font-mono",
          )}
        >
          <span className="min-w-0 truncate">{value}</span>
          <button
            type="button"
            onClick={() => remove(index)}
            disabled={disabled}
            aria-label={removeLabel(value)}
            title={removeLabel(value)}
            className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        id={id}
        data-testid={testId}
        value={draft}
        maxLength={maxLength}
        placeholder={values.length ? undefined : placeholder}
        onChange={event => handleChange(event.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => {
          if (draft.trim()) commit([draft])
        }}
        disabled={disabled}
        readOnly={full}
        autoFocus={autoFocus}
        aria-describedby={describedBy}
        className={cn(
          "h-7 min-w-[8rem] flex-1 bg-transparent px-1 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed",
          mono && "font-mono",
        )}
      />
    </div>
  )
}
