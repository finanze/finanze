import { useState, useEffect, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { Input } from "@/components/ui/Input"
import { DatePicker } from "@/components/ui/DatePicker"
import { Switch } from "@/components/ui/Switch"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { CategorySelector } from "@/components/ui/CategorySelector"
import { Badge } from "@/components/ui/Badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { IconPicker, Icon, type IconName } from "@/components/ui/icon-picker"
import {
  ArrowLeft,
  BanknoteArrowDown,
  BanknoteArrowUp,
  Calendar,
  CalendarDays,
  Edit,
  Plus,
  Tag,
  Trash2,
  X,
} from "lucide-react"
import { getCurrencySymbol, getColorForName } from "@/lib/utils"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { convertCurrency } from "@/utils/financialDataUtils"
import { FlowType, PendingFlow, CreatePendingFlowRequest } from "@/types"
import { savePendingFlows } from "@/services/api"

type PendingFlowFormState = CreatePendingFlowRequest & { icon?: IconName }

export default function PendingMoneyPage() {
  const { t, locale } = useI18n()
  const { showToast, settings, exchangeRates } = useAppContext()
  const { pendingFlows, refreshPendingFlows } = useFinancialData()
  const navigate = useNavigate()
  const defaultCurrency = settings?.general?.defaultCurrency || "EUR"
  const [existingCategories, setExistingCategories] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [sortBy, setSortBy] = useState<"amount" | "date">("amount")
  const [categoryFilter, setCategoryFilter] = useState<string[]>([])
  const [runEntranceAnimation, setRunEntranceAnimation] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [editingFlow, setEditingFlow] = useState<PendingFlow | null>(null)
  const [deletingFlow, setDeletingFlow] = useState<PendingFlow | null>(null)
  const [formData, setFormData] = useState<PendingFlowFormState>({
    name: "",
    amount: 0,
    flow_type: FlowType.EARNING,
    category: "",
    enabled: true,
    date: "",
    currency: defaultCurrency,
  })

  useEffect(() => {
    const categories = pendingFlows
      .map(flow => flow.category)
      .filter((category): category is string => Boolean(category))
      .filter((category, index, arr) => arr.indexOf(category) === index)
    setExistingCategories(categories)
  }, [pendingFlows])

  useEffect(() => {
    // Delay disabling animation to allow entrance animation to complete
    const timer = setTimeout(() => {
      setRunEntranceAnimation(false)
    }, 1000)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      currency: prev.currency || defaultCurrency,
    }))
  }, [defaultCurrency])

  const sortedFlows = useMemo(() => {
    const flows = pendingFlows.filter(flow =>
      categoryFilter.length
        ? flow.category
          ? categoryFilter.includes(flow.category)
          : false
        : true,
    )

    const sorted = [...flows].sort((a, b) => {
      if (a.enabled !== b.enabled) {
        return a.enabled ? -1 : 1
      }
      if (sortBy === "amount") {
        return b.amount - a.amount
      }
      if (!a.date && !b.date) return 0
      if (!a.date) return 1
      if (!b.date) return -1
      return new Date(a.date).getTime() - new Date(b.date).getTime()
    })

    return {
      earnings: sorted.filter(flow => flow.flow_type === FlowType.EARNING),
      expenses: sorted.filter(flow => flow.flow_type === FlowType.EXPENSE),
    }
  }, [pendingFlows, sortBy, categoryFilter])

  const resetForm = () => {
    setFormData({
      name: "",
      amount: 0,
      flow_type: FlowType.EARNING,
      category: "",
      enabled: true,
      date: "",
      currency: defaultCurrency,
    })
    setEditingFlow(null)
    setValidationErrors([])
  }

  const toRequestFlow = (
    flow:
      | PendingFlow
      | (PendingFlowFormState & {
          icon?: IconName
        }),
  ) => ({
    name: flow.name,
    amount: Number(flow.amount),
    flow_type: flow.flow_type,
    category: flow.category,
    enabled: flow.enabled,
    date: flow.date,
    currency: flow.currency || defaultCurrency,
    icon: (flow as any).icon,
  })

  const handleSubmit = async () => {
    const errors: string[] = []
    if (!formData.name.trim()) errors.push("name")
    if (!formData.amount) errors.push("amount")

    setValidationErrors(errors)

    if (errors.length > 0) {
      return
    }

    const sanitizedFormData: PendingFlowFormState = {
      ...formData,
      amount: Number(formData.amount),
      currency: formData.currency || defaultCurrency,
    }

    const flowsPayload = editingFlow
      ? pendingFlows.map(flow =>
          flow.id === editingFlow.id
            ? toRequestFlow({
                ...flow,
                ...sanitizedFormData,
                icon: sanitizedFormData.icon,
              })
            : toRequestFlow(flow),
        )
      : [
          ...pendingFlows.map(flow => toRequestFlow(flow)),
          toRequestFlow(sanitizedFormData),
        ]

    try {
      await savePendingFlows({ flows: flowsPayload })
      showToast(t.management.saveSuccess, "success")
      setIsDialogOpen(false)
      resetForm()
      await refreshPendingFlows()
    } catch (error) {
      console.error("Error saving pending flow:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const handleDelete = async () => {
    if (!deletingFlow) return

    const flowsPayload = pendingFlows
      .filter(flow => flow.id !== deletingFlow.id)
      .map(flow => toRequestFlow(flow))

    try {
      await savePendingFlows({ flows: flowsPayload })
      showToast(t.management.deleteSuccess, "success")
      setIsDeleteDialogOpen(false)
      setDeletingFlow(null)
      await refreshPendingFlows()
    } catch (error) {
      console.error("Error deleting pending flow:", error)
      showToast(t.management.deleteError, "error")
    }
  }

  const openCreateDialog = (flowType: FlowType) => {
    resetForm()
    setFormData(prev => ({ ...prev, flow_type: flowType }))
    setIsDialogOpen(true)
  }

  const openEditDialog = (flow: PendingFlow) => {
    setEditingFlow(flow)
    setValidationErrors([])
    setFormData({
      name: flow.name,
      amount: flow.amount,
      flow_type: flow.flow_type,
      category: flow.category || "",
      enabled: flow.enabled,
      date: flow.date || "",
      currency: flow.currency || defaultCurrency,
      icon: (flow as any).icon,
    })
    setIsDialogOpen(true)
  }

  const openDeleteDialog = (flow: PendingFlow) => {
    setDeletingFlow(flow)
    setIsDeleteDialogOpen(true)
  }

  const earnings = sortedFlows.earnings
  const expenses = sortedFlows.expenses

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

  const kpiEarningsSource = useMemo(() => earnings, [earnings])
  const kpiExpensesSource = useMemo(() => expenses, [expenses])

  const totalPendingEarnings = kpiEarningsSource
    .filter(flow => flow.enabled)
    .reduce((sum, flow) => {
      const amount = flow.amount
      const convertedAmount = convertCurrency(
        amount,
        flow.currency,
        defaultCurrency,
        exchangeRates,
      )
      return sum + convertedAmount
    }, 0)

  const totalPendingExpenses = kpiExpensesSource
    .filter(flow => flow.enabled)
    .reduce((sum, flow) => {
      const amount = flow.amount
      const convertedAmount = convertCurrency(
        amount,
        flow.currency,
        defaultCurrency,
        exchangeRates,
      )
      return sum + convertedAmount
    }, 0)

  // Color functions for different shades - traditional red/green palette
  // Darker colors for bigger amounts (lower index), lighter for smaller amounts
  const getEarningsColor = (index: number) => {
    const greenShades = [
      "bg-green-800", // Darkest for biggest
      "bg-green-700",
      "bg-green-600",
      "bg-green-500",
      "bg-green-400",
      "bg-green-300",
      "bg-green-100",
    ]
    return greenShades[index % greenShades.length]
  }

  const getExpensesColor = (index: number) => {
    const redShades = [
      "bg-red-800", // Darkest for biggest
      "bg-red-700",
      "bg-red-600",
      "bg-red-500",
      "bg-red-400",
      "bg-red-300",
      "bg-red-100",
    ]
    return redShades[index % redShades.length]
  }

  // Calculate flow distribution for the horizontal bar charts
  const flowDistribution = useMemo(() => {
    const enabledEarnings = kpiEarningsSource.filter(flow => flow.enabled)
    const enabledExpenses = kpiExpensesSource.filter(flow => flow.enabled)

    // Group earnings by category
    const earningsGroups = enabledEarnings.reduce(
      (groups, flow) => {
        const category = flow.category || flow.name
        const amount = convertCurrency(
          flow.amount,
          flow.currency,
          defaultCurrency,
          exchangeRates,
        )

        if (!groups[category]) {
          groups[category] = { amount: 0, flows: [] }
        }
        groups[category].amount += amount
        groups[category].flows.push(flow)
        return groups
      },
      {} as Record<string, { amount: number; flows: PendingFlow[] }>,
    )

    // Group expenses by category
    const expensesGroups = enabledExpenses.reduce(
      (groups, flow) => {
        const category = flow.category || flow.name
        const amount = convertCurrency(
          flow.amount,
          flow.currency,
          defaultCurrency,
          exchangeRates,
        )

        if (!groups[category]) {
          groups[category] = { amount: 0, flows: [] }
        }
        groups[category].amount += amount
        groups[category].flows.push(flow)
        return groups
      },
      {} as Record<string, { amount: number; flows: PendingFlow[] }>,
    )

    // Convert to arrays with percentages for earnings
    const earningsData = Object.entries(earningsGroups).map(
      ([category, data], index) => ({
        category,
        amount: data.amount,
        percentage:
          totalPendingEarnings > 0
            ? (data.amount / totalPendingEarnings) * 100
            : 0,
        flows: data.flows,
        type: "earning" as const,
        color: getEarningsColor(index),
      }),
    )

    // Convert to arrays with percentages for expenses
    const expensesData = Object.entries(expensesGroups).map(
      ([category, data], index) => ({
        category,
        amount: data.amount,
        percentage:
          totalPendingExpenses > 0
            ? (data.amount / totalPendingExpenses) * 100
            : 0,
        flows: data.flows,
        type: "expense" as const,
        color: getExpensesColor(index),
      }),
    )

    return {
      earnings: earningsData.sort((a, b) => b.amount - a.amount), // Biggest first
      expenses: expensesData.sort((a, b) => b.amount - a.amount), // Biggest first
    }
  }, [
    kpiEarningsSource,
    kpiExpensesSource,
    totalPendingEarnings,
    totalPendingExpenses,
    defaultCurrency,
    exchangeRates,
  ])

  const getDateUrgencyInfo = (dateString: string | undefined) => {
    if (!dateString) return null

    const today = new Date()
    const targetDate = new Date(dateString)
    const diffTime = targetDate.getTime() - today.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    if (diffDays < 0) {
      return {
        urgencyLevel: "urgent" as const,
        timeText: t.management.overdue,
        show: true,
      }
    } else if (diffDays === 0) {
      return {
        urgencyLevel: "urgent" as const,
        timeText: t.management.today,
        show: true,
      }
    } else if (diffDays === 1) {
      return {
        urgencyLevel: "urgent" as const,
        timeText: t.management.tomorrow,
        show: true,
      }
    } else if (diffDays <= 7) {
      return {
        urgencyLevel: "soon" as const,
        timeText: t.management.inDays.replace("{days}", diffDays.toString()),
        show: true,
      }
    }

    return { urgencyLevel: "normal" as const, timeText: "", show: false }
  }

  const renderFlowSection = ({
    title,
    flows,
    flowType,
    emptyMessage,
    addMessage,
  }: {
    title: string
    flows: PendingFlow[]
    flowType: FlowType
    emptyMessage: string
    addMessage: string
  }) => {
    const initialVariant = runEntranceAnimation ? "hidden" : false

    return (
      <motion.div
        variants={fadeListItem}
        initial={initialVariant}
        animate="show"
        className="space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {flowType === FlowType.EARNING ? (
              <BanknoteArrowUp className="text-green-600" size={24} />
            ) : (
              <BanknoteArrowDown className="text-red-600" size={24} />
            )}
            <h2 className="text-xl font-semibold">{title}</h2>
          </div>
          <Button
            onClick={() => openCreateDialog(flowType)}
            size="sm"
            className="flex items-center gap-2 bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
          >
            <Plus size={16} />
          </Button>
        </div>

        {flows.length === 0 ? (
          <motion.div
            variants={fadeListItem}
            initial={initialVariant}
            animate="show"
            className="text-center py-12 text-gray-500"
          >
            <div className="flex justify-center mb-4">
              {flowType === FlowType.EARNING ? (
                <BanknoteArrowUp className="text-green-400" size={48} />
              ) : (
                <BanknoteArrowDown className="text-red-400" size={48} />
              )}
            </div>
            <p className="text-lg font-medium mb-2">{emptyMessage}</p>
            <p className="text-sm">{addMessage}</p>
          </motion.div>
        ) : (
          <motion.div
            variants={fadeListContainer}
            initial={initialVariant}
            animate="show"
            className="space-y-2"
          >
            {flows.map(flow => (
              <motion.div
                key={flow.id}
                variants={fadeListItem}
                initial={initialVariant}
                animate="show"
                className={`${
                  !flow.enabled
                    ? "opacity-50 bg-gray-50 dark:bg-black"
                    : "bg-card shadow-sm"
                } flex items-start justify-between gap-4 p-4 border rounded-lg`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-3">
                  <div className="flex flex-wrap items-center gap-2 sm:gap-4">
                    <div className="flex items-center gap-2">
                      {(flow as any).icon && (
                        <Icon
                          name={(flow as any).icon as IconName}
                          className="w-5 h-5"
                        />
                      )}
                      <h3 className="font-medium">{flow.name}</h3>
                    </div>
                    {flow.category && (
                      <Badge
                        variant="secondary"
                        onClick={() => toggleCategoryFilter(flow.category!)}
                        className={`flex items-center gap-1 cursor-pointer ${getColorForName(flow.category)}`}
                      >
                        <Tag size={12} />
                        {flow.category}
                      </Badge>
                    )}
                    {(() => {
                      const urgencyInfo = getDateUrgencyInfo(flow.date)
                      if (urgencyInfo?.show) {
                        return (
                          <Badge
                            variant={
                              urgencyInfo.urgencyLevel === "urgent"
                                ? "destructive"
                                : urgencyInfo.urgencyLevel === "soon"
                                  ? "default"
                                  : "outline"
                            }
                            className={`flex items-center gap-1 ${
                              urgencyInfo.urgencyLevel === "urgent"
                                ? "bg-red-500 text-white hover:bg-red-600"
                                : urgencyInfo.urgencyLevel === "soon"
                                  ? "bg-orange-500 text-white hover:bg-orange-600"
                                  : "bg-blue-500 text-white hover:bg-blue-600"
                            }`}
                          >
                            <CalendarDays size={12} />
                            {urgencyInfo.timeText}
                          </Badge>
                        )
                      } else if (flow.date) {
                        return (
                          <Badge
                            variant="outline"
                            className="flex items-center gap-1"
                          >
                            <Calendar size={12} />
                            {formatDate(flow.date || "", locale)}
                          </Badge>
                        )
                      }
                    })()}
                    {!flow.enabled && (
                      <span className="text-sm text-gray-500">
                        {t.management.disabled}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold">
                      {formatCurrency(flow.amount, locale, flow.currency)}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(flow)}
                    className="h-8 w-8 p-0"
                  >
                    <Edit size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openDeleteDialog(flow)}
                    className="text-red-600 hover:text-red-700 h-8 w-8 p-0"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </motion.div>
    )
  }

  return (
    <motion.div
      className="space-y-6"
      variants={fadeListContainer}
      initial={runEntranceAnimation ? "hidden" : false}
      animate="show"
    >
      <motion.div
        variants={fadeListItem}
        initial={runEntranceAnimation ? "hidden" : false}
        animate="show"
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="p-1 h-8 w-8"
            onClick={() => navigate("/management")}
          >
            <ArrowLeft size={20} />
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{t.management.pendingMoney}</h1>
            <PinAssetButton
              assetId="management-pending"
              className="hidden md:inline-flex"
            />
          </div>
        </div>
      </motion.div>

      {/* KPI Cards */}
      <motion.div
        variants={fadeListItem}
        initial={runEntranceAnimation ? "hidden" : false}
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <BanknoteArrowUp className="h-5 w-5 text-green-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {t.management.totalPendingEarnings}
            </span>
          </div>
          <div className="text-2xl font-bold text-green-600">
            {formatCurrency(
              totalPendingEarnings,
              locale,
              settings?.general?.defaultCurrency,
            )}
          </div>
          <div className="text-xs text-gray-500">
            {kpiEarningsSource.filter(flow => flow.enabled).length}{" "}
            {kpiEarningsSource.filter(flow => flow.enabled).length === 1
              ? t.management.flowType.EARNING.toLowerCase()
              : t.management.earnings.toLowerCase()}
          </div>

          {/* Earnings Distribution Bar Chart */}
          {flowDistribution.earnings.length > 0 && (
            <div className="mt-4">
              <div className="relative h-6 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
                <div className="flex h-full">
                  {flowDistribution.earnings.map((earning, index) => {
                    const isRealCategory = existingCategories.includes(
                      earning.category,
                    )
                    return (
                      <div
                        key={`earning-${index}`}
                        className={`${earning.color} relative group ${isRealCategory ? "cursor-pointer" : "cursor-default"} hover:opacity-80 transition-opacity duration-200`}
                        style={{ width: `${earning.percentage}%` }}
                        title={`${earning.category}: ${formatCurrency(
                          earning.amount,
                          locale,
                          settings?.general?.defaultCurrency,
                        )} (${earning.percentage.toFixed(1)}%)`}
                        onClick={() =>
                          isRealCategory &&
                          toggleCategoryFilter(earning.category)
                        }
                      >
                        <div className="absolute inset-0 dark:bg-black opacity-0 group-hover:opacity-10 transition-opacity duration-200"></div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Earnings Legend */}
              <div className="mt-3 flex flex-wrap gap-2 w-full md:max-h-40 md:overflow-auto">
                {flowDistribution.earnings.map((earning, index) => {
                  const isRealCategory = existingCategories.includes(
                    earning.category,
                  )
                  return (
                    <div
                      key={`earning-legend-${index}`}
                      className={`flex items-center gap-1.5 text-xs leading-tight bg-green-50 dark:bg-green-900/20 px-2 py-0 h-7 rounded-md flex-1 sm:flex-none min-w-[180px] ${
                        isRealCategory
                          ? "cursor-pointer"
                          : "cursor-default opacity-70"
                      }`}
                      onClick={() =>
                        isRealCategory && toggleCategoryFilter(earning.category)
                      }
                    >
                      <div
                        className={`w-3 h-3 rounded-sm ${earning.color}`}
                      ></div>
                      <span
                        className="truncate max-w-20"
                        title={earning.category}
                      >
                        {earning.category}
                      </span>
                      <span className="text-gray-500">
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
            </div>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <BanknoteArrowDown className="h-5 w-5 text-red-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {t.management.totalPendingExpenses}
            </span>
          </div>
          <div className="text-2xl font-bold text-red-600">
            {formatCurrency(
              totalPendingExpenses,
              locale,
              settings?.general?.defaultCurrency,
            )}
          </div>
          <div className="text-xs text-gray-500">
            {kpiExpensesSource.filter(flow => flow.enabled).length}{" "}
            {kpiExpensesSource.filter(flow => flow.enabled).length === 1
              ? t.management.flowType.EXPENSE.toLowerCase()
              : t.management.expenses.toLowerCase()}
          </div>

          {/* Expenses Distribution Bar Chart */}
          {flowDistribution.expenses.length > 0 && (
            <div className="mt-4">
              <div className="relative h-6 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
                <div className="flex h-full">
                  {flowDistribution.expenses.map((expense, index) => {
                    const isRealCategory = existingCategories.includes(
                      expense.category,
                    )
                    return (
                      <div
                        key={`expense-${index}`}
                        className={`${expense.color} relative group ${isRealCategory ? "cursor-pointer" : "cursor-default"} hover:opacity-80 transition-opacity duration-200`}
                        style={{ width: `${expense.percentage}%` }}
                        title={`${expense.category}: ${formatCurrency(
                          expense.amount,
                          locale,
                          settings?.general?.defaultCurrency,
                        )} (${expense.percentage.toFixed(1)}%)`}
                        onClick={() =>
                          isRealCategory &&
                          toggleCategoryFilter(expense.category)
                        }
                      >
                        <div className="absolute inset-0 dark:bg-black opacity-0 group-hover:opacity-10 transition-opacity duration-200"></div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Expenses Legend */}
              <div className="mt-3 flex flex-wrap gap-2 w-full md:max-h-40 md:overflow-auto">
                {flowDistribution.expenses.map((expense, index) => {
                  const isRealCategory = existingCategories.includes(
                    expense.category,
                  )
                  return (
                    <div
                      key={`expense-legend-${index}`}
                      className={`flex items-center gap-1.5 text-xs leading-tight bg-red-50 dark:bg-red-900/20 px-2 py-0 h-7 rounded-md flex-1 sm:flex-none min-w-[180px] ${
                        isRealCategory
                          ? "cursor-pointer"
                          : "cursor-default opacity-70"
                      }`}
                      onClick={() =>
                        isRealCategory && toggleCategoryFilter(expense.category)
                      }
                    >
                      <div
                        className={`w-3 h-3 rounded-sm ${expense.color}`}
                      ></div>
                      <span
                        className="truncate max-w-20"
                        title={expense.category}
                      >
                        {expense.category}
                      </span>
                      <span className="text-gray-500">
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
          )}
        </Card>
      </motion.div>

      {/* Sorting Controls */}
      <motion.div
        variants={fadeListItem}
        initial={runEntranceAnimation ? "hidden" : false}
        animate="show"
        className="flex items-center justify-between gap-3 flex-wrap"
      >
        <div className="flex items-center gap-3">
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
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <span className="text-sm text-muted-foreground">
            {t.management.category}
          </span>
          <MultiSelect
            options={categoryOptions}
            value={categoryFilter}
            onChange={setCategoryFilter}
            className="min-w-[220px]"
          />
        </div>
      </motion.div>

      {renderFlowSection({
        title: t.management.pendingEarnings,
        flows: earnings,
        flowType: FlowType.EARNING,
        emptyMessage: t.management.noPendingEarnings,
        addMessage: t.management.addFirstPendingEarning,
      })}

      {renderFlowSection({
        title: t.management.pendingExpenses,
        flows: expenses,
        flowType: FlowType.EXPENSE,
        emptyMessage: t.management.noPendingExpenses,
        addMessage: t.management.addFirstPendingExpense,
      })}

      <AnimatePresence>
        {isDialogOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-gray-900/20 dark:bg-black/50 flex items-center justify-center p-4 z-[18000]"
            onClick={e => {
              if (e.target === e.currentTarget) setIsDialogOpen(false)
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-md"
            >
              <Card>
                <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-4">
                  <CardTitle className="text-xl">
                    {editingFlow ? t.common.edit : t.management.addNew}{" "}
                    {formData.flow_type === FlowType.EARNING
                      ? t.management.flowType.EARNING
                      : t.management.flowType.EXPENSE}
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsDialogOpen(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>

                <CardContent className="space-y-4">
                  <div className="flex items-end justify-between gap-4">
                    <div className="min-w-0">
                      <label className="text-sm font-medium block mb-1">
                        {t.management.iconLabel}
                      </label>
                      <IconPicker
                        value={formData.icon}
                        onValueChange={value =>
                          setFormData(prev => ({ ...prev, icon: value }))
                        }
                        modal
                      />
                    </div>

                    <div className="flex items-center gap-2 pb-1 shrink-0">
                      <label
                        htmlFor="pending-enabled"
                        className="text-sm font-medium"
                      >
                        {t.management.enabled}
                      </label>
                      <Switch
                        id="pending-enabled"
                        checked={formData.enabled}
                        onCheckedChange={checked =>
                          setFormData(prev => ({ ...prev, enabled: checked }))
                        }
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-sm font-medium block mb-1">
                      {t.management.name}
                      <span className="text-red-500 ml-1">*</span>
                    </label>
                    <Input
                      value={formData.name}
                      onChange={e =>
                        setFormData(prev => ({
                          ...prev,
                          name: e.target.value,
                        }))
                      }
                      placeholder={t.management.namePlaceholder}
                      className={
                        validationErrors.includes("name")
                          ? "border-red-500"
                          : ""
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
                      {t.management.category}
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
                      {t.management.date}
                      <span className="text-gray-400 font-normal">
                        ({t.management.optional})
                      </span>
                    </label>
                    <DatePicker
                      value={formData.date}
                      onChange={value =>
                        setFormData(prev => ({ ...prev, date: value }))
                      }
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <Button
                      variant="outline"
                      onClick={() => setIsDialogOpen(false)}
                    >
                      {t.common.cancel}
                    </Button>
                    <Button onClick={handleSubmit}>{t.common.save}</Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={handleDelete}
        onCancel={() => setIsDeleteDialogOpen(false)}
      />
    </motion.div>
  )
}
