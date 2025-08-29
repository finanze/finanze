import { useMemo } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  Info,
  PiggyBank,
  FolderPlus,
  CalendarDays,
  ArrowLeft,
  TrendingUp,
  Folder,
  BarChart3,
} from "lucide-react"
import { Button } from "@/components/ui/Button"
import { useNavigate } from "react-router-dom"
import {
  ContributionFrequency,
  PeriodicContribution,
} from "@/types/contributions"
import { cn } from "@/lib/utils"
// Donut chart removed; using progress bar list visualization

// Monthly multiplier similar logic to recurring money page
const monthlyMultiplier = (f: ContributionFrequency) => {
  switch (f) {
    case ContributionFrequency.WEEKLY:
      return 52 / 12
    case ContributionFrequency.BIWEEKLY:
      return 26 / 12
    case ContributionFrequency.BIMONTHLY:
      return 6 / 12
    case ContributionFrequency.QUARTERLY:
      return 4 / 12
    case ContributionFrequency.SEMIANNUAL:
      return 2 / 12
    case ContributionFrequency.YEARLY:
      return 1 / 12
    case ContributionFrequency.MONTHLY:
    default:
      return 1
  }
}

export default function AutoContributionsPage() {
  const { t, locale } = useI18n()
  const { settings, entities } = useAppContext()
  const { contributions } = useFinancialData()
  const navigate = useNavigate()

  const getNextDateInfo = (nextDate?: string) => {
    if (!nextDate) return null
    const today = new Date()
    const next = new Date(nextDate)
    const diffDays = Math.ceil(
      (next.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
    )
    if (diffDays < 0)
      return { text: formatDate(nextDate, locale), className: "text-red-500" }
    if (diffDays === 0)
      return { text: t.management.today, className: "text-red-500" }
    if (diffDays === 1)
      return { text: t.management.tomorrow, className: "text-amber-500" }
    if (diffDays <= 7)
      return {
        text: t.management.inDays.replace("{days}", diffDays.toString()),
        className: "text-amber-500",
      }
    return {
      text: formatDate(nextDate, locale),
      className: "text-muted-foreground",
    }
  }

  const typeIcon = (type: string, color?: string) => {
    const style = color ? { color } : undefined
    switch (type) {
      case "STOCK_ETF":
      case "FUND":
        return <BarChart3 className="h-5 w-5" style={style} />
      case "FUND_PORTFOLIO":
        return <Folder className="h-5 w-5" style={style} />
      default:
        return <TrendingUp className="h-5 w-5" style={style} />
    }
  }

  // DO NOT change periodicByEntity (user fixed previously)
  const periodicByEntity = contributions || {}

  const flatContributions: {
    entityId: string
    contribution: PeriodicContribution
  }[] = useMemo(() => {
    const acc: { entityId: string; contribution: PeriodicContribution }[] = []
    Object.entries(periodicByEntity).forEach(([entityId, data]) => {
      if (data && Array.isArray((data as any).periodic)) {
        ;(data as any).periodic.forEach((c: PeriodicContribution) =>
          acc.push({ entityId, contribution: c }),
        )
      }
    })
    return acc
  }, [periodicByEntity])

  const monthlyTotal = useMemo(
    () =>
      flatContributions.reduce(
        (acc, { contribution }) =>
          contribution.active
            ? acc +
              contribution.amount * monthlyMultiplier(contribution.frequency)
            : acc,
        0,
      ),
    [flatContributions],
  )

  const grouped = useMemo(() => {
    const map: Record<string, PeriodicContribution[]> = {}
    flatContributions.forEach(({ entityId, contribution }) => {
      if (!map[entityId]) map[entityId] = []
      map[entityId].push(contribution)
    })
    Object.keys(map).forEach(id => {
      map[id].sort((a, b) => {
        if (a.active !== b.active) return a.active ? -1 : 1
        const aHas = !!a.next_date
        const bHas = !!b.next_date
        if (aHas && bHas)
          return (
            new Date(a.next_date!).getTime() - new Date(b.next_date!).getTime()
          )
        if (aHas !== bHas) return aHas ? -1 : 1
        return 0
      })
    })
    return map
  }, [flatContributions])

  const freqLabel = (f: ContributionFrequency) =>
    (t.management.contributionFrequency as any)?.[f] || f

  const activeCount = useMemo(
    () => flatContributions.filter(c => c.contribution.active).length,
    [flatContributions],
  )

  // Distribution data for progress bars (monthly normalized, active only)
  const distributionData = useMemo(() => {
    const map = new Map<
      string,
      { amount: number; type?: string; byType: boolean }
    >()
    flatContributions.forEach(({ contribution }) => {
      if (!contribution.active) return
      const normalized =
        contribution.amount * monthlyMultiplier(contribution.frequency)
      const key =
        (contribution as any).target_name ||
        contribution.target ||
        contribution.target_type
      const byType = !((contribution as any).target_name || contribution.target)
      const existing = map.get(key)
      if (existing) existing.amount += normalized
      else
        map.set(key, {
          amount: normalized,
          type: contribution.target_type,
          byType,
        })
    })
    const entries = Array.from(map.entries()).map(([key, v]) => ({
      name: v.byType
        ? (t.enums?.productType as any)?.[v.type || key] || key
        : key,
      rawKey: key,
      value: v.amount,
      byType: v.byType,
    }))
    entries.sort((a, b) => b.value - a.value)
    const total = entries.reduce((a, b) => a + b.value, 0) || 1
    return entries.map(e => ({
      ...e,
      percentage: (e.value / total) * 100,
      total,
    }))
  }, [flatContributions, t])

  const colors = [
    "#6366F1",
    "#10B981",
    "#F59E0B",
    "#EF4444",
    "#3B82F6",
    "#8B5CF6",
    "#EC4899",
    "#14B8A6",
    "#F97316",
    "#0EA5E9",
  ]
  const barColor = (i: number) => colors[i % colors.length]

  // Map rawKey -> color for quick lookup when painting icons (inactive ones fallback to muted)
  const distributionColorMap = useMemo(() => {
    const m: Record<string, string> = {}
    distributionData.forEach((d, i) => {
      m[d.rawKey] = colors[i % colors.length]
    })
    return m
  }, [distributionData])

  return (
    <div className="space-y-6 pb-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/management")}
        >
          {" "}
          <ArrowLeft className="h-4 w-4" />{" "}
        </Button>
        <h1 className="text-2xl font-bold">{t.management.autoContributions}</h1>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4">
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-3">
              <CalendarDays className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                {t.management.monthlyAverageContributions}
              </span>
            </div>
            <div>
              <div className="text-3xl font-bold leading-tight tracking-tight">
                {formatCurrency(
                  monthlyTotal,
                  locale,
                  settings?.general?.defaultCurrency,
                )}
              </div>
            </div>
          </Card>
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                {t.management.activeContributions}
              </span>
            </div>
            <div>
              <div className="text-3xl font-bold leading-tight tracking-tight">
                {activeCount}
              </div>
            </div>
          </Card>
        </div>
        {distributionData.length > 0 && (
          <Card className="p-5 flex flex-col lg:col-span-2 min-w-0">
            <div className="flex items-center justify-between mb-3">
              <h3
                className="text-sm font-medium text-muted-foreground"
                title={t.management.monthlyPerTarget}
              >
                {t.management.monthlyPerTarget}
              </h3>
              <span className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">
                {formatCurrency(
                  distributionData[0].total,
                  locale,
                  settings?.general?.defaultCurrency,
                )}
              </span>
            </div>
            {/* On small screens allow full height so content isn't visually "cut"; restrict only on large screens */}
            <div className="space-y-3 overflow-auto lg:max-h-72 pr-1 scrollbar-thin scrollbar-thumb-border/30">
              {distributionData.map((d, i) => (
                <div key={d.rawKey} className="group">
                  <div className="flex justify-between gap-4 text-xs font-medium mb-1">
                    <span className="truncate" title={d.name}>
                      {d.name}
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground group-hover:text-foreground transition-colors">
                      {formatCurrency(
                        d.value,
                        locale,
                        settings?.general?.defaultCurrency,
                      )}{" "}
                      · {d.percentage.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${d.percentage}%`,
                        background: barColor(i),
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {flatContributions.length === 0 && (
        <Card className="p-10 flex flex-col items-center gap-4 text-center">
          <PiggyBank className="h-12 w-12 text-muted-foreground" />
          <div>
            <h2 className="text-lg font-semibold mb-1">
              {t.management.noAutoContributionsTitle}
            </h2>
            <p className="text-sm text-muted-foreground max-w-md">
              {t.management.noAutoContributionsDescription}
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate("/entities")}>
            {" "}
            <FolderPlus className="h-4 w-4 mr-2" />{" "}
            {t.management.goToIntegrations}
          </Button>
        </Card>
      )}

      {Object.entries(grouped).map(([entityId, list]) => {
        const entityName =
          entities.find(e => e.id === entityId)?.name || entityId
        return (
          <div key={entityId} className="space-y-4">
            <h2 className="text-sm font-semibold text-muted-foreground tracking-wide">
              {entityName}
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {list.map(c => {
                const productTypeLabel =
                  (t.enums?.productType as any)?.[c.target_type] ||
                  c.target_type
                const nextInfo = c.active ? getNextDateInfo(c.next_date) : null
                return (
                  <Card
                    key={c.id}
                    className={cn(
                      "px-6 pt-4 pb-5 flex flex-col transition-shadow hover:shadow-md border-border/60 dark:border-border/60 h-full",
                      !c.active && "opacity-50",
                    )}
                  >
                    <div className="flex items-start gap-4">
                      <div className="shrink-0 mt-0.5">
                        {typeIcon(
                          c.target_type,
                          c.active
                            ? distributionColorMap[
                                (c as any).target_name ||
                                  c.target ||
                                  c.target_type
                              ]
                            : undefined,
                        )}
                      </div>
                      <div className="min-w-0 flex-1 flex flex-col">
                        <div className="flex justify-between gap-3 items-start">
                          <h3 className="font-semibold text-base leading-snug truncate pr-2">
                            {c.alias || c.target_name || productTypeLabel}
                          </h3>
                          <div className="text-2xl font-semibold tracking-tight leading-none">
                            {formatCurrency(
                              c.amount,
                              locale,
                              settings?.general?.defaultCurrency || c.currency,
                              c.currency,
                            )}
                          </div>
                        </div>
                        <div className="mt-auto flex items-center justify-between pt-4 text-[0.7rem] font-medium">
                          <div className="flex items-center gap-3">
                            <Badge className="bg-muted text-foreground/80 dark:bg-muted/70 flex items-center gap-1 px-2 py-0.5 rounded-full">
                              <CalendarDays className="h-3 w-3" />{" "}
                              {freqLabel(c.frequency)}
                            </Badge>
                            {nextInfo && (
                              <span
                                className={cn(
                                  "flex items-center gap-1",
                                  nextInfo.className,
                                )}
                              >
                                <CalendarDays className="h-3 w-3" />{" "}
                                {nextInfo.text}
                              </span>
                            )}
                          </div>
                          <Popover>
                            <PopoverTrigger asChild>
                              <button
                                className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                aria-label="info"
                              >
                                <Info className="h-4 w-4" />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent
                              side="left"
                              align="start"
                              className="w-80"
                            >
                              <div className="space-y-2 text-sm">
                                <div className="flex justify-between gap-4">
                                  <span className="font-medium text-muted-foreground">
                                    {t.management.targetType}
                                  </span>
                                  <span className="font-medium">
                                    {productTypeLabel}
                                  </span>
                                </div>
                                {c.target && (
                                  <div className="flex justify-between gap-4">
                                    <span className="font-medium text-muted-foreground">
                                      {t.management.target}
                                    </span>
                                    <span className="truncate max-w-[55%] text-right">
                                      {c.target}
                                    </span>
                                  </div>
                                )}
                                <div className="flex justify-between gap-4">
                                  <span className="font-medium text-muted-foreground">
                                    {t.management.since}
                                  </span>
                                  <span>
                                    {c.since
                                      ? formatDate(c.since, locale)
                                      : t.common.notAvailable}
                                  </span>
                                </div>
                                {c.until && (
                                  <div className="flex justify-between gap-4">
                                    <span className="font-medium text-muted-foreground">
                                      {t.management.until}
                                    </span>
                                    <span>{formatDate(c.until, locale)}</span>
                                  </div>
                                )}
                                <div className="flex justify-between gap-4">
                                  <span className="font-medium text-muted-foreground">
                                    {t.management.enabled}
                                  </span>
                                  <span
                                    className={cn(
                                      "font-medium",
                                      c.active
                                        ? "text-green-500"
                                        : "text-red-500",
                                    )}
                                  >
                                    {c.active
                                      ? t.management.enabled
                                      : t.management.disabled}
                                  </span>
                                </div>
                                <div className="flex justify-between gap-4">
                                  <span className="font-medium text-muted-foreground">
                                    {t.management.monthlyAverageContribution}
                                  </span>
                                  <span>
                                    {formatCurrency(
                                      c.amount * monthlyMultiplier(c.frequency),
                                      locale,
                                      settings?.general?.defaultCurrency ||
                                        c.currency,
                                      c.currency,
                                    )}
                                  </span>
                                </div>
                              </div>
                            </PopoverContent>
                          </Popover>
                        </div>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
