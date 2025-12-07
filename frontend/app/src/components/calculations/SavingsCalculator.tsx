import { useState, useMemo, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Switch } from "@/components/ui/Switch"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  Calculator,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  TrendingUp,
  Wallet,
  PiggyBank,
  Target,
  CalendarClock,
  Clock,
} from "lucide-react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ComposedChart,
  Line,
  Area,
  LabelList,
  Cell,
} from "recharts"
import { cn, getCurrencySymbol } from "@/lib/utils"
import { formatCurrency } from "@/lib/formatters"
import { calculateSavings } from "@/services/api"
import {
  SavingsPeriodicity,
  SavingsCalculationRequest,
  SavingsCalculationResult,
  SavingsScenarioResult,
} from "@/types"

type CalculationMode = "contribution" | "target" | "years" | "retirement"

interface ScenarioFormData {
  id: string
  name: string
  annualReturn: string
  contribution: string
  targetAmount: string
}

const SCENARIO_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

// Slightly lighter/different hue for gains in dark mode
const SCENARIO_GAINS_COLORS = [
  "hsl(var(--chart-1) / 0.6)",
  "hsl(var(--chart-2) / 0.6)",
  "hsl(var(--chart-3) / 0.6)",
  "hsl(var(--chart-4) / 0.6)",
  "hsl(var(--chart-5) / 0.6)",
]

const WITHDRAWAL_COLORS = [
  "hsl(0, 84%, 60%)", // Red
  "hsl(15, 84%, 55%)", // Red-orange
  "hsl(350, 84%, 50%)", // Pink-red
  "hsl(0, 70%, 45%)", // Dark red
  "hsl(10, 90%, 65%)", // Light red-orange
]

const getPeriodsPerYear = (periodicity: SavingsPeriodicity): number => {
  switch (periodicity) {
    case SavingsPeriodicity.MONTHLY:
      return 12
    case SavingsPeriodicity.QUARTERLY:
      return 4
    case SavingsPeriodicity.YEARLY:
      return 1
  }
}

export function SavingsCalculator() {
  const { t, locale } = useI18n()
  const { settings, showToast } = useAppContext()
  const defaultCurrency = settings?.general?.defaultCurrency || "EUR"
  const currencySymbol = getCurrencySymbol(defaultCurrency)

  const [baseAmount, setBaseAmount] = useState("")
  const [years, setYears] = useState("")
  const [periodicity, setPeriodicity] = useState<SavingsPeriodicity>(
    SavingsPeriodicity.MONTHLY,
  )
  const [mode, setMode] = useState<CalculationMode>("contribution")
  const [scenarios, setScenarios] = useState<ScenarioFormData[]>([
    {
      id: "1",
      name: "",
      annualReturn: "7",
      contribution: "500",
      targetAmount: "",
    },
  ])

  const [enableRetirement, setEnableRetirement] = useState(false)
  const [withdrawalAmount, setWithdrawalAmount] = useState("")
  const [withdrawalYears, setWithdrawalYears] = useState("")

  const [calculating, setCalculating] = useState(false)
  const [result, setResult] = useState<SavingsCalculationResult | null>(null)
  const [calculatedParams, setCalculatedParams] = useState<{
    years: number | null
    periodicity: SavingsPeriodicity
    baseAmount: number
    enableRetirement: boolean
  } | null>(null)
  const [expandedScenario, setExpandedScenario] = useState<string | null>(null)
  const [chartView, setChartView] = useState<"yearly" | "period">("yearly")
  const [fieldErrors, setFieldErrors] = useState<{
    years?: boolean
    scenarios?: Record<
      string,
      { annualReturn?: boolean; contribution?: boolean; targetAmount?: boolean }
    >
    retirement?: { withdrawalAmount?: boolean; withdrawalYears?: boolean }
  }>({})

  const addScenario = useCallback(() => {
    const newId = String(Date.now())
    setScenarios(prev => [
      ...prev,
      {
        id: newId,
        name: "",
        annualReturn: "5",
        contribution: "500",
        targetAmount: "",
      },
    ])
  }, [])

  const removeScenario = useCallback((id: string) => {
    setScenarios(prev => prev.filter(s => s.id !== id))
  }, [])

  const updateScenario = useCallback(
    (id: string, field: keyof ScenarioFormData, value: string) => {
      setScenarios(prev =>
        prev.map(s => (s.id === id ? { ...s, [field]: value } : s)),
      )
    },
    [],
  )

  const handleCalculate = async () => {
    const errors: typeof fieldErrors = {}
    let hasErrors = false

    if (scenarios.length === 0) {
      showToast(t.calculations.savings.errors.atLeastOneScenario, "error")
      return
    }

    // Years mode calculates the years, so it's optional in that case
    const yearsNum = parseInt(years)
    if (mode !== "years" && (!years || isNaN(yearsNum) || yearsNum <= 0)) {
      errors.years = true
      hasErrors = true
    }

    const scenarioErrors: Record<
      string,
      { annualReturn?: boolean; contribution?: boolean; targetAmount?: boolean }
    > = {}

    const scenarioRequests = scenarios.map(s => {
      const annualPerf = parseFloat(s.annualReturn)
      if (isNaN(annualPerf) || s.annualReturn === "") {
        scenarioErrors[s.id] = { ...scenarioErrors[s.id], annualReturn: true }
        hasErrors = true
      }

      // In retirement mode, contribution is calculated by the API
      // In years mode, both contribution and target are required
      const contribution =
        (mode === "contribution" || mode === "years") && s.contribution
          ? parseFloat(s.contribution)
          : null
      const target =
        (mode === "target" || mode === "years") && s.targetAmount
          ? parseFloat(s.targetAmount)
          : null

      if (
        mode === "contribution" &&
        (contribution === null || isNaN(contribution) || s.contribution === "")
      ) {
        scenarioErrors[s.id] = { ...scenarioErrors[s.id], contribution: true }
        hasErrors = true
      }
      if (
        mode === "target" &&
        (target === null || isNaN(target) || s.targetAmount === "")
      ) {
        scenarioErrors[s.id] = { ...scenarioErrors[s.id], targetAmount: true }
        hasErrors = true
      }
      if (mode === "years") {
        if (
          contribution === null ||
          isNaN(contribution) ||
          s.contribution === ""
        ) {
          scenarioErrors[s.id] = { ...scenarioErrors[s.id], contribution: true }
          hasErrors = true
        }
        if (target === null || isNaN(target) || s.targetAmount === "") {
          scenarioErrors[s.id] = { ...scenarioErrors[s.id], targetAmount: true }
          hasErrors = true
        }
      }

      return {
        id: s.id,
        annual_market_performance: isNaN(annualPerf) ? 0 : annualPerf / 100,
        periodic_contribution: contribution,
        target_amount: target,
      }
    })

    if (Object.keys(scenarioErrors).length > 0) {
      errors.scenarios = scenarioErrors
    }

    // Build retirement request - required for retirement mode or when enabled
    const retirementRequest =
      enableRetirement && (withdrawalAmount || withdrawalYears)
        ? {
            withdrawal_amount: withdrawalAmount
              ? parseFloat(withdrawalAmount)
              : null,
            withdrawal_years: withdrawalYears
              ? parseInt(withdrawalYears)
              : null,
          }
        : null

    // Validate retirement fields when enabled (any mode) or in retirement mode
    if (enableRetirement) {
      if (
        !retirementRequest ||
        (!retirementRequest.withdrawal_amount &&
          !retirementRequest.withdrawal_years)
      ) {
        errors.retirement = {
          withdrawalAmount: !withdrawalAmount,
          withdrawalYears: !withdrawalYears,
        }
        hasErrors = true
      }
    }

    setFieldErrors(errors)

    if (hasErrors) {
      return
    }

    const request: SavingsCalculationRequest = {
      base_amount: baseAmount ? parseFloat(baseAmount) : 0,
      years: mode === "years" ? null : yearsNum,
      periodicity,
      scenarios: scenarioRequests,
      retirement: retirementRequest,
    }

    setCalculating(true)
    try {
      const response = await calculateSavings(request)
      setResult(response)
      setCalculatedParams({
        years: mode === "years" ? null : yearsNum,
        periodicity,
        baseAmount: baseAmount ? parseFloat(baseAmount) : 0,
        enableRetirement,
      })
      if (response.scenarios.length > 0) {
        setExpandedScenario(response.scenarios[0].scenario_id)
      }
    } catch (err) {
      console.error("Calculation error:", err)
      showToast(
        err instanceof Error
          ? err.message
          : t.calculations.savings.errors.calculationFailed,
        "error",
      )
    } finally {
      setCalculating(false)
    }
  }

  const chartData = useMemo(() => {
    if (!result || result.scenarios.length === 0 || !calculatedParams) return []

    const periodsPerYear = getPeriodsPerYear(calculatedParams.periodicity)

    // Get the maximum period index for each scenario
    const scenarioMaxPeriods = result.scenarios.map(s =>
      Math.max(...s.accumulation_periods.map(p => p.period_index)),
    )

    // Get the overall maximum period index across all scenarios
    const maxPeriodIndex = Math.max(...scenarioMaxPeriods)

    // Derive years from result, including partial years
    const fullYears = Math.floor(maxPeriodIndex / periodsPerYear)
    const hasPartialYear = maxPeriodIndex % periodsPerYear !== 0
    const yearsNum = hasPartialYear ? fullYears + 1 : fullYears

    if (chartView === "yearly") {
      const yearlyData: Array<Record<string, number | string>> = []

      // Calculate each scenario's accumulation end year and retirement end year
      const scenarioTimelines = result.scenarios.map((scenario, idx) => {
        const accumulationEndYear = Math.ceil(
          scenarioMaxPeriods[idx] / periodsPerYear,
        )
        const retirementDurationYears = scenario.retirement
          ? Math.ceil(scenario.retirement.duration_years)
          : 0
        const retirementEndYear = accumulationEndYear + retirementDurationYears
        return {
          accumulationEndYear,
          retirementDurationYears,
          retirementEndYear,
        }
      })

      // Find the maximum year across all scenarios (including retirement)
      const maxYear = Math.max(
        ...scenarioTimelines.map(t => t.retirementEndYear),
        yearsNum,
      )

      for (let y = 0; y <= maxYear; y++) {
        const entry: Record<string, number | string> = { year: y }

        // Check if any scenario is in retirement at this year
        const anyInRetirement = result.scenarios.some((scenario, idx) => {
          const timeline = scenarioTimelines[idx]
          return scenario.retirement && y > timeline.accumulationEndYear
        })

        if (anyInRetirement) {
          entry.isRetirement = "true"
        }

        result.scenarios.forEach((scenario, idx) => {
          const timeline = scenarioTimelines[idx]
          const scenarioMaxPeriod = scenarioMaxPeriods[idx]
          const periodIndex = y * periodsPerYear

          // Determine which phase this scenario is in at year y
          const isInAccumulation = y <= timeline.accumulationEndYear
          const isInRetirement =
            scenario.retirement &&
            y > timeline.accumulationEndYear &&
            y <= timeline.retirementEndYear

          if (isInAccumulation) {
            // Accumulation phase
            const isLastYearForScenario =
              y === timeline.accumulationEndYear &&
              scenarioMaxPeriod % periodsPerYear !== 0

            let period
            if (isLastYearForScenario) {
              period =
                scenario.accumulation_periods[
                  scenario.accumulation_periods.length - 1
                ]
            } else {
              period = scenario.accumulation_periods.find(
                p => p.period_index === periodIndex,
              )
            }

            if (period) {
              entry[`capital_${idx}`] = period.total_invested
              entry[`gains_${idx}`] = period.total_revaluation
              entry[`balance_${idx}`] =
                period.total_invested + period.total_revaluation
            } else if (y === 0) {
              entry[`capital_${idx}`] = calculatedParams.baseAmount
              entry[`gains_${idx}`] = 0
              entry[`balance_${idx}`] = calculatedParams.baseAmount
            }
          } else if (isInRetirement && scenario.retirement) {
            // Retirement phase - calculate retirement year relative to this scenario's start
            const retirementYearForScenario = y - timeline.accumulationEndYear
            const yearStartPeriod =
              (retirementYearForScenario - 1) * periodsPerYear + 1
            const yearEndPeriod = retirementYearForScenario * periodsPerYear

            let yearlyWithdrawal = 0
            scenario.retirement.periods.forEach(p => {
              if (
                p.period_index >= yearStartPeriod &&
                p.period_index <= yearEndPeriod
              ) {
                yearlyWithdrawal += p.withdrawal
              }
            })

            // Get the last period's balance for this retirement year
            const lastPeriodInYear =
              scenario.retirement.periods.find(
                p => p.period_index === yearEndPeriod,
              ) ||
              scenario.retirement.periods
                .filter(p => p.period_index <= yearEndPeriod)
                .pop()

            if (lastPeriodInYear) {
              entry[`balance_${idx}`] = lastPeriodInYear.balance
            }
            entry[`withdrawn_${idx}`] = yearlyWithdrawal
          }
        })

        yearlyData.push(entry)
      }

      return yearlyData
    } else {
      const periodData: Array<Record<string, number | string>> = []

      // Add accumulation periods for each scenario
      result.scenarios.forEach((scenario, scenarioIdx) => {
        scenario.accumulation_periods.forEach(period => {
          let entry = periodData.find(e => e.period === period.period_index)
          if (!entry) {
            entry = { period: period.period_index }
            periodData.push(entry)
          }
          entry[`capital_${scenarioIdx}`] = period.total_invested
          entry[`gains_${scenarioIdx}`] = period.total_revaluation
          entry[`balance_${scenarioIdx}`] =
            period.total_invested + period.total_revaluation
        })
      })

      // Add retirement periods for each scenario, offset by their own accumulation end
      if (calculatedParams.enableRetirement) {
        result.scenarios.forEach((scenario, scenarioIdx) => {
          if (scenario.retirement) {
            // Each scenario's retirement starts after its own accumulation ends
            const scenarioAccumulationEnd = scenarioMaxPeriods[scenarioIdx]

            scenario.retirement.periods.forEach(period => {
              const adjustedPeriod =
                scenarioAccumulationEnd + period.period_index
              let entry = periodData.find(e => e.period === adjustedPeriod)
              if (!entry) {
                entry = { period: adjustedPeriod }
                periodData.push(entry)
              }
              // Mark as retirement if any scenario is in retirement at this period
              entry.isRetirement = "true"
              entry[`balance_${scenarioIdx}`] = period.balance
              entry[`withdrawn_${scenarioIdx}`] = period.withdrawal
            })
          }
        })
      }

      periodData.sort((a, b) => (a.period as number) - (b.period as number))

      return periodData
    }
  }, [result, chartView, calculatedParams])

  const getScenarioColor = (index: number): string => {
    return SCENARIO_COLORS[index % SCENARIO_COLORS.length]
  }

  const getScenarioGainsColor = (index: number): string => {
    return SCENARIO_GAINS_COLORS[index % SCENARIO_GAINS_COLORS.length]
  }

  const getScenarioDisplayName = useCallback(
    (index: number, scenarioId?: string): string => {
      const scenario = scenarioId
        ? scenarios.find(s => s.id === scenarioId)
        : scenarios[index]
      if (scenario?.name?.trim()) {
        return scenario.name.trim()
      }
      return t.calculations.savings.scenarioName.replace(
        "{number}",
        String(index + 1),
      )
    },
    [scenarios, t],
  )

  const formatYAxisTick = (value: number): string => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`
    }
    if (value >= 1000) {
      return `${(value / 1000).toFixed(0)}k`
    }
    return value.toString()
  }

  const renderScenarioSummary = (
    scenario: SavingsScenarioResult,
    index: number,
  ) => {
    const scenarioName = getScenarioDisplayName(index, scenario.scenario_id)

    return (
      <Card
        key={scenario.scenario_id}
        className={cn(
          "border-l-4 transition-all",
          expandedScenario === scenario.scenario_id
            ? "ring-2 ring-primary/20"
            : "",
        )}
        style={{ borderLeftColor: getScenarioColor(index) }}
      >
        <CardHeader
          className="cursor-pointer py-3 sm:py-4 px-3 sm:px-6"
          onClick={() =>
            setExpandedScenario(
              expandedScenario === scenario.scenario_id
                ? null
                : scenario.scenario_id,
            )
          }
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div
                className="h-3 w-3 rounded-full shrink-0"
                style={{ backgroundColor: getScenarioColor(index) }}
              />
              <CardTitle className="text-sm sm:text-base font-medium truncate">
                {scenarioName}
              </CardTitle>
              <span className="text-xs sm:text-sm text-muted-foreground shrink-0">
                {(scenario.annual_market_performance * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-2 sm:gap-4 shrink-0">
              <span className="text-base sm:text-lg font-semibold">
                {formatCurrency(
                  scenario.final_balance,
                  locale,
                  defaultCurrency,
                )}
              </span>
              {expandedScenario === scenario.scenario_id ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </div>
        </CardHeader>

        <AnimatePresence>
          {expandedScenario === scenario.scenario_id && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {mode === "years" && (
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">
                        {t.calculations.savings.yearsToTarget}
                      </p>
                      <p className="font-semibold text-primary">
                        {(() => {
                          const periodsPerYear = getPeriodsPerYear(
                            calculatedParams?.periodicity ||
                              SavingsPeriodicity.MONTHLY,
                          )
                          const totalPeriods =
                            scenario.accumulation_periods.length
                          const fullYears = Math.floor(
                            totalPeriods / periodsPerYear,
                          )
                          const remainingPeriods = totalPeriods % periodsPerYear

                          if (remainingPeriods === 0) {
                            return t.calculations.savings.yearsLabel.replace(
                              "{years}",
                              String(fullYears),
                            )
                          }

                          const monthsEquivalent =
                            calculatedParams?.periodicity ===
                            SavingsPeriodicity.MONTHLY
                              ? remainingPeriods
                              : calculatedParams?.periodicity ===
                                  SavingsPeriodicity.QUARTERLY
                                ? remainingPeriods * 3
                                : remainingPeriods * 12

                          if (fullYears === 0) {
                            return t.calculations.savings.monthsLabel.replace(
                              "{months}",
                              String(monthsEquivalent),
                            )
                          }

                          return `${t.calculations.savings.yearsLabel.replace("{years}", String(fullYears))} ${t.calculations.savings.monthsLabel.replace("{months}", String(monthsEquivalent))}`
                        })()}
                      </p>
                    </div>
                  )}
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t.calculations.savings.totalContributions}
                    </p>
                    <p className="font-medium">
                      {formatCurrency(
                        scenario.total_contributions,
                        locale,
                        defaultCurrency,
                      )}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t.calculations.savings.totalRevaluation}
                    </p>
                    <p className="font-medium text-green-600 dark:text-green-400">
                      +
                      {formatCurrency(
                        scenario.total_revaluation,
                        locale,
                        defaultCurrency,
                      )}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t.calculations.savings.periodicContribution}
                    </p>
                    <p className="font-medium">
                      {formatCurrency(
                        scenario.periodic_contribution,
                        locale,
                        defaultCurrency,
                      )}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      {t.calculations.savings.finalBalance}
                    </p>
                    <p className="font-semibold text-primary">
                      {formatCurrency(
                        scenario.final_balance,
                        locale,
                        defaultCurrency,
                      )}
                    </p>
                  </div>
                </div>

                {scenario.retirement && (
                  <div className="mt-4 pt-4 border-t">
                    <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                      <PiggyBank className="h-4 w-4" />
                      {t.calculations.savings.retirementPhase}
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">
                          {t.calculations.savings.withdrawalPerPeriod}
                        </p>
                        <p className="font-medium">
                          {formatCurrency(
                            scenario.retirement.withdrawal_amount,
                            locale,
                            defaultCurrency,
                          )}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">
                          {t.calculations.savings.retirementDuration}
                        </p>
                        <p className="font-medium">
                          {t.calculations.savings.yearsLabel.replace(
                            "{years}",
                            scenario.retirement.duration_years.toFixed(1),
                          )}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">
                          {t.calculations.savings.totalWithdrawn}
                        </p>
                        <p className="font-medium">
                          {formatCurrency(
                            scenario.retirement.total_withdrawn,
                            locale,
                            defaultCurrency,
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    )
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null

    const isRetirement = payload[0]?.payload?.isRetirement === "true"
    const data = payload[0]?.payload

    const formatPeriodLabel = (periodIndex: number): string => {
      if (!calculatedParams)
        return `${t.calculations.savings.period} ${periodIndex}`

      const periodsPerYear = getPeriodsPerYear(calculatedParams.periodicity)

      // Period indices are 0-based, so period 0 is Year 0 Month 1, period 11 is Year 0 Month 12
      // Period 12 is Year 1 Month 1, etc.
      const year = Math.floor(periodIndex / periodsPerYear)
      const periodInYear = (periodIndex % periodsPerYear) + 1 // 1-indexed for display

      const yearLabel = t.calculations.savings.periodLabels.year.replace(
        "{year}",
        String(year),
      )

      if (calculatedParams.periodicity === SavingsPeriodicity.MONTHLY) {
        const monthLabel = t.calculations.savings.periodLabels.month.replace(
          "{period}",
          String(periodInYear),
        )
        return `${yearLabel} - ${monthLabel}`
      } else if (
        calculatedParams.periodicity === SavingsPeriodicity.QUARTERLY
      ) {
        const quarterLabel =
          t.calculations.savings.periodLabels.quarter.replace(
            "{period}",
            String(periodInYear),
          )
        return `${yearLabel} - ${quarterLabel}`
      }
      return yearLabel
    }

    // Build tooltip items manually with correct colors
    const tooltipItems: Array<{ name: string; value: number; color: string }> =
      []

    if (result) {
      result.scenarios.forEach((scenario, idx) => {
        const scenarioName = getScenarioDisplayName(idx, scenario.scenario_id)

        if (isRetirement) {
          // Retirement phase: show balance and withdrawal
          const balance = data[`balance_${idx}`]
          const withdrawn = data[`withdrawn_${idx}`]

          if (balance !== undefined) {
            tooltipItems.push({
              name: `${scenarioName} - ${t.calculations.savings.chart.balance}`,
              value: balance,
              color: getScenarioColor(idx),
            })
          }
          if (withdrawn !== undefined) {
            tooltipItems.push({
              name: `${scenarioName} - ${t.calculations.savings.chart.withdrawal}`,
              value: withdrawn,
              color: getWithdrawalColor(idx),
            })
          }
        } else {
          // Accumulation phase: show capital, gains, and balance
          const capital = data[`capital_${idx}`]
          const gains = data[`gains_${idx}`]
          const balance = data[`balance_${idx}`]

          if (capital !== undefined) {
            tooltipItems.push({
              name: `${scenarioName} - ${t.calculations.savings.chart.capital}`,
              value: capital,
              color: getScenarioColor(idx),
            })
          }
          if (gains !== undefined) {
            tooltipItems.push({
              name: `${scenarioName} - ${t.calculations.savings.chart.gains}`,
              value: gains,
              color: getScenarioGainsColor(idx),
            })
          }
          if (balance !== undefined) {
            tooltipItems.push({
              name: `${scenarioName} - ${t.calculations.savings.chart.balance}`,
              value: balance,
              color: getScenarioColor(idx),
            })
          }
        }
      })
    }

    return (
      <div className="rounded-lg border border-border/50 bg-popover/95 backdrop-blur-sm p-3 shadow-lg">
        <p className="text-sm font-medium text-foreground/90 mb-2">
          {chartView === "yearly"
            ? `${t.calculations.savings.yearsLabel.replace("{years}", String(label))}${isRetirement ? ` (${t.calculations.savings.retirementPhase})` : ""}`
            : formatPeriodLabel(label as number)}
        </p>
        <div className="space-y-1.5">
          {tooltipItems.map((item, index) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-muted-foreground/80">{item.name}:</span>
              <span className="font-medium text-foreground/90">
                {formatCurrency(item.value, locale, defaultCurrency)}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const CustomLegend = useCallback(() => {
    if (!result) return null

    const hasRetirement =
      calculatedParams?.enableRetirement &&
      result.scenarios.some(s => s.retirement)

    return (
      <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-2 text-sm">
        {result.scenarios.map((scenario, idx) => {
          const scenarioName = getScenarioDisplayName(idx, scenario.scenario_id)
          return (
            <div key={scenario.scenario_id} className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div
                  className="h-3 w-3 rounded-sm"
                  style={{
                    backgroundColor: getScenarioColor(idx),
                  }}
                />
                <span className="text-muted-foreground">{scenarioName}</span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <div className="flex items-center gap-1">
                  <div
                    className="h-2 w-2 rounded-sm"
                    style={{
                      backgroundColor: getScenarioColor(idx),
                    }}
                  />
                  <span className="text-muted-foreground/70">
                    {t.calculations.savings.chart.capital}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <div
                    className="h-2 w-2 rounded-sm"
                    style={{
                      backgroundColor: getScenarioGainsColor(idx),
                    }}
                  />
                  <span className="text-muted-foreground/70">
                    {t.calculations.savings.chart.gains}
                  </span>
                </div>
                {hasRetirement && (
                  <div className="flex items-center gap-1">
                    <div
                      className="h-2 w-2 rounded-sm"
                      style={{
                        backgroundColor: getWithdrawalColor(idx),
                      }}
                    />
                    <span className="text-muted-foreground/70">
                      {t.calculations.savings.chart.withdrawal}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  }, [result, getScenarioColor, calculatedParams, getScenarioDisplayName])

  const totalPeriods = useMemo(() => {
    if (!result || !calculatedParams) return 0
    const periodsPerYear = getPeriodsPerYear(calculatedParams.periodicity)

    // Derive years from result when not provided (years mode)
    const yearsNum =
      calculatedParams.years ??
      Math.ceil(
        Math.max(
          ...result.scenarios.map(s =>
            Math.max(...s.accumulation_periods.map(p => p.period_index)),
          ),
        ) / periodsPerYear,
      )

    let total = yearsNum * periodsPerYear

    if (
      calculatedParams.enableRetirement &&
      result.scenarios.some(s => s.retirement)
    ) {
      const retirementPeriods = Math.max(
        ...result.scenarios
          .filter(s => s.retirement)
          .map(s => Math.ceil(s.retirement!.duration_years) * periodsPerYear),
      )
      total += retirementPeriods
    }
    return total
  }, [result, calculatedParams])

  const getWithdrawalColor = (index: number): string => {
    return WITHDRAWAL_COLORS[index % WITHDRAWAL_COLORS.length]
  }

  // Use line chart when there are too many data points
  // For period view: > 60 periods
  // For yearly view: scenarios * years > 40 (e.g., 3 scenarios * 15 years = 45 bars per year position)
  const totalYearlyBars = useMemo(() => {
    if (!result || !calculatedParams) return 0
    const periodsPerYear = getPeriodsPerYear(calculatedParams.periodicity)
    const yearsNum =
      calculatedParams.years ??
      Math.ceil(
        Math.max(
          ...result.scenarios.map(s =>
            Math.max(...s.accumulation_periods.map(p => p.period_index)),
          ),
        ) / periodsPerYear,
      )
    // Each year has 2 bars per scenario (capital + gains), plus retirement years
    let retirementYears = 0
    if (
      calculatedParams.enableRetirement &&
      result.scenarios.some(s => s.retirement)
    ) {
      retirementYears = Math.max(
        ...result.scenarios
          .filter(s => s.retirement)
          .map(s => Math.ceil(s.retirement!.duration_years)),
      )
    }
    return (yearsNum + retirementYears) * result.scenarios.length
  }, [result, calculatedParams])

  // Use line chart when there are too many data points (> 30 bars)
  const MAX_BAR_CHART_BARS = 60
  const totalPeriodBars = result ? totalPeriods * result.scenarios.length : 0
  const currentTotalBars =
    chartView === "period" ? totalPeriodBars : totalYearlyBars
  const useLineChart = currentTotalBars > MAX_BAR_CHART_BARS
  const MAX_BAR_CHART_BARS_FOR_LABEL = 30

  // Calculate reference line position (earliest retirement start)
  const referenceLinePosition = useMemo(() => {
    if (!calculatedParams || !result || !calculatedParams.enableRetirement)
      return null

    const periodsPerYear = getPeriodsPerYear(calculatedParams.periodicity)

    // Find the earliest retirement start across all scenarios
    const retirementStarts = result.scenarios
      .filter(s => s.retirement)
      .map(s => Math.max(...s.accumulation_periods.map(p => p.period_index)))

    if (retirementStarts.length === 0) return null

    const earliestRetirementStart = Math.min(...retirementStarts)
    const earliestRetirementYear = Math.ceil(
      earliestRetirementStart / periodsPerYear,
    )

    return chartView === "yearly"
      ? earliestRetirementYear
      : earliestRetirementStart
  }, [chartView, calculatedParams, result])

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-lg flex items-center gap-2">
                <Calculator className="h-5 w-5" />
                {t.calculations.savings.title}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {t.calculations.savings.description}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="baseAmount">
                  {t.calculations.savings.baseAmount}
                </Label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    {currencySymbol}
                  </span>
                  <Input
                    id="baseAmount"
                    type="number"
                    min="0"
                    step="100"
                    value={baseAmount}
                    onChange={e => setBaseAmount(e.target.value)}
                    placeholder={t.calculations.savings.baseAmountPlaceholder}
                    className="pl-8"
                  />
                </div>
              </div>

              {mode !== "years" && (
                <div className="space-y-2">
                  <Label htmlFor="years">{t.calculations.savings.years}</Label>
                  <Input
                    id="years"
                    type="number"
                    min="1"
                    max="100"
                    value={years}
                    onChange={e => {
                      setYears(e.target.value)
                      if (fieldErrors.years) {
                        setFieldErrors(prev => ({ ...prev, years: false }))
                      }
                    }}
                    placeholder={t.calculations.savings.yearsPlaceholder}
                    className={cn(
                      fieldErrors.years &&
                        "border-red-500 focus-visible:ring-red-500",
                    )}
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label>{t.calculations.savings.periodicity}</Label>
                <div className="flex gap-2">
                  {Object.values(SavingsPeriodicity).map(p => (
                    <Button
                      key={p}
                      variant={periodicity === p ? "default" : "outline"}
                      size="sm"
                      onClick={() => setPeriodicity(p)}
                      className="flex-1"
                    >
                      {t.calculations.savings.periodicities[p]}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2 pt-2">
                <Label>{t.calculations.savings.mode.label}</Label>
                <div className="flex flex-col gap-1.5">
                  <Button
                    variant={mode === "contribution" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setMode("contribution")}
                    className="justify-start h-8"
                  >
                    <Wallet className="h-4 w-4 mr-2 shrink-0" />
                    <span className="truncate">
                      {t.calculations.savings.mode.contribution}
                    </span>
                  </Button>
                  <Button
                    variant={mode === "target" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setMode("target")}
                    className="justify-start h-8"
                  >
                    <Target className="h-4 w-4 mr-2 shrink-0" />
                    <span className="truncate">
                      {t.calculations.savings.mode.target}
                    </span>
                  </Button>
                  <Button
                    variant={mode === "years" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setMode("years")}
                    className="justify-start h-8"
                  >
                    <Clock className="h-4 w-4 mr-2 shrink-0" />
                    <span className="truncate">
                      {t.calculations.savings.mode.years}
                    </span>
                  </Button>
                  <Button
                    variant={mode === "retirement" ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setMode("retirement")
                      setEnableRetirement(true)
                    }}
                    className="justify-start h-8"
                  >
                    <CalendarClock className="h-4 w-4 mr-2 shrink-0" />
                    <span className="truncate">
                      {t.calculations.savings.mode.retirement}
                    </span>
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {mode === "contribution"
                    ? t.calculations.savings.mode.contributionDesc
                    : mode === "target"
                      ? t.calculations.savings.mode.targetDesc
                      : mode === "years"
                        ? t.calculations.savings.mode.yearsDesc
                        : t.calculations.savings.mode.retirementDesc}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  {t.calculations.savings.scenarios}
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={addScenario}
                  disabled={scenarios.length >= 5}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {scenarios.map((scenario, index) => (
                <div
                  key={scenario.id}
                  className="p-3 border rounded-lg space-y-3"
                  style={{
                    borderLeftWidth: "3px",
                    borderLeftColor: getScenarioColor(index),
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={scenario.name}
                      onChange={e =>
                        updateScenario(scenario.id, "name", e.target.value)
                      }
                      placeholder={t.calculations.savings.scenarioName.replace(
                        "{number}",
                        String(index + 1),
                      )}
                      className="text-sm font-medium bg-transparent border-none outline-none placeholder:text-foreground focus:placeholder:text-muted-foreground w-full min-w-0"
                    />
                    {scenarios.length > 1 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 shrink-0"
                        onClick={() => removeScenario(scenario.id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs">
                        {t.calculations.savings.annualReturn}
                      </Label>
                      <div className="relative">
                        <Input
                          type="number"
                          step="0.1"
                          value={scenario.annualReturn}
                          onChange={e => {
                            updateScenario(
                              scenario.id,
                              "annualReturn",
                              e.target.value,
                            )
                            if (
                              fieldErrors.scenarios?.[scenario.id]?.annualReturn
                            ) {
                              setFieldErrors(prev => ({
                                ...prev,
                                scenarios: {
                                  ...prev.scenarios,
                                  [scenario.id]: {
                                    ...prev.scenarios?.[scenario.id],
                                    annualReturn: false,
                                  },
                                },
                              }))
                            }
                          }}
                          placeholder={
                            t.calculations.savings.annualReturnPlaceholder
                          }
                          className={cn(
                            "pr-6 h-8 text-sm",
                            fieldErrors.scenarios?.[scenario.id]
                              ?.annualReturn &&
                              "border-red-500 focus-visible:ring-red-500",
                          )}
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                          %
                        </span>
                      </div>
                    </div>

                    {(mode === "contribution" || mode === "years") && (
                      <div className="space-y-1">
                        <Label className="text-xs">
                          {t.calculations.savings.contribution}
                        </Label>
                        <div className="relative">
                          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                            {currencySymbol}
                          </span>
                          <Input
                            type="number"
                            min="0"
                            step="50"
                            value={scenario.contribution}
                            onChange={e => {
                              updateScenario(
                                scenario.id,
                                "contribution",
                                e.target.value,
                              )
                              if (
                                fieldErrors.scenarios?.[scenario.id]
                                  ?.contribution
                              ) {
                                setFieldErrors(prev => ({
                                  ...prev,
                                  scenarios: {
                                    ...prev.scenarios,
                                    [scenario.id]: {
                                      ...prev.scenarios?.[scenario.id],
                                      contribution: false,
                                    },
                                  },
                                }))
                              }
                            }}
                            placeholder={
                              t.calculations.savings.contributionPlaceholder
                            }
                            className={cn(
                              "pl-6 h-8 text-sm",
                              fieldErrors.scenarios?.[scenario.id]
                                ?.contribution &&
                                "border-red-500 focus-visible:ring-red-500",
                            )}
                          />
                        </div>
                      </div>
                    )}
                    {(mode === "target" || mode === "years") && (
                      <div className="space-y-1">
                        <Label className="text-xs">
                          {t.calculations.savings.targetAmount}
                        </Label>
                        <div className="relative">
                          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                            {currencySymbol}
                          </span>
                          <Input
                            type="number"
                            min="0"
                            step="1000"
                            value={scenario.targetAmount}
                            onChange={e => {
                              updateScenario(
                                scenario.id,
                                "targetAmount",
                                e.target.value,
                              )
                              if (
                                fieldErrors.scenarios?.[scenario.id]
                                  ?.targetAmount
                              ) {
                                setFieldErrors(prev => ({
                                  ...prev,
                                  scenarios: {
                                    ...prev.scenarios,
                                    [scenario.id]: {
                                      ...prev.scenarios?.[scenario.id],
                                      targetAmount: false,
                                    },
                                  },
                                }))
                              }
                            }}
                            placeholder={
                              t.calculations.savings.targetAmountPlaceholder
                            }
                            className={cn(
                              "pl-6 h-8 text-sm",
                              fieldErrors.scenarios?.[scenario.id]
                                ?.targetAmount &&
                                "border-red-500 focus-visible:ring-red-500",
                            )}
                          />
                        </div>
                      </div>
                    )}
                    {mode === "retirement" && (
                      <div className="text-xs text-muted-foreground italic pt-2">
                        {t.calculations.savings.retirementModeInfo}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <PiggyBank className="h-4 w-4" />
                  {t.calculations.savings.retirement}
                </CardTitle>
                <Switch
                  checked={enableRetirement}
                  onCheckedChange={setEnableRetirement}
                  disabled={mode === "retirement"}
                />
              </div>
            </CardHeader>
            {enableRetirement && (
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  <Label className="text-xs">
                    {t.calculations.savings.withdrawalAmount}
                  </Label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                      {currencySymbol}
                    </span>
                    <Input
                      type="number"
                      min="0"
                      step="100"
                      value={withdrawalAmount}
                      onChange={e => {
                        setWithdrawalAmount(e.target.value)
                        if (fieldErrors.retirement?.withdrawalAmount) {
                          setFieldErrors(prev => ({
                            ...prev,
                            retirement: {
                              ...prev.retirement,
                              withdrawalAmount: false,
                            },
                          }))
                        }
                      }}
                      placeholder={
                        t.calculations.savings.withdrawalAmountPlaceholder
                      }
                      className={cn(
                        "pl-8",
                        fieldErrors.retirement?.withdrawalAmount &&
                          "border-red-500 focus-visible:ring-red-500",
                      )}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">
                    {t.calculations.savings.withdrawalYears}
                  </Label>
                  <Input
                    type="number"
                    min="1"
                    max="50"
                    value={withdrawalYears}
                    onChange={e => {
                      setWithdrawalYears(e.target.value)
                      if (fieldErrors.retirement?.withdrawalYears) {
                        setFieldErrors(prev => ({
                          ...prev,
                          retirement: {
                            ...prev.retirement,
                            withdrawalYears: false,
                          },
                        }))
                      }
                    }}
                    placeholder={
                      t.calculations.savings.withdrawalYearsPlaceholder
                    }
                    className={cn(
                      fieldErrors.retirement?.withdrawalYears &&
                        "border-red-500 focus-visible:ring-red-500",
                    )}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {
                    t.calculations.savings.errors.invalidRetirement.split(
                      ".",
                    )[0]
                  }
                  .
                </p>
              </CardContent>
            )}
          </Card>

          <Button
            className="w-full"
            onClick={handleCalculate}
            disabled={calculating || scenarios.length === 0}
          >
            {calculating ? (
              <span className="flex items-center gap-2">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                >
                  <Calculator className="h-4 w-4" />
                </motion.div>
                {t.common.loading}
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Calculator className="h-4 w-4" />
                {t.calculations.savings.calculate}
              </span>
            )}
          </Button>
        </div>

        <div className="lg:col-span-2 space-y-4">
          {result ? (
            <>
              <Card>
                <CardHeader className="px-3 sm:px-4 py-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <CardTitle className="text-sm sm:text-base">
                      {t.calculations.savings.simulation}
                    </CardTitle>
                    <div className="flex gap-1 sm:gap-2">
                      <Button
                        variant={chartView === "yearly" ? "default" : "outline"}
                        size="sm"
                        className="text-xs sm:text-sm px-2 sm:px-3"
                        onClick={() => setChartView("yearly")}
                      >
                        {t.calculations.savings.yearlyView}
                      </Button>
                      <Button
                        variant={chartView === "period" ? "default" : "outline"}
                        size="sm"
                        className="text-xs sm:text-sm px-2 sm:px-3"
                        onClick={() => setChartView("period")}
                      >
                        {t.calculations.savings.periodView}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-2 pb-3 pt-0">
                  <div className="h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                      {useLineChart ? (
                        <ComposedChart
                          data={chartData}
                          margin={{ top: 25, right: 10, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            className="opacity-30"
                          />
                          <XAxis
                            dataKey={chartView === "yearly" ? "year" : "period"}
                            tick={{ fontSize: 11 }}
                            tickFormatter={value => {
                              if (chartView === "yearly") {
                                return String(value)
                              }
                              const periodsPerYear = getPeriodsPerYear(
                                calculatedParams?.periodicity ||
                                  SavingsPeriodicity.MONTHLY,
                              )
                              // For period view, show year labels
                              if (value % periodsPerYear === 0) {
                                return `Y${value / periodsPerYear}`
                              }
                              return ""
                            }}
                            ticks={
                              chartView === "period"
                                ? chartData
                                    .filter(d => {
                                      const periodsPerYear = getPeriodsPerYear(
                                        calculatedParams?.periodicity ||
                                          SavingsPeriodicity.MONTHLY,
                                      )
                                      return (
                                        (d.period as number) %
                                          periodsPerYear ===
                                        0
                                      )
                                    })
                                    .map(d => d.period as number)
                                : undefined
                            }
                          />
                          <YAxis
                            tickFormatter={formatYAxisTick}
                            tick={{ fontSize: 12 }}
                            width={45}
                          />
                          <Tooltip
                            content={<CustomTooltip />}
                            cursor={{
                              stroke: "currentColor",
                              className: "opacity-20",
                            }}
                          />
                          {result.scenarios.map((scenario, idx) => (
                            <Area
                              key={`area_capital_${idx}`}
                              dataKey={`capital_${idx}`}
                              name={`${getScenarioDisplayName(idx, scenario.scenario_id)} - ${t.calculations.savings.chart.capital}`}
                              stackId={`scenario_${idx}`}
                              fill={getScenarioColor(idx)}
                              fillOpacity={0.7}
                              stroke="none"
                              connectNulls={false}
                            />
                          ))}
                          {result.scenarios.map((scenario, idx) => (
                            <Area
                              key={`area_${idx}`}
                              dataKey={`gains_${idx}`}
                              name={`${getScenarioDisplayName(idx, scenario.scenario_id)} - ${t.calculations.savings.chart.gains}`}
                              stackId={`scenario_${idx}`}
                              fill={getScenarioGainsColor(idx)}
                              fillOpacity={0.5}
                              stroke="none"
                              connectNulls={false}
                            />
                          ))}
                          {result.scenarios.map((scenario, idx) => (
                            <Line
                              key={`line_${idx}`}
                              type="monotone"
                              dataKey={(
                                data: Record<string, number | string>,
                              ) => {
                                const balance = data[`balance_${idx}`] as
                                  | number
                                  | undefined
                                if (balance !== undefined) return balance
                                const capital = data[`capital_${idx}`] as
                                  | number
                                  | undefined
                                const gains = data[`gains_${idx}`] as
                                  | number
                                  | undefined
                                if (
                                  capital !== undefined &&
                                  gains !== undefined
                                ) {
                                  return capital + gains
                                }
                                return undefined
                              }}
                              name={getScenarioDisplayName(
                                idx,
                                scenario.scenario_id,
                              )}
                              stroke={getScenarioColor(idx)}
                              strokeWidth={2}
                              dot={false}
                              connectNulls={false}
                            />
                          ))}
                          {calculatedParams?.enableRetirement &&
                            result.scenarios.map(
                              (scenario, idx) =>
                                scenario.retirement && (
                                  <Area
                                    key={`area_withdrawn_${idx}`}
                                    dataKey={`withdrawn_${idx}`}
                                    name={`${getScenarioDisplayName(idx, scenario.scenario_id)} - ${t.calculations.savings.chart.withdrawal}`}
                                    fill={getWithdrawalColor(idx)}
                                    fillOpacity={0.3}
                                    stroke={getWithdrawalColor(idx)}
                                    strokeWidth={1}
                                  />
                                ),
                            )}
                          {calculatedParams?.enableRetirement &&
                            referenceLinePosition !== null && (
                              <ReferenceLine
                                x={referenceLinePosition}
                                stroke="hsl(var(--muted-foreground))"
                                strokeDasharray="3 3"
                                label={{
                                  value: t.calculations.savings.retirementPhase,
                                  position: "top",
                                  fontSize: 10,
                                }}
                              />
                            )}
                        </ComposedChart>
                      ) : (
                        <BarChart
                          data={chartData}
                          margin={{ top: 25, right: 10, left: 0, bottom: 5 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            className="opacity-30"
                          />
                          <XAxis
                            dataKey={chartView === "yearly" ? "year" : "period"}
                            tick={{ fontSize: 12 }}
                          />
                          <YAxis
                            tickFormatter={formatYAxisTick}
                            tick={{ fontSize: 12 }}
                            width={45}
                          />
                          <Tooltip
                            content={<CustomTooltip />}
                            cursor={{
                              fill: "currentColor",
                              className: "opacity-5 dark:opacity-10",
                            }}
                          />
                          {result.scenarios.map((scenario, idx) => (
                            <Bar
                              key={`capital_${idx}`}
                              dataKey={(
                                data: Record<string, number | string>,
                              ) => {
                                // During retirement, show balance instead of capital
                                if (data.isRetirement === "true") {
                                  const balance = data[`balance_${idx}`]
                                  return balance !== undefined ? balance : null
                                }
                                const capital = data[`capital_${idx}`]
                                return capital !== undefined ? capital : null
                              }}
                              name={`${getScenarioDisplayName(idx, scenario.scenario_id)} - ${t.calculations.savings.chart.capital}`}
                              stackId={`scenario_${idx}`}
                              fill={getScenarioColor(idx)}
                              fillOpacity={0.8}
                            />
                          ))}
                          {result.scenarios.map((scenario, idx) => (
                            <Bar
                              key={`gains_${idx}`}
                              dataKey={(
                                data: Record<string, number | string>,
                              ) => {
                                // During retirement, show withdrawal instead of gains
                                if (data.isRetirement === "true") {
                                  const withdrawn = data[`withdrawn_${idx}`]
                                  return withdrawn !== undefined
                                    ? withdrawn
                                    : null
                                }
                                const gains = data[`gains_${idx}`]
                                return gains !== undefined ? gains : null
                              }}
                              name={`${getScenarioDisplayName(idx, scenario.scenario_id)} - ${t.calculations.savings.chart.gains}`}
                              stackId={`scenario_${idx}`}
                            >
                              {chartData.map((entry, index) => (
                                <Cell
                                  key={`cell_${idx}_${index}`}
                                  fill={
                                    entry.isRetirement === "true"
                                      ? getWithdrawalColor(idx)
                                      : getScenarioGainsColor(idx)
                                  }
                                />
                              ))}
                              {chartView === "yearly" &&
                                result.scenarios.length === 1 &&
                                currentTotalBars <=
                                  MAX_BAR_CHART_BARS_FOR_LABEL && (
                                  <LabelList
                                    dataKey={(
                                      data: Record<string, number | string>,
                                    ) => {
                                      const balance = data[`balance_${idx}`] as
                                        | number
                                        | undefined
                                      const withdrawn = data[
                                        `withdrawn_${idx}`
                                      ] as number | undefined
                                      if (
                                        data.isRetirement === "true" &&
                                        balance !== undefined &&
                                        withdrawn !== undefined
                                      ) {
                                        return balance + withdrawn
                                      }
                                      return balance
                                    }}
                                    position="top"
                                    formatter={formatYAxisTick}
                                    fontSize={9}
                                    fill="hsl(var(--muted-foreground))"
                                  />
                                )}
                            </Bar>
                          ))}
                          {calculatedParams?.enableRetirement &&
                            referenceLinePosition !== null && (
                              <ReferenceLine
                                x={referenceLinePosition}
                                stroke="hsl(var(--muted-foreground))"
                                strokeDasharray="3 3"
                                label={{
                                  value: t.calculations.savings.retirementPhase,
                                  position: "top",
                                  fontSize: 10,
                                }}
                              />
                            )}
                        </BarChart>
                      )}
                    </ResponsiveContainer>
                  </div>
                  <CustomLegend />
                </CardContent>
              </Card>

              <div className="space-y-3">
                <h3 className="text-lg font-semibold">
                  {t.calculations.savings.summary.title}
                </h3>
                {result.scenarios.map((scenario, index) =>
                  renderScenarioSummary(scenario, index),
                )}
              </div>
            </>
          ) : (
            <div className="space-y-4 select-none pointer-events-none">
              <Card>
                <CardHeader className="px-3 sm:px-4 py-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <span className="text-sm sm:text-base font-medium text-muted-foreground/30">
                      {t.calculations.savings.simulation}
                    </span>
                    <div className="flex gap-2">
                      <div className="h-8 px-3 rounded-md bg-muted/20 flex items-center">
                        <span className="text-xs text-muted-foreground/25">
                          {t.calculations.savings.yearlyView}
                        </span>
                      </div>
                      <div className="h-8 px-3 rounded-md bg-muted/10 flex items-center">
                        <span className="text-xs text-muted-foreground/20">
                          {t.calculations.savings.periodView}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-4 pt-0">
                  <div className="h-[400px] relative">
                    {/* Y-axis labels */}
                    <div className="absolute left-0 top-0 bottom-8 w-10 flex flex-col justify-between text-[10px] text-muted-foreground/20">
                      <span>250k</span>
                      <span>200k</span>
                      <span>150k</span>
                      <span>100k</span>
                      <span>50k</span>
                      <span>0</span>
                    </div>
                    {/* Chart area */}
                    <div className="ml-10 h-full flex flex-col">
                      {/* Grid lines */}
                      <div className="flex-1 relative border-l border-b border-muted-foreground/5">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <div
                            key={i}
                            className="absolute left-0 right-0 border-t border-dashed border-muted-foreground/5"
                            style={{ top: `${(i + 1) * 16.67}%` }}
                          />
                        ))}
                        {/* Bars - Two scenarios with accumulation and decline */}
                        <div className="absolute inset-0 flex items-end gap-[6px] px-2 pb-1">
                          {Array.from({ length: 20 }).map((_, i) => {
                            // Scenario 1: peaks around bar 12, then declines
                            const peak1 = 12
                            let base1, gains1
                            if (i <= peak1) {
                              base1 = 5 + i * 5
                              gains1 = 2 + i * 2.5
                            } else {
                              const decline = (i - peak1) * 8
                              base1 = Math.max(5, 65 - decline)
                              gains1 = Math.max(1, 32 - decline * 0.5)
                            }

                            // Scenario 2: peaks around bar 15, then declines
                            const peak2 = 15
                            let base2, gains2
                            if (i <= peak2) {
                              base2 = 4 + i * 4
                              gains2 = 1.5 + i * 2
                            } else {
                              const decline = (i - peak2) * 10
                              base2 = Math.max(4, 64 - decline)
                              gains2 = Math.max(1, 31.5 - decline * 0.5)
                            }

                            return (
                              <div
                                key={i}
                                className="flex-1 flex gap-[4px] items-end h-full"
                              >
                                {/* Scenario 1 - Blue/grey tones */}
                                <div className="flex-1 flex flex-col justify-end h-full">
                                  <div
                                    className="w-full"
                                    style={{
                                      height: `${Math.min(gains1, 35)}%`,
                                      backgroundColor: "hsl(210 10% 50% / 0.2)",
                                    }}
                                  />
                                  <div
                                    className="w-full"
                                    style={{
                                      height: `${Math.min(base1, 55)}%`,
                                      backgroundColor:
                                        "hsl(210 15% 45% / 0.25)",
                                    }}
                                  />
                                </div>
                                {/* Scenario 2 - Green/grey tones */}
                                <div className="flex-1 flex flex-col justify-end h-full">
                                  <div
                                    className="w-full"
                                    style={{
                                      height: `${Math.min(gains2, 32)}%`,
                                      backgroundColor: "hsl(160 10% 45% / 0.2)",
                                    }}
                                  />
                                  <div
                                    className="w-full"
                                    style={{
                                      height: `${Math.min(base2, 55)}%`,
                                      backgroundColor:
                                        "hsl(160 15% 40% / 0.25)",
                                    }}
                                  />
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                      {/* X-axis labels */}
                      <div className="h-6 flex justify-between px-1 pt-1">
                        {Array.from({ length: 10 }).map((_, i) => (
                          <span
                            key={i}
                            className="text-[10px] text-muted-foreground/20"
                          >
                            {i * 2}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  {/* Legend */}
                  <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-3">
                    {/* Scenario 1 */}
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <div
                          className="h-3 w-3 rounded-sm"
                          style={{ backgroundColor: "hsl(210 15% 45% / 0.3)" }}
                        />
                        <span className="text-xs text-muted-foreground/30">
                          {t.calculations.savings.scenarioName.replace(
                            "{number}",
                            "1",
                          )}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div
                          className="h-2 w-2 rounded-sm"
                          style={{ backgroundColor: "hsl(210 15% 45% / 0.3)" }}
                        />
                        <span className="text-[10px] text-muted-foreground/25">
                          {t.calculations.savings.chart.capital}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div
                          className="h-2 w-2 rounded-sm"
                          style={{ backgroundColor: "hsl(210 10% 50% / 0.25)" }}
                        />
                        <span className="text-[10px] text-muted-foreground/25">
                          {t.calculations.savings.chart.gains}
                        </span>
                      </div>
                    </div>
                    {/* Scenario 2 */}
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <div
                          className="h-3 w-3 rounded-sm"
                          style={{ backgroundColor: "hsl(160 15% 40% / 0.3)" }}
                        />
                        <span className="text-xs text-muted-foreground/30">
                          {t.calculations.savings.scenarioName.replace(
                            "{number}",
                            "2",
                          )}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div
                          className="h-2 w-2 rounded-sm"
                          style={{ backgroundColor: "hsl(160 15% 40% / 0.3)" }}
                        />
                        <span className="text-[10px] text-muted-foreground/25">
                          {t.calculations.savings.chart.capital}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div
                          className="h-2 w-2 rounded-sm"
                          style={{ backgroundColor: "hsl(160 10% 45% / 0.25)" }}
                        />
                        <span className="text-[10px] text-muted-foreground/25">
                          {t.calculations.savings.chart.gains}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Summary section */}
              <div className="space-y-3">
                <span className="text-lg font-semibold text-muted-foreground/25">
                  {t.calculations.savings.summary.title}
                </span>
                {/* Scenario 1 */}
                <Card
                  className="border-l-4 opacity-40"
                  style={{ borderLeftColor: "hsl(210 15% 45% / 0.4)" }}
                >
                  <CardHeader className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: "hsl(210 15% 45% / 0.4)" }}
                        />
                        <span className="text-sm font-medium text-muted-foreground/30">
                          {t.calculations.savings.scenarioName.replace(
                            "{number}",
                            "1",
                          )}
                        </span>
                        <span className="text-xs text-muted-foreground/20">
                          7.0%
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-muted-foreground/25">
                          € ---,---
                        </span>
                        <ChevronDown className="h-4 w-4 text-muted-foreground/20" />
                      </div>
                    </div>
                  </CardHeader>
                </Card>
                {/* Scenario 2 */}
                <Card
                  className="border-l-4 opacity-40"
                  style={{ borderLeftColor: "hsl(160 15% 40% / 0.4)" }}
                >
                  <CardHeader className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: "hsl(160 15% 40% / 0.4)" }}
                        />
                        <span className="text-sm font-medium text-muted-foreground/30">
                          {t.calculations.savings.scenarioName.replace(
                            "{number}",
                            "2",
                          )}
                        </span>
                        <span className="text-xs text-muted-foreground/20">
                          5.0%
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-muted-foreground/25">
                          € ---,---
                        </span>
                        <ChevronDown className="h-4 w-4 text-muted-foreground/20" />
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
