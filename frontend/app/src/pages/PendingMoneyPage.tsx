import { useState, useEffect, useMemo, useRef, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { Input } from "@/components/ui/Input"
import { DecimalInput } from "@/components/ui/DecimalInput"
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
  ArrowRight,
  Ban,
  Banknote,
  BanknoteArrowDown,
  BanknoteArrowUp,
  Calendar,
  CalendarDays,
  ChevronDown,
  CircleCheckBig,
  Edit,
  Plus,
  SlidersHorizontal,
  Tag,
  Trash2,
  Undo2,
  X,
} from "lucide-react"
import { cn, getCurrencySymbol, getColorForName } from "@/lib/utils"
import { formatCurrency, formatDate } from "@/lib/formatters"
import { Sensitive } from "@/components/ui/Sensitive"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { convertCurrency } from "@/utils/financialDataUtils"
import {
  FlowType,
  FlowStatus,
  FlowSortField,
  SortOrder,
  PendingFlow,
  PendingFlowStats,
  CreatePendingFlowRequest,
} from "@/types"
import {
  createPendingFlow,
  updatePendingFlow,
  deletePendingFlow,
  getPendingFlows,
} from "@/services/api"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"

type PendingFlowFormState = Omit<CreatePendingFlowRequest, "status"> & {
  status: FlowStatus
  icon?: IconName
}

const PAGE_SIZE = 20

const DEFAULT_STATUS_FILTER: FlowStatus[] = [
  FlowStatus.ACTIVE,
  FlowStatus.DISABLED,
]

export default function PendingMoneyPage() {
  const { t, locale } = useI18n()
  const { showToast, settings, exchangeRates } = useAppContext()
  const { refreshPendingFlows } = useFinancialData()
  const navigate = useNavigate()
  const defaultCurrency = settings?.general?.defaultCurrency || "EUR"

  const [activeTab, setActiveTab] = useState<FlowType>(FlowType.EARNING)
  const [statusFilter, setStatusFilter] = useState<FlowStatus[]>(
    DEFAULT_STATUS_FILTER,
  )
  const [sortBy, setSortBy] = useState<FlowSortField>(FlowSortField.AMOUNT)
  const [sortOrder, setSortOrder] = useState<SortOrder>(SortOrder.DESC)
  const [categoryFilter, setCategoryFilter] = useState<string[]>([])
  const [groupByCategory, setGroupByCategory] = useState(() => {
    try {
      return sessionStorage.getItem("pendingGroupByCategory") === "true"
    } catch {
      return false
    }
  })
  const [showMobileFilters, setShowMobileFilters] = useState(false)

  const [entries, setEntries] = useState<PendingFlow[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [stats, setStats] = useState<PendingFlowStats | null>(null)
  const [allCategories, setAllCategories] = useState<string[]>([])
  const [dataVersion, setDataVersion] = useState(0)

  const [existingCategories, setExistingCategories] = useState<string[]>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [runEntranceAnimation, setRunEntranceAnimation] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isCompleteDialogOpen, setIsCompleteDialogOpen] = useState(false)
  const [editingFlow, setEditingFlow] = useState<PendingFlow | null>(null)
  const [deletingFlow, setDeletingFlow] = useState<PendingFlow | null>(null)
  const [completingFlow, setCompletingFlow] = useState<PendingFlow | null>(null)

  const pageRef = useRef(1)
  const loadingRef = useRef(false)
  const fetchIdRef = useRef(0)
  const observerRef = useRef<IntersectionObserver | null>(null)

  useModalBackHandler(isDialogOpen, () => setIsDialogOpen(false))
  useModalBackHandler(isDeleteDialogOpen, () => setIsDeleteDialogOpen(false))
  useModalBackHandler(isCompleteDialogOpen, () =>
    setIsCompleteDialogOpen(false),
  )

  const [formData, setFormData] = useState<PendingFlowFormState>({
    name: "",
    amount: 0,
    flow_type: FlowType.EARNING,
    category: "",
    status: FlowStatus.ACTIVE,
    date: "",
    currency: defaultCurrency,
  })

  useEffect(() => {
    try {
      sessionStorage.setItem("pendingGroupByCategory", String(groupByCategory))
    } catch {
      // ignore
    }
  }, [groupByCategory])

  useEffect(() => {
    setExistingCategories(allCategories)
  }, [allCategories])

  useEffect(() => {
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

  const fetchEntries = useCallback(
    async (append: boolean) => {
      if (loadingRef.current) return
      loadingRef.current = true

      const fetchId = ++fetchIdRef.current
      const nextPage = append ? pageRef.current + 1 : 1

      if (append) {
        setIsLoadingMore(true)
      } else {
        setIsLoading(true)
      }

      try {
        const response = await getPendingFlows({
          flow_type: activeTab,
          status: statusFilter.length ? statusFilter : undefined,
          category: categoryFilter.length ? categoryFilter : undefined,
          sort_by: sortBy,
          order: sortOrder,
          page: groupByCategory ? undefined : nextPage,
          limit: groupByCategory ? undefined : PAGE_SIZE,
          stats: !append,
          categories: !append,
        })

        if (fetchIdRef.current !== fetchId) return

        setEntries(prev =>
          append ? [...prev, ...response.entries] : response.entries,
        )
        setHasMore(groupByCategory ? false : response.has_more)
        pageRef.current = nextPage
        if (!append) {
          setStats(response.stats)
          setAllCategories(response.categories ?? [])
        }
      } catch (error) {
        if (fetchIdRef.current !== fetchId) return
        console.error("Error loading pending flows:", error)
        showToast(t.management.loadError, "error")
      } finally {
        if (fetchIdRef.current === fetchId) {
          setIsLoading(false)
          setIsLoadingMore(false)
          loadingRef.current = false
        }
      }
    },
    [
      activeTab,
      statusFilter,
      categoryFilter,
      sortBy,
      sortOrder,
      groupByCategory,
      showToast,
      t.management.loadError,
    ],
  )

  useEffect(() => {
    pageRef.current = 1
    loadingRef.current = false
    fetchEntries(false)
  }, [fetchEntries, dataVersion])

  const loadMore = useCallback(() => {
    if (loadingRef.current || !hasMore) return
    fetchEntries(true)
  }, [fetchEntries, hasMore])

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }
      if (!node) return
      observerRef.current = new IntersectionObserver(
        observed => {
          if (observed[0]?.isIntersecting && !loadingRef.current && hasMore) {
            loadMore()
          }
        },
        { rootMargin: "200px" },
      )
      observerRef.current.observe(node)
    },
    [loadMore, hasMore],
  )

  useEffect(() => {
    return () => {
      if (observerRef.current) observerRef.current.disconnect()
    }
  }, [])

  const refreshAll = () => {
    setDataVersion(v => v + 1)
    void refreshPendingFlows()
  }

  const resetForm = () => {
    setFormData({
      name: "",
      amount: 0,
      flow_type: activeTab,
      category: "",
      status: FlowStatus.ACTIVE,
      date: "",
      currency: defaultCurrency,
    })
    setEditingFlow(null)
    setValidationErrors([])
  }

  const handleSubmit = async () => {
    const errors: string[] = []
    if (!formData.name.trim()) errors.push("name")
    if (!formData.amount) errors.push("amount")

    setValidationErrors(errors)
    if (errors.length > 0) return

    const payload = {
      name: formData.name.trim(),
      amount: Number(formData.amount),
      flow_type: formData.flow_type,
      category: formData.category || undefined,
      status: formData.status,
      date: formData.date || undefined,
      currency: formData.currency || defaultCurrency,
      icon: formData.icon,
    }

    try {
      if (editingFlow) {
        await updatePendingFlow({ id: editingFlow.id, ...payload })
      } else {
        await createPendingFlow(payload)
      }
      showToast(t.management.saveSuccess, "success")
      setIsDialogOpen(false)
      resetForm()
      refreshAll()
    } catch (error) {
      console.error("Error saving pending flow:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const handleDelete = async () => {
    if (!deletingFlow) return
    try {
      await deletePendingFlow(deletingFlow.id)
      showToast(t.management.deleteSuccess, "success")
      setIsDeleteDialogOpen(false)
      setDeletingFlow(null)
      refreshAll()
    } catch (error) {
      console.error("Error deleting pending flow:", error)
      showToast(t.management.deleteError, "error")
    }
  }

  const handleComplete = async () => {
    if (!completingFlow) return
    try {
      await updatePendingFlow({
        id: completingFlow.id,
        name: completingFlow.name,
        amount: Number(completingFlow.amount),
        flow_type: completingFlow.flow_type,
        category: completingFlow.category || undefined,
        status: FlowStatus.COMPLETED,
        date: completingFlow.date || undefined,
        currency: completingFlow.currency || defaultCurrency,
        icon: (completingFlow as { icon?: IconName }).icon,
      })
      showToast(t.management.saveSuccess, "success")
      setIsCompleteDialogOpen(false)
      setCompletingFlow(null)
      refreshAll()
    } catch (error) {
      console.error("Error completing pending flow:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const handleReactivate = async (flow: PendingFlow) => {
    try {
      await updatePendingFlow({
        id: flow.id,
        name: flow.name,
        amount: Number(flow.amount),
        flow_type: flow.flow_type,
        category: flow.category || undefined,
        status: FlowStatus.ACTIVE,
        date: flow.date || undefined,
        currency: flow.currency || defaultCurrency,
        icon: (flow as { icon?: IconName }).icon,
      })
      showToast(t.management.saveSuccess, "success")
      refreshAll()
    } catch (error) {
      console.error("Error reactivating pending flow:", error)
      showToast(t.management.saveError, "error")
    }
  }

  const openCreateDialog = () => {
    resetForm()
    setFormData(prev => ({ ...prev, flow_type: activeTab }))
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
      status: flow.status,
      date: flow.date || "",
      currency: flow.currency || defaultCurrency,
      icon: (flow as { icon?: IconName }).icon,
    })
    setIsDialogOpen(true)
  }

  const openDeleteDialog = (flow: PendingFlow) => {
    setDeletingFlow(flow)
    setIsDeleteDialogOpen(true)
  }

  const openCompleteDialog = (flow: PendingFlow) => {
    setCompletingFlow(flow)
    setIsCompleteDialogOpen(true)
  }

  const toggleCategoryFilter = (category: string) => {
    setCategoryFilter(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category],
    )
  }

  const toggleStatusFilter = (status: FlowStatus) => {
    setStatusFilter(prev =>
      prev.includes(status)
        ? prev.filter(s => s !== status)
        : [...prev, status],
    )
  }

  const categoryOptions: MultiSelectOption[] = useMemo(
    () => allCategories.map(c => ({ value: c, label: c })),
    [allCategories],
  )

  const isDefaultStatusFilter =
    statusFilter.length === DEFAULT_STATUS_FILTER.length &&
    DEFAULT_STATUS_FILTER.every(s => statusFilter.includes(s))
  const activeFilterCount =
    categoryFilter.length +
    (groupByCategory ? 1 : 0) +
    (isDefaultStatusFilter ? 0 : 1) +
    (sortBy !== FlowSortField.AMOUNT ? 1 : 0) +
    (sortOrder !== SortOrder.DESC ? 1 : 0)

  const sumTotals = (totals: Record<string, number>) =>
    Object.entries(totals).reduce(
      (sum, [currency, amount]) =>
        sum + convertCurrency(amount, currency, defaultCurrency, exchangeRates),
      0,
    )

  const totalPendingEarnings = stats ? sumTotals(stats.earning.totals) : 0
  const totalPendingExpenses = stats ? sumTotals(stats.expense.totals) : 0
  const earningsCount = stats?.earning.count ?? 0
  const expensesCount = stats?.expense.count ?? 0

  const getEarningsColor = (index: number) => {
    const greenShades = [
      "bg-green-800",
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
      "bg-red-800",
      "bg-red-700",
      "bg-red-600",
      "bg-red-500",
      "bg-red-400",
      "bg-red-300",
      "bg-red-100",
    ]
    return redShades[index % redShades.length]
  }

  const flowDistribution = useMemo(() => {
    const MAX_SLICES = 8
    const build = (
      byCategory: {
        category: string | null
        name: string | null
        amounts: Record<string, number>
      }[],
      total: number,
      type: "earning" | "expense",
    ) => {
      const mapped = byCategory
        .map(entry => {
          const amount = Object.entries(entry.amounts).reduce(
            (sum, [currency, value]) =>
              sum +
              convertCurrency(value, currency, defaultCurrency, exchangeRates),
            0,
          )
          return {
            category: entry.category,
            label: entry.name ?? entry.category ?? t.management.uncategorized,
            amount,
            percentage: total > 0 ? (amount / total) * 100 : 0,
            type,
          }
        })
        .sort((a, b) => b.amount - a.amount)

      let shown = mapped
      if (mapped.length > MAX_SLICES) {
        const top = mapped.slice(0, MAX_SLICES - 1)
        const rest = mapped.slice(MAX_SLICES - 1)
        const otherAmount = rest.reduce((sum, entry) => sum + entry.amount, 0)
        shown = [
          ...top,
          {
            category: null,
            label: t.management.other,
            amount: otherAmount,
            percentage: total > 0 ? (otherAmount / total) * 100 : 0,
            type,
          },
        ]
      }

      return shown.map((entry, index) => ({
        ...entry,
        color:
          type === "earning"
            ? getEarningsColor(index)
            : getExpensesColor(index),
      }))
    }

    return {
      earnings: stats
        ? build(stats.earning.by_category, totalPendingEarnings, "earning")
        : [],
      expenses: stats
        ? build(stats.expense.by_category, totalPendingExpenses, "expense")
        : [],
    }
  }, [
    stats,
    totalPendingEarnings,
    totalPendingExpenses,
    defaultCurrency,
    exchangeRates,
    t.management.uncategorized,
    t.management.other,
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

  const statusChips: { status: FlowStatus; label: string }[] = [
    { status: FlowStatus.ACTIVE, label: t.management.flowStatus.ACTIVE },
    { status: FlowStatus.DISABLED, label: t.management.flowStatus.DISABLED },
    { status: FlowStatus.COMPLETED, label: t.management.flowStatus.COMPLETED },
  ]

  const renderFlowCard = (flow: PendingFlow) => {
    const isInactive = flow.status !== FlowStatus.ACTIVE
    const icon = (flow as { icon?: IconName }).icon
    return (
      <motion.div
        key={flow.id}
        variants={fadeListItem}
        initial={runEntranceAnimation ? "hidden" : false}
        animate="show"
        className={cn(
          "p-4 border rounded-lg",
          isInactive
            ? "opacity-60 bg-gray-50 dark:bg-black"
            : "bg-card shadow-sm",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Icon
              name={(icon as IconName) || "circle-dashed"}
              className="w-5 h-5 shrink-0"
            />
            <h3 className="font-medium truncate">{flow.name}</h3>
            {flow.status === FlowStatus.DISABLED && (
              <span className="flex items-center gap-1 text-xs font-medium text-muted-foreground bg-muted px-2 py-1 rounded-full shrink-0">
                <Ban size={13} />
                <span className="hidden sm:inline">
                  {t.management.flowStatus.DISABLED}
                </span>
              </span>
            )}
            {flow.status === FlowStatus.COMPLETED && (
              <span className="flex items-center gap-1 text-xs font-medium text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded-full shrink-0">
                <CircleCheckBig size={13} />
                <span className="hidden sm:inline">
                  {t.management.flowStatus.COMPLETED}
                </span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-mono font-semibold">
              <Sensitive>
                {formatCurrency(flow.amount, locale, flow.currency)}
              </Sensitive>
            </span>
            <div className="hidden sm:flex items-center gap-1">
              {flow.status === FlowStatus.COMPLETED ? (
                <Button
                  variant="ghost"
                  size="sm"
                  title={t.management.markActive}
                  onClick={() => handleReactivate(flow)}
                  className="text-blue-600 hover:text-blue-700 h-8 w-8 p-0"
                >
                  <Undo2 size={16} />
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  title={t.management.markCompleted}
                  onClick={() => openCompleteDialog(flow)}
                  className="text-green-600 hover:text-green-700 h-8 w-8 p-0"
                >
                  <CircleCheckBig size={16} />
                </Button>
              )}
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
          </div>
        </div>

        {((!groupByCategory && flow.category) || flow.date) && (
          <div className="flex flex-wrap items-center gap-2 mt-1.5">
            {!groupByCategory && flow.category && (
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
                  <Badge variant="outline" className="flex items-center gap-1">
                    <Calendar size={12} />
                    {formatDate(flow.date || "", locale)}
                  </Badge>
                )
              }
            })()}
          </div>
        )}

        <div className="flex sm:hidden justify-end gap-1 mt-2">
          {flow.status === FlowStatus.COMPLETED ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleReactivate(flow)}
              className="text-blue-600 hover:text-blue-700 h-8 w-8 p-0"
            >
              <Undo2 size={16} />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => openCompleteDialog(flow)}
              className="text-green-600 hover:text-green-700 h-8 w-8 p-0"
            >
              <CircleCheckBig size={16} />
            </Button>
          )}
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
    )
  }

  const renderGroupedList = () => {
    const groups = entries.reduce(
      (acc, flow) => {
        const key = flow.category || "__uncategorized__"
        if (!acc[key]) acc[key] = []
        acc[key].push(flow)
        return acc
      },
      {} as Record<string, PendingFlow[]>,
    )

    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (a === "__uncategorized__") return 1
      if (b === "__uncategorized__") return -1
      return a.localeCompare(b)
    })

    return sortedKeys.map(key => (
      <div key={key} className="space-y-2">
        <div className="flex items-center gap-2 pt-2">
          <Badge
            variant="secondary"
            className={cn(
              "flex items-center gap-1",
              key !== "__uncategorized__" && getColorForName(key),
            )}
          >
            <Tag size={12} />
            {key === "__uncategorized__" ? t.management.uncategorized : key}
          </Badge>
        </div>
        <div className="space-y-2 pl-2 border-l-2 border-muted">
          {groups[key].map(renderFlowCard)}
        </div>
      </div>
    ))
  }

  const emptyMessage =
    activeTab === FlowType.EARNING
      ? t.management.noPendingEarnings
      : t.management.noPendingExpenses
  const addMessage =
    activeTab === FlowType.EARNING
      ? t.management.addFirstPendingEarning
      : t.management.addFirstPendingExpense

  const renderDistribution = (
    data: typeof flowDistribution.earnings,
    total: number,
    tone: "earning" | "expense",
  ) => {
    if (data.length === 0) return null
    const bgTone =
      tone === "earning"
        ? "bg-green-50 dark:bg-green-900/20"
        : "bg-red-50 dark:bg-red-900/20"
    return (
      <div className="mt-4">
        <div className="relative h-6 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
          <div className="flex h-full">
            {data.map((entry, index) => {
              const clickable = Boolean(
                entry.category && existingCategories.includes(entry.category),
              )
              return (
                <div
                  key={`${tone}-${index}`}
                  className={`${entry.color} relative group ${clickable ? "cursor-pointer" : "cursor-default"} hover:opacity-80 transition-opacity duration-200`}
                  style={{ width: `${entry.percentage}%` }}
                  title={`${entry.label}: ${formatCurrency(
                    entry.amount,
                    locale,
                    defaultCurrency,
                  )} (${entry.percentage.toFixed(1)}%)`}
                  onClick={() =>
                    clickable && toggleCategoryFilter(entry.category!)
                  }
                >
                  <div className="absolute inset-0 dark:bg-black opacity-0 group-hover:opacity-10 transition-opacity duration-200"></div>
                </div>
              )
            })}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 w-full md:max-h-40 md:overflow-auto">
          {data.map((entry, index) => {
            const clickable = Boolean(
              entry.category && existingCategories.includes(entry.category),
            )
            return (
              <div
                key={`${tone}-legend-${index}`}
                className={`flex items-center gap-2 text-xs leading-tight ${bgTone} px-2 py-0 h-7 shrink-0 rounded-md flex-1 sm:flex-none min-w-[180px] max-w-full overflow-hidden ${
                  clickable ? "cursor-pointer" : "cursor-default opacity-70"
                }`}
                onClick={() =>
                  clickable && toggleCategoryFilter(entry.category!)
                }
              >
                <div className={`w-3 h-3 rounded ${entry.color}`}></div>
                <span
                  className="font-medium truncate min-w-0 flex-1"
                  title={entry.label}
                >
                  {entry.label}
                </span>
                <span
                  className={`font-mono shrink-0 ${
                    tone === "earning" ? "text-green-600" : "text-red-600"
                  }`}
                >
                  <Sensitive>
                    {formatCurrency(entry.amount, locale, defaultCurrency)}
                  </Sensitive>
                </span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const renderDetailedControls = () => (
    <>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {t.management.sortBy}
          </span>
          <div className="flex items-center bg-muted rounded-lg p-1">
            <button
              onClick={() => setSortBy(FlowSortField.AMOUNT)}
              title={t.management.sortByAmount}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                sortBy === FlowSortField.AMOUNT
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Banknote size={16} />
            </button>
            <button
              onClick={() => setSortBy(FlowSortField.DATE)}
              title={t.management.sortByDate}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                sortBy === FlowSortField.DATE
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <CalendarDays size={16} />
            </button>
          </div>
          <button
            onClick={() =>
              setSortOrder(
                sortOrder === SortOrder.ASC ? SortOrder.DESC : SortOrder.ASC,
              )
            }
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
            aria-label={
              sortOrder === SortOrder.ASC ? "Sort descending" : "Sort ascending"
            }
          >
            {sortOrder === SortOrder.ASC ? (
              <ArrowRight size={16} className="rotate-[-90deg]" />
            ) : (
              <ArrowRight size={16} className="rotate-90" />
            )}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {t.management.statusFilter}
          </span>
          <div className="flex items-center gap-1 flex-wrap">
            {statusChips.map(chip => (
              <button
                key={chip.status}
                onClick={() => toggleStatusFilter(chip.status)}
                className={cn(
                  "px-2.5 py-1 text-xs font-medium rounded-full transition-all border",
                  statusFilter.includes(chip.status)
                    ? "bg-foreground text-background border-foreground"
                    : "bg-muted text-muted-foreground border-transparent hover:text-foreground",
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:ml-auto flex-wrap max-w-full sm:justify-end">
        <span className="text-sm text-muted-foreground">
          {t.management.groupBy}
        </span>
        <button
          onClick={() => setGroupByCategory(prev => !prev)}
          title={t.management.groupByCategory}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-all bg-muted",
            groupByCategory
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Tag size={14} />
          <span className="hidden sm:inline">
            {t.management.groupByCategory}
          </span>
        </button>
        <MultiSelect
          options={categoryOptions}
          value={categoryFilter}
          onChange={setCategoryFilter}
          className="hidden sm:block min-w-[180px] md:min-w-[220px] flex-grow max-w-full"
        />
      </div>
    </>
  )

  return (
    <>
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
              <h1 className="text-2xl font-bold">
                {t.management.pendingMoney}
              </h1>
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
              <Sensitive>
                {formatCurrency(totalPendingEarnings, locale, defaultCurrency)}
              </Sensitive>
            </div>
            <div className="text-xs text-gray-500">
              {earningsCount}{" "}
              {earningsCount === 1
                ? t.management.flowType.EARNING.toLowerCase()
                : t.management.earnings.toLowerCase()}
            </div>
            {renderDistribution(
              flowDistribution.earnings,
              totalPendingEarnings,
              "earning",
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
              <Sensitive>
                {formatCurrency(totalPendingExpenses, locale, defaultCurrency)}
              </Sensitive>
            </div>
            <div className="text-xs text-gray-500">
              {expensesCount}{" "}
              {expensesCount === 1
                ? t.management.flowType.EXPENSE.toLowerCase()
                : t.management.expenses.toLowerCase()}
            </div>
            {renderDistribution(
              flowDistribution.expenses,
              totalPendingExpenses,
              "expense",
            )}
          </Card>
        </motion.div>

        {/* Tab toggle */}
        <motion.div
          variants={fadeListItem}
          initial={runEntranceAnimation ? "hidden" : false}
          animate="show"
          className="flex items-center justify-between gap-3 flex-wrap"
        >
          <div className="flex items-center bg-muted rounded-lg p-1">
            <button
              onClick={() => setActiveTab(FlowType.EARNING)}
              className={cn(
                "flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md transition-all",
                activeTab === FlowType.EARNING
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <BanknoteArrowUp size={16} className="text-green-600" />
              <span
                className={cn(
                  activeTab !== FlowType.EARNING && "hidden min-[400px]:inline",
                )}
              >
                {t.management.earnings}
              </span>
            </button>
            <button
              onClick={() => setActiveTab(FlowType.EXPENSE)}
              className={cn(
                "flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded-md transition-all",
                activeTab === FlowType.EXPENSE
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <BanknoteArrowDown size={16} className="text-red-600" />
              <span
                className={cn(
                  activeTab !== FlowType.EXPENSE && "hidden min-[400px]:inline",
                )}
              >
                {t.management.expenses}
              </span>
            </button>
          </div>

          <Button
            onClick={openCreateDialog}
            size="sm"
            className="flex items-center gap-2 bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
          >
            <Plus size={16} />
          </Button>
        </motion.div>

        {/* Controls */}
        <motion.div
          variants={fadeListItem}
          initial={runEntranceAnimation ? "hidden" : false}
          animate="show"
          className="space-y-3"
        >
          {/* Mobile: filters toggle + category select */}
          <div className="flex items-center gap-2 sm:hidden">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowMobileFilters(prev => !prev)}
              className="flex items-center gap-2 shrink-0"
            >
              <SlidersHorizontal size={16} />
              <span className="hidden min-[400px]:inline">
                {t.management.filters}
              </span>
              {activeFilterCount > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-foreground text-background text-[0.65rem] font-semibold h-5 min-w-5 px-1">
                  {activeFilterCount}
                </span>
              )}
              <ChevronDown
                size={16}
                className={cn(
                  "transition-transform",
                  showMobileFilters && "rotate-180",
                )}
              />
            </Button>
            <MultiSelect
              options={categoryOptions}
              value={categoryFilter}
              onChange={setCategoryFilter}
              className="flex-grow min-w-0"
            />
          </div>

          {/* Detailed controls: always on desktop, animated toggle on mobile */}
          <div className="hidden sm:flex items-center justify-between gap-3 flex-wrap">
            {renderDetailedControls()}
          </div>

          <div className="sm:hidden">
            <AnimatePresence initial={false}>
              {showMobileFilters && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2, ease: "easeInOut" }}
                  className="overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-3 flex-wrap pt-1">
                    {renderDetailedControls()}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* List */}
        <motion.div
          variants={fadeListItem}
          initial={runEntranceAnimation ? "hidden" : false}
          animate="show"
          className="space-y-2"
        >
          {entries.length === 0 && !isLoading ? (
            <div className="text-center py-12 text-gray-500">
              <div className="flex justify-center mb-4">
                {activeTab === FlowType.EARNING ? (
                  <BanknoteArrowUp className="text-green-400" size={48} />
                ) : (
                  <BanknoteArrowDown className="text-red-400" size={48} />
                )}
              </div>
              <p className="text-lg font-medium mb-2">{emptyMessage}</p>
              <p className="text-sm">{addMessage}</p>
            </div>
          ) : groupByCategory ? (
            renderGroupedList()
          ) : (
            <motion.div
              variants={fadeListContainer}
              initial={runEntranceAnimation ? "hidden" : false}
              animate="show"
              className="space-y-2"
            >
              {entries.map(renderFlowCard)}
            </motion.div>
          )}

          {!groupByCategory && hasMore && (
            <div
              ref={sentinelRef}
              className="h-8 flex items-center justify-center"
            >
              {isLoadingMore && (
                <span className="text-xs text-muted-foreground">
                  {t.management.loadMore}…
                </span>
              )}
            </div>
          )}
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {isDialogOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-gray-900/20 dark:bg-black/50 flex items-center justify-center p-4 z-[18000]"
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
                      {formData.status === FlowStatus.COMPLETED ? (
                        <span className="text-xs font-medium text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded-full flex items-center gap-1">
                          <CircleCheckBig size={12} />
                          {t.management.flowStatus.COMPLETED}
                        </span>
                      ) : (
                        <>
                          <label
                            htmlFor="pending-enabled"
                            className="text-sm font-medium"
                          >
                            {t.management.enabled}
                          </label>
                          <Switch
                            id="pending-enabled"
                            checked={formData.status === FlowStatus.ACTIVE}
                            onCheckedChange={checked =>
                              setFormData(prev => ({
                                ...prev,
                                status: checked
                                  ? FlowStatus.ACTIVE
                                  : FlowStatus.DISABLED,
                              }))
                            }
                          />
                        </>
                      )}
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
                      <DecimalInput
                        value={formData.amount || ""}
                        onValueChange={v =>
                          setFormData(prev => ({
                            ...prev,
                            amount: v ?? 0,
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

      <ConfirmationDialog
        isOpen={isCompleteDialogOpen}
        title={t.management.markCompletedTitle.replace(
          "{type}",
          completingFlow?.flow_type === FlowType.EARNING
            ? t.management.flowType.EARNING.toLowerCase()
            : t.management.flowType.EXPENSE.toLowerCase(),
        )}
        message={t.management.markCompletedConfirm.replace(
          "{type}",
          completingFlow?.flow_type === FlowType.EARNING
            ? t.management.flowType.EARNING.toLowerCase()
            : t.management.flowType.EXPENSE.toLowerCase(),
        )}
        confirmText={t.management.markCompleted}
        cancelText={t.common.cancel}
        onConfirm={handleComplete}
        onCancel={() => setIsCompleteDialogOpen(false)}
      />
    </>
  )
}
