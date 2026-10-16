import { useEffect, useState } from "react"
import {
  ArrowLeftRight,
  Link2,
  Loader2,
  Lock,
  Save,
  Wand2,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Switch } from "@/components/ui/Switch"
import { Sensitive } from "@/components/ui/Sensitive"
import { updateTransactionLabels } from "@/services/api"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { TxType, type AccountTx } from "@/types/transactions"
import { LabelingModal } from "./LabelingModal"
import { LabelSelector } from "./LabelSelector"

export type LabelableTx = Pick<
  AccountTx,
  | "id"
  | "name"
  | "amount"
  | "currency"
  | "type"
  | "date"
  | "counterparty"
  | "labels"
  | "labels_locked"
  | "linked_tx"
  | "transfer_pair"
  | "entity"
>

interface TransactionLabelsDialogProps {
  isOpen: boolean
  tx: LabelableTx | null
  onClose: () => void
  onSaved: () => void
  onCreateRule?: (tx: LabelableTx) => void
}

export function TransactionLabelsDialog({
  isOpen,
  tx,
  onClose,
  onSaved,
  onCreateRule,
}: TransactionLabelsDialogProps) {
  const { t, locale } = useI18n()
  const { showToast, settings, entities } = useAppContext()
  const [selected, setSelected] = useState<string[]>([])
  const [locked, setLocked] = useState(true)
  const [unlink, setUnlink] = useState(false)
  const [unpair, setUnpair] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isOpen || !tx) return
    setSelected((tx.labels ?? []).map(label => label.label_id))
    setLocked(true)
    setUnlink(false)
    setUnpair(false)
  }, [isOpen, tx])

  const handleClose = () => {
    if (saving) return
    onClose()
  }

  const incoming = tx?.type === TxType.INFLOW || tx?.type === TxType.INTEREST
  const forcedLock = unlink || unpair
  const pairEntity = tx?.transfer_pair
    ? ((entities ?? []).find(
        entity => entity.id === tx.transfer_pair?.entity_id,
      )?.name ?? t.labels.transferPairOtherEntity)
    : null

  const handleSave = async () => {
    if (!tx) return
    setSaving(true)
    try {
      await updateTransactionLabels(tx.id, {
        labels: selected,
        locked,
        unlink,
        unpair,
      })
      showToast(t.labels.transactionLabelsSaved, "success")
      onSaved()
    } catch (error) {
      console.error("Error updating transaction labels:", error)
      showToast(t.labels.saveError, "error")
    } finally {
      setSaving(false)
    }
  }

  return (
    <LabelingModal
      isOpen={isOpen && tx !== null}
      title={t.labels.editTransactionLabels}
      onClose={handleClose}
      testId="tx-labels-dialog"
      footer={
        <>
          {onCreateRule && tx && (
            <Button
              variant="ghost"
              size="sm"
              className="mr-auto gap-1.5"
              onClick={() => onCreateRule(tx)}
              disabled={saving}
            >
              <Wand2 className="h-4 w-4" />
              {t.labels.createRuleFromMovement}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={saving}
            aria-label={t.common.cancel}
            title={t.common.cancel}
            className="h-9 w-9 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            aria-label={saving ? t.common.saving : t.common.save}
            title={saving ? t.common.saving : t.common.save}
            className="h-9 w-9 p-0"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
          </Button>
        </>
      }
    >
      {tx && (
        <>
          <div className="-mx-4 border-y border-border bg-muted/40 px-4 py-3 sm:mx-0 sm:rounded-md sm:border sm:px-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="break-words text-sm font-medium text-foreground">
                  {tx.name}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground">
                  <span>{formatDate(tx.date, locale)}</span>
                  <span>·</span>
                  <span>{tx.entity.name}</span>
                  {tx.counterparty && (
                    <>
                      <span>·</span>
                      <span className="break-all">{tx.counterparty}</span>
                    </>
                  )}
                </div>
              </div>
              <div
                className={cn(
                  "shrink-0 text-sm font-semibold tabular-nums",
                  incoming && "text-green-600 dark:text-green-400",
                )}
              >
                <Sensitive>
                  {incoming ? "+" : "-"}
                  {formatCurrency(
                    Math.abs(tx.amount),
                    locale,
                    settings.general.defaultCurrency,
                    tx.currency,
                  )}
                </Sensitive>
              </div>
            </div>
          </div>

          <LabelSelector
            value={selected}
            onChange={setSelected}
            disabled={saving}
          />

          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-2">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <div className="text-sm font-medium">{t.labels.lockLabels}</div>
                <p className="text-xs text-muted-foreground">
                  {t.labels.lockLabelsHint}
                </p>
              </div>
            </div>
            <Switch
              checked={locked || forcedLock}
              onCheckedChange={setLocked}
              disabled={saving || forcedLock}
              data-testid="lock-labels-switch"
            />
          </div>

          {tx.transfer_pair && pairEntity && (
            <div className="space-y-3 rounded-md border border-dashed border-sky-300 p-3 dark:border-sky-700">
              <div className="flex items-start gap-2 text-xs text-muted-foreground">
                <ArrowLeftRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-600 dark:text-sky-400" />
                <span>
                  {t.labels.transferPairHint.replace("{entity}", pairEntity)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium">
                    {t.labels.unpairTransfer}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t.labels.unpairTransferHint}
                  </p>
                </div>
                <Switch
                  checked={unpair}
                  onCheckedChange={setUnpair}
                  disabled={saving}
                  data-testid="unpair-transfer-switch"
                />
              </div>
            </div>
          )}

          {tx.linked_tx && (
            <div className="space-y-3 rounded-md border border-dashed border-border p-3">
              <div className="flex items-start gap-2 text-xs text-muted-foreground">
                <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{t.labels.settlementHint}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">
                  {t.labels.unlinkSettlement}
                </span>
                <Switch
                  checked={unlink}
                  onCheckedChange={setUnlink}
                  disabled={saving}
                />
              </div>
            </div>
          )}
        </>
      )}
    </LabelingModal>
  )
}
