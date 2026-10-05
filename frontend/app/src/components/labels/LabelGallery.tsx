import { useMemo, useState } from "react"
import { EyeOff, Pencil, Search, SearchX, Trash2 } from "lucide-react"
import { useI18n } from "@/i18n"
import { EmptyState } from "@/components/ui/EmptyState"
import { LabelCategory, type Label } from "@/types/labeling"
import { LabelIcon, getLabelColor, hexToRgba } from "./LabelChip"

const CATEGORY_ORDER: LabelCategory[] = [
  LabelCategory.EXPENSE,
  LabelCategory.INCOME,
  LabelCategory.EXCLUDED,
]

interface LabelGalleryProps {
  labels: Label[]
  getLabelName: (label: Label) => string
  onEdit: (label: Label) => void
  onDelete: (label: Label) => void
  onOpenMovements: (label: Label) => void
}

export function LabelGallery({
  labels,
  getLabelName,
  onEdit,
  onDelete,
  onOpenMovements,
}: LabelGalleryProps) {
  const { t } = useI18n()
  const [query, setQuery] = useState("")

  const groups = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    const byCategory = new Map<LabelCategory, Label[]>()
    labels
      .filter(
        label =>
          !normalized ||
          getLabelName(label).toLocaleLowerCase().includes(normalized),
      )
      .forEach(label => {
        const category = label.category ?? LabelCategory.EXPENSE
        byCategory.set(category, [...(byCategory.get(category) ?? []), label])
      })
    return CATEGORY_ORDER.filter(category => byCategory.has(category)).map(
      category => ({
        category,
        labels: byCategory.get(category)!,
      }),
    )
  }, [labels, getLabelName, query])

  return (
    <div className="space-y-6">
      <div className="relative max-w-xs">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder={t.labels.searchLabels}
          className="h-9 w-full rounded-full border border-input bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {groups.length === 0 && (
        <EmptyState icon={SearchX} title={t.common.noOptionsFound} />
      )}

      {groups.map(({ category, labels: groupLabels }) => (
        <section key={category} className="space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {t.labels.categories[category]}
            </h3>
            <span className="rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
              {groupLabels.length}
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {groupLabels.map(label => (
              <LabelTile
                key={label.id}
                label={label}
                name={getLabelName(label)}
                onEdit={() => onEdit(label)}
                onDelete={() => onDelete(label)}
                onOpenMovements={() => onOpenMovements(label)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

interface LabelTileProps {
  label: Label
  name: string
  onEdit: () => void
  onDelete: () => void
  onOpenMovements: () => void
}

function LabelTile({
  label,
  name,
  onEdit,
  onDelete,
  onOpenMovements,
}: LabelTileProps) {
  const { t } = useI18n()
  const color = getLabelColor(label)
  const usage = label.usage ?? 0

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onEdit}
      onKeyDown={event => {
        if (event.key === "Enter") onEdit()
      }}
      data-testid={`label-card-${label.key ?? label.id}`}
      className="flex cursor-pointer items-center gap-3 rounded-xl border bg-card p-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      style={{ borderColor: hexToRgba(color, 0.6) }}
    >
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: hexToRgba(color, 0.18), color }}
      >
        <LabelIcon label={label} className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium text-foreground">
            {name}
          </span>
          {label.category === LabelCategory.EXCLUDED && (
            <EyeOff
              className="h-3 w-3 shrink-0 text-muted-foreground"
              aria-label={t.labels.excluded}
            />
          )}
        </div>
        {usage > 0 ? (
          <button
            type="button"
            onClick={event => {
              event.stopPropagation()
              onOpenMovements()
            }}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            {t.labels.usage.replace("{count}", `${usage}`)}
          </button>
        ) : (
          <span className="text-xs text-muted-foreground/70">
            {t.labels.noUsage}
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          onClick={event => {
            event.stopPropagation()
            onEdit()
          }}
          aria-label={t.common.edit}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={event => {
            event.stopPropagation()
            onDelete()
          }}
          aria-label={t.common.delete}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-red-600 dark:hover:text-red-400"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
