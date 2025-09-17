import { useState, useEffect, useMemo } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { DatePicker } from "@/components/ui/DatePicker"
import { Switch } from "@/components/ui/Switch"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { CategorySelector } from "@/components/ui/CategorySelector"
import { Badge } from "@/components/ui/Badge"
import { Card } from "@/components/ui/Card"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { IconPicker, Icon, type IconName } from "@/components/ui/icon-picker"
import {
  Plus,
  Edit,
  Trash2,
  BanknoteArrowUp,
  BanknoteArrowDown,
  Tag,
  Clock,
  ArrowLeft,
  CalendarDays,
  Lightbulb,
  LightbulbOff,
  X,
  Check,
  Link2,
  AlertTriangle,
  PiggyBank,
} from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { cn, getCurrencySymbol, getColorForName } from "@/lib/utils"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  FlowType,
  FlowFrequency,
  PeriodicFlow,
  CreatePeriodicFlowRequest,
  UpdatePeriodicFlowRequest,
} from "@/types"
import { ProductType, Loan, Loans } from "@/types/position"
import { ContributionFrequency } from "@/types/contributions"
import {
  createPeriodicFlow,
  updatePeriodicFlow,
  deletePeriodicFlow,
} from "@/services/api"

export default function RecurringMoneyPage() {
  const { t, locale } = useI18n()
  const { showToast, settings } = useAppContext()
  const { periodicFlows, refreshFlows, positionsData, contributions } =
    useFinancialData()
  const navigate = useNavigate()
  const [loading] = useState(false)
  const [sortBy, setSortBy] = useState<"amount" | "date">("amount")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [editingFlow, setEditingFlow] = useState<PeriodicFlow | null>(null)
  const [deletingFlow, setDeletingFlow] = useState<PeriodicFlow | null>(null)
  const [existingCategories, setExistingCategories] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [categoryFilter, setCategoryFilter] = useState<string[]>([])
  const [showContributions, setShowContributions] = useState(true)
  // When category filter is active we suppress contributions per requirement
  const effectiveShowContributions =
    showContributions && categoryFilter.length === 0
  const [formData, setFormData] = useState<CreatePeriodicFlowRequest>({
    name: "",
    amount: 0,
    flow_type: FlowType.EARNING,
    frequency: FlowFrequency.MONTHLY,
    category: "",
    enabled: true,
    since: "",
    until: "",
    currency: settings?.general?.defaultCurrency,
  })

  // Sort flows by amount or next_date
  const sortedFlows = useMemo(() => {
    const baseFlows = categoryFilter.length
      ? periodicFlows.filter(
          f => f.category && categoryFilter.includes(f.category),
        )
      : periodicFlows
    const sortFn = (a: PeriodicFlow, b: PeriodicFlow) => {
      if (sortBy === "amount") {
        return b.amount - a.amount
      } else {
        // Sort by next_date
        const aDate = a.next_date ? new Date(a.next_date).getTime() : Infinity
        const bDate = b.next_date ? new Date(b.next_date).getTime() : Infinity
        return aDate - bDate
      }
    }

    const sortedPeriodicFlows = [...baseFlows].sort(sortFn)

    return {
      earnings: sortedPeriodicFlows.filter(
        flow => flow.flow_type === FlowType.EARNING,
      ),
      expenses: sortedPeriodicFlows.filter(
        flow => flow.flow_type === FlowType.EXPENSE,
      ),
    }
  }, [periodicFlows, sortBy, categoryFilter])

  // Calculate monthly amounts for KPIs
  const monthlyAmounts = useMemo(() => {
    const baseFlows = categoryFilter.length
      ? periodicFlows.filter(
          f => f.category && categoryFilter.includes(f.category),
        )
      : periodicFlows
    const getMonthlyMultiplier = (frequency: FlowFrequency): number => {
      switch (frequency) {
        case FlowFrequency.DAILY:
          return 30 // Approximate days per month
        case FlowFrequency.WEEKLY:
          return 4.33 // Approximate weeks per month (52/12)
        case FlowFrequency.MONTHLY:
          return 1
        case FlowFrequency.EVERY_TWO_MONTHS:
          return 0.5
        case FlowFrequency.QUARTERLY:
          return 1 / 3 // Every 3 months
        case FlowFrequency.EVERY_FOUR_MONTHS:
          return 1 / 4
        case FlowFrequency.SEMIANNUALLY:
          return 1 / 6 // Every 6 months
        case FlowFrequency.YEARLY:
          return 1 / 12
        default:
          return 1
      }
    }

    const monthlyEarnings = baseFlows
      .filter(flow => flow.flow_type === FlowType.EARNING && flow.enabled)
      .reduce((total, flow) => {
        const amount = flow.amount
        const multiplier = getMonthlyMultiplier(flow.frequency)
        return total + amount * multiplier
      }, 0)

    const monthlyExpenses = baseFlows
      .filter(flow => flow.flow_type === FlowType.EXPENSE && flow.enabled)
      .reduce((total, flow) => {
        const amount = flow.amount
        const multiplier = getMonthlyMultiplier(flow.frequency)
        return total + amount * multiplier
      }, 0)

    // Monthly contributions (active only) if enabled
    let monthlyContributions = 0
    if (effectiveShowContributions && contributions) {
      Object.values(contributions).forEach(group => {
        if (!group?.periodic) return
        group.periodic.forEach(c => {
          if (!c.active) return
          const freq = c.frequency as ContributionFrequency
          const multiplier =
            freq === ContributionFrequency.WEEKLY
              ? 52 / 12
              : freq === ContributionFrequency.BIWEEKLY
                ? 26 / 12
                : freq === ContributionFrequency.BIMONTHLY
                  ? 6 / 12
                  : freq === ContributionFrequency.QUARTERLY
                    ? 4 / 12
                    : freq === ContributionFrequency.SEMIANNUAL
                      ? 2 / 12
                      : freq === ContributionFrequency.YEARLY
                        ? 1 / 12
                        : 1
          monthlyContributions += c.amount * multiplier
        })
      })
    }
    return { monthlyEarnings, monthlyExpenses, monthlyContributions }
  }, [periodicFlows, categoryFilter, contributions, effectiveShowContributions])

  // Utilization badge color scale (starts warm >55%)
  const getUtilizationBadgeClasses = (percent: number) => {
    if (percent <= 55)
      return "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
    if (percent <= 70)
      return "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
    if (percent <= 85)
      return "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300"
    if (percent <= 100)
      return "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
    return "bg-red-200 text-red-800 dark:bg-red-950 dark:text-red-200 border border-red-500/40"
  }

  // Color functions for different shades - traditional red/green palette
  // Darker colors for bigger amounts (lower index), lighter for smaller amounts
  const getEarningsColor = (index: number) => {
    const greenShades = [
      "bg-green-700", // Darkest for biggest
      "bg-green-600",
      "bg-green-500",
      "bg-green-400",
      "bg-green-300",
      "bg-green-200",
      "bg-green-100",
    ]
    return greenShades[index % greenShades.length]
  }

  const getExpensesColor = (index: number) => {
    const redShades = [
      "bg-red-700", // Darkest for biggest
      "bg-red-600",
      "bg-red-500",
      "bg-red-400",
      "bg-red-300",
      "bg-red-200",
      "bg-red-100",
    ]
    return redShades[index % redShades.length]
  }

  // Calculate flow distribution for the horizontal bar chart
  const flowDistribution = useMemo(() => {
    const baseFlows = categoryFilter.length
      ? periodicFlows.filter(
          f => f.category && categoryFilter.includes(f.category),
        )
      : periodicFlows
    const enabledFlows = baseFlows.filter(flow => flow.enabled)

    // Group earnings by category
    const earningsGroups = enabledFlows
      .filter(flow => flow.flow_type === FlowType.EARNING)
      .reduce(
        (groups, flow) => {
          const category = flow.category || flow.name
          const monthlyAmount =
            flow.amount *
            (flow.frequency === FlowFrequency.DAILY
              ? 30
              : flow.frequency === FlowFrequency.WEEKLY
                ? 4.33
                : flow.frequency === FlowFrequency.MONTHLY
                  ? 1
                  : flow.frequency === FlowFrequency.EVERY_TWO_MONTHS
                    ? 0.5
                    : flow.frequency === FlowFrequency.QUARTERLY
                      ? 1 / 3
                      : flow.frequency === FlowFrequency.EVERY_FOUR_MONTHS
                        ? 1 / 4
                        : flow.frequency === FlowFrequency.SEMIANNUALLY
                          ? 1 / 6
                          : flow.frequency === FlowFrequency.YEARLY
                            ? 1 / 12
                            : 1)

          if (!groups[category]) {
            groups[category] = { amount: 0, flows: [] }
          }
          groups[category].amount += monthlyAmount
          groups[category].flows.push(flow)
          return groups
        },
        {} as Record<string, { amount: number; flows: PeriodicFlow[] }>,
      )

    // Group expenses by category
    const expensesGroups = enabledFlows
      .filter(flow => flow.flow_type === FlowType.EXPENSE)
      .reduce(
        (groups, flow) => {
          const category = flow.category || flow.name
          const monthlyAmount =
            flow.amount *
            (flow.frequency === FlowFrequency.DAILY
              ? 30
              : flow.frequency === FlowFrequency.WEEKLY
                ? 4.33
                : flow.frequency === FlowFrequency.MONTHLY
                  ? 1
                  : flow.frequency === FlowFrequency.EVERY_TWO_MONTHS
                    ? 0.5
                    : flow.frequency === FlowFrequency.QUARTERLY
                      ? 1 / 3
                      : flow.frequency === FlowFrequency.EVERY_FOUR_MONTHS
                        ? 1 / 4
                        : flow.frequency === FlowFrequency.SEMIANNUALLY
                          ? 1 / 6
                          : flow.frequency === FlowFrequency.YEARLY
                            ? 1 / 12
                            : 1)

          if (!groups[category]) {
            groups[category] = { amount: 0, flows: [] }
          }
          groups[category].amount += monthlyAmount
          groups[category].flows.push(flow)
          return groups
        },
        {} as Record<string, { amount: number; flows: PeriodicFlow[] }>,
      )

    const totalEarnings = monthlyAmounts.monthlyEarnings
    const totalExpensesBase = monthlyAmounts.monthlyExpenses
    const totalContributions = monthlyAmounts.monthlyContributions
    const totalExpenses =
      totalExpensesBase + (effectiveShowContributions ? totalContributions : 0)
    const totalAmount = totalEarnings + totalExpenses

    // Convert to arrays with percentages
    const earningsData = Object.entries(earningsGroups).map(
      ([category, data], index) => ({
        category,
        amount: data.amount,
        percentage: totalAmount > 0 ? (data.amount / totalAmount) * 100 : 0,
        flows: data.flows,
        type: "earning" as const,
        color: getEarningsColor(index),
      }),
    )

    const expensesData = Object.entries(expensesGroups).map(
      ([category, data], index) => ({
        category,
        amount: data.amount,
        percentage: totalAmount > 0 ? (data.amount / totalAmount) * 100 : 0,
        flows: data.flows,
        type: "expense" as const,
        color: getExpensesColor(index),
      }),
    )

    return {
      earnings: earningsData.sort((a, b) => b.amount - a.amount), // Biggest first (leftmost)
      expenses: expensesData.sort((a, b) => b.amount - a.amount), // Biggest first (rightmost)
      totalEarnings,
      totalExpenses, // includes contributions when toggle on
      totalAmount,
      contributionsAmount: effectiveShowContributions ? totalContributions : 0,
    }
  }, [
    periodicFlows,
    monthlyAmounts,
    categoryFilter,
    effectiveShowContributions,
  ])

  const toggleCategoryFilter = (category: string) => {
    setCategoryFilter(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category],
    )
  }

  const categoryOptions: MultiSelectOption[] = useMemo(
    () => existingCategories.map(c => ({ value: c, label: c })),
    [existingCategories],
  )

  // Get loan suggestions from positions data
  const loanSuggestions = useMemo(() => {
    if (!positionsData?.positions) {
      return []
    }

    const loans: Loan[] = []

    // Extract all loans from positions data
    Object.values(positionsData.positions).forEach(globalPosition => {
      // Check if this entity has loan products
      if (
        globalPosition.products &&
        globalPosition.products[ProductType.LOAN]
      ) {
        const loanProducts = globalPosition.products[ProductType.LOAN] as Loans

        if (loanProducts && loanProducts.entries) {
          const entityLoans = loanProducts.entries
          loans.push(...entityLoans)
        }
      }
    })

    // Filter loans that don't already have a corresponding recurring expense
    const filteredLoans = loans
      .filter(loan => {
        // Skip loans without essential data
        if (
          !loan ||
          typeof loan.current_installment !== "number" ||
          loan.current_installment <= 0
        ) {
          return false
        }

        const existingExpense = periodicFlows.find(
          flow =>
            flow.flow_type === FlowType.EXPENSE &&
            Math.abs(flow.amount - loan.current_installment) < 0.01 &&
            // Check by creation date and until date matches
            loan.creation &&
            flow.since === loan.creation,
        )
        return !existingExpense
      })
      .map(loan => {
        // Use creation date as since, fallback to next_payment_date if creation doesn't exist
        const sinceDate = loan.creation || loan.next_payment_date

        return {
          id: loan.id,
          name: loan.name || t.management.loanSuggestions.loanName,
          amount: loan.current_installment,
          currency: loan.currency,
          maturityDate: loan.maturity,
          sinceDate: sinceDate,
        }
      })

    return filteredLoans
  }, [positionsData, periodicFlows, t.management.loanSuggestions.loanName])

  const [dismissedSuggestions, setDismissedSuggestions] = useState<string[]>(
    () => {
      try {
        if (typeof window === "undefined") return []
        const stored = localStorage.getItem("dismissedLoanSuggestions")
        return stored ? JSON.parse(stored) : []
      } catch {
        return []
      }
    },
  )
  const [showDismissed, setShowDismissed] = useState(false)

  const handleDismissSuggestion = (loanId: string) => {
    const newDismissed = [...dismissedSuggestions, loanId]
    setDismissedSuggestions(newDismissed)
    localStorage.setItem(
      "dismissedLoanSuggestions",
      JSON.stringify(newDismissed),
    )
  }

  const handleRestoreSuggestion = (loanId: string) => {
    const newDismissed = dismissedSuggestions.filter(id => id !== loanId)
    setDismissedSuggestions(newDismissed)
    localStorage.setItem(
      "dismissedLoanSuggestions",
      JSON.stringify(newDismissed),
    )
  }

  const handleAcceptSuggestion = async (suggestion: any) => {
    const newFlow: CreatePeriodicFlowRequest = {
      name: t.management.loanSuggestions.loanPayment.replace(
        "{loanName}",
        suggestion.name,
      ),
      amount: suggestion.amount.toString(),
      flow_type: FlowType.EXPENSE,
      frequency: FlowFrequency.MONTHLY,
      category: t.management.loanSuggestions.loanCategory,
      enabled: true,
      since: suggestion.sinceDate || new Date().toISOString().split("T")[0],
      until: suggestion.maturityDate || "",
      currency: suggestion.currency,
    }

    try {
      await createPeriodicFlow(newFlow)
      showToast(t.management.loanSuggestions.acceptedSuccess, "success")
      refreshFlows()
      handleDismissSuggestion(suggestion.id)
    } catch (error) {
      console.error("Error accepting suggestion:", error)
      showToast(t.management.loanSuggestions.acceptedError, "error")
    }
  }

  useEffect(() => {
    // Extract unique categories for suggestions
    const categories = periodicFlows
      .map(flow => flow.category)
      .filter((category): category is string => Boolean(category))
      .filter((category, index, arr) => arr.indexOf(category) === index)
    setExistingCategories(categories)
  }, [periodicFlows])

  const handleSubmit = async () => {
    // Validate required fields
    const errors: string[] = []
    if (!formData.name.trim()) errors.push("name")
    if (!formData.amount) errors.push("amount")
    if (!formData.since.trim()) errors.push("since")
    if (!formData.frequency.trim()) errors.push("frequency")

    setValidationErrors(errors)

    if (errors.length > 0) {
      return
    }

    try {
      if (editingFlow) {
        const updateData: UpdatePeriodicFlowRequest = {
          id: editingFlow.id!,
          ...formData,
        }
        await updatePeriodicFlow(updateData)
      } else {
        await createPeriodicFlow(formData)
      }

      showToast(t.management.saveSuccess, "success")
      setIsDialogOpen(false)
      resetForm()
      refreshFlows()
    } catch (error) {
      console.error("Error saving flow:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const handleDelete = async () => {
    if (!deletingFlow) return

    try {
      await deletePeriodicFlow(deletingFlow.id!)
      showToast(t.management.deleteSuccess, "success")
      setIsDeleteDialogOpen(false)
      setDeletingFlow(null)
      refreshFlows()
    } catch (error) {
      console.error("Error deleting flow:", error)
      showToast(t.management.deleteError, "error")
    }
  }

  const resetForm = () => {
    setFormData({
      name: "",
      amount: 0,
      flow_type: FlowType.EARNING,
      frequency: FlowFrequency.MONTHLY,
      category: "",
      enabled: true,
      since: "",
      until: "",
      currency: settings?.general?.defaultCurrency,
    })
    setEditingFlow(null)
    setValidationErrors([])
  }

  const openEditDialog = (flow: PeriodicFlow) => {
    setEditingFlow(flow)
    setValidationErrors([])
    setFormData({
      name: flow.name,
      amount: flow.amount,
      flow_type: flow.flow_type,
      frequency: flow.frequency,
      category: flow.category || "",
      enabled: flow.enabled,
      since: flow.since,
      until: flow.until || "",
      currency: flow.currency,
      icon: flow.icon,
    })
    setIsDialogOpen(true)
  }

  const openDeleteDialog = (flow: PeriodicFlow) => {
    setDeletingFlow(flow)
    setIsDeleteDialogOpen(true)
  }

  const getFrequencyLabel = (frequency: FlowFrequency) => {
    const frequencyMap: Record<FlowFrequency, string> = {
      [FlowFrequency.DAILY]: t.management.frequency.DAILY,
      [FlowFrequency.WEEKLY]: t.management.frequency.WEEKLY,
      [FlowFrequency.MONTHLY]: t.management.frequency.MONTHLY,
      [FlowFrequency.EVERY_TWO_MONTHS]: t.management.frequency.EVERY_TWO_MONTHS,
      [FlowFrequency.QUARTERLY]: t.management.frequency.QUARTERLY,
      [FlowFrequency.EVERY_FOUR_MONTHS]:
        t.management.frequency.EVERY_FOUR_MONTHS,
      [FlowFrequency.SEMIANNUALLY]: t.management.frequency.SEMIANNUALLY,
      [FlowFrequency.YEARLY]: t.management.frequency.YEARLY,
    }
    return frequencyMap[frequency] || frequency
  }

  const getNextDateInfo = (nextDate: string | undefined) => {
    if (!nextDate) return null

    const today = new Date()
    const next = new Date(nextDate)
    const diffTime = next.getTime() - today.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    let urgencyLevel: "urgent" | "soon" | "normal" = "normal"
    let timeText = ""

    if (diffDays === 0) {
      urgencyLevel = "urgent"
      timeText = t.management.today
    } else if (diffDays === 1) {
      urgencyLevel = "urgent"
      timeText = t.management.tomorrow
    } else if (diffDays <= 7) {
      urgencyLevel = "soon"
      timeText = t.management.inDays.replace("{days}", diffDays.toString())
    } else {
      urgencyLevel = "normal"
      timeText = formatDate(nextDate, locale)
    }

    return {
      urgencyLevel,
      timeText,
      formattedDate: formatDate(nextDate, locale),
    }
  }

  const FlowSection = ({
    title,
    flows,
    flowType,
    emptyMessage,
    addMessage,
    extraButton,
  }: {
    title: string
    flows: PeriodicFlow[]
    flowType: FlowType
    emptyMessage: string
    addMessage: string
    extraButton?: any
  }) => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {flowType === FlowType.EARNING ? (
            <BanknoteArrowUp className="text-green-600" size={24} />
          ) : (
            <BanknoteArrowDown className="text-red-600" size={24} />
          )}
          <h2 className="text-xl font-semibold">{title}</h2>
        </div>
        <div className="flex items-center gap-2">
          {extraButton}
          <Button
            onClick={() => {
              resetForm()
              setFormData(prev => ({ ...prev, flow_type: flowType }))
              setIsDialogOpen(true)
            }}
            size="sm"
            className="flex items-center gap-2 bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
          >
            <Plus size={16} />
          </Button>
        </div>
      </div>

      {flows.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <div className="flex justify-center mb-4">
            {flowType === FlowType.EARNING ? (
              <BanknoteArrowUp className="text-green-400" size={48} />
            ) : (
              <BanknoteArrowDown className="text-red-400" size={48} />
            )}
          </div>
          <p className="text-lg font-medium mb-2">{emptyMessage}</p>
          <p className="text-sm">{addMessage}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {flows.map(flow => {
            const nextDateInfo = getNextDateInfo(flow.next_date)

            return (
              <div
                key={flow.id}
                className={cn(
                  "flex flex-wrap items-start justify-between gap-3 p-4 border rounded-lg",
                  !flow.enabled
                    ? "opacity-50 bg-gray-50 dark:bg-black"
                    : "bg-card shadow-sm",
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-4 flex-wrap">
                      <div className="flex items-center gap-2 w-full sm:w-auto">
                        {flow.icon && (
                          <Icon
                            name={flow.icon as IconName}
                            className="w-5 h-5"
                          />
                        )}
                        <h3 className="font-medium">{flow.name}</h3>
                      </div>
                      {flow.linked && (
                        <Link2
                          size={18}
                          strokeWidth={2.5}
                          style={{ transform: "rotate(155deg)" }}
                        />
                      )}
                      {flow.category && (
                        <Badge
                          variant="secondary"
                          onClick={() => toggleCategoryFilter(flow.category!)}
                          className={cn(
                            "flex items-center gap-1 cursor-pointer",
                            getColorForName(flow.category),
                          )}
                        >
                          <Tag size={12} />
                          {flow.category}
                        </Badge>
                      )}
                      <Badge
                        variant="outline"
                        className="flex items-center gap-1"
                      >
                        <Clock size={12} />
                        {getFrequencyLabel(flow.frequency)}
                      </Badge>

                      {/* Next Date Badge */}
                      {nextDateInfo && (
                        <Badge
                          variant={
                            nextDateInfo.urgencyLevel === "urgent"
                              ? "destructive"
                              : nextDateInfo.urgencyLevel === "soon"
                                ? "default"
                                : "secondary"
                          }
                          className={cn(
                            "flex items-center gap-1 font-medium",
                            nextDateInfo.urgencyLevel === "urgent" &&
                              "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
                            nextDateInfo.urgencyLevel === "soon" &&
                              "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
                            nextDateInfo.urgencyLevel === "normal" &&
                              "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
                          )}
                          title={`${t.management.nextPayment}: ${nextDateInfo.formattedDate}`}
                        >
                          <CalendarDays size={12} />
                          {nextDateInfo.timeText}
                        </Badge>
                      )}
                      {!flow.enabled && (
                        <span className="text-sm text-gray-500">
                          {t.management.disabled}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {t.management.since}: {formatDate(flow.since, locale)}
                    {flow.until &&
                      ` • ${t.management.until}: ${formatDate(flow.until, locale)}`}
                  </div>
                </div>

                <div className="flex items-center gap-2 mr-0 sm:mr-4 self-start sm:self-center shrink-0 w-full sm:w-auto justify-end text-right">
                  <span className="font-mono font-semibold">
                    {formatCurrency(flow.amount, locale, flow.currency)}
                  </span>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center shrink-0 w-full sm:w-auto justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(flow)}
                  >
                    <Edit size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openDeleteDialog(flow)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-center">{t.common.loading}</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/management")}
        >
          <ArrowLeft size={16} />
        </Button>
        <h1 className="text-2xl font-bold">{t.management.recurringMoney}</h1>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <BanknoteArrowUp className="h-5 w-5 text-green-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {t.management.monthlyRecurringEarnings}
            </span>
          </div>
          <div className="text-2xl font-bold text-green-600">
            {formatCurrency(
              monthlyAmounts.monthlyEarnings,
              locale,
              settings?.general?.defaultCurrency,
            )}
          </div>
          <div className="text-xs text-gray-500">
            {sortedFlows.earnings.filter(flow => flow.enabled).length}{" "}
            {sortedFlows.earnings.filter(flow => flow.enabled).length === 1
              ? t.management.flowType.EARNING.toLowerCase()
              : t.management.earnings.toLowerCase()}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <BanknoteArrowDown className="h-5 w-5 text-red-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {t.management.monthlyRecurringExpenses}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-2xl font-bold text-red-600">
              {formatCurrency(
                monthlyAmounts.monthlyExpenses,
                locale,
                settings?.general?.defaultCurrency,
              )}
            </div>
            {monthlyAmounts.monthlyEarnings > 0 &&
              (() => {
                // Percentage intentionally excludes contributions per latest requirement
                const percent =
                  (monthlyAmounts.monthlyExpenses /
                    Math.max(monthlyAmounts.monthlyEarnings, 1)) *
                  100
                const overrun = percent > 100
                return (
                  <div
                    className={cn(
                      "text-xs px-2 py-0.5 rounded-md font-semibold",
                      getUtilizationBadgeClasses(percent),
                      overrun && "animate-pulse",
                    )}
                    title={
                      overrun
                        ? t.management.expensesOverrunMessage.replace(
                            "{percentage}",
                            (percent - 100).toFixed(1),
                          )
                        : undefined
                    }
                  >
                    {percent.toFixed(1)}%
                  </div>
                )
              })()}
          </div>
          <div className="text-xs text-gray-500">
            {sortedFlows.expenses.filter(flow => flow.enabled).length}{" "}
            {sortedFlows.expenses.filter(flow => flow.enabled).length === 1
              ? t.management.flowType.EXPENSE.toLowerCase()
              : t.management.expenses.toLowerCase()}
          </div>
        </Card>
      </div>

      {/* Earnings vs Expenses Consumption Bars */}
      {(flowDistribution.totalEarnings > 0 ||
        flowDistribution.totalExpenses > 0) && (
        <Card className="p-4 space-y-4">
          {(() => {
            const scale = Math.max(
              flowDistribution.totalEarnings,
              flowDistribution.totalExpenses,
              1,
            )
            const earningsOverrun =
              flowDistribution.totalExpenses > flowDistribution.totalEarnings
            return (
              <div className="space-y-3">
                {/* Earnings Bar */}
                <div className="space-y-1">
                  <div className="text-xs font-medium text-green-600 dark:text-green-400">
                    {t.management.earnings}
                  </div>
                  <div
                    className={cn(
                      "relative h-6 rounded-md overflow-hidden bg-green-50 dark:bg-green-950/20",
                    )}
                  >
                    <div className="flex h-full relative">
                      {flowDistribution.earnings.map(earning => {
                        const w = (earning.amount / scale) * 100
                        const isRealCategory = existingCategories.includes(
                          earning.category,
                        )
                        return (
                          <div
                            key={`earning-bar-${earning.category}`}
                            className={cn(
                              "h-full transition-all duration-300 hover:opacity-80 relative group",
                              earning.color,
                              isRealCategory
                                ? "cursor-pointer"
                                : "cursor-default opacity-70",
                            )}
                            style={{ width: `${w}%` }}
                            onClick={() =>
                              isRealCategory &&
                              toggleCategoryFilter(earning.category)
                            }
                            title={`${earning.category}: ${formatCurrency(
                              earning.amount,
                              locale,
                              settings?.general?.defaultCurrency,
                            )}`}
                          >
                            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
                              {formatCurrency(
                                earning.amount,
                                locale,
                                settings?.general?.defaultCurrency,
                              )}
                            </div>
                          </div>
                        )
                      })}
                      {earningsOverrun &&
                        flowDistribution.totalEarnings > 0 && (
                          <Popover>
                            <PopoverTrigger asChild>
                              <div
                                className="absolute inset-y-0 right-0 h-full flex items-stretch cursor-pointer"
                                style={{
                                  width: `${((flowDistribution.totalExpenses - flowDistribution.totalEarnings) / scale) * 100}%`,
                                }}
                              >
                                <div className="w-full h-full bg-yellow-300/60 dark:bg-yellow-300/30 backdrop-blur-[1px]" />
                              </div>
                            </PopoverTrigger>
                            <PopoverContent
                              className="max-w-xs text-xs"
                              side="bottom"
                            >
                              <div className="flex items-start gap-2">
                                <AlertTriangle className="text-yellow-600 dark:text-yellow-400 h-4 w-4 mt-0.5" />
                                <div className="space-y-1">
                                  <div className="font-semibold text-yellow-700 dark:text-yellow-300 text-xs">
                                    {t.management.expensesOverrunTitle}
                                  </div>
                                  <div className="text-muted-foreground leading-snug">
                                    {t.management.expensesOverrunMessage.replace(
                                      "{percentage}",
                                      (
                                        ((flowDistribution.totalExpenses -
                                          flowDistribution.totalEarnings) /
                                          Math.max(
                                            flowDistribution.totalEarnings,
                                            1,
                                          )) *
                                        100
                                      ).toFixed(1),
                                    )}
                                  </div>
                                </div>
                              </div>
                            </PopoverContent>
                          </Popover>
                        )}
                    </div>
                  </div>
                </div>

                {/* Expenses Bar (with optional contributions segment) */}
                <div className="space-y-1">
                  <div
                    className={cn(
                      "text-xs font-medium",
                      earningsOverrun
                        ? "text-red-600 dark:text-red-400"
                        : "text-red-600 dark:text-red-400",
                    )}
                  >
                    {t.management.expenses}
                  </div>
                  <div
                    className={cn(
                      "relative h-6 rounded-md overflow-hidden bg-red-50 dark:bg-red-950/20",
                    )}
                  >
                    <div className="flex h-full relative">
                      {flowDistribution.expenses.map(expense => {
                        const w = (expense.amount / scale) * 100
                        const isRealCategory = existingCategories.includes(
                          expense.category,
                        )
                        return (
                          <div
                            key={`expense-bar-${expense.category}`}
                            className={cn(
                              "h-full transition-all duration-300 hover:opacity-80 relative group",
                              expense.color,
                              isRealCategory
                                ? "cursor-pointer"
                                : "cursor-default opacity-70",
                            )}
                            style={{ width: `${w}%` }}
                            onClick={() =>
                              isRealCategory &&
                              toggleCategoryFilter(expense.category)
                            }
                            title={`${expense.category}: ${formatCurrency(
                              expense.amount,
                              locale,
                              settings?.general?.defaultCurrency,
                            )}`}
                          >
                            <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
                              {expense.category}:{" "}
                              {formatCurrency(
                                expense.amount,
                                locale,
                                settings?.general?.defaultCurrency,
                              )}
                            </div>
                          </div>
                        )
                      })}
                      {(() => {
                        if (
                          !effectiveShowContributions ||
                          monthlyAmounts.monthlyContributions <= 0
                        )
                          return null
                        const earnings = flowDistribution.totalEarnings
                        const expensesOnly = monthlyAmounts.monthlyExpenses
                        const contributionsAmt =
                          monthlyAmounts.monthlyContributions
                        const contributionsCount = (() => {
                          if (!contributions) return 0
                          let count = 0
                          Object.values(contributions).forEach(group => {
                            group?.periodic?.forEach(c => {
                              if (c.active) count++
                            })
                          })
                          return count
                        })()
                        // Gap only if earnings covers expenses + contributions fully
                        const gap =
                          earnings >= expensesOnly + contributionsAmt
                            ? earnings - (expensesOnly + contributionsAmt)
                            : 0
                        const gapPct = (gap / scale) * 100
                        const contribPct = (contributionsAmt / scale) * 100
                        return (
                          <>
                            {gapPct > 0 && (
                              <div
                                className="h-full bg-neutral-200 dark:bg-neutral-800/50"
                                style={{ width: `${gapPct}%` }}
                                aria-hidden
                              />
                            )}
                            <Popover>
                              <PopoverTrigger asChild>
                                <div
                                  className="h-full relative group cursor-pointer bg-cyan-700 dark:bg-cyan-600 hover:bg-cyan-600 dark:hover:bg-cyan-500 transition-colors"
                                  style={{ width: `${contribPct}%` }}
                                >
                                  <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
                                    {t.management.contributionsShort}:{" "}
                                    {formatCurrency(
                                      monthlyAmounts.monthlyContributions,
                                      locale,
                                      settings?.general?.defaultCurrency,
                                    )}
                                  </div>
                                </div>
                              </PopoverTrigger>
                              <PopoverContent
                                side="top"
                                className="text-xs space-y-2 w-64"
                              >
                                <div className="font-semibold text-cyan-700 dark:text-cyan-300">
                                  {t.management.contributionsPopoverTitle}
                                </div>
                                <div className="text-muted-foreground leading-snug">
                                  {(() => {
                                    const tpl = t.management
                                      .contributionsPopoverDetails as string
                                    const formattedAmount = formatCurrency(
                                      monthlyAmounts.monthlyContributions,
                                      locale,
                                      settings?.general?.defaultCurrency,
                                    )
                                    return tpl
                                      .split(/({count}|{amount})/g)
                                      .map((part, idx) => {
                                        if (part === "{count}")
                                          return (
                                            <strong key={idx}>
                                              {contributionsCount}
                                            </strong>
                                          )
                                        if (part === "{amount}")
                                          return (
                                            <strong key={idx}>
                                              {formattedAmount}
                                            </strong>
                                          )
                                        return <span key={idx}>{part}</span>
                                      })
                                  })()}
                                </div>
                                <div
                                  className="pt-1 text-[11px] text-cyan-600 dark:text-cyan-400/90 hover:text-cyan-500 dark:hover:text-cyan-300 cursor-pointer underline-offset-2"
                                  onClick={() =>
                                    navigate("/management/auto-contributions")
                                  }
                                >
                                  {t.management.contributionsPopoverCta}
                                </div>
                              </PopoverContent>
                            </Popover>
                          </>
                        )
                      })()}
                    </div>
                  </div>
                </div>
                {/* Removed bottom tiny numbers per new requirement */}
              </div>
            )
          })()}

          {/* Legends */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div className="flex flex-wrap gap-2 w-full md:max-h-40 md:overflow-auto">
              {flowDistribution.earnings.map(earning => {
                const isRealCategory = existingCategories.includes(
                  earning.category,
                )
                return (
                  <div
                    key={`legend2-earning-${earning.category}`}
                    className={cn(
                      "flex items-center gap-2 text-xs leading-tight bg-green-50 dark:bg-green-900/20 px-2 py-0 h-7 rounded-md flex-1 sm:flex-none min-w-[180px]",
                      isRealCategory
                        ? "cursor-pointer"
                        : "cursor-default opacity-70",
                    )}
                    onClick={() =>
                      isRealCategory && toggleCategoryFilter(earning.category)
                    }
                  >
                    <div className={`w-3 h-3 rounded ${earning.color}`}></div>
                    <span className="font-medium">{earning.category}</span>
                    <span className="font-mono text-green-600">
                      {formatCurrency(
                        earning.amount,
                        locale,
                        settings?.general?.defaultCurrency,
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
            <div className="flex flex-wrap gap-2 w-full md:max-h-40 md:overflow-auto justify-end">
              {flowDistribution.expenses.map(expense => {
                const isRealCategory = existingCategories.includes(
                  expense.category,
                )
                return (
                  <div
                    key={`legend2-expense-${expense.category}`}
                    className={cn(
                      "flex items-center gap-2 text-xs leading-tight bg-red-50 dark:bg-red-900/20 px-2 py-0 h-7 rounded-md flex-1 sm:flex-none min-w-[180px]",
                      isRealCategory
                        ? "cursor-pointer"
                        : "cursor-default opacity-70",
                    )}
                    onClick={() =>
                      isRealCategory && toggleCategoryFilter(expense.category)
                    }
                  >
                    <div className={`w-3 h-3 rounded ${expense.color}`}></div>
                    <span className="font-medium">{expense.category}</span>
                    <span className="font-mono text-red-600">
                      {formatCurrency(
                        expense.amount,
                        locale,
                        settings?.general?.defaultCurrency,
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </Card>
      )}

      {/* Sorting Controls */}
      <div className="flex items-center gap-3 pt-4 flex-wrap">
        <span className="text-sm text-muted-foreground">
          {t.management.sortBy}
        </span>
        <div className="flex items-center bg-muted rounded-lg p-1">
          <button
            onClick={() => setSortBy("amount")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
              sortBy === "amount"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.management.sortByAmount}
          </button>
          <button
            onClick={() => setSortBy("date")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
              sortBy === "date"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.management.sortByDate}
          </button>
        </div>

        <div className="flex items-center gap-2 ml-auto flex-wrap max-w-full justify-end">
          <Button
            size="sm"
            variant={effectiveShowContributions ? "default" : "outline"}
            onClick={() => setShowContributions(s => !s)}
            className={cn(
              "h-8 px-2 text-xs font-medium flex items-center justify-center flex-shrink-0",
              effectiveShowContributions
                ? "bg-cyan-600 hover:bg-cyan-600/90 dark:bg-cyan-500 dark:hover:bg-cyan-500/90"
                : "",
            )}
            aria-label={t.management.contributionsShort}
            title={t.management.contributionsShort}
          >
            <PiggyBank className="h-4 w-4" />
            <span className="sr-only">{t.management.contributionsShort}</span>
          </Button>
          <span className="text-sm text-muted-foreground">
            {t.management.category}
          </span>
          <MultiSelect
            options={categoryOptions}
            value={categoryFilter}
            onChange={setCategoryFilter}
            className="min-w-[140px] sm:min-w-[180px] md:min-w-[220px] flex-grow max-w-full"
          />
        </div>
      </div>

      {/* Loan Suggestions */}
      {(loanSuggestions.filter(
        suggestion => !dismissedSuggestions.includes(suggestion.id),
      ).length > 0 ||
        showDismissed) && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Lightbulb className="text-yellow-500" size={20} />
            <h2 className="text-lg font-semibold">
              {t.management.loanSuggestions.title}
            </h2>
            <span className="text-xs text-muted-foreground">
              ({loanSuggestions.length} {t.management.loanSuggestions.found})
            </span>
          </div>
          <div className="space-y-3">
            {loanSuggestions
              .filter(
                suggestion =>
                  showDismissed ||
                  !dismissedSuggestions.includes(suggestion.id),
              )
              .map(suggestion => {
                const isDismissed = dismissedSuggestions.includes(suggestion.id)
                return (
                  <div
                    key={suggestion.id}
                    className={`flex items-start justify-between p-4 border rounded-lg ${
                      isDismissed
                        ? "bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700 opacity-70"
                        : "bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800"
                    }`}
                  >
                    <div className="flex-1">
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-4 flex-wrap">
                          <h3 className="font-medium">
                            {t.management.loanSuggestions.loanPayment.replace(
                              "{loanName}",
                              suggestion.name,
                            )}
                          </h3>
                          <Badge
                            variant="secondary"
                            className="flex items-center gap-1"
                          >
                            <Tag size={12} />
                            {t.management.loanSuggestions.loanCategory}
                          </Badge>
                          <Badge
                            variant="outline"
                            className="flex items-center gap-1"
                          >
                            <Clock size={12} />
                            {t.management.frequency.MONTHLY}
                          </Badge>
                        </div>
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        {suggestion.sinceDate && (
                          <>
                            {t.management.since}:{" "}
                            {formatDate(suggestion.sinceDate, locale)}
                            {suggestion.maturityDate &&
                              ` • ${t.management.until}: ${formatDate(suggestion.maturityDate, locale)}`}
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mr-4 self-center">
                      <span className="font-mono font-semibold">
                        {formatCurrency(
                          suggestion.amount,
                          locale,
                          suggestion.currency,
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 self-center">
                      {isDismissed ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRestoreSuggestion(suggestion.id)}
                          className="h-8 px-3"
                        >
                          <Check size={14} className="mr-1" />
                          {t.management.loanSuggestions.add}
                        </Button>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              handleDismissSuggestion(suggestion.id)
                            }
                            className="h-8 w-8 p-0"
                          >
                            <X size={14} />
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleAcceptSuggestion(suggestion)}
                            className="h-8 px-3"
                          >
                            <Check size={14} className="mr-1" />
                            {t.management.loanSuggestions.add}
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      <div className="pt-4">
        <FlowSection
          title={t.management.earnings}
          flows={sortedFlows.earnings}
          flowType={FlowType.EARNING}
          emptyMessage={t.management.noEarnings}
          addMessage={t.management.addFirstEarning}
        />
      </div>

      <FlowSection
        title={t.management.expenses}
        flows={sortedFlows.expenses}
        flowType={FlowType.EXPENSE}
        emptyMessage={t.management.noExpenses}
        addMessage={t.management.addFirstExpense}
        extraButton={
          dismissedSuggestions.length > 0 &&
          loanSuggestions.some(suggestion =>
            dismissedSuggestions.includes(suggestion.id),
          ) ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowDismissed(!showDismissed)}
              className="h-8 px-3 text-yellow-600 hover:text-yellow-700"
            >
              {showDismissed ? (
                <LightbulbOff size={14} />
              ) : (
                <Lightbulb size={14} />
              )}
            </Button>
          ) : undefined
        }
      />

      {/* Dialog for Add/Edit */}
      {isDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                {editingFlow ? t.common.edit : t.management.addNew}{" "}
                {formData.flow_type === FlowType.EARNING
                  ? t.management.flowType.EARNING
                  : t.management.flowType.EXPENSE}
              </h3>
              {editingFlow?.linked && (
                <Popover>
                  <PopoverTrigger asChild>
                    <span className="inline-flex text-muted-foreground">
                      <Link2
                        size={18}
                        strokeWidth={2.5}
                        style={{ transform: "rotate(155deg)" }}
                      />
                    </span>
                  </PopoverTrigger>
                  <PopoverContent side="left" className="w-72 text-xs">
                    {(t.management as any).editLinkedWarning.replace(
                      "{type}",
                      (editingFlow?.flow_type === FlowType.EARNING
                        ? t.management.flowType.EARNING
                        : t.management.flowType.EXPENSE
                      ).toLowerCase(),
                    )}
                  </PopoverContent>
                </Popover>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.iconLabel}
                </label>
                <IconPicker
                  value={formData.icon as IconName | undefined}
                  onValueChange={value =>
                    setFormData(prev => ({ ...prev, icon: value }))
                  }
                  modal
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.name}
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <Input
                  value={formData.name}
                  onChange={e =>
                    setFormData(prev => ({ ...prev, name: e.target.value }))
                  }
                  placeholder={t.management.namePlaceholder}
                  className={
                    validationErrors.includes("name") ? "border-red-500" : ""
                  }
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.amount}
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                    {getCurrencySymbol(formData.currency)}
                  </span>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.amount}
                    onChange={e =>
                      setFormData(prev => ({
                        ...prev,
                        amount: parseFloat(e.target.value),
                      }))
                    }
                    placeholder={t.management.amountPlaceholder}
                    className={`pl-8 ${validationErrors.includes("amount") ? "border-red-500" : ""}`}
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.category}{" "}
                  <span className="text-gray-400 font-normal">
                    ({t.management.optional})
                  </span>
                </label>
                <CategorySelector
                  value={formData.category || ""}
                  onChange={value =>
                    setFormData(prev => ({
                      ...prev,
                      category: value,
                    }))
                  }
                  placeholder={t.management.categoryPlaceholder}
                  categories={existingCategories}
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.frequencyLabel}
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <select
                  value={formData.frequency}
                  onChange={e =>
                    setFormData(prev => ({
                      ...prev,
                      frequency: e.target.value as FlowFrequency,
                    }))
                  }
                  className={`w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 ${validationErrors.includes("frequency") ? "border-red-500" : ""}`}
                >
                  {Object.values(FlowFrequency).map(freq => (
                    <option key={freq} value={freq}>
                      {getFrequencyLabel(freq)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.since}
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <DatePicker
                  value={formData.since}
                  onChange={value =>
                    setFormData(prev => ({ ...prev, since: value }))
                  }
                  className={
                    validationErrors.includes("since") ? "border-red-500" : ""
                  }
                />
              </div>

              <div>
                <label className="text-sm font-medium block mb-1">
                  {t.management.until}{" "}
                  <span className="text-gray-400 font-normal">
                    ({t.management.optional})
                  </span>
                </label>
                <DatePicker
                  value={formData.until}
                  onChange={value =>
                    setFormData(prev => ({ ...prev, until: value }))
                  }
                />
              </div>

              <div className="flex items-center justify-between">
                <label htmlFor="enabled" className="text-sm font-medium">
                  {t.management.enabled}
                </label>
                <Switch
                  id="enabled"
                  checked={formData.enabled}
                  onCheckedChange={checked =>
                    setFormData(prev => ({ ...prev, enabled: checked }))
                  }
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                {t.common.cancel}
              </Button>
              <Button onClick={handleSubmit}>{t.common.save}</Button>
            </div>
          </div>
        </div>
      )}

      <ConfirmationDialog
        isOpen={isDeleteDialogOpen}
        title={t.management.deleteConfirmTitle.replace(
          "{type}",
          deletingFlow?.flow_type === FlowType.EARNING
            ? t.management.flowType.EARNING.toLowerCase()
            : t.management.flowType.EXPENSE.toLowerCase(),
        )}
        message={t.management.deleteConfirm.replace(
          "{type}",
          deletingFlow?.flow_type === FlowType.EARNING
            ? t.management.flowType.EARNING.toLowerCase()
            : t.management.flowType.EXPENSE.toLowerCase(),
        )}
        warning={
          deletingFlow?.linked
            ? t.management.deleteLinkedWarning.replace(
                "{type}",
                deletingFlow?.flow_type === FlowType.EARNING
                  ? t.management.flowType.EARNING.toLowerCase()
                  : t.management.flowType.EXPENSE.toLowerCase(),
              )
            : undefined
        }
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={handleDelete}
        onCancel={() => setIsDeleteDialogOpen(false)}
      />
    </div>
  )
}
