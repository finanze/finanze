import { addDays, format, parseISO, startOfWeek } from "date-fns"
import type { CashflowPoint } from "@/types/cashflow"

export const HEATMAP_LEVELS = 4

export interface HeatmapDay {
  date: string
  income: number
  expenses: number
  count: number
  level: number
}

export interface HeatmapWeek {
  days: (HeatmapDay | null)[]
  monthStart: string | null
}

function upperBound(sorted: number[], value: number): number {
  let low = 0
  let high = sorted.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (sorted[mid] <= value) low = mid + 1
    else high = mid
  }
  return low
}

export function buildHeatmapWeeks(
  series: CashflowPoint[],
  fromDate: string,
  toDate: string,
): HeatmapWeek[] {
  if (fromDate > toDate) return []
  const points = new Map(series.map(point => [point.period, point]))
  const inRange = series.filter(
    point => point.period >= fromDate && point.period <= toDate,
  )
  const sortedMagnitudes = (sign: 1 | -1) =>
    inRange
      .map(point => sign * (point.income - point.expenses))
      .filter(net => net > 0)
      .sort((a, b) => a - b)
  const gains = sortedMagnitudes(1)
  const losses = sortedMagnitudes(-1)
  const rank = (sorted: number[], value: number) =>
    Math.max(
      1,
      Math.ceil((HEATMAP_LEVELS * upperBound(sorted, value)) / sorted.length),
    )
  const levelOf = (net: number) =>
    net > 0 ? rank(gains, net) : net < 0 ? -rank(losses, -net) : 0

  const end = parseISO(toDate)
  const weeks: HeatmapWeek[] = []
  let cursor = startOfWeek(parseISO(fromDate), { weekStartsOn: 1 })
  while (cursor <= end) {
    const days: (HeatmapDay | null)[] = []
    let monthStart: string | null = null
    for (let i = 0; i < 7 && cursor <= end; i++) {
      const date = format(cursor, "yyyy-MM-dd")
      if (date < fromDate) {
        days.push(null)
      } else {
        const point = points.get(date)
        days.push({
          date,
          income: point?.income ?? 0,
          expenses: point?.expenses ?? 0,
          count: point?.count ?? 0,
          level: levelOf((point?.income ?? 0) - (point?.expenses ?? 0)),
        })
        if (date === fromDate || cursor.getDate() === 1) monthStart = date
      }
      cursor = addDays(cursor, 1)
    }
    weeks.push({ days, monthStart })
  }
  if (weeks[0]?.monthStart && weeks.slice(1, 3).some(week => week.monthStart))
    weeks[0].monthStart = null
  return weeks
}
