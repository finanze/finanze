import { useId, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import {
  AlertTriangle,
  ArrowUpRight,
  ChevronDown,
  Info,
  PiggyBank,
  ShieldCheck,
  Sparkles,
  Tag,
  TrendingUp,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useLabels } from "@/context/LabelsContext"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Sensitive } from "@/components/ui/Sensitive"
import { getLabelColor, LabelChip } from "@/components/labels/LabelChip"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { formatCurrency } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { DataDisplayMode, FlowType } from "@/types"
import type { BudgetSummary } from "@/types/cashflow"

interface BudgetPerformanceProps {
  budget: BudgetSummary
  currency: string
  className?: string
  loading?: boolean
  onOpenBudget: () => void
  onLabelClick: (labelId: string, flowType: FlowType) => void
  onTargetClick: (section: "expenses" | "investments") => void
}

export function BudgetPerformance({
  budget,
  currency,
  className,
  loading,
  onOpenBudget,
  onLabelClick,
  onTargetClick,
}: BudgetPerformanceProps) {
  const { t, locale } = useI18n()
  const { getLabel, getLabelName } = useLabels()
  const { mode } = useDataDisplayMode()
  const [cardExpanded, setCardExpanded] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const detailsId = useId()
  const labelDetailsId = useId()
  const reducedMotion = useReducedMotion()
  const privateMode = mode === DataDisplayMode.PRIVATE
  const money = (value: number) => formatCurrency(value, locale, currency)
  const percent = (ratio: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 1,
    }).format(ratio)
  const month = (value: string) =>
    new Intl.DateTimeFormat(locale, { month: "short", year: "numeric" }).format(
      new Date(`${value}T00:00:00`),
    )
  const months =
    budget.from_month === budget.to_month
      ? month(budget.from_month)
      : `${month(budget.from_month)} - ${month(budget.to_month)}`
  const incomplete = budget.missing_conversion_count > 0
  const earnings = budget.income.actual
  const labelTargets = budget.by_label.filter(
    row =>
      row.label_id !== null &&
      row.flow_type === FlowType.EXPENSE &&
      row.comparison.expected > 0,
  )
  if (!budget.needs || !budget.wants) return null

  const metrics = [
    {
      key: "needs",
      title: t.cashflow.budget.needs,
      icon: ShieldCheck,
      comparison: budget.needs,
      color: "bg-sky-500",
    },
    {
      key: "wants",
      title: t.cashflow.budget.wants,
      icon: Sparkles,
      comparison: budget.wants,
      color: "bg-red-500",
    },
    {
      key: "invested",
      title: t.management.monthlyInvestedAmount,
      icon: TrendingUp,
      comparison: budget.invested,
      color: "bg-cyan-500",
    },
  ]
  return (
    <Card
      className={cn("overflow-hidden", className)}
      data-testid="cashflow-budget"
      aria-busy={loading}
    >
      <div className="flex items-center gap-2 px-4 hover:bg-muted/30">
        <button
          type="button"
          className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1 py-3 text-left"
          onClick={() => setCardExpanded(value => !value)}
          aria-expanded={cardExpanded}
          aria-controls={detailsId}
          id={`${detailsId}-toggle`}
          data-testid="budget-details-toggle"
        >
          <span className="inline-flex min-w-0 items-center gap-2">
            <PiggyBank className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="text-sm font-semibold">
              {t.cashflow.budget.title}
            </span>
          </span>
          <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <span data-testid="budget-target-months">{months}</span>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none",
                cardExpanded && "rotate-180",
              )}
            />
          </span>
        </button>
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
              aria-label={t.cashflow.budget.targetInfo}
              onClick={event => event.stopPropagation()}
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="max-w-xs text-xs">
            {t.cashflow.budget.targetInfo}
          </PopoverContent>
        </Popover>
      </div>
      <div
        id={detailsId}
        role="region"
        aria-labelledby={`${detailsId}-toggle`}
        aria-hidden={!cardExpanded}
        inert={!cardExpanded}
      >
        <AnimatePresence initial={false}>
          {cardExpanded && (
            <motion.div
              className="overflow-hidden"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{
                duration: reducedMotion ? 0 : 0.2,
                ease: "easeOut",
              }}
              data-testid="budget-details-content"
            >
              <div className="border-t">
                {incomplete && (
                  <div
                    className="flex items-center gap-2 border-b px-4 py-2 text-xs text-amber-700 dark:text-amber-300"
                    role="status"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    {t.cashflow.budget.incomplete}
                  </div>
                )}
                {budget.entry_count === 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
                    <span className="text-xs text-muted-foreground">
                      {t.cashflow.budget.empty}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onOpenBudget}
                      className="h-7 gap-1.5 text-xs"
                    >
                      <ArrowUpRight className="h-3.5 w-3.5" />
                      {t.cashflow.budget.openBudget}
                    </Button>
                  </div>
                )}
                <div
                  className={cn(
                    "grid grid-cols-1 divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0",
                    loading && "opacity-50",
                  )}
                >
                  {metrics.map(
                    ({ key, title, icon: MetricIcon, comparison, color }) => {
                      const expense = key !== "invested"
                      const targetSection = expense ? "expenses" : "investments"
                      const shareOfEarnings =
                        earnings !== null &&
                        earnings > 0 &&
                        comparison.actual !== null
                          ? comparison.actual / earnings
                          : null
                      const progress =
                        shareOfEarnings !== null
                          ? Math.min(Math.max(shareOfEarnings * 100, 0), 100)
                          : null
                      const hasTarget =
                        budget.entry_count > 0 && comparison.expected > 0
                      const targetShare =
                        hasTarget && earnings !== null && earnings > 0
                          ? comparison.expected / earnings
                          : null
                      const overSpent =
                        expense && (comparison.difference ?? 0) > 0 && hasTarget
                      const aboveTarget =
                        !expense &&
                        (comparison.difference ?? 0) > 0 &&
                        hasTarget
                      const remainingLabel = expense
                        ? overSpent
                          ? t.cashflow.budget.exceeded
                          : t.cashflow.budget.available
                        : aboveTarget
                          ? t.cashflow.budget.extra
                          : t.cashflow.budget.remaining
                      return (
                        <div
                          key={key}
                          className="min-w-0 space-y-2 px-4 py-3"
                          data-testid={`budget-${key}`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="inline-flex items-center gap-1.5 text-sm font-medium">
                              <MetricIcon className="h-3.5 w-3.5 text-muted-foreground" />
                              {title}
                              {key === "invested" &&
                                budget.invested_breakdown && (
                                  <Popover>
                                    <PopoverTrigger asChild>
                                      <button
                                        type="button"
                                        className="inline-flex h-6 w-6 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
                                        aria-label={
                                          t.cashflow.budget.investedBreakdown
                                        }
                                        title={
                                          t.cashflow.budget.investedBreakdown
                                        }
                                      >
                                        <Info className="h-3.5 w-3.5" />
                                      </button>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      className="w-72 max-w-[calc(100vw-2rem)] text-xs"
                                      align="start"
                                    >
                                      <dl className="space-y-2">
                                        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,auto)] gap-3">
                                          <dt className="text-muted-foreground">
                                            {t.cashflow.budget.savingsMovements}
                                          </dt>
                                          <dd
                                            className="min-w-0 break-words text-right font-medium tabular-nums"
                                            data-testid="budget-invested-savings"
                                          >
                                            <Sensitive>
                                              {budget.invested_breakdown
                                                .savings !== null
                                                ? money(
                                                    budget.invested_breakdown
                                                      .savings,
                                                  )
                                                : t.cashflow.budget
                                                    .incompleteTarget}
                                            </Sensitive>
                                          </dd>
                                        </div>
                                        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,auto)] gap-3">
                                          <dt className="text-muted-foreground">
                                            {
                                              t.cashflow.budget
                                                .investmentTransactions
                                            }
                                          </dt>
                                          <dd
                                            className="min-w-0 break-words text-right font-medium tabular-nums"
                                            data-testid="budget-invested-transactions"
                                          >
                                            <Sensitive>
                                              {budget.invested_breakdown
                                                .transactions !== null
                                                ? money(
                                                    budget.invested_breakdown
                                                      .transactions,
                                                  )
                                                : t.cashflow.budget
                                                    .incompleteTarget}
                                            </Sensitive>
                                          </dd>
                                        </div>
                                      </dl>
                                    </PopoverContent>
                                  </Popover>
                                )}
                            </span>
                            {shareOfEarnings !== null && (
                              <span className="inline-flex flex-wrap items-baseline justify-end gap-1 text-xs tabular-nums text-muted-foreground">
                                <span
                                  className={cn(
                                    "text-sm font-semibold",
                                    !privateMode &&
                                      overSpent &&
                                      "text-red-600 dark:text-red-400",
                                  )}
                                  title={t.management.ofEarnings}
                                >
                                  <Sensitive>
                                    {percent(shareOfEarnings)}
                                  </Sensitive>
                                </span>
                                {targetShare !== null && (
                                  <Sensitive>
                                    <span>
                                      {"/ "}
                                      <button
                                        type="button"
                                        className="rounded-sm underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        onClick={() =>
                                          onTargetClick(targetSection)
                                        }
                                      >
                                        {`${t.cashflow.targetShort} ${percent(targetShare)}`}
                                      </button>
                                    </span>
                                  </Sensitive>
                                )}
                              </span>
                            )}
                          </div>
                          {!privateMode &&
                            progress !== null &&
                            shareOfEarnings !== null && (
                              <div className="relative h-2">
                                <div
                                  className="h-full overflow-hidden rounded-full bg-muted"
                                  role="progressbar"
                                  aria-label={title}
                                  aria-valuemin={0}
                                  aria-valuemax={100}
                                  aria-valuenow={progress}
                                  aria-valuetext={`${percent(shareOfEarnings)} ${t.management.ofEarnings}`}
                                >
                                  <div
                                    className={cn("h-full rounded-full", color)}
                                    style={{
                                      width: `${progress}%`,
                                    }}
                                  />
                                </div>
                                {targetShare !== null && (
                                  <span
                                    className="absolute -inset-y-0.5 w-0.5 -translate-x-1/2 rounded-full bg-foreground"
                                    style={{
                                      left: `${Math.min(targetShare * 100, 100)}%`,
                                    }}
                                    data-testid={`budget-${key}-target-marker`}
                                    aria-hidden="true"
                                  />
                                )}
                              </div>
                            )}
                          <div className="grid grid-cols-2 gap-3">
                            <div className="min-w-0">
                              <div className="text-xs text-muted-foreground">
                                {t.cashflow.budget.actual}
                              </div>
                              <div className="break-words text-base font-semibold tabular-nums">
                                <Sensitive>
                                  {comparison.actual !== null
                                    ? money(comparison.actual)
                                    : t.cashflow.budget.incompleteTarget}
                                </Sensitive>
                              </div>
                            </div>
                            {hasTarget ? (
                              <div className="min-w-0">
                                <div className="text-xs text-muted-foreground">
                                  {remainingLabel}
                                </div>
                                <div
                                  className={cn(
                                    "break-words text-base font-medium tabular-nums",
                                    !privateMode &&
                                      overSpent &&
                                      "text-red-600 dark:text-red-400",
                                    !privateMode &&
                                      aboveTarget &&
                                      "text-green-600 dark:text-green-400",
                                  )}
                                >
                                  <Sensitive>
                                    {comparison.difference === null
                                      ? t.cashflow.budget.incompleteTarget
                                      : money(Math.abs(comparison.difference))}
                                  </Sensitive>
                                </div>
                              </div>
                            ) : (
                              (!incomplete || budget.entry_count === 0) && (
                                <div className="flex min-h-10 items-center justify-end">
                                  <Button
                                    type="button"
                                    variant="link"
                                    size="sm"
                                    onClick={onOpenBudget}
                                    className="h-auto shrink-0 gap-1 p-0 text-xs font-normal text-muted-foreground dark:text-gray-500"
                                    aria-label={`${title}: ${t.cashflow.budget.notSet}. ${t.cashflow.budget.openBudget}`}
                                    title={t.cashflow.budget.openBudget}
                                  >
                                    {t.cashflow.budget.notSet}
                                    <ArrowUpRight className="h-3 w-3" />
                                  </Button>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )
                    },
                  )}
                </div>
                {budget.entry_count > 0 && (
                  <div className="border-t">
                    <div className="flex items-center gap-2 px-4 hover:bg-muted/30">
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-center justify-between gap-2 py-3 text-xs font-medium"
                        onClick={() => setExpanded(value => !value)}
                        aria-expanded={expanded}
                        aria-controls={labelDetailsId}
                        id={`${labelDetailsId}-toggle`}
                        data-testid="budget-label-details-toggle"
                      >
                        {t.cashflow.byLabel}
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none",
                            expanded && "rotate-180",
                          )}
                        />
                      </button>
                      {expanded && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <button
                              type="button"
                              className="inline-flex h-6 w-6 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
                              aria-label={t.cashflow.overlapHint}
                              onClick={event => event.stopPropagation()}
                            >
                              <Info className="h-3.5 w-3.5" />
                            </button>
                          </PopoverTrigger>
                          <PopoverContent className="max-w-xs text-xs">
                            {t.cashflow.overlapHint}
                          </PopoverContent>
                        </Popover>
                      )}
                    </div>
                    <div
                      id={labelDetailsId}
                      role="region"
                      aria-labelledby={`${labelDetailsId}-toggle`}
                      aria-hidden={!expanded}
                      inert={!expanded}
                    >
                      <AnimatePresence initial={false}>
                        {expanded && (
                          <motion.div
                            className="overflow-hidden"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{
                              duration: reducedMotion ? 0 : 0.2,
                              ease: "easeOut",
                            }}
                            data-testid="budget-label-details-content"
                          >
                            <div className="space-y-1 px-2 pb-3">
                              {labelTargets.length === 0 && (
                                <div
                                  className="flex flex-wrap items-center gap-3 px-2 py-3"
                                  data-testid="budget-label-empty"
                                >
                                  <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                                    <Tag className="h-4 w-4" />
                                  </span>
                                  <span className="min-w-0 flex-1 text-xs text-muted-foreground">
                                    {t.cashflow.budget.noLabelTargets}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={onOpenBudget}
                                    className="h-7 gap-1.5 text-xs"
                                  >
                                    <ArrowUpRight className="h-3.5 w-3.5" />
                                    {t.cashflow.budget.openBudget}
                                  </Button>
                                </div>
                              )}
                              {labelTargets.map(row => {
                                const label = row.label_id
                                  ? getLabel(row.label_id)
                                  : undefined
                                const comparison = row.comparison
                                const progress =
                                  comparison.ratio !== null
                                    ? Math.min(
                                        Math.max(comparison.ratio * 100, 0),
                                        100,
                                      )
                                    : null
                                return (
                                  <button
                                    key={`${row.flow_type}:${row.label_id ?? "unassigned"}`}
                                    type="button"
                                    disabled={!row.label_id || loading}
                                    onClick={() =>
                                      row.label_id &&
                                      onLabelClick(row.label_id, row.flow_type)
                                    }
                                    className="grid w-full grid-cols-[minmax(0,1fr)_minmax(0,auto)] items-center gap-x-3 gap-y-1.5 rounded-md px-2 py-1.5 text-left enabled:hover:bg-muted/40 disabled:cursor-default"
                                    data-testid={`budget-label-${row.flow_type}-${row.label_id ?? "unassigned"}`}
                                  >
                                    <div className="flex min-w-0 items-center">
                                      {label ? (
                                        <LabelChip
                                          label={label}
                                          name={getLabelName(label)}
                                          className="min-w-0 max-w-full"
                                        />
                                      ) : (
                                        <span className="text-xs font-medium text-muted-foreground">
                                          {t.management.budgetLabel.unassigned}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-0.5 text-xs tabular-nums">
                                      <span className="break-words text-muted-foreground">
                                        <Sensitive>
                                          {comparison.actual !== null
                                            ? money(comparison.actual)
                                            : t.cashflow.budget.unlinked}
                                        </Sensitive>
                                        {" / "}
                                        <Sensitive>
                                          {money(comparison.expected)}
                                        </Sensitive>
                                      </span>
                                      <span
                                        className={cn(
                                          "font-medium",
                                          !privateMode &&
                                            (comparison.ratio ?? 0) > 1 &&
                                            "text-red-600 dark:text-red-400",
                                        )}
                                      >
                                        <Sensitive>
                                          {comparison.ratio !== null
                                            ? percent(comparison.ratio)
                                            : comparison.actual === null
                                              ? t.cashflow.budget.unlinked
                                              : incomplete
                                                ? t.cashflow.budget
                                                    .incompleteTarget
                                                : t.cashflow.budget.noTarget}
                                        </Sensitive>
                                      </span>
                                    </div>
                                    {!privateMode && progress !== null && (
                                      <div
                                        className="col-span-2 h-1 overflow-hidden rounded-full bg-muted"
                                        role="progressbar"
                                        aria-label={
                                          label
                                            ? getLabelName(label)
                                            : t.management.budgetLabel
                                                .unassigned
                                        }
                                        aria-valuemin={0}
                                        aria-valuemax={100}
                                        aria-valuenow={progress}
                                      >
                                        <div
                                          className="h-full rounded-full"
                                          style={{
                                            width: `${progress}%`,
                                            backgroundColor:
                                              getLabelColor(label),
                                          }}
                                        />
                                      </div>
                                    )}
                                  </button>
                                )
                              })}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Card>
  )
}
