import { FlowFrequency, PeriodicFlow } from "@/domain"

const frequencyMonthsMap: Partial<Record<FlowFrequency, number>> = {
  [FlowFrequency.MONTHLY]: 1,
  [FlowFrequency.EVERY_TWO_MONTHS]: 2,
  [FlowFrequency.QUARTERLY]: 3,
  [FlowFrequency.EVERY_FOUR_MONTHS]: 4,
  [FlowFrequency.SEMIANNUALLY]: 6,
  [FlowFrequency.YEARLY]: 12,
}

function parseLocalDate(dateStr: string): Date {
  // Expected: YYYY-MM-DD
  const [y, m, d] = dateStr.split("-").map(p => Number(p))
  return new Date(y, (m ?? 1) - 1, d ?? 1)
}

function formatLocalDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

function startOfToday(): Date {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

function daysInMonth(year: number, monthZeroBased: number): number {
  return new Date(year, monthZeroBased + 1, 0).getDate()
}

function addMonthsClamped(date: Date, months: number): Date {
  const year = date.getFullYear()
  const month = date.getMonth()
  const day = date.getDate()

  const total = month + months
  const newYear = year + Math.floor(total / 12)
  const newMonth = ((total % 12) + 12) % 12

  const dim = daysInMonth(newYear, newMonth)
  const newDay = Math.min(day, dim)

  return new Date(newYear, newMonth, newDay)
}

export function getNextDate(flow: PeriodicFlow): string | null {
  if (!flow.enabled) return null

  const today = startOfToday()
  const sinceDate = parseLocalDate(flow.since)

  if (sinceDate > today) {
    return formatLocalDate(sinceDate)
  }

  let nextDate: Date | null = null

  if (flow.frequency === FlowFrequency.DAILY) {
    nextDate = new Date(today)
    nextDate.setDate(nextDate.getDate() + 1)
  } else if (flow.frequency === FlowFrequency.WEEKLY) {
    const daysSince = Math.floor(
      (today.getTime() - sinceDate.getTime()) / (24 * 60 * 60 * 1000),
    )
    const weeksPassed = Math.floor(daysSince / 7)
    const candidate = new Date(sinceDate)
    candidate.setDate(candidate.getDate() + (weeksPassed + 1) * 7)

    if (candidate > today) {
      nextDate = candidate
    } else {
      const candidate2 = new Date(sinceDate)
      candidate2.setDate(candidate2.getDate() + (weeksPassed + 2) * 7)
      nextDate = candidate2
    }
  } else {
    const months = frequencyMonthsMap[flow.frequency]
    if (months) {
      let candidate = new Date(sinceDate)
      while (candidate <= today) {
        candidate = addMonthsClamped(candidate, months)
      }
      nextDate = candidate
    }
  }

  if (nextDate && flow.until) {
    const untilDate = parseLocalDate(flow.until)
    if (nextDate > untilDate) return null
  }

  return nextDate ? formatLocalDate(nextDate) : null
}
