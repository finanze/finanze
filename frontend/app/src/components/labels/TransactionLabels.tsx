import { useMemo } from "react"
import { ArrowLeftRight, Link2, Tag } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useLabels } from "@/context/LabelsContext"
import { cn } from "@/lib/utils"
import type { MultiSelectOption } from "@/components/ui/MultiSelect"
import { LabelChip, LabelIcon, getLabelColor } from "./LabelChip"
import { LABELABLE_TX_TYPES, type AccountTx } from "@/types/transactions"

export function useLabelOptions(): MultiSelectOption[] {
  const { labels, getLabelName } = useLabels()
  return useMemo(
    () =>
      labels.map(label => ({
        value: label.id,
        label: getLabelName(label),
        icon: (
          <span className="inline-flex" style={{ color: getLabelColor(label) }}>
            <LabelIcon label={label} className="h-4 w-4" />
          </span>
        ),
      })),
    [labels, getLabelName],
  )
}

export const isLabelableTx = (tx: { type: string; product_type: string }) =>
  tx.product_type === "ACCOUNT" &&
  LABELABLE_TX_TYPES.includes(tx.type as AccountTx["type"])

interface TransactionLabelsProps {
  tx: Pick<
    AccountTx,
    "labels" | "linked_tx" | "labels_locked" | "transfer_pair"
  >
  onLabelClick?: (labelId: string) => void
  onEdit?: () => void
  compact?: boolean
  className?: string
}

export function TransactionLabels({
  tx,
  onLabelClick,
  onEdit,
  compact = false,
  className,
}: TransactionLabelsProps) {
  const { t } = useI18n()
  const { entities } = useAppContext()
  const { getLabel, getLabelName } = useLabels()
  const txLabels = tx.labels ?? []
  const pairEntity = tx.transfer_pair
    ? (entities ?? []).find(entity => entity.id === tx.transfer_pair?.entity_id)
        ?.name
    : undefined

  if (!txLabels.length && !tx.linked_tx && !tx.transfer_pair && !onEdit) {
    return null
  }

  return (
    <div
      className={cn("flex flex-wrap items-center gap-1.5", className)}
      data-testid="tx-labels"
    >
      {tx.transfer_pair && (
        <span
          className="inline-flex items-center gap-1 rounded-full border border-dashed border-sky-300 px-2 py-0.5 text-xs text-sky-700 dark:border-sky-700 dark:text-sky-300"
          title={t.labels.transferPairHint.replace(
            "{entity}",
            pairEntity ?? t.labels.transferPairOtherEntity,
          )}
          data-testid="transfer-pair-chip"
        >
          <ArrowLeftRight className="h-3 w-3" />
          {compact ? null : (pairEntity ?? t.labels.transferPair)}
        </span>
      )}
      {tx.linked_tx && (
        <span
          className="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-300 px-2 py-0.5 text-xs text-gray-500 dark:border-gray-600 dark:text-gray-400"
          title={t.labels.settlementHint}
          data-testid="settlement-chip"
        >
          <Link2 className="h-3 w-3" />
          {t.labels.settlement}
        </span>
      )}
      {txLabels.map(txLabel => {
        const label = getLabel(txLabel.label_id)
        if (!label) return null
        return (
          <LabelChip
            key={txLabel.label_id}
            label={label}
            name={getLabelName(label)}
            origin={txLabel.origin}
            confidence={txLabel.confidence}
            onClick={
              onLabelClick ? () => onLabelClick(txLabel.label_id) : undefined
            }
          />
        )
      })}
      {onEdit && (
        <button
          type="button"
          onClick={onEdit}
          data-testid="edit-tx-labels"
          title={t.labels.editTransactionLabels}
          aria-label={t.labels.editTransactionLabels}
          className="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-300 px-2 py-0.5 text-xs text-gray-500 transition-colors hover:border-gray-400 hover:text-gray-700 dark:border-gray-600 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <Tag className="h-3 w-3" />
          {txLabels.length || compact ? null : t.labels.addLabel}
        </button>
      )}
    </div>
  )
}
