import { Pencil, Trash2 } from "lucide-react"

import { useI18n } from "@/i18n"

interface ManualPositionActionsProps {
  onEdit: () => void
  onDelete: () => void
}

const ICON_ACTION_CLASS =
  "inline-flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"

export function ManualPositionActions({
  onEdit,
  onDelete,
}: ManualPositionActionsProps) {
  const { t } = useI18n()

  return (
    <>
      <button
        type="button"
        onClick={onEdit}
        className={ICON_ACTION_CLASS}
        aria-label={t.common.edit}
        title={t.common.edit}
      >
        <Pencil className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={onDelete}
        className={`${ICON_ACTION_CLASS} hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400`}
        aria-label={t.common.delete}
        title={t.common.delete}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </>
  )
}
