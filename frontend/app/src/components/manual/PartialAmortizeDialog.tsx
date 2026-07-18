import { useState, useMemo } from "react"
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
import { DecimalInput } from "@/components/ui/DecimalInput"
import { Label } from "@/components/ui/Label"
import { DatePicker } from "@/components/ui/DatePicker"
import { Switch } from "@/components/ui/Switch"
import { getCurrencySymbol } from "@/lib/utils"
import { ProductType } from "@/types/position"
import { partialAmortizeManualInvestment } from "@/services/api"

type TaxMode = "percent" | "amount"

const TAX_PRESETS = [19, 26, 33]

export interface PartialAmortizeDialogProps {
  isOpen: boolean
  onClose: () => void
  entityId: string
  entryId: string
  productType: ProductType
  currency: string
  onSubmitted: () => void
}

export function PartialAmortizeDialog({
  isOpen,
  onClose,
  entityId,
  entryId,
  productType,
  currency,
  onSubmitted,
}: PartialAmortizeDialogProps) {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const at = t.management.manualPositions.amortize
  const st = t.management.manualPositions.settle

  const today = new Date().toISOString().slice(0, 10)
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState<string>(today)
  const [interests, setInterests] = useState<number | null>(0)
  const [fees, setFees] = useState<number | null>(0)
  const [taxMode, setTaxMode] = useState<TaxMode>("percent")
  const [taxPercent, setTaxPercent] = useState<number | null>(0)
  const [taxAmount, setTaxAmount] = useState<number | null>(0)
  const [createInvestmentTx, setCreateInvestmentTx] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const symbol = getCurrencySymbol(currency)

  const resolvedRetentions = useMemo<number>(() => {
    if (taxMode === "amount") return taxAmount ?? 0
    return Number(((interests ?? 0) * ((taxPercent ?? 0) / 100)).toFixed(2))
  }, [taxMode, taxAmount, taxPercent, interests])

  const handleSubmit = async () => {
    if (!amount || amount <= 0) {
      showToast(at.invalidAmount, "error")
      return
    }
    setIsSubmitting(true)
    try {
      await partialAmortizeManualInvestment({
        entity_id: entityId,
        entry_id: entryId,
        product_type: productType,
        amount,
        date,
        interests: interests ?? 0,
        fees: fees ?? 0,
        retentions: resolvedRetentions,
        create_investment_tx: createInvestmentTx,
      })
      showToast(at.success, "success")
      onSubmitted()
      onClose()
    } catch (e) {
      console.error("Partial amortize failed", e)
      showToast(at.error, "error")
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
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-md"
          >
            <Card className="max-h-[calc(100vh-5rem)] flex flex-col">
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <CardTitle className="text-xl">{at.title}</CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  disabled={isSubmitting}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-5 flex-1 overflow-y-auto">
                <div className="space-y-2">
                  <Label>
                    {at.amount} <span className="text-red-500">*</span>
                  </Label>
                  <DecimalInput
                    value={amount}
                    onValueChange={setAmount}
                    placeholder="0.00"
                    prefix={symbol}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{at.date}</Label>
                  <DatePicker value={date} onChange={setDate} />
                </div>
                <div className="space-y-2">
                  <Label>{at.interests}</Label>
                  <DecimalInput
                    value={interests}
                    onValueChange={setInterests}
                    placeholder="0.00"
                    prefix={symbol}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{st.taxes}</Label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant={taxMode === "percent" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setTaxMode("percent")}
                    >
                      {st.taxModes.percent}
                    </Button>
                    <Button
                      type="button"
                      variant={taxMode === "amount" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setTaxMode("amount")}
                    >
                      {st.taxModes.amount}
                    </Button>
                  </div>
                  {taxMode === "percent" ? (
                    <div className="space-y-1">
                      <div className="flex flex-wrap gap-2">
                        {TAX_PRESETS.map(preset => (
                          <Button
                            key={preset}
                            type="button"
                            variant={
                              taxPercent === preset ? "default" : "outline"
                            }
                            size="sm"
                            onClick={() => setTaxPercent(preset)}
                          >
                            {preset}%
                          </Button>
                        ))}
                        <div className="w-24">
                          <DecimalInput
                            value={taxPercent}
                            onValueChange={setTaxPercent}
                            placeholder="0"
                            className="h-8"
                            suffix="%"
                          />
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {st.resolvedRetentions.replace(
                          "{amount}",
                          `${symbol}${resolvedRetentions.toFixed(2)}`,
                        )}
                      </p>
                    </div>
                  ) : (
                    <DecimalInput
                      value={taxAmount}
                      onValueChange={setTaxAmount}
                      placeholder="0.00"
                      prefix={symbol}
                    />
                  )}
                </div>
                <div className="space-y-2">
                  <Label>{at.fees}</Label>
                  <DecimalInput
                    value={fees}
                    onValueChange={setFees}
                    placeholder="0.00"
                    prefix={symbol}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Switch
                    id="amortize_create_investment_tx"
                    checked={createInvestmentTx}
                    onCheckedChange={setCreateInvestmentTx}
                  />
                  <Label
                    htmlFor="amortize_create_investment_tx"
                    className="cursor-pointer text-sm"
                  >
                    {st.createInvestmentTx}
                  </Label>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={onClose}
                  disabled={isSubmitting}
                >
                  {t.common.cancel}
                </Button>
                <Button onClick={handleSubmit} disabled={isSubmitting}>
                  {at.confirm}
                </Button>
              </CardFooter>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
