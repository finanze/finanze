import { useState, useEffect, useMemo } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { DatePicker } from "@/components/ui/DatePicker"
import { Switch } from "@/components/ui/Switch"
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
  Trash2,
  Save,
  BanknoteArrowUp,
  BanknoteArrowDown,
  Edit,
  Tag,
  Calendar,
  ArrowLeft,
  CalendarDays,
} from "lucide-react"
import { getCurrencySymbol, getColorForName } from "@/lib/utils"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { convertCurrency } from "@/utils/financialDataUtils"
import {
  FlowType,
  PendingFlow,
  SavePendingFlowsRequest,
  CreatePendingFlowRequest,
} from "@/types"
import { savePendingFlows } from "@/services/api"

export default function PendingMoneyPage() {
  const { t, locale } = useI18n()
  const { showToast, settings, exchangeRates } = useAppContext()
  const { pendingFlows, refreshFlows } = useFinancialData()
  const navigate = useNavigate()
  const [unsavedChanges, setUnsavedChanges] = useState(false)
  const [existingCategories, setExistingCategories] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string[]>
  >({})
  const [hasTriedSave, setHasTriedSave] = useState(false)
  const [editingFlowId, setEditingFlowId] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<"amount" | "date">("amount")
  const [localPendingFlows, setLocalPendingFlows] = useState<PendingFlow[]>([])
  const [categoryFilter, setCategoryFilter] = useState<string[]>([])

  useEffect(() => {
    setLocalPendingFlows(pendingFlows)
    // Extract categories
    const categories = pendingFlows
      .map(flow => flow.category)
      .filter((category): category is string => Boolean(category))
      .filter((category, index, arr) => arr.indexOf(category) === index)
    setExistingCategories(categories)
  }, [pendingFlows])

  // Sort flows based on selected criteria
  const sortedFlows = useMemo(() => {
    const flows = [...localPendingFlows].filter(f =>
      categoryFilter.length
        ? f.category
          ? categoryFilter.includes(f.category)
          : false
        : true,
    )
    if (sortBy === "amount") {
      return flows.sort((a, b) => {
        const amountA = a.amount
        const amountB = b.amount
        return amountB - amountA // Descending order
      })
    } else {
      return flows.sort((a, b) => {
        if (!a.date && !b.date) return 0
        if (!a.date) return 1
        if (!b.date) return -1
        return new Date(a.date).getTime() - new Date(b.date).getTime()
      })
    }
  }, [localPendingFlows, sortBy, categoryFilter])

  // Component for controlled input that doesn't update state on every keystroke
  const DebouncedInput = ({
    value,
    onChange,
    onBlur,
    ...props
  }: {
    value: string
    onChange: (value: string) => void
    onBlur?: () => void
  } & Omit<React.ComponentProps<typeof Input>, "onChange" | "onBlur">) => {
    const [localValue, setLocalValue] = useState(value)

    useEffect(() => {
      setLocalValue(value)
    }, [value])

    const handleBlur = () => {
      if (localValue !== value) {
        onChange(localValue)
      }
      onBlur?.()
    }

    return (
      <Input
        {...props}
        value={localValue}
        onChange={e => setLocalValue(e.target.value)}
        onBlur={handleBlur}
      />
    )
  }

  const addNewFlow = (flowType: FlowType) => {
    const newFlow: CreatePendingFlowRequest = {
      name: "",
      amount: 0,
      flow_type: flowType,
      category: "",
      enabled: true,
      date: "", // Leave empty initially since it's optional
      currency: settings?.general?.defaultCurrency,
    }
    // Use a more stable ID for temporary flows
    const tempId = `temp-${flowType}-${localPendingFlows.length}-${Date.now()}`
    setLocalPendingFlows(prev => [...prev, { ...newFlow, id: tempId }])
    setUnsavedChanges(true)
    // Automatically set the new flow in edit mode
    setEditingFlowId(tempId)
  }

  const updateFlow = (
    index: number,
    field: keyof CreatePendingFlowRequest,
    value: string,
  ) => {
    setLocalPendingFlows(prev => {
      const newFlows = [...prev]
      const currentFlow = newFlows[index]
      if (field === "enabled") {
        newFlows[index] = { ...currentFlow, [field]: value === "true" }
      } else {
        newFlows[index] = { ...currentFlow, [field]: value }
      }
      return newFlows
    })
    setUnsavedChanges(true)
  }

  const removeFlow = (index: number) => {
    setLocalPendingFlows(prev => prev.filter((_, i) => i !== index))
    setUnsavedChanges(true)
  }

  const handleSave = async () => {
    setHasTriedSave(true)

    // Validate all flows
    const errors: Record<string, string[]> = {}
    localPendingFlows.forEach((flow, index) => {
      const flowErrors: string[] = []
      if (!flow.name.trim()) flowErrors.push("name")
      if (!flow.amount) flowErrors.push("amount")

      if (flowErrors.length > 0) {
        errors[`flow-${index}`] = flowErrors
      }
    })

    setValidationErrors(errors)

    if (Object.keys(errors).length > 0) {
      return
    }

    try {
      const flowsToSave = localPendingFlows.map(flow => ({
        name: flow.name,
        amount: flow.amount,
        flow_type: flow.flow_type,
        category: flow.category,
        enabled: flow.enabled,
        date: flow.date,
        currency: flow.currency,
        icon: (flow as any).icon,
      }))

      const request: SavePendingFlowsRequest = {
        flows: flowsToSave,
      }

      await savePendingFlows(request)
      showToast(t.management.saveSuccess, "success")
      setUnsavedChanges(false)
      setHasTriedSave(false)
      setValidationErrors({})
      // Refresh flows from context
      await refreshFlows()
    } catch (error) {
      console.error("Error saving pending flows:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const earnings = sortedFlows.filter(
    flow => flow.flow_type === FlowType.EARNING,
  )
  const expenses = sortedFlows.filter(
    flow => flow.flow_type === FlowType.EXPENSE,
  )

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

  // Calculate totals for KPIs (excluding disabled flows)
  const defaultCurrency = settings?.general?.defaultCurrency

  const totalPendingEarnings = earnings
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

  const totalPendingExpenses = expenses
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
    const enabledEarnings = earnings.filter(flow => flow.enabled)
    const enabledExpenses = expenses.filter(flow => flow.enabled)

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
    earnings,
    expenses,
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

  const FlowSection = ({
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
    const sectionFlows = flows.map(flow => {
      const sectionIndex = localPendingFlows.findIndex(f => f === flow)
      return { flow, index: sectionIndex }
    })

    return (
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
          <Button
            onClick={() => addNewFlow(flowType)}
            size="sm"
            className="flex items-center gap-2 bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
          >
            <Plus size={16} />
          </Button>
        </div>

        {sectionFlows.length === 0 ? (
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
            {sectionFlows.map(({ flow, index }) => (
              <div
                key={flow.id}
                className={`${
                  !flow.enabled
                    ? "opacity-50 bg-gray-50 dark:bg-black"
                    : "bg-card shadow-sm"
                } ${editingFlowId === flow.id ? "flex flex-col gap-4 opacity-95" : "flex items-start justify-between gap-4"} p-4 border rounded-lg`}
              >
                {editingFlowId === flow.id ? (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          {t.management.iconLabel}
                        </label>
                        <IconPicker
                          value={(flow as any).icon as IconName | undefined}
                          onValueChange={value =>
                            updateFlow(index, "icon" as any, value as any)
                          }
                          modal
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          {t.management.name}
                        </label>
                        <DebouncedInput
                          id={`name-${flow.id}`}
                          value={flow.name}
                          onChange={value => updateFlow(index, "name", value)}
                          placeholder={t.management.namePlaceholder}
                          className={`h-9 ${hasTriedSave && validationErrors[`flow-${index}`]?.includes("name") ? "border-red-500" : ""}`}
                        />
                      </div>

                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          {t.management.amount}
                        </label>
                        <div className="relative">
                          <span className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                            {getCurrencySymbol(flow.currency)}
                          </span>
                          <DebouncedInput
                            id={`amount-${flow.id}`}
                            type="number"
                            step="0.01"
                            value={flow.amount.toString()}
                            onChange={value =>
                              updateFlow(index, "amount", value)
                            }
                            placeholder={t.management.amountPlaceholder}
                            className={`h-9 pl-6 ${hasTriedSave && validationErrors[`flow-${index}`]?.includes("amount") ? "border-red-500" : ""}`}
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          {t.management.category}
                        </label>
                        <CategorySelector
                          id={`category-${flow.id}`}
                          value={flow.category || ""}
                          onChange={value =>
                            updateFlow(index, "category", value)
                          }
                          placeholder={t.management.categoryPlaceholder}
                          className="h-9"
                          categories={existingCategories}
                        />
                      </div>

                      <div>
                        <label className="text-xs font-medium text-gray-500 block mb-1">
                          {t.management.date}
                        </label>
                        <DatePicker
                          value={flow.date || ""}
                          onChange={value => updateFlow(index, "date", value)}
                          className={`h-9 ${hasTriedSave && validationErrors[`flow-${index}`]?.includes("date") ? "border-red-500" : ""}`}
                        />
                      </div>

                      <div
                        className={`flex flex-col items-center justify-center gap-1 ${!flow.enabled ? "opacity-100" : ""}`}
                      >
                        <label className="text-xs font-medium text-gray-500">
                          {t.management.enabled}
                        </label>
                        <Switch
                          checked={flow.enabled}
                          onCheckedChange={checked =>
                            updateFlow(index, "enabled", checked.toString())
                          }
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-1 mt-2 border-t pt-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingFlowId(null)}
                        className="text-blue-600 hover:text-blue-700 h-8 px-3"
                      >
                        Done
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFlow(index)}
                        className="text-red-600 hover:text-red-700 h-8 w-8 p-0"
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
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
                        onClick={() => setEditingFlowId(flow.id)}
                        className="h-8 w-8 p-0"
                      >
                        <Edit size={16} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFlow(index)}
                        className="text-red-600 hover:text-red-700 h-8 w-8 p-0"
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/management")}
          >
            <ArrowLeft size={16} />
          </Button>
          <h1 className="text-2xl font-bold">{t.management.pendingMoney}</h1>
        </div>

        {unsavedChanges && (
          <div className="flex flex-col xs:flex-row items-start xs:items-center gap-2 xs:gap-4">
            <span className="text-sm text-orange-600">
              {t.management.unsavedChanges}
            </span>
            <Button
              onClick={handleSave}
              className="flex items-center gap-2"
              size="sm"
            >
              <Save size={16} />
              {t.common.save}
            </Button>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
            {earnings.filter(flow => flow.enabled).length}{" "}
            {earnings.filter(flow => flow.enabled).length === 1
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
            {expenses.filter(flow => flow.enabled).length}{" "}
            {expenses.filter(flow => flow.enabled).length === 1
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
      </div>

      {/* Sorting Controls */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
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
      </div>

      <FlowSection
        title={t.management.pendingEarnings}
        flows={earnings}
        flowType={FlowType.EARNING}
        emptyMessage={t.management.noPendingEarnings}
        addMessage={t.management.addFirstPendingEarning}
      />

      <FlowSection
        title={t.management.pendingExpenses}
        flows={expenses}
        flowType={FlowType.EXPENSE}
        emptyMessage={t.management.noPendingExpenses}
        addMessage={t.management.addFirstPendingExpense}
      />
    </div>
  )
}
