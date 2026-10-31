import { describe, expect, it } from "vitest"
import { buildHeatmapWeeks } from "@/utils/cashflowHeatmap"

const point = (period: string, expenses: number, income = 0, count = 1) => ({
  period,
  income,
  expenses,
  count,
})

describe("buildHeatmapWeeks", () => {
  it("lays out monday-first weeks with placeholders before the range", () => {
    const weeks = buildHeatmapWeeks([], "2025-03-05", "2025-03-18")

    expect(weeks).toHaveLength(3)
    expect(weeks[0].days.slice(0, 2)).toEqual([null, null])
    expect(weeks[0].days[2]?.date).toBe("2025-03-05")
    expect(weeks[2].days.map(day => day?.date)).toEqual([
      "2025-03-17",
      "2025-03-18",
    ])
  })

  it("zero fills days without movements", () => {
    const weeks = buildHeatmapWeeks(
      [point("2025-03-04", 20, 100, 3)],
      "2025-03-03",
      "2025-03-05",
    )

    expect(weeks[0].days).toEqual([
      { date: "2025-03-03", income: 0, expenses: 0, count: 0, level: 0 },
      { date: "2025-03-04", income: 100, expenses: 20, count: 3, level: 4 },
      { date: "2025-03-05", income: 0, expenses: 0, count: 0, level: 0 },
    ])
  })

  it("ranks net outflow and inflow days on separate signed scales", () => {
    const weeks = buildHeatmapWeeks(
      [
        point("2025-03-03", 10),
        point("2025-03-04", 20),
        point("2025-03-05", 30),
        point("2025-03-06", 40),
        point("2025-03-07", 80, 4000),
        point("2025-03-08", 50, 50),
      ],
      "2025-03-03",
      "2025-03-09",
    )

    expect(weeks[0].days.map(day => day?.level)).toEqual([
      -1, -2, -3, -4, 4, 0, 0,
    ])
  })

  it("ignores days outside the range when ranking", () => {
    const weeks = buildHeatmapWeeks(
      [point("2025-02-01", 1000), point("2025-03-03", 10)],
      "2025-03-03",
      "2025-03-03",
    )

    expect(weeks[0].days[0]?.level).toBe(-4)
  })

  it("marks month starts and drops a crowded leading label", () => {
    const weeks = buildHeatmapWeeks([], "2025-01-27", "2025-03-09")

    expect(weeks.map(week => week.monthStart)).toEqual([
      "2025-02-01",
      null,
      null,
      null,
      "2025-03-01",
      null,
    ])
    expect(
      buildHeatmapWeeks([], "2025-02-17", "2025-03-09").map(
        week => week.monthStart,
      ),
    ).toEqual([null, "2025-03-01", null])
  })

  it("keeps the leading label when the next month is far", () => {
    const weeks = buildHeatmapWeeks([], "2025-03-03", "2025-03-23")

    expect(weeks.map(week => week.monthStart)).toEqual([
      "2025-03-03",
      null,
      null,
    ])
  })
})
