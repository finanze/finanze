import { useMemo, useState } from "react"
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
import { getCurrencySymbol, cn } from "@/lib/utils"
import { ProductType } from "@/types/position"
import { settleManualInvestment } from "@/services/api"

type InterestMode = "default" | "amount" | "rate" | "gain"
type TaxMode = "percent" | "amount"

const TAX_PRESETS = [19, 26, 33]

export interface SettleManualInvestmentDialogProps {
  isOpen: boolean
  onClose: () => void
  entityId: string
  entryId: string
  productType: ProductType
  investedAmount: number
  currency: string
  startDate?: string | null
  defaultInterests: number
  onSubmitted: () => void
}

function daysBetween(start?: string | null, end?: string | null): number {
  if (!start || !end) return 0
  const s = new Date(start).getTime()
  const e = new Date(end).getTime()
  if (Number.isNaN(s) || Number.isNaN(e)) return 0
  const diff = Math.round((e - s) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
}

export function SettleManualInvestmentDialog({
  isOpen,
  onClose,
  entityId,
  entryId,
  productType,
  investedAmount,
  currency,
  startDate,
  defaultInterests,
  onSubmitted,
}: SettleManualInvestmentDialogProps) {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const st = t.management.manualPositions.settle

  const today = new Date().toISOString().slice(0, 10)

  const [maturity, setMaturity] = useState<string>(today)
  const [interestMode, setInterestMode] = useState<InterestMode>("default")
  const [interestAmount, setInterestAmount] = useState<number | null>(null)
  const [interestRate, setInterestRate] = useState<number | null>(null)
  const [interestGain, setInterestGain] = useState<number | null>(null)

  const [taxMode, setTaxMode] = useState<TaxMode>("percent")
  const [taxPercent, setTaxPercent] = useState<number | null>(0)
  const [taxAmount, setTaxAmount] = useState<number | null>(0)
  const [fees, setFees] = useState<number | null>(0)
  const [pendingCapital, setPendingCapital] = useState<number | null>(0)
  const [createInvestmentTx, setCreateInvestmentTx] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const symbol = getCurrencySymbol(currency)

  const repaidCapital = useMemo<number>(() => {
    const value = investedAmount - (pendingCapital ?? 0)
    return value > 0 ? value : 0
  }, [investedAmount, pendingCapital])

  const defaultInterestsForRepaid = useMemo<number>(() => {
    if (investedAmount <= 0) return defaultInterests
    return Number(
      (defaultInterests * (repaidCapital / investedAmount)).toFixed(2),
    )
  }, [defaultInterests, repaidCapital, investedAmount])

  const resolvedInterests = useMemo<number | null>(() => {
    switch (interestMode) {
      case "amount":
        return interestAmount ?? 0
      case "gain":
        return Number((repaidCapital * ((interestGain ?? 0) / 100)).toFixed(2))
      case "rate": {
        const days = daysBetween(startDate, maturity)
        const rate = (interestRate ?? 0) / 100
        return Number((repaidCapital * rate * (days / 365)).toFixed(2))
      }
      default:
        return null
    }
  }, [
    interestMode,
    interestAmount,
    interestGain,
    interestRate,
    startDate,
    maturity,
    repaidCapital,
  ])

  const baseInterests = resolvedInterests ?? defaultInterestsForRepaid

  const resolvedRetentions = useMemo<number>(() => {
    if (taxMode === "amount") return taxAmount ?? 0
    return Number((baseInterests * ((taxPercent ?? 0) / 100)).toFixed(2))
  }, [taxMode, taxAmount, taxPercent, baseInterests])

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await settleManualInvestment({
        entity_id: entityId,
        entry_id: entryId,
        product_type: productType,
        maturity,
        interests: resolvedInterests,
        fees: fees ?? 0,
        retentions: resolvedRetentions,
        pending_capital: pendingCapital ?? 0,
        create_investment_tx: createInvestmentTx,
      })
      showToast(st.success, "success")
      onSubmitted()
      onClose()
    } catch (e) {
      console.error("Settle manual investment failed", e)
      showToast(st.error, "error")
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
            className="w-full max-w-lg"
          >
            <Card className="max-h-[calc(100vh-5rem)] flex flex-col">
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <CardTitle className="text-xl">{st.title}</CardTitle>
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
                  <Label>{st.maturity}</Label>
                  <DatePicker value={maturity} onChange={setMaturity} />
                </div>

                <div className="space-y-2">
                  <Label>{st.interests}</Label>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ["default", st.interestModes.default],
                        ["amount", st.interestModes.amount],
                        ["rate", st.interestModes.rate],
                        ["gain", st.interestModes.gain],
                      ] as [InterestMode, string][]
                    ).map(([value, label]) => (
                      <Button
                        key={value}
                        type="button"
                        variant={interestMode === value ? "default" : "outline"}
                        size="sm"
                        onClick={() => setInterestMode(value)}
                      >
                        {label}
                      </Button>
                    ))}
                  </div>
                  {interestMode === "default" && (
                    <p className="text-sm text-muted-foreground">
                      {st.defaultInterestsHint.replace(
                        "{amount}",
                        `${symbol}${defaultInterestsForRepaid.toFixed(2)}`,
                      )}
                    </p>
                  )}
                  {interestMode === "amount" && (
                    <DecimalInput
                      value={interestAmount}
                      onValueChange={setInterestAmount}
                      placeholder="0.00"
                      prefix={symbol}
                    />
                  )}
                  {interestMode === "gain" && (
                    <div className="space-y-1">
                      <DecimalInput
                        value={interestGain}
                        onValueChange={setInterestGain}
                        placeholder="0.00"
                        suffix="%"
                      />
                      <p className="text-sm text-muted-foreground">
                        {st.resolvedInterests.replace(
                          "{amount}",
                          `${symbol}${(resolvedInterests ?? 0).toFixed(2)}`,
                        )}
                      </p>
                    </div>
                  )}
                  {interestMode === "rate" && (
                    <div className="space-y-1">
                      <DecimalInput
                        value={interestRate}
                        onValueChange={setInterestRate}
                        placeholder="0.00"
                        suffix="%"
                      />
                      <p className="text-sm text-muted-foreground">
                        {st.resolvedInterests.replace(
                          "{amount}",
                          `${symbol}${(resolvedInterests ?? 0).toFixed(2)}`,
                        )}
                      </p>
                    </div>
                  )}
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
                  <Label>{st.fees}</Label>
                  <DecimalInput
                    value={fees}
                    onValueChange={setFees}
                    placeholder="0.00"
                    prefix={symbol}
                  />
                </div>

                <div className="space-y-2">
                  <Label>{st.pendingCapital}</Label>
                  <DecimalInput
                    value={pendingCapital}
                    onValueChange={setPendingCapital}
                    placeholder="0.00"
                    prefix={symbol}
                  />
                  <p
                    className={cn(
                      "text-sm text-muted-foreground",
                      (pendingCapital ?? 0) > 0 && "text-amber-500",
                    )}
                  >
                    {(pendingCapital ?? 0) > 0
                      ? st.willDefault
                      : st.willComplete}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Switch
                    id="settle_create_investment_tx"
                    checked={createInvestmentTx}
                    onCheckedChange={setCreateInvestmentTx}
                  />
                  <Label
                    htmlFor="settle_create_investment_tx"
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
                  {st.confirm}
                </Button>
              </CardFooter>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
