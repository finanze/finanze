import React, { useMemo, useState } from "react"
import { useI18n } from "@/i18n"
import { Card } from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { formatCurrency } from "@/lib/formatters"
import type {
  RealEstateFlow,
  RealEstateFlowSubtype,
  LoanPayload,
  PurchaseExpense,
  FlowFrequency,
  PeriodicFlow,
} from "@/types"
import {
  Plus,
  Minus,
  Equal,
  TrendingUp,
  Calculator,
  Landmark,
  Info,
} from "lucide-react"

type Props = {
  currency: string
  isRented: boolean
  flows: RealEstateFlow[]
  purchasePrice: number
  purchaseExpenses: PurchaseExpense[]
  estimatedMarketValue: number
  marginalTaxRate?: number
  amortizationsAnnual?: { amount: number }[]
  onChangeMarginalTaxRate?: (value: number | undefined) => void
  cardClassName?: string
  vacancyRate?: number
}

export function RealEstateStats({
  currency,
  isRented,
  flows,
  purchasePrice,
  purchaseExpenses,
  estimatedMarketValue,
  marginalTaxRate,
  amortizationsAnnual,
  onChangeMarginalTaxRate,
  cardClassName,
  vacancyRate,
}: Props) {
  const { t, locale } = useI18n()
  const [annual, setAnnual] = useState(false)
  // Alias to avoid union key narrowing between locales for recently added keys
  const labelsAny = t.realEstate.labels as any

  const purchaseTotal = useMemo(() => {
    const expensesTotal = (purchaseExpenses || []).reduce(
      (s, e) => s + (e.amount || 0),
      0,
    )
    return (purchasePrice || 0) + expensesTotal
  }, [purchasePrice, purchaseExpenses])

  const totalFinanced = useMemo(() => {
    return (flows || [])
      .filter(f => f.flow_subtype === ("LOAN" as RealEstateFlowSubtype))
      .reduce(
        (sum, f) => sum + ((f.payload as LoanPayload)?.loan_amount || 0),
        0,
      )
  }, [flows])

  const totalOutstanding = useMemo(() => {
    return (flows || [])
      .filter(f => f.flow_subtype === ("LOAN" as RealEstateFlowSubtype))
      .reduce(
        (sum, f) =>
          sum + ((f.payload as LoanPayload)?.principal_outstanding || 0),
        0,
      )
  }, [flows])

  const capitalContributed = useMemo(
    () => purchaseTotal - totalFinanced,
    [purchaseTotal, totalFinanced],
  )

  const equity = useMemo(
    () => (estimatedMarketValue || 0) - (totalOutstanding || 0),
    [estimatedMarketValue, totalOutstanding],
  )

  const getMonthlyCost = (flow: PeriodicFlow | null | undefined) => {
    if (!flow) return 0
    let amount = flow.amount || 0
    switch (flow.frequency as FlowFrequency) {
      case "DAILY":
        amount = amount * 30
        break
      case "WEEKLY":
        amount = amount * 4.33
        break
      case "EVERY_TWO_MONTHS":
        amount = amount / 2
        break
      case "QUARTERLY":
        amount = amount / 3
        break
      case "EVERY_FOUR_MONTHS":
        amount = amount / 4
        break
      case "SEMIANNUALLY":
        amount = amount / 6
        break
      case "YEARLY":
        amount = amount / 12
        break
    }
    return amount
  }

  const monthlyCosts = useMemo(() => {
    return (flows || [])
      .filter(
        f =>
          f.flow_subtype === ("COST" as RealEstateFlowSubtype) ||
          f.flow_subtype === ("SUPPLY" as RealEstateFlowSubtype),
      )
      .reduce((sum, f) => {
        const pf = f.periodic_flow
        return sum + getMonthlyCost(pf)
      }, 0)
  }, [flows])

  // Gross rent income per month (sum of rents)
  const monthlyIncomeGross = useMemo(() => {
    return (flows || [])
      .filter(f => f.flow_subtype === ("RENT" as RealEstateFlowSubtype))
      .reduce((sum, f) => sum + (f.periodic_flow?.amount || 0), 0)
  }, [flows])
  // Apply vacancy rate if provided
  const monthlyIncome = useMemo(() => {
    const rate = vacancyRate ?? 0
    const adj = Math.max(0, 1 - rate)
    return monthlyIncomeGross * adj
  }, [monthlyIncomeGross, vacancyRate])

  const monthlyLoanPayments = useMemo(() => {
    return (flows || [])
      .filter(f => f.flow_subtype === ("LOAN" as RealEstateFlowSubtype))
      .reduce((sum, f) => sum + (f.periodic_flow?.amount || 0), 0)
  }, [flows])

  // Monthly interests only (sum of loan interests if available)
  const monthlyLoanInterests = useMemo(() => {
    return (flows || [])
      .filter(f => f.flow_subtype === ("LOAN" as RealEstateFlowSubtype))
      .reduce((sum, f) => {
        const payload = f.payload as LoanPayload
        return sum + (payload?.monthly_interests || 0)
      }, 0)
  }, [flows])

  const monthlyTaxDeductibleRaw = useMemo(() => {
    const flowCosts = (flows || [])
      .filter(
        f =>
          f.flow_subtype === ("COST" as RealEstateFlowSubtype) ||
          f.flow_subtype === ("SUPPLY" as RealEstateFlowSubtype),
      )
      .reduce((sum, f) => {
        if ((f.payload as any)?.tax_deductible ?? false) {
          return sum + getMonthlyCost(f.periodic_flow)
        }
        return sum
      }, 0)

    const loanInterests = (flows || [])
      .filter(f => f.flow_subtype === ("LOAN" as RealEstateFlowSubtype))
      .reduce((sum, f) => {
        const payload = f.payload as LoanPayload
        if (payload?.monthly_interests) return sum + payload.monthly_interests
        return sum
      }, 0)
    // Annual amortizations reduce taxable base; convert to monthly equivalent
    const monthlyAmorts = (amortizationsAnnual || []).reduce(
      (s, a) => s + (a.amount || 0) / 12,
      0,
    )
    return flowCosts + loanInterests + monthlyAmorts
  }, [flows, amortizationsAnnual])

  // Deductible cannot exceed taxable base; taxable cannot be negative
  const taxableBaseMonthly = useMemo(() => {
    const base = monthlyIncome
    return Math.max(0, base)
  }, [monthlyIncome])

  const monthlyTaxDeductible = useMemo(() => {
    return Math.min(monthlyTaxDeductibleRaw, taxableBaseMonthly)
  }, [monthlyTaxDeductibleRaw, taxableBaseMonthly])

  const totalMonthlyPayments = useMemo(
    () => monthlyCosts + monthlyLoanPayments,
    [monthlyCosts, monthlyLoanPayments],
  )
  const netMonthlyProfit = useMemo(
    () => monthlyIncome - totalMonthlyPayments,
    [monthlyIncome, totalMonthlyPayments],
  )
  const taxesAnnual = useMemo(() => {
    const taxableMonthly = Math.max(0, monthlyIncome - monthlyTaxDeductible)
    return taxableMonthly * 12 * (marginalTaxRate ?? 0)
  }, [monthlyIncome, monthlyTaxDeductible, marginalTaxRate])
  const profitAfterTaxAnnual = useMemo(
    () => netMonthlyProfit * 12 - taxesAnnual,
    [netMonthlyProfit, taxesAnnual],
  )

  // Break-even: months to recover invested capital (use NET cashflow: after-tax if available)
  const netAfterTaxMonthly = useMemo(() => {
    return profitAfterTaxAnnual / 12
  }, [profitAfterTaxAnnual])
  const breakEvenMonths = useMemo(() => {
    if (!capitalContributed || capitalContributed <= 0) return undefined
    const ref =
      typeof marginalTaxRate !== "undefined"
        ? netAfterTaxMonthly
        : netMonthlyProfit
    if (!ref || ref <= 0) return undefined
    return capitalContributed / ref
  }, [
    capitalContributed,
    netAfterTaxMonthly,
    netMonthlyProfit,
    marginalTaxRate,
  ])
  const breakEvenYears = useMemo(() => {
    if (!breakEvenMonths) return undefined
    return breakEvenMonths / 12
  }, [breakEvenMonths])

  // ---- Calculators (extracted helpers) ----
  const calcROI = (
    totalPurchase: number,
    monthlyInc: number,
    monthlyCost: number,
  ) => {
    const denom = totalPurchase || 1
    return (((monthlyInc - monthlyCost) * 12) / denom) * 100
  }

  const calcCoC = (employedCapital: number, monthlyNet: number) => {
    if (!employedCapital || employedCapital <= 0) return undefined
    return ((monthlyNet * 12) / employedCapital) * 100
  }

  // Total Return (CoC + Amortization): exclude only loan interests from costs
  const calcTotalReturn = (
    employedCapital: number,
    monthlyInc: number,
    monthlyCost: number,
    monthlyLoanInt: number,
  ) => {
    if (!employedCapital || employedCapital <= 0) return undefined
    const annual = (monthlyInc - monthlyCost - monthlyLoanInt) * 12
    return (annual / employedCapital) * 100
  }

  // Net CoC: after-tax annual profit divided by employed capital
  const calcNetCoC = (employedCapital: number, afterTaxAnnual: number) => {
    if (!employedCapital || employedCapital <= 0) return undefined
    return (afterTaxAnnual / employedCapital) * 100
  }

  return (
    <Card
      className={
        cardClassName ??
        "p-4 border-gray-200 bg-gray-50 dark:bg-gray-900 dark:border-gray-700"
      }
    >
      <h4 className="font-medium mb-3">{t.realEstate.summary}</h4>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <span className="text-gray-600 dark:text-gray-400">
            {t.realEstate.labels.totalPurchaseCost}:
          </span>
          <div className="font-medium">
            {formatCurrency(purchaseTotal, locale, currency)}
          </div>
        </div>
        <div>
          <span className="text-gray-600 dark:text-gray-400">
            {t.realEstate.labels.estimatedValue}:
          </span>
          <div className="font-medium">
            {formatCurrency(estimatedMarketValue || 0, locale, currency)}
          </div>
        </div>
        <div>
          <span className="text-gray-600 dark:text-gray-400">
            {t.realEstate.labels.equity}:
          </span>
          <div className="font-medium">
            {formatCurrency(equity || 0, locale, currency)}
          </div>
        </div>
        <div>
          <span className="text-gray-600 dark:text-gray-400">
            {t.realEstate.loans.capitalContributed}:
          </span>
          <div className="font-medium">
            {formatCurrency(capitalContributed, locale, currency)}
          </div>
        </div>
        <div>
          <span className="text-gray-600 dark:text-gray-400">
            {t.realEstate.loans.totalFinanced}:
          </span>
          <div className="font-medium">
            {formatCurrency(totalFinanced, locale, currency)}
          </div>
        </div>
      </div>

      {!isRented ? (
        <div className="border-t pt-4 mb-2">
          <div className="mb-3 p-3 bg-red-50 dark:bg-red-900/10 rounded-lg">
            <div className="flex justify-between items-center">
              <span className="text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
                {t.realEstate.labels.totalMonthlyExpenses}
              </span>
              <span className="font-medium text-red-600 text-lg">
                {formatCurrency(totalMonthlyPayments, locale, currency)}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="border-t pt-4 mb-4">
            <div className="flex justify-between items-center mb-3">
              <h5 className="font-medium text-gray-900 dark:text-white">
                {t.realEstate.analysis.profitabilityAnalysis}
              </h5>
              <div className="flex items-center gap-1 bg-gray-200 dark:bg-gray-700 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => setAnnual(false)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${!annual ? "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm" : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"}`}
                >
                  {t.realEstate.analysis.monthly}
                </button>
                <button
                  type="button"
                  onClick={() => setAnnual(true)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${annual ? "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm" : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"}`}
                >
                  {t.realEstate.analysis.annual}
                </button>
              </div>
            </div>

            <div className="mb-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <div className="flex justify-between items-center">
                <span className="text-sm text-green-700 dark:text-green-300 flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  {annual
                    ? t.realEstate.labels.annualIncome
                    : t.realEstate.labels.monthlyIncome}
                </span>
                <span className="font-medium text-green-600 text-lg">
                  {formatCurrency(
                    annual ? monthlyIncome * 12 : monthlyIncome,
                    locale,
                    currency,
                  )}
                </span>
              </div>
            </div>

            <div className="mb-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <div className="flex justify-between items-center">
                <span className="text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
                  <Minus className="h-4 w-4" />
                  {annual
                    ? t.realEstate.labels.annualExpenses
                    : t.realEstate.labels.totalMonthlyExpenses}
                </span>
                <span className="font-medium text-red-600 text-lg">
                  {formatCurrency(
                    annual ? totalMonthlyPayments * 12 : totalMonthlyPayments,
                    locale,
                    currency,
                  )}
                </span>
              </div>
              <div className="text-xs text-red-600 dark:text-red-400 mt-1 flex justify-end">
                <span>
                  {t.realEstate.labels.taxDeductible}:{" "}
                  {formatCurrency(
                    annual ? monthlyTaxDeductible * 12 : monthlyTaxDeductible,
                    locale,
                    currency,
                  )}
                </span>
              </div>
            </div>

            <div className="border-t pt-2 mb-1 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="flex justify-between items-center">
                <span className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                  <Equal className="h-4 w-4" />
                  {annual
                    ? t.realEstate.analysis.annualCashflow
                    : t.realEstate.analysis.monthlyCashflow}
                </span>
                <span
                  className={`font-bold text-lg ${netMonthlyProfit >= 0 ? "text-green-600" : "text-red-600"}`}
                >
                  {formatCurrency(
                    annual ? netMonthlyProfit * 12 : netMonthlyProfit,
                    locale,
                    currency,
                  )}
                </span>
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 flex justify-end">
                <span>
                  {t.realEstate.labels.taxableAmount}:{" "}
                  {formatCurrency(
                    annual
                      ? Math.max(0, monthlyIncome - monthlyTaxDeductible) * 12
                      : Math.max(0, monthlyIncome - monthlyTaxDeductible),
                    locale,
                    currency,
                  )}
                </span>
              </div>
            </div>
            {/* space before KPI cards */}
            <div className="mb-4" />

            <div className="grid grid-cols-2 gap-4 text-sm mb-4">
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-blue-700 dark:text-blue-300 flex items-center gap-2 font-medium">
                    <TrendingUp className="h-4 w-4" />
                    {t.realEstate.labels.roi}
                  </span>
                  <div className="font-bold text-lg text-blue-600 dark:text-blue-400">
                    {calcROI(
                      purchaseTotal,
                      monthlyIncome,
                      monthlyCosts,
                    )?.toFixed(2)}
                    %
                  </div>
                </div>
                <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                  {t.realEstate.labels.roiDescription}
                </div>
              </div>
              <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-purple-700 dark:text-purple-300 flex items-center gap-2 font-medium">
                    <Calculator className="h-4 w-4" />
                    {t.realEstate.labels.coc}
                    {capitalContributed <= 0 && (
                      <Popover>
                        <PopoverTrigger asChild>
                          <span
                            className="ml-1 inline-flex items-center cursor-help align-middle"
                            aria-label={t.common.viewDetails}
                            title={t.common.viewDetails}
                          >
                            <Info className="h-3.5 w-3.5 opacity-70 hover:opacity-100" />
                          </span>
                        </PopoverTrigger>
                        <PopoverContent className="w-80 text-xs">
                          {t.realEstate.popovers.cocNotApplicable}
                        </PopoverContent>
                      </Popover>
                    )}
                  </span>
                  <div
                    className={`font-bold text-lg ${capitalContributed > 0 ? (netMonthlyProfit >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400") : "text-gray-500"}`}
                  >
                    {capitalContributed > 0
                      ? `${calcCoC(capitalContributed, netMonthlyProfit)!.toFixed(2)}%`
                      : t.common.notAvailable}
                  </div>
                </div>
                <div className="text-xs text-purple-600 dark:text-purple-400 mt-1">
                  {t.realEstate.labels.cocDescription}
                </div>
              </div>
              {/* Total Return (CoC + Amortization) */}
              <div className="p-3 bg-teal-50 dark:bg-teal-900/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-teal-700 dark:text-teal-300 flex items-center gap-2 font-medium">
                    <Calculator className="h-4 w-4" />
                    {t.realEstate.labels.totalReturn}
                  </span>
                  <div
                    className={`font-bold text-lg ${capitalContributed > 0 ? "text-teal-600 dark:text-teal-400" : "text-gray-500"}`}
                  >
                    {capitalContributed > 0
                      ? `${calcTotalReturn(
                          capitalContributed,
                          monthlyIncome,
                          monthlyCosts,
                          monthlyLoanInterests,
                        )!.toFixed(2)}%`
                      : t.common.notAvailable}
                  </div>
                </div>
                <div className="text-xs text-teal-600 dark:text-teal-400 mt-1">
                  {t.realEstate.labels.totalReturnDescription}
                </div>
              </div>
              {/* ROE (always based on annual net cashflow before taxes) */}
              <div className="p-3 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-indigo-700 dark:text-indigo-300 flex items-center gap-2 font-medium">
                    <TrendingUp className="h-4 w-4" />
                    {t.realEstate.labels.roe}
                  </span>
                  <div
                    className={`font-bold text-lg ${equity > 0 ? "text-indigo-600 dark:text-indigo-400" : "text-gray-500"}`}
                  >
                    {equity > 0
                      ? `${(((netMonthlyProfit * 12) / equity) * 100).toFixed(2)}%`
                      : t.common.notAvailable}
                  </div>
                </div>
                <div className="text-xs text-indigo-600 dark:text-indigo-400 mt-1">
                  {t.realEstate.labels.roeDescription}
                </div>
              </div>
              {/* Net CoC (after tax) - show only if marginal tax rate is provided */}
              {typeof marginalTaxRate !== "undefined" && (
                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-amber-700 dark:text-amber-300 flex items-center gap-2 font-medium">
                      <Calculator className="h-4 w-4" />
                      {t.realEstate.labels.netCoC}
                    </span>
                    <div
                      className={`font-bold text-lg ${capitalContributed > 0 ? (profitAfterTaxAnnual >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400") : "text-gray-500"}`}
                    >
                      {capitalContributed > 0
                        ? `${calcNetCoC(capitalContributed, profitAfterTaxAnnual)!.toFixed(2)}%`
                        : t.common.notAvailable}
                    </div>
                  </div>
                  <div className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                    {t.realEstate.labels.netCoCDescription}
                  </div>
                </div>
              )}
            </div>

            {(() => {
              // Show fiscal section if editing (onChange provided) and it's rented, even if marginalTaxRate is undefined.
              // In read-only, show only when marginalTaxRate is provided.
              const showSection = onChangeMarginalTaxRate
                ? isRented
                : typeof marginalTaxRate !== "undefined"
              return showSection
            })() && (
              <div className="border-t pt-4">
                <h5 className="font-medium mb-3 text-gray-900 dark:text-white">
                  {t.realEstate.analysis.fiscalEstimation}
                </h5>
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label className="m-0">
                      {t.realEstate.labels.marginalTaxRate}
                    </Label>
                    {onChangeMarginalTaxRate ? (
                      <div className="relative w-28">
                        <Input
                          type="number"
                          min="0"
                          max="99"
                          step="0.1"
                          value={
                            marginalTaxRate ? String(marginalTaxRate * 100) : ""
                          }
                          onChange={e => {
                            const value = e.target.value
                            if (!onChangeMarginalTaxRate) return
                            if (value === "") {
                              onChangeMarginalTaxRate(undefined)
                            } else {
                              const numValue = parseFloat(value)
                              if (!isNaN(numValue)) {
                                onChangeMarginalTaxRate(numValue / 100)
                              }
                            }
                          }}
                          placeholder={t.realEstate.placeholders.example24}
                          className="pr-8 h-8 text-sm"
                        />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 text-xs">
                          %
                        </span>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-700 dark:text-gray-300">
                        {marginalTaxRate !== undefined
                          ? `${(marginalTaxRate * 100).toFixed(2)}%`
                          : t.common.notAvailable}
                      </div>
                    )}
                  </div>
                  {marginalTaxRate ? (
                    <div className="text-sm space-y-2">
                      <div className="flex justify-between py-2 px-3 bg-orange-50 dark:bg-orange-900/20 rounded">
                        <span className="text-orange-700 dark:text-orange-300 flex items-center gap-2">
                          <Landmark className="h-4 w-4" />
                          {annual
                            ? t.realEstate.labels.estimatedAnnualTax
                            : t.realEstate.labels.estimatedMonthlyTax}
                        </span>
                        <span className="font-medium text-orange-600">
                          {formatCurrency(
                            annual ? taxesAnnual : taxesAnnual / 12,
                            locale,
                            currency,
                          )}
                        </span>
                      </div>
                      <div className="border-t pt-2 mb-2 p-3 bg-green-50 dark:bg-green-900/20 rounded">
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                            <Calculator className="h-4 w-4" />
                            {annual
                              ? t.realEstate.analysis.profitAfterTaxes
                              : t.realEstate.analysis.monthlyAfterTaxProfit}
                          </span>
                          <span
                            className={`font-bold text-lg ${profitAfterTaxAnnual >= 0 ? "text-green-600" : "text-red-600"}`}
                          >
                            {formatCurrency(
                              annual
                                ? profitAfterTaxAnnual
                                : profitAfterTaxAnnual / 12,
                              locale,
                              currency,
                            )}
                          </span>
                        </div>
                        {/* Break-even (discreet) under NET cashflow */}
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 flex justify-end">
                          <span className="inline-flex items-center gap-1">
                            {labelsAny.breakEven}{" "}
                            {breakEvenMonths ? (
                              `${Math.ceil(breakEvenMonths)} ${labelsAny.months} (~${(breakEvenYears as number).toFixed(1)} ${labelsAny.years})`
                            ) : (
                              <>
                                {t.common.notAvailable}
                                {capitalContributed <= 0 && (
                                  <Popover>
                                    <PopoverTrigger asChild>
                                      <span
                                        className="ml-1 inline-flex items-center cursor-help align-middle"
                                        aria-label={t.common.viewDetails}
                                        title={t.common.viewDetails}
                                      >
                                        <Info className="h-3.5 w-3.5 opacity-70 hover:opacity-100" />
                                      </span>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-80 text-xs">
                                      {
                                        t.realEstate.popovers
                                          .breakEvenNotApplicable
                                      }
                                    </PopoverContent>
                                  </Popover>
                                )}
                              </>
                            )}
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {t.realEstate.analysis.loanInterestNote}
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </Card>
  )
}

export default RealEstateStats
