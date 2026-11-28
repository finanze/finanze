import { useId, useState } from "react"
import {
  Check,
  ChevronDown,
  ChevronUp,
  Edit2,
  Info,
  Landmark,
  PlusCircle,
  X,
} from "lucide-react"
import { useAppContext } from "@/context/AppContext"
import { useI18n } from "@/i18n"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { formatIban } from "@/lib/formatters"
import { isValidExclusionIban, normalizeIban } from "@/lib/accountExclusions"
import type { AccountExclusion } from "@/types/accountExclusions"

interface AccountExclusionsEditorProps {
  rules: AccountExclusion[]
  expanded: boolean
  onToggle: () => void
  onSave: (rules: AccountExclusion[]) => Promise<boolean>
}

const chipInputClass =
  "h-7 w-60 rounded-full border border-border/40 bg-background/40 px-3 font-mono text-xs uppercase focus:border-border/60 focus-visible:outline-none focus-visible:ring-0"

export function AccountExclusionsEditor({
  rules,
  expanded,
  onToggle,
  onSave,
}: AccountExclusionsEditorProps) {
  const { t } = useI18n()
  const copy = t.settings.assets.accounts
  const { showToast } = useAppContext()
  const id = useId()
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reset = () => {
    setAdding(false)
    setEditing(null)
    setDraft("")
    setError(null)
  }

  const persist = async (next: AccountExclusion[]) => {
    setSaving(true)
    try {
      const saved = await onSave(next)
      if (saved) {
        showToast(copy.rulesChanged, "success")
        reset()
      } else {
        setError(t.settings.saveError)
      }
    } finally {
      setSaving(false)
    }
  }

  const submit = async () => {
    const value = normalizeIban(draft)
    if (!isValidExclusionIban(value)) {
      setError(copy.invalidIban)
      return
    }
    if (rules.some(rule => rule.value === value && rule.value !== editing)) {
      setError(copy.duplicateIban)
      return
    }
    if (value === editing) {
      reset()
      return
    }
    await persist(
      editing
        ? rules.map(rule =>
            rule.value === editing ? { type: "IBAN", value } : rule,
          )
        : [...rules, { type: "IBAN", value }],
    )
  }

  const renderDraftInput = (confirmLabel: string, cancelLabel: string) => (
    <div className="flex items-center gap-2 py-0.5">
      <Input
        autoFocus
        value={draft}
        aria-label={copy.ibanLabel}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
        placeholder={copy.ibanPlaceholder}
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        disabled={saving}
        className={chipInputClass}
        onChange={event => {
          setDraft(event.target.value)
          setError(null)
        }}
        onKeyDown={event => {
          if (event.key === "Enter") {
            event.preventDefault()
            void submit()
          } else if (event.key === "Escape") {
            event.preventDefault()
            reset()
          }
        }}
      />
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="h-7 w-7 rounded-full p-0"
        disabled={saving || !draft.trim()}
        aria-label={confirmLabel}
        onClick={() => void submit()}
      >
        <Check className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 w-7 rounded-full p-0"
        disabled={saving}
        aria-label={cancelLabel}
        onClick={reset}
      >
        <X className="h-3.5 w-3.5" />
      </Button>
    </div>
  )

  return (
    <div className="space-y-3" data-testid="account-exclusions-settings">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-md border border-border/50 bg-muted/20 px-3 py-2 text-left transition-colors hover:bg-muted/30 dark:bg-muted/10 dark:hover:bg-muted/20"
        aria-expanded={expanded}
        aria-controls={id}
        onClick={onToggle}
      >
        <div className="flex items-start gap-3">
          <Landmark className="mt-0.5 h-5 w-5 text-primary" />
          <div>
            <p className="font-medium">{copy.title}</p>
            <p className="text-xs text-muted-foreground">{copy.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {rules.length > 0 && (
            <Badge className="bg-primary/10 text-primary dark:bg-primary/20">
              {rules.length}
            </Badge>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>
      {expanded && (
        <div
          id={id}
          className="space-y-4 rounded-md border border-dashed border-border/60 bg-background/60 p-4 dark:bg-muted/10"
        >
          <div className="space-y-1">
            <Label>{copy.exclusionsLabel}</Label>
            <p className="text-sm text-muted-foreground">
              {copy.exclusionsDescription}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {rules.map(rule =>
              editing === rule.value ? (
                <div key={rule.value}>
                  {renderDraftInput(copy.saveIban, copy.cancelEdit)}
                </div>
              ) : (
                <Badge
                  key={rule.value}
                  className="flex items-center gap-2 bg-primary/10 text-primary dark:bg-primary/20"
                >
                  <span className="font-mono">
                    {formatIban(rule.value, true)}
                  </span>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => {
                      setAdding(false)
                      setEditing(rule.value)
                      setDraft(formatIban(rule.value, true) ?? rule.value)
                      setError(null)
                    }}
                    className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-primary/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                    <span className="sr-only">{copy.editIban}</span>
                  </button>
                  <span aria-hidden="true" className="h-4 w-px bg-primary/30" />
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() =>
                      void persist(
                        rules.filter(entry => entry.value !== rule.value),
                      )
                    }
                    className="inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-primary/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
                  >
                    <X className="h-3.5 w-3.5" />
                    <span className="sr-only">{copy.removeIban}</span>
                  </button>
                </Badge>
              ),
            )}
            {adding ? (
              renderDraftInput(copy.addIban, t.common.cancel)
            ) : (
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  setEditing(null)
                  setDraft("")
                  setError(null)
                  setAdding(true)
                }}
                className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-primary/50 px-2.5 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:ring-offset-0"
              >
                <PlusCircle className="h-3 w-3" />
                <span>{copy.addIban}</span>
              </button>
            )}
          </div>
          {error && (
            <p
              id={`${id}-error`}
              role="alert"
              className="text-xs text-destructive"
            >
              {error}
            </p>
          )}
          {rules.length === 0 && !adding && (
            <p className="text-sm italic text-muted-foreground">
              {copy.emptyState}
            </p>
          )}
          <div className="flex items-start gap-2 border-t border-border/50 pt-4 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>{copy.dataUnchanged}</p>
          </div>
        </div>
      )}
    </div>
  )
}
