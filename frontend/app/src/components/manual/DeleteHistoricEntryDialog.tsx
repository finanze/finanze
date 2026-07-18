import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Label } from "@/components/ui/Label"
import { HistoricTxDeletion } from "@/types/historic"
import { deleteManualHistoricEntry } from "@/services/api"

export interface DeleteHistoricEntryDialogProps {
  isOpen: boolean
  onClose: () => void
  entryId: string
  hasRelatedTxs: boolean
  onSubmitted: () => void
}

export function DeleteHistoricEntryDialog({
  isOpen,
  onClose,
  entryId,
  hasRelatedTxs,
  onSubmitted,
}: DeleteHistoricEntryDialogProps) {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const dt = t.management.manualPositions.deleteHistoric

  const [txDeletion, setTxDeletion] = useState<HistoricTxDeletion>(
    HistoricTxDeletion.NONE,
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  const options: [HistoricTxDeletion, string, string][] = [
    [HistoricTxDeletion.NONE, dt.keepTxs, dt.keepTxsHint],
    [HistoricTxDeletion.SETTLEMENT, dt.settlementTxs, dt.settlementTxsHint],
    [HistoricTxDeletion.ALL, dt.allTxs, dt.allTxsHint],
  ]

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await deleteManualHistoricEntry(entryId, txDeletion)
      showToast(dt.success, "success")
      onSubmitted()
      onClose()
    } catch (e) {
      console.error("Delete historic entry failed", e)
      showToast(dt.error, "error")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center pt-10 px-4 pb-4 z-[18000]"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-md"
            onClick={e => e.stopPropagation()}
          >
            <Card className="max-h-[calc(100vh-5rem)] flex flex-col">
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <CardTitle className="text-xl">{dt.title}</CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  disabled={isSubmitting}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4 flex-1 overflow-y-auto">
                <p className="text-sm text-muted-foreground">
                  {dt.description}
                </p>
                {hasRelatedTxs && (
                  <div className="space-y-2">
                    <Label>{dt.txHandling}</Label>
                    {options.map(([value, label, hint]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTxDeletion(value)}
                        className={`w-full text-left rounded-md border p-3 transition-colors ${
                          txDeletion === value
                            ? "border-primary bg-primary/5"
                            : "border-border hover:bg-muted/50"
                        }`}
                      >
                        <div className="font-medium text-sm">{label}</div>
                        <div className="text-xs text-muted-foreground">
                          {hint}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
              <CardFooter className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={onClose}
                  disabled={isSubmitting}
                >
                  {t.common.cancel}
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                >
                  {dt.confirm}
                </Button>
              </CardFooter>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
