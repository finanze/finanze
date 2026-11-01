import { useMemo, useState } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { useI18n } from "@/i18n"
import { useLabels } from "@/context/LabelsContext"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { Sensitive } from "@/components/ui/Sensitive"
import { formatCompactCurrency, formatCurrency } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { DataDisplayMode } from "@/types"
import {
  CashflowGranularity,
  type BudgetPoint,
  type CashflowPoint,
} from "@/types/cashflow"
import {
  buildCompositionChart,
  type CompositionMode,
  type CompositionSeries,
  type CompositionSeriesKind,
} from "@/utils/cashflowComposition"

const MODE_KEY = "cashflowCompositionMode"
const MODES: readonly CompositionMode[] = ["labels", "budget"]

const KIND_COLORS: Record<Exclude<CompositionSeriesKind, "label">, string> = {
  other: "#64748b",
  unlabeled: "#9ca3af",
  needs: "#0ea5e9",
  wants: "#ef4444",
  invested: "#06b6d4",
  remainder: "#8b5cf6",
}

interface CashflowCompositionProps {
  series: CashflowPoint[]
  budgetSeries?: BudgetPoint[] | null
  granularity: CashflowGranularity
  fromDate: string
  toDate: string
  currency: string
}

export function CashflowComposition({
  series,
  budgetSeries,
  granularity,
  fromDate,
  toDate,
  currency,
}: CashflowCompositionProps) {
  const { t, locale } = useI18n()
  const { getLabel, getLabelName } = useLabels()
  const { mode: displayMode } = useDataDisplayMode()
  const [storedMode, setStoredMode] = useState<CompositionMode>(() =>
    localStorage.getItem(MODE_KEY) === "budget" ? "budget" : "labels",
  )
  const [width, setWidth] = useState(0)
  const mode: CompositionMode = budgetSeries ? storedMode : "labels"
  const privateMode = displayMode === DataDisplayMode.PRIVATE

  const changeMode = (next: CompositionMode) => {
    setStoredMode(next)
    localStorage.setItem(MODE_KEY, next)
  }

  const chart = useMemo(
    () =>
      buildCompositionChart(
        mode,
        series,
        budgetSeries ?? [],
        fromDate,
        toDate,
        granularity,
      ),
    [mode, series, budgetSeries, fromDate, toDate, granularity],
  )

  const hasNegative = chart.rows.some(row =>
    chart.series.some(({ key }) => Number(row[key]) < 0),
  )

  const describe = (item: CompositionSeries) => {
    if (item.kind === "label") {
      const label = item.labelId ? getLabel(item.labelId) : undefined
      return {
        name: label ? getLabelName(label) : t.labels.unlabeled,
        color: label?.color ?? KIND_COLORS.other,
      }
    }
    const names: Record<Exclude<CompositionSeriesKind, "label">, string> = {
      other: t.cashflow.composition.otherLabels,
      unlabeled: t.labels.unlabeled,
      needs: t.cashflow.budget.needs,
      wants: t.cashflow.budget.wants,
      invested: t.management.monthlyInvestedAmount,
      remainder: t.cashflow.composition.remainder,
    }
    return { name: names[item.kind], color: KIND_COLORS[item.kind] }
  }

  const formatPeriod = (period: string) =>
    new Intl.DateTimeFormat(
      locale,
      granularity === CashflowGranularity.DAY
        ? { day: "numeric", month: "short" }
        : { month: "short", year: "2-digit" },
    ).format(new Date(`${period}T00:00:00`))

  const money = (value: number) =>
    formatCurrency(value, locale, currency, currency)

  const legendItem = (item: CompositionSeries) => {
    const { name, color } = describe(item)
    return (
      <span
        key={item.key}
        className="inline-flex min-w-0 items-center gap-1.5"
        data-testid={`composition-legend-${item.key}`}
      >
        <span
          className="h-2.5 w-2.5 shrink-0 rounded-sm"
          style={{ backgroundColor: color }}
        />
        <span className="truncate">{name}</span>
      </span>
    )
  }

  const legendGroup = (title: string, kinds: CompositionSeriesKind[]) => (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="font-medium text-foreground">{title}</span>
      {chart.series.filter(item => kinds.includes(item.kind)).map(legendItem)}
    </span>
  )

  return (
    <div className="space-y-3" data-testid="cashflow-composition">
      {budgetSeries && (
        <div className="flex flex-wrap gap-1.5">
          {MODES.map(value => (
            <button
              key={value}
              type="button"
              data-testid={`composition-mode-${value}`}
              aria-pressed={mode === value}
              onClick={() => changeMode(value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                mode === value
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {t.cashflow.composition.modes[value]}
            </button>
          ))}
        </div>
      )}
      {chart.series.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
          {t.cashflow.empty.noExpenses}
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer
            width="100%"
            height="100%"
            onResize={value => setWidth(value)}
          >
            <AreaChart
              data={chart.rows}
              stackOffset="sign"
              margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                className="opacity-30"
              />
              <XAxis
                dataKey="period"
                tickFormatter={value => formatPeriod(String(value))}
                tick={{ fontSize: 11 }}
                tickLine={false}
                minTickGap={12}
              />
              <YAxis
                tick={privateMode ? false : { fontSize: width < 480 ? 10 : 11 }}
                tickLine={false}
                axisLine={false}
                width={privateMode ? 8 : width < 480 ? 42 : 55}
                tickFormatter={value =>
                  width < 480
                    ? new Intl.NumberFormat(locale, {
                        notation: "compact",
                        compactDisplay: "short",
                        maximumFractionDigits: 1,
                      }).format(Number(value))
                    : formatCompactCurrency(Number(value), locale, currency)
                }
              />
              {hasNegative && (
                <ReferenceLine
                  y={0}
                  stroke="currentColor"
                  strokeOpacity={0.3}
                />
              )}
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  const row = payload[0].payload as Record<string, number>
                  const items = chart.series
                    .filter(item => mode === "budget" || row[item.key])
                    .reverse()
                  const total = chart.series.reduce(
                    (sum, item) => sum + (row[item.key] ?? 0),
                    0,
                  )
                  return (
                    <div className="min-w-40 rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                      <p className="mb-1 font-semibold">
                        {formatPeriod(String(label))}
                      </p>
                      {items.map(item => {
                        const { name, color } = describe(item)
                        const value = row[item.key] ?? 0
                        const percentage =
                          mode === "budget" && total > 0
                            ? new Intl.NumberFormat(locale, {
                                style: "percent",
                                maximumFractionDigits: 1,
                              }).format(value / total)
                            : null
                        return (
                          <p
                            key={item.key}
                            className="flex items-center justify-between gap-3"
                          >
                            <span className="flex min-w-0 items-center gap-1.5">
                              <span
                                className="h-2 w-2 shrink-0 rounded-sm"
                                style={{ backgroundColor: color }}
                              />
                              <span className="truncate">{name}</span>
                            </span>
                            <Sensitive>
                              {money(value)}
                              {percentage && (
                                <span className="ml-1.5 text-muted-foreground">
                                  ({percentage})
                                </span>
                              )}
                            </Sensitive>
                          </p>
                        )
                      })}
                      <p className="mt-1 flex justify-between gap-3 border-t pt-1 font-medium">
                        <span>
                          {mode === "budget"
                            ? t.cashflow.income
                            : t.cashflow.expenses}
                        </span>
                        <Sensitive>{money(total)}</Sensitive>
                      </p>
                    </div>
                  )
                }}
              />
              {chart.series.map(item => {
                const { color } = describe(item)
                return (
                  <Area
                    key={item.key}
                    type="monotone"
                    dataKey={item.key}
                    stackId="composition"
                    stroke={color}
                    fill={color}
                    fillOpacity={0.55}
                    strokeWidth={1.5}
                  />
                )
              })}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        {mode === "budget" ? (
          <>
            {legendGroup(t.cashflow.composition.spending, ["needs", "wants"])}
            {legendGroup(t.cashflow.composition.savings, [
              "invested",
              "remainder",
            ])}
          </>
        ) : (
          chart.series.map(legendItem)
        )}
      </div>
    </div>
  )
}
