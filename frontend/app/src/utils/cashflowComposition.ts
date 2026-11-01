import { addDays, addMonths, format, parseISO, startOfMonth } from "date-fns"
import {
  CashflowGranularity,
  type BudgetPoint,
  type CashflowPoint,
} from "@/types/cashflow"

export const MAX_COMPOSITION_LABELS = 6

export type CompositionMode = "labels" | "budget"

export type CompositionSeriesKind =
  "label" | "other" | "unlabeled" | "needs" | "wants" | "invested" | "remainder"

export interface CompositionSeries {
  key: string
  kind: CompositionSeriesKind
  labelId?: string
  total: number
}

export type CompositionRow = Record<string, string | number>

export interface CompositionChart {
  series: CompositionSeries[]
  rows: CompositionRow[]
}

const BUDGET_KINDS = ["needs", "wants", "invested", "remainder"] as const

export function compositionPeriods(
  fromDate: string,
  toDate: string,
  granularity: CashflowGranularity,
): string[] {
  const end = parseISO(toDate)
  const periods: string[] = []
  if (granularity === CashflowGranularity.DAY) {
    for (let day = parseISO(fromDate); day <= end; day = addDays(day, 1))
      periods.push(format(day, "yyyy-MM-dd"))
  } else {
    for (
      let month = startOfMonth(parseISO(fromDate));
      month <= end;
      month = addMonths(month, 1)
    )
      periods.push(format(month, "yyyy-MM-dd"))
  }
  return periods
}

function labelSeries(points: CashflowPoint[]): {
  series: CompositionSeries[]
  values: Map<string, Record<string, number>>
} {
  const totals = new Map<string | null, number>()
  points.forEach(point =>
    point.expenses_by_label?.forEach(row =>
      totals.set(row.label_id, (totals.get(row.label_id) ?? 0) + row.amount),
    ),
  )
  const ranked = [...totals]
    .filter(
      (entry): entry is [string, number] => entry[0] !== null && entry[1] > 0,
    )
    .sort((a, b) => b[1] - a[1])
  const visible =
    ranked.length > MAX_COMPOSITION_LABELS
      ? ranked.slice(0, MAX_COMPOSITION_LABELS - 1)
      : ranked
  const keyByLabel = new Map(
    visible.map(([labelId], index) => [labelId, `label${index}`]),
  )
  const series: CompositionSeries[] = visible.map(([labelId, total]) => ({
    key: keyByLabel.get(labelId)!,
    kind: "label",
    labelId,
    total,
  }))
  const otherTotal = ranked
    .slice(visible.length)
    .reduce((sum, [, total]) => sum + total, 0)
  if (otherTotal > 0)
    series.push({ key: "other", kind: "other", total: otherTotal })
  const unlabeledTotal = totals.get(null) ?? 0
  if (unlabeledTotal > 0)
    series.push({ key: "unlabeled", kind: "unlabeled", total: unlabeledTotal })

  const values = new Map<string, Record<string, number>>()
  points.forEach(point => {
    const row: Record<string, number> = {}
    point.expenses_by_label?.forEach(({ label_id, amount }) => {
      const key =
        label_id === null ? "unlabeled" : (keyByLabel.get(label_id) ?? "other")
      row[key] = (row[key] ?? 0) + amount
    })
    values.set(point.period, row)
  })
  return { series, values }
}

function budgetSeries(points: BudgetPoint[]): {
  series: CompositionSeries[]
  values: Map<string, Record<string, number>>
} {
  const values = new Map<string, Record<string, number>>()
  points.forEach(point =>
    values.set(
      point.period,
      Object.fromEntries(BUDGET_KINDS.map(kind => [kind, point[kind]])),
    ),
  )
  return {
    series: BUDGET_KINDS.map(kind => ({
      key: kind,
      kind,
      total: points.reduce((sum, point) => sum + point[kind], 0),
    })),
    values,
  }
}

export function buildCompositionChart(
  mode: CompositionMode,
  points: CashflowPoint[],
  budgetPoints: BudgetPoint[],
  fromDate: string,
  toDate: string,
  granularity: CashflowGranularity,
): CompositionChart {
  const { series, values } =
    mode === "budget" ? budgetSeries(budgetPoints) : labelSeries(points)
  const rows = compositionPeriods(fromDate, toDate, granularity).map(period => {
    const row: CompositionRow = { period }
    const periodValues = values.get(period)
    series.forEach(({ key }) => {
      row[key] = Math.round((periodValues?.[key] ?? 0) * 100) / 100
    })
    return row
  })
  return { series, rows }
}
