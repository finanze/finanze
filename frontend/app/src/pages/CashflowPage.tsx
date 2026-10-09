import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import {
  endOfMonth,
  format,
  parseISO,
  startOfMonth,
  startOfYear,
  subMonths,
} from "date-fns"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  ArrowDownLeft,
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  CalendarSync,
  ChartPie,
  ChevronDown,
  Check,
  EyeOff,
  Filter,
  Grid3x3,
  Info,
  PiggyBank,
  Plus,
  Receipt,
  RefreshCcw,
  RotateCcw,
  Scale,
  Tags,
  TrendingDown,
  TrendingUp,
  Users,
  Wand2,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useLabels } from "@/context/LabelsContext"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { DatePicker } from "@/components/ui/DatePicker"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Sensitive } from "@/components/ui/Sensitive"
import { FormattedMarketValue } from "@/components/ui/FormattedMarketValue"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { EmptyState } from "@/components/ui/EmptyState"
import {
  PageTabs,
  useTabSearchParam,
  type PageTab,
} from "@/components/ui/PageTabs"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Icon, type IconName } from "@/components/ui/icon-picker"
import { EntitySelector } from "@/components/EntitySelector"
import { LabelChip } from "@/components/labels/LabelChip"
import { LabelsManager } from "@/components/labels/LabelsManager"
import { CashflowHeatmap } from "@/components/cashflow/CashflowHeatmap"
import {
  useNavigateWithReturn,
  useRestoreReturnScroll,
} from "@/hooks/useReturnNavigation"
import {
  createPeriodicFlow,
  getCashflowSummary,
  getRecurringMovements,
  ignoreRecurringMovement,
  restoreRecurringMovement,
} from "@/services/api"
import { formatCompactCurrency, formatCurrency } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { DataDisplayMode, EntityType, FlowType } from "@/types"
import { TxType } from "@/types/transactions"
import {
  CashflowGranularity,
  type CashflowLabelBreakdown,
  type CashflowSummary,
  type CashflowTotals,
  type RecurringMovement,
} from "@/types/cashflow"

type PeriodPreset =
  | "thisMonth"
  | "lastMonth"
  | "last3Months"
  | "last6Months"
  | "last12Months"
  | "ytd"
  | "custom"

type CashflowTab = "analysis" | "labels" | "rules" | "automation"

type EvolutionView = "bars" | "heatmap"

const EVOLUTION_VIEWS: readonly EvolutionView[] = ["bars", "heatmap"]
const EVOLUTION_VIEW_KEY = "cashflowEvolutionView"

const CASHFLOW_TABS: readonly CashflowTab[] = [
  "analysis",
  "labels",
  "rules",
  "automation",
]

const PRESETS: Exclude<PeriodPreset, "custom">[] = [
  "thisMonth",
  "lastMonth",
  "last3Months",
  "last6Months",
  "last12Months",
  "ytd",
]

const DEFAULT_PRESET: PeriodPreset = "last3Months"
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

const DAILY_GRANULARITY_MAX_DAYS = 62
const MAX_VISIBLE_RECURRING_MOVEMENTS = 8
const MAX_COUNTERPARTY_LABEL_DOTS = 4
const INCOME_COLOR = "#16a34a"
const EXPENSE_COLOR = "#ef4444"

const EDGE_CARD =
  "-mx-6 rounded-none border-x-0 md:mx-0 md:rounded-lg md:border-x"

type KpiTone = "income" | "expenses" | "net" | "savings"

const KPI_ICON_TONES: Record<KpiTone, string> = {
  income: "bg-green-500/10 text-green-600 dark:text-green-400",
  expenses: "bg-red-500/10 text-red-600 dark:text-red-400",
  net: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  savings: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
}

const toIso = (date: Date) => format(date, "yyyy-MM-dd")

const presetRange = (preset: PeriodPreset): [string, string] => {
  const today = new Date()
  switch (preset) {
    case "lastMonth": {
      const previous = subMonths(today, 1)
      return [toIso(startOfMonth(previous)), toIso(endOfMonth(previous))]
    }
    case "last3Months":
      return [toIso(startOfMonth(subMonths(today, 2))), toIso(today)]
    case "last6Months":
      return [toIso(startOfMonth(subMonths(today, 5))), toIso(today)]
    case "last12Months":
      return [toIso(startOfMonth(subMonths(today, 11))), toIso(today)]
    case "ytd":
      return [toIso(startOfYear(today)), toIso(today)]
    default:
      return [toIso(startOfMonth(today)), toIso(today)]
  }
}

const recurringMovementId = (movement: RecurringMovement) =>
  `${movement.key}-${movement.type}-${movement.currency}-${movement.amount}`

const FILTER_PARAMS = ["period", "from", "to", "entity"] as const

const filtersFromParams = (params: URLSearchParams) => {
  const period = params.get("period")
  const preset: PeriodPreset =
    period === "custom" || PRESETS.some(key => key === period)
      ? (period as PeriodPreset)
      : DEFAULT_PRESET
  const from = params.get("from") ?? ""
  const to = params.get("to") ?? ""
  const range: [string, string] =
    preset === "custom" && ISO_DATE.test(from) && ISO_DATE.test(to)
      ? [from, to]
      : presetRange(preset)
  return { preset, range, entityIds: params.getAll("entity") }
}

const formatRecurringDate = (dateInput: string, locale: string) => {
  const date = parseISO(dateInput)
  if (Number.isNaN(date.getTime())) return "—"

  const options: Intl.DateTimeFormatOptions = {
    day: "numeric",
    month: "short",
  }
  if (date.getFullYear() !== new Date().getFullYear()) {
    options.year = "2-digit"
  }

  return new Intl.DateTimeFormat(locale, options).format(date)
}

const daysBetween = (from: string, to: string) =>
  Math.round(
    (new Date(`${to}T00:00:00`).getTime() -
      new Date(`${from}T00:00:00`).getTime()) /
      86_400_000,
  )

const changeRatio = (current: number, previous: number): number | null => {
  if (!previous) return null
  return (current - previous) / Math.abs(previous)
}

function InfoHint({ text }: { text: string }) {
  const [hovered, setHovered] = useState(false)
  const [pinned, setPinned] = useState(false)
  return (
    <Popover
      open={hovered || pinned}
      onOpenChange={open => {
        if (!open) {
          setHovered(false)
          setPinned(false)
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={text}
          className="text-muted-foreground transition-colors hover:text-foreground"
          onPointerEnter={event => {
            if (event.pointerType === "mouse") setHovered(true)
          }}
          onPointerLeave={event => {
            if (event.pointerType === "mouse") setHovered(false)
          }}
          onClick={event => {
            event.preventDefault()
            setPinned(value => !value)
          }}
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto max-w-xs px-3 py-1.5 text-xs"
        onOpenAutoFocus={event => event.preventDefault()}
      >
        {text}
      </PopoverContent>
    </Popover>
  )
}

export default function CashflowPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [tab, setTab] = useTabSearchParam(CASHFLOW_TABS, "analysis")
  const [analysisVisited, setAnalysisVisited] = useState(tab === "analysis")
  const [tabAction, setTabAction] = useState<ReactNode | null>(null)

  useEffect(() => {
    if (tab === "analysis") setAnalysisVisited(true)
  }, [tab])

  const tabs: PageTab<CashflowTab>[] = [
    { key: "analysis", label: t.cashflow.tabs.analysis, Icon: ChartPie },
    { key: "labels", label: t.labels.tabs.labels, Icon: Tags },
    { key: "rules", label: t.labels.tabs.rules, Icon: Wand2 },
    { key: "automation", label: t.labels.tabs.automation, Icon: RefreshCcw },
  ]

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="w-full min-w-0 space-y-4 sm:space-y-6"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 shrink-0 p-1 md:hidden"
            onClick={() => navigate("/management")}
            aria-label={t.common.back}
          >
            <ArrowLeft size={20} />
          </Button>
          <h1 className="truncate text-2xl font-bold">{t.cashflow.title}</h1>
          <PinAssetButton
            assetId="management-cashflow"
            className="hidden shrink-0 md:inline-flex"
          />
        </div>
        {tabAction && (tab === "labels" || tab === "rules") && (
          <div className="flex shrink-0">{tabAction}</div>
        )}
      </div>

      <PageTabs
        tabs={tabs}
        active={tab}
        onChange={setTab}
        layoutId="cashflow-tab-indicator"
        className="-mt-2"
      />

      {(tab === "analysis" || analysisVisited) && (
        <div className={cn("min-w-0", tab !== "analysis" && "hidden")}>
          <CashflowAnalysis />
        </div>
      )}

      {tab !== "analysis" && (
        <LabelsManager tab={tab} onActionChange={setTabAction} />
      )}
    </motion.div>
  )
}

function CashflowAnalysis() {
  const { t, locale } = useI18n()
  const { mode } = useDataDisplayMode()
  const navigate = useNavigate()
  const navigateWithReturn = useNavigateWithReturn(t.cashflow.title)
  const [searchParams, setSearchParams] = useSearchParams()
  const { settings, entities, showToast } = useAppContext()
  const { getLabel, getLabelName } = useLabels()
  const { periodicFlows, ensurePeriodicFlows, refreshFlows } =
    useFinancialData()
  const currency = settings.general.defaultCurrency

  const [initialFilters] = useState(() => filtersFromParams(searchParams))
  const [preset, setPreset] = useState<PeriodPreset>(initialFilters.preset)
  const [[fromDate, toDate], setRange] = useState<[string, string]>(
    initialFilters.range,
  )
  const [entityIds, setEntityIds] = useState<string[]>(initialFilters.entityIds)
  const [summary, setSummary] = useState<CashflowSummary | null>(null)
  const [summaryGranularity, setSummaryGranularity] =
    useState<CashflowGranularity | null>(null)
  const [evolutionView, setEvolutionView] = useState<EvolutionView>(() =>
    localStorage.getItem(EVOLUTION_VIEW_KEY) === "heatmap" ? "heatmap" : "bars",
  )
  const [loading, setLoading] = useState(false)
  const [summarySettled, setSummarySettled] = useState(false)
  const [chartWidth, setChartWidth] = useState(0)
  const [breakdownSide, setBreakdownSide] = useState<"expenses" | "income">(
    "expenses",
  )
  const [recurring, setRecurring] = useState<RecurringMovement[] | null>(null)
  const recurringSectionRef = useRef<HTMLElement | null>(null)
  const recurringRequestedFor = useRef<(() => Promise<void>) | null>(null)
  const [showAllRecurring, setShowAllRecurring] = useState(false)
  const [showIgnoredRecurring, setShowIgnoredRecurring] = useState(false)
  const [trackingKey, setTrackingKey] = useState<string | null>(null)

  const granularity =
    evolutionView === "heatmap" ||
    daysBetween(fromDate, toDate) <= DAILY_GRANULARITY_MAX_DAYS
      ? CashflowGranularity.DAY
      : CashflowGranularity.MONTH

  const changeEvolutionView = (view: EvolutionView) => {
    setEvolutionView(view)
    localStorage.setItem(EVOLUTION_VIEW_KEY, view)
  }

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    FILTER_PARAMS.forEach(key => next.delete(key))
    if (preset !== DEFAULT_PRESET) next.set("period", preset)
    if (preset === "custom") {
      next.set("from", fromDate)
      next.set("to", toDate)
    }
    entityIds.forEach(id => next.append("entity", id))
    if (next.toString() !== searchParams.toString())
      setSearchParams(next, { replace: true })
  }, [preset, fromDate, toDate, entityIds, searchParams, setSearchParams])

  useRestoreReturnScroll(summarySettled)

  const entityOptions = useMemo(
    () =>
      (entities ?? []).filter(
        entity =>
          entity.type === EntityType.FINANCIAL_INSTITUTION ||
          entity.type === EntityType.CRYPTO_EXCHANGE,
      ),
    [entities],
  )

  const loadSummary = useCallback(async () => {
    if (!fromDate || !toDate || fromDate > toDate) return
    setLoading(true)
    try {
      const response = await getCashflowSummary({
        currency,
        from_date: fromDate,
        to_date: toDate,
        granularity,
        entities: entityIds.length ? entityIds : undefined,
      })
      setSummary(response)
      setSummaryGranularity(granularity)
    } catch (error) {
      console.error("Error loading cashflow:", error)
      showToast(t.common.unexpectedError, "error")
    } finally {
      setLoading(false)
      setSummarySettled(true)
    }
  }, [currency, fromDate, toDate, granularity, entityIds, showToast, t])

  const loadRecurring = useCallback(async () => {
    try {
      const response = await getRecurringMovements({
        currency,
        entities: entityIds.length ? entityIds : undefined,
      })
      setRecurring(response.movements)
    } catch (error) {
      console.error("Error loading recurring movements:", error)
      setRecurring([])
    }
  }, [currency, entityIds])

  const [activeRecurring, ignoredRecurring] = useMemo(() => {
    const active: RecurringMovement[] = []
    const ignored: RecurringMovement[] = []
    recurring?.forEach(movement =>
      (movement.ignored_id ? ignored : active).push(movement),
    )
    return [active, ignored]
  }, [recurring])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 639px)")
    let observer: IntersectionObserver | null = null

    const loadOnce = () => {
      if (recurringRequestedFor.current === loadRecurring) return
      recurringRequestedFor.current = loadRecurring
      void loadRecurring()
    }

    const loadWhenVisible = () => {
      observer?.disconnect()

      if (!mediaQuery.matches) {
        loadOnce()
        return
      }
      // Section sits at the top until the summary renders above it
      if (!summarySettled || recurringRequestedFor.current === loadRecurring)
        return

      const section = recurringSectionRef.current
      if (!section) return

      observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          observer?.disconnect()
          loadOnce()
        }
      })
      observer.observe(section)
    }

    loadWhenVisible()
    mediaQuery.addEventListener("change", loadWhenVisible)

    return () => {
      observer?.disconnect()
      mediaQuery.removeEventListener("change", loadWhenVisible)
    }
  }, [loadRecurring, summarySettled])

  useEffect(() => {
    void ensurePeriodicFlows()
  }, [ensurePeriodicFlows])

  const flowsById = useMemo(
    () =>
      new Map(
        periodicFlows
          .filter(flow => flow.id)
          .map(flow => [String(flow.id), flow]),
      ),
    [periodicFlows],
  )

  const handlePreset = (next: PeriodPreset) => {
    setPreset(next)
    if (next !== "custom") {
      setRange(presetRange(next))
    }
  }

  const money = (value: number, target = currency) =>
    formatCurrency(value, locale, currency, target)

  const txLink = (params: Record<string, string>) => {
    const search = new URLSearchParams({
      scope: "account",
      from_date: fromDate,
      to_date: toDate,
      ...params,
    })
    entityIds.forEach(id => search.append("entity", id))
    return `/transactions?${search.toString()}`
  }

  const chartData = useMemo(
    () =>
      (summary?.series ?? []).map(point => {
        const date = new Date(`${point.period}T00:00:00`)
        return {
          period: point.period,
          label:
            summaryGranularity === CashflowGranularity.DAY
              ? new Intl.DateTimeFormat(locale, {
                  day: "numeric",
                  month: "short",
                }).format(date)
              : new Intl.DateTimeFormat(locale, {
                  month: "short",
                  year: "2-digit",
                }).format(date),
          income: point.income,
          expenses: point.expenses,
        }
      }),
    [summary, summaryGranularity, locale],
  )

  const breakdown = useMemo(() => {
    if (!summary) return []
    const key = breakdownSide
    const rows = summary.by_label
      .filter(row => row[key] > 0)
      .sort((a, b) => b[key] - a[key])
    const total =
      key === "income" ? summary.totals.income : summary.totals.expenses
    return rows.map(row => ({
      row,
      amount: row[key],
      share: total > 0 ? row[key] / total : 0,
    }))
  }, [summary, breakdownSide])

  const handleTrack = async (movement: RecurringMovement) => {
    setTrackingKey(recurringMovementId(movement))
    const firstLabel = movement.label_ids.map(id => getLabel(id)).find(Boolean)
    try {
      await createPeriodicFlow({
        name: movement.name,
        amount: movement.amount,
        max_amount: movement.variable ? movement.max_amount : undefined,
        currency: movement.currency,
        flow_type:
          movement.type === TxType.INFLOW ? FlowType.EARNING : FlowType.EXPENSE,
        frequency: movement.frequency,
        category: firstLabel ? getLabelName(firstLabel) : undefined,
        icon: firstLabel?.icon ?? undefined,
        enabled: true,
        since: movement.last_date,
      })
      showToast(t.cashflow.recurring.tracked, "success")
      await Promise.all([loadRecurring(), refreshFlows()])
    } catch (error) {
      console.error("Error tracking recurring movement:", error)
      showToast(t.management.saveError, "error")
    } finally {
      setTrackingKey(null)
    }
  }

  const handleIgnore = async (movement: RecurringMovement) => {
    setTrackingKey(recurringMovementId(movement))
    try {
      await ignoreRecurringMovement({
        key: movement.key,
        type: movement.type,
        currency: movement.currency,
        amount: movement.amount,
      })
      showToast(t.cashflow.recurring.ignoredToast, "success")
      await loadRecurring()
    } catch (error) {
      console.error("Error ignoring recurring movement:", error)
      showToast(t.management.saveError, "error")
    } finally {
      setTrackingKey(null)
    }
  }

  const handleRestore = async (movement: RecurringMovement) => {
    if (!movement.ignored_id) return
    setTrackingKey(recurringMovementId(movement))
    try {
      await restoreRecurringMovement(movement.ignored_id)
      showToast(t.cashflow.recurring.restoredToast, "success")
      await loadRecurring()
    } catch (error) {
      console.error("Error restoring recurring movement:", error)
      showToast(t.management.saveError, "error")
    } finally {
      setTrackingKey(null)
    }
  }

  const renderKpiTitle = (
    title: string,
    Icon: typeof ArrowDownLeft,
    tone: KpiTone,
  ) => (
    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
      <span
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-md",
          KPI_ICON_TONES[tone],
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="truncate">{title}</span>
    </div>
  )

  const renderKpi = (
    title: string,
    Icon: typeof ArrowDownLeft,
    value: number,
    previous: number,
    tone: Exclude<KpiTone, "savings">,
    testId: string,
  ) => {
    const change = changeRatio(value, previous)
    const positiveIsGood = tone !== "expenses"
    const good = change !== null && change >= 0 === positiveIsGood
    const ChangeIcon = change !== null && change < 0 ? TrendingDown : TrendingUp
    return (
      <div
        className="min-w-0 space-y-1.5 bg-card p-3 sm:p-4"
        data-testid={testId}
      >
        {renderKpiTitle(title, Icon, tone)}
        <div
          className={cn(
            "truncate text-lg font-semibold tabular-nums sm:text-2xl",
            tone === "income" && "text-green-600 dark:text-green-400",
            tone === "expenses" && "text-red-600 dark:text-red-400",
            tone === "net" && value < 0 && "text-red-600 dark:text-red-400",
          )}
        >
          <Sensitive>
            <FormattedMarketValue value={money(value)} locale={locale} />
          </Sensitive>
        </div>
        <div className="flex h-5 items-center">
          {change !== null && (
            <span
              title={t.cashflow.vsPrevious}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
                good
                  ? "bg-green-500/10 text-green-600 dark:text-green-400"
                  : "bg-red-500/10 text-red-600 dark:text-red-400",
              )}
            >
              <ChangeIcon className="h-3 w-3" />
              {Math.abs(change * 100).toLocaleString(locale, {
                maximumFractionDigits: 1,
              })}
              %
            </span>
          )}
        </div>
      </div>
    )
  }

  const renderSavingsRate = (totals: CashflowTotals) => {
    const rate = totals.savings_rate
    return (
      <div
        className="min-w-0 space-y-1.5 bg-card p-3 sm:p-4"
        data-testid="kpi-savings-rate"
      >
        {renderKpiTitle(t.cashflow.savingsRate, PiggyBank, "savings")}
        <div
          className={cn(
            "truncate text-lg font-semibold tabular-nums sm:text-2xl",
            rate != null && rate < 0 && "text-red-600 dark:text-red-400",
          )}
        >
          {rate != null ? (
            <Sensitive>
              {(rate * 100).toLocaleString(locale, {
                maximumFractionDigits: 1,
              })}
              %
            </Sensitive>
          ) : (
            "—"
          )}
        </div>
        <div className="flex h-5 items-center">
          {mode !== DataDisplayMode.PRIVATE && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              {rate != null && (
                <div
                  className={cn(
                    "h-full rounded-full",
                    rate >= 0 ? "bg-violet-500" : "bg-red-500",
                  )}
                  style={{ width: `${Math.min(Math.abs(rate) * 100, 100)}%` }}
                />
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderBreakdownRow = (
    row: CashflowLabelBreakdown,
    amount: number,
    share: number,
  ) => {
    const label = row.label_id ? getLabel(row.label_id) : undefined
    const params: Record<string, string> = row.label_id
      ? { label: row.label_id }
      : { unlabeled: "true" }
    return (
      <button
        key={row.label_id ?? "unlabeled"}
        type="button"
        onClick={() => navigateWithReturn(txLink(params))}
        className="w-full space-y-1 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/50"
        data-testid="cashflow-label-row"
      >
        <div className="flex items-center justify-between gap-3">
          {label ? (
            <LabelChip label={label} name={getLabelName(label)} />
          ) : (
            <span className="text-xs font-medium text-muted-foreground">
              {t.labels.unlabeled}
            </span>
          )}
          <span className="text-sm font-medium">
            <Sensitive>{money(amount)}</Sensitive>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(share * 100, 100)}%`,
                backgroundColor: label?.color ?? "#9ca3af",
              }}
            />
          </div>
          <span className="w-12 text-right text-xs text-muted-foreground">
            {(share * 100).toLocaleString(locale, {
              maximumFractionDigits: 1,
            })}
            %
          </span>
        </div>
      </button>
    )
  }

  return (
    <div className="min-w-0 space-y-4 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="no-scrollbar -mx-6 flex gap-1.5 overflow-x-auto px-6 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
          {["custom" as const, ...PRESETS].map(key => (
            <button
              key={key}
              type="button"
              onClick={() => handlePreset(key)}
              data-testid={`cashflow-preset-${key}`}
              aria-pressed={preset === key}
              aria-label={
                key === "custom" ? t.cashflow.presets.custom : undefined
              }
              title={key === "custom" ? t.cashflow.presets.custom : undefined}
              className={cn(
                "flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                key === "custom" &&
                  "h-7 w-7 px-0 sm:h-auto sm:w-auto sm:justify-start sm:px-3",
                preset === key
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {key === "custom" && (
                <CalendarDays className="h-4 w-4 shrink-0" />
              )}
              <span
                className={key === "custom" ? "hidden sm:inline" : undefined}
              >
                {t.cashflow.presets[key]}
              </span>
            </button>
          ))}
        </div>
        {preset === "custom" && (
          <div className="grid min-w-0 grid-cols-1 gap-2 sm:flex">
            <div className="min-w-0 sm:w-40">
              <DatePicker
                value={fromDate}
                onChange={value => setRange([value, toDate])}
                placeholder={t.transactions.fromDate}
                className="w-full min-w-0"
              />
            </div>
            <div className="min-w-0 sm:w-40">
              <DatePicker
                value={toDate}
                onChange={value => setRange([fromDate, value])}
                placeholder={t.transactions.toDate}
                className="w-full min-w-0"
              />
            </div>
          </div>
        )}
        <div className="flex w-full min-w-0 items-center gap-2 sm:ml-auto sm:w-64">
          <Filter
            className="h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <EntitySelector
            entities={entityOptions}
            selectedEntityIds={entityIds}
            onSelectionChange={setEntityIds}
            className="min-w-0 flex-1"
          />
        </div>
      </div>

      {loading && !summary ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : summary ? (
        <>
          <Card
            className={cn(EDGE_CARD, "overflow-hidden")}
            data-testid="cashflow-kpis"
          >
            <div className="grid grid-cols-2 gap-px bg-border lg:grid-cols-4">
              {renderKpi(
                t.cashflow.income,
                ArrowDownLeft,
                summary.totals.income,
                summary.previous.income,
                "income",
                "kpi-income",
              )}
              {renderKpi(
                t.cashflow.expenses,
                ArrowUpRight,
                summary.totals.expenses,
                summary.previous.expenses,
                "expenses",
                "kpi-expenses",
              )}
              {renderKpi(
                t.cashflow.net,
                Scale,
                summary.totals.net,
                summary.previous.net,
                "net",
                "kpi-net",
              )}
              {renderSavingsRate(summary.totals)}
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border px-3 py-2 text-xs text-muted-foreground sm:px-4">
              <span>
                {t.cashflow.movementsCount.replace(
                  "{count}",
                  `${summary.totals.count}`,
                )}
              </span>
              {summary.excluded_count > 0 && (
                <span className="inline-flex items-center gap-1">
                  <span>·</span>
                  {t.cashflow.excludedCount.replace(
                    "{count}",
                    `${summary.excluded_count}`,
                  )}
                  <InfoHint text={t.cashflow.excludedInfo} />
                </span>
              )}
              <span className="ml-auto inline-flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                {t.cashflow.vsPrevious}
              </span>
            </div>
          </Card>

          {chartData.length === 0 ? (
            <Card className={EDGE_CARD}>
              <EmptyState
                icon={BarChart3}
                title={t.cashflow.empty.title}
                description={t.cashflow.empty.description}
                className="py-16"
                action={
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigateWithReturn("/transactions")}
                  >
                    {t.cashflow.empty.goToTransactions}
                  </Button>
                }
              />
            </Card>
          ) : (
            <>
              <section className="min-w-0 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="flex items-center text-lg font-bold">
                    <BarChart3 className="mr-2 h-5 w-5 text-primary" />
                    {t.cashflow.evolution}
                  </h2>
                  <div className="flex items-center gap-2">
                    {loading && <LoadingSpinner size="sm" />}
                    <div className="inline-flex rounded-md border border-input p-0.5">
                      {EVOLUTION_VIEWS.map(view => {
                        const ViewIcon = view === "bars" ? BarChart3 : Grid3x3
                        return (
                          <button
                            key={view}
                            type="button"
                            data-testid={`cashflow-evolution-${view}`}
                            aria-label={t.cashflow.evolutionViews[view]}
                            title={t.cashflow.evolutionViews[view]}
                            aria-pressed={evolutionView === view}
                            onClick={() => changeEvolutionView(view)}
                            className={cn(
                              "rounded px-2 py-1",
                              evolutionView === view
                                ? "bg-foreground text-background"
                                : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            <ViewIcon className="h-4 w-4" />
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
                <Card className={cn(EDGE_CARD, "p-4")}>
                  {evolutionView === "heatmap" ? (
                    summary &&
                    summaryGranularity === CashflowGranularity.DAY ? (
                      <CashflowHeatmap
                        series={summary.series}
                        fromDate={fromDate}
                        toDate={toDate}
                        formatAmount={value => money(value)}
                        onOpenDay={date =>
                          navigateWithReturn(
                            txLink({ from_date: date, to_date: date }),
                          )
                        }
                      />
                    ) : (
                      <div className="flex h-64 items-center justify-center">
                        <LoadingSpinner />
                      </div>
                    )
                  ) : (
                    <div className="h-64">
                      <ResponsiveContainer
                        width="100%"
                        height="100%"
                        onResize={width => setChartWidth(width)}
                      >
                        <BarChart
                          data={chartData}
                          margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            vertical={false}
                            className="opacity-30"
                          />
                          <XAxis
                            dataKey="label"
                            tick={{ fontSize: 11 }}
                            tickLine={false}
                            minTickGap={12}
                          />
                          <YAxis
                            tick={{ fontSize: chartWidth < 480 ? 10 : 11 }}
                            tickLine={false}
                            axisLine={false}
                            width={chartWidth < 480 ? 42 : 55}
                            tickFormatter={value =>
                              chartWidth < 480
                                ? new Intl.NumberFormat(locale, {
                                    notation: "compact",
                                    compactDisplay: "short",
                                    maximumFractionDigits: 1,
                                  }).format(Number(value))
                                : formatCompactCurrency(
                                    Number(value),
                                    locale,
                                    currency,
                                  )
                            }
                          />
                          <Tooltip
                            cursor={{
                              fill: "currentColor",
                              className: "opacity-5 dark:opacity-10",
                            }}
                            content={({ active, payload, label }) => {
                              if (!active || !payload?.length) return null
                              const row = payload[0].payload as {
                                income: number
                                expenses: number
                              }
                              return (
                                <div className="rounded-md border bg-background px-3 py-2 text-xs shadow-md">
                                  <p className="mb-1 font-semibold">{label}</p>
                                  <p className="text-green-600 dark:text-green-400">
                                    {t.cashflow.income}:{" "}
                                    <Sensitive>{money(row.income)}</Sensitive>
                                  </p>
                                  <p className="text-red-600 dark:text-red-400">
                                    {t.cashflow.expenses}:{" "}
                                    <Sensitive>{money(row.expenses)}</Sensitive>
                                  </p>
                                </div>
                              )
                            }}
                          />
                          <Bar
                            dataKey="income"
                            fill={INCOME_COLOR}
                            radius={[3, 3, 0, 0]}
                            maxBarSize={28}
                          />
                          <Bar
                            dataKey="expenses"
                            fill={EXPENSE_COLOR}
                            radius={[3, 3, 0, 0]}
                            maxBarSize={28}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Card>
              </section>

              <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:grid-cols-2">
                <section className="min-w-0 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <h2 className="flex items-center text-lg font-bold">
                        <Tags className="mr-2 h-5 w-5 text-primary" />
                        {t.cashflow.byLabel}
                      </h2>
                      <InfoHint text={t.cashflow.overlapHint} />
                    </div>
                    <div className="inline-flex rounded-md border border-input p-0.5">
                      {(["expenses", "income"] as const).map(side => (
                        <button
                          key={side}
                          type="button"
                          onClick={() => setBreakdownSide(side)}
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-medium",
                            breakdownSide === side
                              ? "bg-foreground text-background"
                              : "text-muted-foreground",
                          )}
                        >
                          {t.cashflow[side]}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Card className={cn(EDGE_CARD, "p-4")}>
                    {breakdown.length === 0 ? (
                      <EmptyState
                        icon={Tags}
                        title={
                          breakdownSide === "income"
                            ? t.cashflow.empty.noIncome
                            : t.cashflow.empty.noExpenses
                        }
                      />
                    ) : (
                      <div className="space-y-0.5">
                        {breakdown.map(item =>
                          renderBreakdownRow(item.row, item.amount, item.share),
                        )}
                      </div>
                    )}
                  </Card>
                </section>

                <section className="min-w-0 space-y-3">
                  <h2 className="flex items-center text-lg font-bold">
                    <Receipt className="mr-2 h-5 w-5 text-primary" />
                    {t.cashflow.topCounterparties}
                  </h2>
                  <Card className={cn(EDGE_CARD, "p-4")}>
                    {summary.top_counterparties.length === 0 ? (
                      <EmptyState
                        icon={Users}
                        title={t.cashflow.empty.noCounterparties}
                      />
                    ) : (
                      <div className="space-y-0.5">
                        {summary.top_counterparties.map(counterparty => (
                          <button
                            key={counterparty.name}
                            type="button"
                            data-testid="cashflow-counterparty-row"
                            onClick={() =>
                              navigateWithReturn(
                                txLink({ search: counterparty.name }),
                              )
                            }
                            className="flex w-full items-center justify-between gap-3 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/50"
                          >
                            <div className="min-w-0">
                              <div className="truncate text-sm">
                                {counterparty.name}
                              </div>
                              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                <span>
                                  {t.cashflow.movementsCount.replace(
                                    "{count}",
                                    `${counterparty.count}`,
                                  )}
                                </span>
                                {counterparty.label_ids
                                  .map(labelId => getLabel(labelId))
                                  .filter(label => label !== undefined)
                                  .slice(0, MAX_COUNTERPARTY_LABEL_DOTS)
                                  .map(label => (
                                    <span
                                      key={label.id}
                                      data-testid="counterparty-label-dot"
                                      title={getLabelName(label)}
                                      className="h-2 w-2 shrink-0 rounded-full"
                                      style={{
                                        backgroundColor:
                                          label.color ?? "#9ca3af",
                                      }}
                                    />
                                  ))}
                              </div>
                            </div>
                            <div className="shrink-0 text-right text-sm">
                              {counterparty.expenses > 0 && (
                                <div className="text-red-600 dark:text-red-400">
                                  <Sensitive>
                                    -{money(counterparty.expenses)}
                                  </Sensitive>
                                </div>
                              )}
                              {counterparty.income > 0 && (
                                <div className="text-green-600 dark:text-green-400">
                                  <Sensitive>
                                    +{money(counterparty.income)}
                                  </Sensitive>
                                </div>
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </Card>
                </section>
              </div>
            </>
          )}
        </>
      ) : null}

      <section ref={recurringSectionRef} className="min-w-0 space-y-3">
        <div className="flex items-center gap-1.5">
          <h2 className="flex items-center text-lg font-bold">
            <CalendarSync className="mr-2 h-5 w-5 text-primary" />
            {t.cashflow.recurring.title}
          </h2>
          <InfoHint text={t.cashflow.recurring.description} />
        </div>
        <Card
          className={cn(EDGE_CARD, "px-4 py-1")}
          data-testid="recurring-movements"
        >
          {recurring === null ? (
            <div className="flex justify-center py-6">
              <LoadingSpinner size="sm" />
            </div>
          ) : activeRecurring.length === 0 && ignoredRecurring.length === 0 ? (
            <EmptyState
              icon={CalendarSync}
              title={t.cashflow.recurring.empty}
              description={t.cashflow.recurring.emptyHint}
            />
          ) : (
            <>
              <div className="divide-y divide-border">
                {activeRecurring
                  .slice(
                    0,
                    showAllRecurring
                      ? activeRecurring.length
                      : MAX_VISIBLE_RECURRING_MOVEMENTS,
                  )
                  .map(movement => {
                    const incoming = movement.type === TxType.INFLOW
                    return (
                      <div
                        key={recurringMovementId(movement)}
                        className="flex min-w-0 flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
                        data-testid="recurring-movement"
                      >
                        <div className="min-w-0 flex-1 space-y-1">
                          <button
                            type="button"
                            onClick={() =>
                              navigateWithReturn(
                                `/transactions?scope=account&search=${encodeURIComponent(movement.search)}`,
                              )
                            }
                            className="block max-w-full truncate text-left text-sm font-medium hover:underline"
                            title={movement.name}
                          >
                            {movement.name}
                          </button>
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                            <span>
                              {t.management.frequency[movement.frequency]}
                            </span>
                            <span>·</span>
                            <span>
                              {t.cashflow.recurring.next.replace(
                                "{date}",
                                formatRecurringDate(movement.next_date, locale),
                              )}
                            </span>
                            <span>·</span>
                            <span>
                              {t.cashflow.recurring.occurrences.replace(
                                "{count}",
                                `${movement.occurrences}`,
                              )}
                            </span>
                            {movement.label_ids.map(labelId => {
                              const label = getLabel(labelId)
                              return label ? (
                                <LabelChip
                                  key={labelId}
                                  label={label}
                                  name={getLabelName(label)}
                                  hideNameOnMobile
                                />
                              ) : null
                            })}
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <div className="text-right">
                            <div
                              className={cn(
                                "text-sm font-semibold",
                                incoming
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-foreground",
                              )}
                            >
                              <Sensitive>
                                {incoming ? "+" : "-"}
                                {movement.variable ? "≈ " : ""}
                                {money(movement.amount, movement.currency)}
                              </Sensitive>
                            </div>
                            {movement.variable && (
                              <div className="text-xs text-muted-foreground">
                                <Sensitive>
                                  {t.cashflow.recurring.upTo.replace(
                                    "{amount}",
                                    money(
                                      movement.max_amount,
                                      movement.currency,
                                    ),
                                  )}
                                </Sensitive>
                              </div>
                            )}
                          </div>
                          {movement.tracked_flow_id ? (
                            <Popover>
                              <PopoverTrigger asChild>
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800 transition-colors hover:bg-green-200 dark:bg-green-900/30 dark:text-green-300 dark:hover:bg-green-900/50"
                                  data-testid="tracked-badge"
                                >
                                  <Check className="h-3 w-3" />
                                  {t.cashflow.recurring.trackedBadge}
                                </button>
                              </PopoverTrigger>
                              <PopoverContent align="end" className="w-72 p-3">
                                {(() => {
                                  const flow = flowsById.get(
                                    movement.tracked_flow_id,
                                  )
                                  if (!flow) {
                                    return (
                                      <div className="flex justify-center py-2">
                                        <LoadingSpinner size="sm" />
                                      </div>
                                    )
                                  }
                                  return (
                                    <div className="space-y-3">
                                      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                                        {t.cashflow.recurring.trackedAs}
                                      </div>
                                      <div className="flex items-start gap-2.5">
                                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                                          <Icon
                                            name={
                                              (flow.icon as IconName) ||
                                              "circle-dashed"
                                            }
                                            className="h-4 w-4"
                                          />
                                        </span>
                                        <div className="min-w-0 flex-1">
                                          <div className="truncate text-sm font-medium">
                                            {flow.name}
                                          </div>
                                          <div className="text-xs text-muted-foreground">
                                            {
                                              t.management.frequency[
                                                flow.frequency
                                              ]
                                            }
                                            {flow.category
                                              ? ` · ${flow.category}`
                                              : ""}
                                          </div>
                                        </div>
                                        <div className="shrink-0 text-sm font-semibold tabular-nums">
                                          <Sensitive>
                                            {money(flow.amount, flow.currency)}
                                          </Sensitive>
                                        </div>
                                      </div>
                                      {flow.next_date && (
                                        <div className="text-xs text-muted-foreground">
                                          {t.cashflow.recurring.next.replace(
                                            "{date}",
                                            formatRecurringDate(
                                              flow.next_date,
                                              locale,
                                            ),
                                          )}
                                        </div>
                                      )}
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 w-full gap-1.5"
                                        onClick={() =>
                                          navigate(
                                            `/management/recurring?tab=${flow.flow_type === FlowType.EARNING ? "earnings" : "expenses"}`,
                                          )
                                        }
                                      >
                                        {t.cashflow.recurring.openRecurring}
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                      </Button>
                                    </div>
                                  )
                                })()}
                              </PopoverContent>
                            </Popover>
                          ) : (
                            <div className="flex items-center gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 gap-1.5 rounded-full border-border bg-muted/60 px-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                                onClick={() => handleTrack(movement)}
                                disabled={
                                  trackingKey === recurringMovementId(movement)
                                }
                              >
                                <Plus className="h-3 w-3" />
                                {t.cashflow.recurring.track}
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
                                onClick={() => handleIgnore(movement)}
                                disabled={
                                  trackingKey === recurringMovementId(movement)
                                }
                                title={t.cashflow.recurring.ignore}
                                aria-label={t.cashflow.recurring.ignore}
                                data-testid="ignore-recurring"
                              >
                                <EyeOff className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
              </div>
              {activeRecurring.length > MAX_VISIBLE_RECURRING_MOVEMENTS &&
                !showAllRecurring && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 h-8 w-full gap-1.5 hover:bg-transparent hover:text-foreground"
                    onClick={() => setShowAllRecurring(true)}
                  >
                    {t.cashflow.recurring.showMore}
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                )}
              {ignoredRecurring.length > 0 && (
                <div
                  className={cn(
                    "py-2",
                    activeRecurring.length > 0 && "border-t border-border",
                  )}
                  data-testid="ignored-recurring"
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-2 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                    onClick={() => setShowIgnoredRecurring(value => !value)}
                  >
                    <span className="flex items-center gap-1.5">
                      <EyeOff className="h-3.5 w-3.5" />
                      {t.cashflow.recurring.ignoredSection.replace(
                        "{count}",
                        `${ignoredRecurring.length}`,
                      )}
                    </span>
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 transition-transform",
                        showIgnoredRecurring && "rotate-180",
                      )}
                    />
                  </button>
                  {showIgnoredRecurring && (
                    <div className="mt-1 divide-y divide-border">
                      {ignoredRecurring.map(movement => (
                        <div
                          key={recurringMovementId(movement)}
                          className="flex min-w-0 items-center justify-between gap-3 py-2"
                          data-testid="ignored-recurring-movement"
                        >
                          <div className="min-w-0 flex-1">
                            <div
                              className="truncate text-sm text-muted-foreground"
                              title={movement.name}
                            >
                              {movement.name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {t.management.frequency[movement.frequency]}
                            </div>
                          </div>
                          <div className="shrink-0 text-sm text-muted-foreground">
                            <Sensitive>
                              {movement.type === TxType.INFLOW ? "+" : "-"}
                              {movement.variable ? "≈ " : ""}
                              {money(movement.amount, movement.currency)}
                            </Sensitive>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 shrink-0 gap-1.5 rounded-full border-border bg-muted/60 px-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                            onClick={() => handleRestore(movement)}
                            disabled={
                              trackingKey === recurringMovementId(movement)
                            }
                          >
                            <RotateCcw className="h-3 w-3" />
                            {t.cashflow.recurring.restore}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </Card>
      </section>
    </div>
  )
}
