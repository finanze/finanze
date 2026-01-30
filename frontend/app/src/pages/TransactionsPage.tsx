import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  getTransactions,
  createManualTransaction,
  updateManualTransaction,
  deleteManualTransaction,
} from "@/services/api"
import {
  TransactionsResult,
  TransactionQueryRequest,
  TxType,
  type AccountTx,
  type StockTx,
  type CryptoCurrencyTx,
  type FundTx,
  type FundPortfolioTx,
  type FactoringTx,
  type RealEstateCFTx,
  type DepositTx,
} from "@/types/transactions"
import { ProductType } from "@/types/position"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { Badge } from "@/components/ui/Badge"
import { DatePicker } from "@/components/ui/DatePicker"
import { formatCurrency } from "@/lib/formatters"
import { getTransactionDisplayType } from "@/utils/financialDataUtils"
import { getSourceIcon } from "@/components/ui/SourceBadge"
import { EntityBadge } from "@/components/ui/EntityBadge"
import {
  Search,
  RotateCcw,
  Calendar,
  ChevronDown,
  ChevronUp,
  Pencil,
  Plus,
  Trash2,
  List,
  CalendarDays,
  Layers,
  ArrowLeftRight,
  Landmark,
} from "lucide-react"
import {
  getIconForTxType,
  getIconForProductType,
  getProductTypeColor,
} from "@/utils/dashboardUtils"
import { DataSource, EntityOrigin, EntityType } from "@/types"
import {
  ManualTransactionDialog,
  type ManualTransactionEntityOption,
  type ManualTransactionSubmitResult,
} from "@/components/transactions/ManualTransactionDialog"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { TransactionsCalendarView } from "@/components/transactions/TransactionsCalendarView"
import { useLocation, useNavigate } from "react-router-dom"

type ViewMode = "list" | "calendar"

interface TransactionFilters {
  entities: string[]
  product_types: ProductType[]
  types: TxType[]
  from_date: string
  to_date: string
  historic_entry_id: string
}

type TransactionItem = TransactionsResult["transactions"][number]

const ITEMS_PER_PAGE = 20

export default function TransactionsPage() {
  const { t, locale } = useI18n()
  const { entities, settings, showToast, exchangeRates } = useAppContext()
  const location = useLocation()
  const navigateRouter = useNavigate()

  const initialHistoricEntryIdRef = useRef(
    new URLSearchParams(location.search).get("historic_entry_id") ?? "",
  )
  const initialHistoricEntryNameRef = useRef<string | null>(
    new URLSearchParams(location.search).get("historic_entry_name"),
  )
  const skipInitialFetchRef = useRef(Boolean(initialHistoricEntryIdRef.current))
  const latestFetchIdRef = useRef(0)
  const historicFilterWatchStartedRef = useRef(false)
  const previousHistoricIdRef = useRef<string>(
    initialHistoricEntryIdRef.current,
  )
  const initialFetchTriggeredRef = useRef(false)

  const [transactions, setTransactions] = useState<TransactionsResult | null>(
    null,
  )
  const [loadingTxs, setLoadingTxs] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<ViewMode>("list")

  const today = new Date()
  const [calendarMonth, setCalendarMonth] = useState(today.getMonth())
  const [calendarYear, setCalendarYear] = useState(today.getFullYear())
  const [calendarTransactions, setCalendarTransactions] = useState<
    TransactionsResult["transactions"]
  >([])

  const [filters, setFilters] = useState<TransactionFilters>(() => ({
    entities: [],
    product_types: [],
    types: [],
    from_date: "",
    to_date: "",
    historic_entry_id: initialHistoricEntryIdRef.current,
  }))

  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create")
  const [selectedTransaction, setSelectedTransaction] =
    useState<TransactionItem | null>(null)
  const [isSubmittingTransaction, setIsSubmittingTransaction] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<TransactionItem | null>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isDeletingTransaction, setIsDeletingTransaction] = useState(false)
  const [historicEntryName, setHistoricEntryName] = useState<string | null>(
    initialHistoricEntryNameRef.current,
  )

  const entityOptions: MultiSelectOption[] = useMemo(() => {
    return (
      entities
        ?.filter(
          entity =>
            "TRANSACTIONS" in entity.last_fetch ||
            "TRANSACTIONS" in entity.virtual_features,
        )
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities])

  const productTypeOptions: MultiSelectOption[] = useMemo(() => {
    const supportedTypes = [
      ProductType.STOCK_ETF,
      ProductType.FUND,
      ProductType.FUND_PORTFOLIO,
      ProductType.DEPOSIT,
      ProductType.FACTORING,
      ProductType.REAL_ESTATE_CF,
      ProductType.CRYPTO,
    ]
    return supportedTypes.map(type => ({
      value: type,
      label: t.enums?.productType?.[type] || type,
      icon: getIconForProductType(type, "h-4 w-4"),
    }))
  }, [t])

  const transactionTypeOptions: MultiSelectOption[] = useMemo(() => {
    const txTypes = Object.values(TxType)
    return txTypes.map(type => ({
      value: type,
      label: (t.enums as any)?.transactionType?.[type] || type,
      icon: getIconForTxType(type, "h-4 w-4"),
    }))
  }, [t])

  const defaultCurrency = settings.general.defaultCurrency

  const supportedCurrencySet = useMemo<Set<string> | null>(() => {
    if (typeof Intl.supportedValuesOf !== "function") {
      return null
    }
    try {
      return new Set(Intl.supportedValuesOf("currency"))
    } catch (error) {
      console.warn("Failed to read supported currencies", error)
      return null
    }
  }, [])

  const currencyOptions = useMemo(() => {
    const set = new Set<string>()
    set.add(defaultCurrency.toUpperCase())

    Object.entries(exchangeRates || {}).forEach(([base, targets]) => {
      set.add(base.toUpperCase())
      Object.keys(targets).forEach(code => set.add(code.toUpperCase()))
    })

    let options = Array.from(set)
    if (supportedCurrencySet) {
      options = options.filter(code => supportedCurrencySet.has(code))
    }

    return options.sort((a, b) => a.localeCompare(b))
  }, [exchangeRates, defaultCurrency, supportedCurrencySet])

  const manualEntityOptions = useMemo<ManualTransactionEntityOption[]>(() => {
    if (!entities) return []
    return entities
      .filter(entity => entity.type === EntityType.FINANCIAL_INSTITUTION)
      .map(entity => ({
        id: entity.id,
        name: entity.name,
        origin: entity.origin as EntityOrigin,
      }))
      .sort((a, b) =>
        a.name.localeCompare(b.name, locale, { sensitivity: "base" }),
      )
  }, [entities, locale])

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const entryIdParam = params.get("historic_entry_id") ?? ""
    const entryNameParam = params.get("historic_entry_name")

    setHistoricEntryName(entryNameParam ? entryNameParam : null)

    setFilters(prev => {
      if (prev.historic_entry_id === entryIdParam) {
        return prev
      }
      return {
        ...prev,
        historic_entry_id: entryIdParam,
      }
    })
  }, [location.search])

  const fetchTransactions = async (
    page: number = 1,
    resetPage: boolean = false,
  ) => {
    const fetchId = ++latestFetchIdRef.current
    setLoadingTxs(true)
    // Clear previous error toast implicitly by showing a new one only on failure

    try {
      const queryParams: TransactionQueryRequest = {
        page: resetPage ? 1 : page,
        limit: ITEMS_PER_PAGE,
        ...filters,
      }

      // Remove empty arrays and strings
      Object.keys(queryParams).forEach(key => {
        const value = queryParams[key as keyof TransactionQueryRequest]
        if (Array.isArray(value) && value.length === 0) {
          delete queryParams[key as keyof TransactionQueryRequest]
        } else if (typeof value === "string" && value === "") {
          delete queryParams[key as keyof TransactionQueryRequest]
        }
      })

      const result = await getTransactions(queryParams)
      if (latestFetchIdRef.current === fetchId) {
        setTransactions(result)

        if (resetPage) {
          setCurrentPage(1)
        }
      }

      return result
    } catch (err) {
      console.error("Error fetching transactions:", err)
      if (latestFetchIdRef.current === fetchId) {
        showToast(t.common.unexpectedError, "error")
      }
      return undefined
    } finally {
      if (latestFetchIdRef.current === fetchId) {
        setLoadingTxs(false)
      }
    }
  }

  useEffect(() => {
    if (initialFetchTriggeredRef.current) {
      return
    }

    initialFetchTriggeredRef.current = true

    if (skipInitialFetchRef.current) {
      skipInitialFetchRef.current = false
      return
    }

    fetchTransactions(1, true)
  }, [])

  useEffect(() => {
    if (!historicFilterWatchStartedRef.current) {
      historicFilterWatchStartedRef.current = true
      previousHistoricIdRef.current = filters.historic_entry_id

      if (filters.historic_entry_id) {
        fetchTransactions(1, true)
      }
      return
    }

    if (previousHistoricIdRef.current !== filters.historic_entry_id) {
      previousHistoricIdRef.current = filters.historic_entry_id
      fetchTransactions(1, true)
    }
  }, [filters.historic_entry_id])

  const handleFilterChange = (key: keyof TransactionFilters, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }))
  }

  const clearHistoricFilter = useCallback(() => {
    setFilters(prev => {
      if (!prev.historic_entry_id) {
        return prev
      }

      return {
        ...prev,
        historic_entry_id: "",
      }
    })

    setHistoricEntryName(null)

    const params = new URLSearchParams(location.search)
    params.delete("historic_entry_id")
    params.delete("historic_entry_name")

    const searchString = params.toString()

    navigateRouter(
      {
        pathname: location.pathname,
        search: searchString ? `?${searchString}` : "",
      },
      { replace: true },
    )
  }, [location.pathname, location.search, navigateRouter])

  const handleApplyFilters = () => {
    if (viewMode === "calendar") {
      fetchCalendarTransactions(calendarMonth, calendarYear)
    } else {
      fetchTransactions(1, true)
    }
  }

  const handleClearFilters = () => {
    clearHistoricFilter()
    setFilters({
      entities: [],
      product_types: [],
      types: [],
      from_date: "",
      to_date: "",
      historic_entry_id: "",
    })
    if (viewMode === "calendar") {
      fetchCalendarTransactions(calendarMonth, calendarYear, true)
    } else {
      fetchTransactions(1, true)
    }
  }

  const fetchCalendarTransactions = async (
    month: number,
    year: number,
    clearFilters?: boolean,
  ) => {
    const fetchId = ++latestFetchIdRef.current
    setLoadingTxs(true)

    try {
      // Calculate the actual visible date range in the calendar grid
      // The grid always shows 6 weeks (42 days) starting from Monday
      const firstDayOfMonth = new Date(year, month, 1)
      let startDay = firstDayOfMonth.getDay()
      startDay = startDay === 0 ? 6 : startDay - 1 // Adjust for Monday start

      // First visible day (may be in previous month)
      const firstVisibleDay = new Date(year, month, 1 - startDay)
      // Last visible day (42 days total in the grid)
      const lastVisibleDay = new Date(firstVisibleDay)
      lastVisibleDay.setDate(firstVisibleDay.getDate() + 41)

      // Format dates as YYYY-MM-DD without timezone conversion
      const formatDateStr = (d: Date) => {
        const yyyy = d.getFullYear()
        const mm = String(d.getMonth() + 1).padStart(2, "0")
        const dd = String(d.getDate()).padStart(2, "0")
        return `${yyyy}-${mm}-${dd}`
      }

      const fromDate = formatDateStr(firstVisibleDay)
      const toDate = formatDateStr(lastVisibleDay)

      const queryParams: TransactionQueryRequest = clearFilters
        ? {
            from_date: fromDate,
            to_date: toDate,
            limit: 1000,
          }
        : {
            ...filters,
            from_date: fromDate,
            to_date: toDate,
            limit: 1000,
          }

      Object.keys(queryParams).forEach(key => {
        const value = queryParams[key as keyof TransactionQueryRequest]
        if (Array.isArray(value) && value.length === 0) {
          delete queryParams[key as keyof TransactionQueryRequest]
        } else if (typeof value === "string" && value === "") {
          delete queryParams[key as keyof TransactionQueryRequest]
        }
      })

      const result = await getTransactions(queryParams)
      if (latestFetchIdRef.current === fetchId) {
        setCalendarTransactions(result.transactions)
      }
    } catch (err) {
      console.error("Error fetching calendar transactions:", err)
      if (latestFetchIdRef.current === fetchId) {
        showToast(t.common.unexpectedError, "error")
      }
    } finally {
      if (latestFetchIdRef.current === fetchId) {
        setLoadingTxs(false)
      }
    }
  }

  const handleCalendarMonthChange = (month: number, year: number) => {
    setCalendarMonth(month)
    setCalendarYear(year)
    fetchCalendarTransactions(month, year)
  }

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode)
    if (mode === "calendar") {
      fetchCalendarTransactions(calendarMonth, calendarYear)
    }
  }

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
    fetchTransactions(page, false)
  }

  const toggleCardExpansion = (transactionId: string) => {
    setExpandedCards(prev => {
      const newSet = new Set(prev)
      if (newSet.has(transactionId)) {
        newSet.delete(transactionId)
      } else {
        newSet.add(transactionId)
      }
      return newSet
    })
  }

  const handleBadgeClick = (
    type: "entity" | "productType" | "transactionType",
    value: string,
  ) => {
    setFilters(prev => {
      switch (type) {
        case "entity":
          if (!prev.entities.includes(value)) {
            return {
              ...prev,
              entities: [...prev.entities, value],
            }
          }
          break
        case "productType":
          if (!prev.product_types.includes(value as ProductType)) {
            return {
              ...prev,
              product_types: [...prev.product_types, value as ProductType],
            }
          }
          break
        case "transactionType":
          if (!prev.types.includes(value as TxType)) {
            return {
              ...prev,
              types: [...prev.types, value as TxType],
            }
          }
          break
      }
      return prev
    })
  }

  const handleOpenCreateDialog = () => {
    setDialogMode("create")
    setSelectedTransaction(null)
    setIsDialogOpen(true)
  }

  const handleDialogClose = () => {
    if (isSubmittingTransaction) return
    setIsDialogOpen(false)
    setSelectedTransaction(null)
    setDialogMode("create")
  }

  const handleEditTransaction = (tx: TransactionItem) => {
    setDialogMode("edit")
    setSelectedTransaction(tx)
    setIsDialogOpen(true)
  }

  const handleRequestDelete = (tx: TransactionItem) => {
    setDeleteTarget(tx)
    setIsDeleteDialogOpen(true)
  }

  const handleCancelDelete = () => {
    if (isDeletingTransaction) return
    setIsDeleteDialogOpen(false)
    setDeleteTarget(null)
  }

  const handleSubmitTransaction = async (
    result: ManualTransactionSubmitResult,
  ) => {
    const isEdit = dialogMode === "edit"
    setIsSubmittingTransaction(true)
    try {
      if (isEdit && result.transactionId) {
        await updateManualTransaction(result.transactionId, result.payload)
        showToast(t.transactions.form.updateSuccess, "success")
      } else {
        await createManualTransaction(result.payload)
        showToast(t.transactions.form.createSuccess, "success")
      }

      setIsDialogOpen(false)
      setSelectedTransaction(null)
      setDialogMode("create")

      if (isEdit) {
        await fetchTransactions(currentPage, false)
      } else {
        await fetchTransactions(1, true)
      }
    } catch (error) {
      console.error("Error saving manual transaction:", error)
      showToast(t.transactions.form.submitError, "error")
    } finally {
      setIsSubmittingTransaction(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    setIsDeletingTransaction(true)
    const targetId = deleteTarget.id
    try {
      await deleteManualTransaction(targetId)
      showToast(t.transactions.form.deleteSuccess, "success")
      setIsDeleteDialogOpen(false)
      setDeleteTarget(null)
      setExpandedCards(prev => {
        const next = new Set(prev)
        next.delete(targetId)
        return next
      })

      const current = currentPage
      const result = await fetchTransactions(current, false)
      if (result && result.transactions.length === 0 && current > 1) {
        setCurrentPage(current - 1)
        await fetchTransactions(current - 1, false)
      }
    } catch (error) {
      console.error("Error deleting manual transaction:", error)
      showToast(t.transactions.form.deleteError, "error")
    } finally {
      setIsDeletingTransaction(false)
    }
  }

  const getTransactionTypeColor = (type: TxType): string => {
    switch (type) {
      case TxType.BUY:
      case TxType.INVESTMENT:
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
      case TxType.SELL:
      case TxType.REPAYMENT:
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100"
      case TxType.DIVIDEND:
      case TxType.INTEREST:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
      case TxType.SWAP_FROM:
      case TxType.SWAP_TO:
      case TxType.TRANSFER_IN:
      case TxType.TRANSFER_OUT:
      case TxType.SWITCH_FROM:
      case TxType.SWITCH_TO:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
      case TxType.FEE:
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
    }
  }

  const detailRowClass = "text-sm text-gray-600 dark:text-gray-400"
  const detailLabelClass = "font-medium text-gray-500 dark:text-gray-300"

  const getSourceInfo = (source: DataSource) => {
    if (source === DataSource.REAL) {
      return null
    }

    const Icon = getSourceIcon(source)

    return (
      <div className={`${detailRowClass} flex items-center gap-2`}>
        <span className={detailLabelClass}>{t.transactions.source}:</span>
        <span className="inline-flex items-center gap-1 text-gray-600 dark:text-gray-400">
          {Icon && <Icon className="h-3.5 w-3.5" />}
          {t.enums?.dataSource?.[source] || source}
        </span>
      </div>
    )
  }

  const renderTransactionDetails = (tx: any) => {
    const commonFields = <>{getSourceInfo(tx.source)}</>

    switch (tx.product_type) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return (
          <>
            {commonFields}
            {stockTx.ticker && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.ticker}:
                </span>{" "}
                {stockTx.ticker}
              </div>
            )}
            {stockTx.isin && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.isin}:</span>{" "}
                {stockTx.isin}
              </div>
            )}
            {stockTx.shares && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.shares}:
                </span>{" "}
                {stockTx.shares.toLocaleString()}
              </div>
            )}
            {Number(stockTx.price || 0) !== 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.price}:
                </span>{" "}
                {formatCurrency(
                  stockTx.price,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {stockTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  stockTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {stockTx.market && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.market}:
                </span>{" "}
                {stockTx.market}
              </div>
            )}
          </>
        )
      }

      case ProductType.CRYPTO: {
        const cryptoTx = tx as CryptoCurrencyTx
        return (
          <>
            {commonFields}
            {cryptoTx.symbol && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.symbol}:
                </span>{" "}
                {cryptoTx.symbol}
              </div>
            )}
            {cryptoTx.currency_amount !== undefined && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.currencyAmount}:
                </span>{" "}
                {cryptoTx.currency_amount.toLocaleString()}
              </div>
            )}
            {Number(cryptoTx.price || 0) !== 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.price}:
                </span>{" "}
                {formatCurrency(
                  cryptoTx.price,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {cryptoTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  cryptoTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {cryptoTx.retentions != null && cryptoTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  cryptoTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      case ProductType.FUND: {
        const fundTx = tx as FundTx
        return (
          <>
            {commonFields}
            <div className={detailRowClass}>
              <span className={detailLabelClass}>{t.transactions.isin}:</span>{" "}
              {fundTx.isin}
            </div>
            <div className={detailRowClass}>
              <span className={detailLabelClass}>{t.transactions.shares}:</span>{" "}
              {fundTx.shares.toLocaleString()}
            </div>
            <div className={detailRowClass}>
              <span className={detailLabelClass}>{t.transactions.price}:</span>{" "}
              {formatCurrency(
                fundTx.price,
                locale,
                settings.general.defaultCurrency,
                tx.currency,
              )}
            </div>
            {fundTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  fundTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            <div className={detailRowClass}>
              <span className={detailLabelClass}>{t.transactions.market}:</span>{" "}
              {fundTx.market}
            </div>
          </>
        )
      }
      case ProductType.FUND_PORTFOLIO: {
        const fpTx = tx as FundPortfolioTx & { portfolio_name?: string }
        return (
          <>
            {commonFields}
            {typeof fpTx.fees === "number" && fpTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  fpTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {fpTx.iban && (
              <div className={`${detailRowClass} break-all`}>
                <span className={detailLabelClass}>{t.transactions.iban}:</span>{" "}
                {fpTx.iban}
              </div>
            )}
            {fpTx.portfolio_name && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.portfolioName}:
                </span>{" "}
                {fpTx.portfolio_name}
              </div>
            )}
          </>
        )
      }

      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return (
          <>
            {commonFields}
            {tx.type === TxType.INTEREST && tx.amount !== undefined && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.grossAmount}:
                </span>{" "}
                {formatCurrency(
                  tx.amount,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {accountTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  accountTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {accountTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  accountTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {accountTx.interest_rate && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.interestRate}:
                </span>{" "}
                {(accountTx.interest_rate * 100).toFixed(2)}%
              </div>
            )}
            {accountTx.avg_balance && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.avgBalance}:
                </span>{" "}
                {formatCurrency(
                  accountTx.avg_balance,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      case ProductType.FACTORING: {
        const factoringTx = tx as FactoringTx
        return (
          <>
            {commonFields}
            {factoringTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  factoringTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {factoringTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  factoringTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      case ProductType.REAL_ESTATE_CF: {
        const realEstateTx = tx as RealEstateCFTx
        return (
          <>
            {commonFields}
            {realEstateTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  realEstateTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {realEstateTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  realEstateTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      case ProductType.DEPOSIT: {
        const depositTx = tx as DepositTx
        return (
          <>
            {commonFields}
            {depositTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  depositTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {depositTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  depositTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      default:
        return commonFields
    }
  }

  const hasTransactionDetails = (tx: any): boolean => {
    if (tx.source !== DataSource.REAL) return true

    switch (tx.product_type) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return !!(
          stockTx.ticker ||
          stockTx.isin ||
          stockTx.shares ||
          Number(stockTx.price || 0) !== 0 ||
          (stockTx.fees && stockTx.fees > 0) ||
          (stockTx.retentions && stockTx.retentions > 0) ||
          stockTx.market
        )
      }
      case ProductType.FUND: {
        const fundTx = tx as FundTx
        return !!(
          fundTx.isin ||
          fundTx.shares ||
          fundTx.price ||
          fundTx.fees > 0 ||
          fundTx.market
        )
      }
      case ProductType.FUND_PORTFOLIO: {
        const fpTx = tx as FundPortfolioTx
        return !!(
          (typeof fpTx.fees === "number" && fpTx.fees > 0) ||
          fpTx.iban ||
          (fpTx as any).portfolio_name
        )
      }
      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return !!(
          tx.type === TxType.INTEREST ||
          accountTx.fees > 0 ||
          accountTx.retentions > 0 ||
          (accountTx.interest_rate && accountTx.interest_rate > 0) ||
          (accountTx.avg_balance && accountTx.avg_balance > 0)
        )
      }
      case ProductType.FACTORING: {
        const factoringTx = tx as FactoringTx
        return !!(factoringTx.fees > 0 || factoringTx.retentions > 0)
      }
      case ProductType.REAL_ESTATE_CF: {
        const realEstateTx = tx as RealEstateCFTx
        return !!(realEstateTx.fees > 0 || realEstateTx.retentions > 0)
      }
      case ProductType.DEPOSIT: {
        const depositTx = tx as DepositTx
        return !!(depositTx.fees > 0 || depositTx.retentions > 0)
      }
      case ProductType.CRYPTO: {
        const cryptoTx = tx as CryptoCurrencyTx
        return !!(
          cryptoTx.symbol ||
          cryptoTx.currency_amount ||
          cryptoTx.price ||
          cryptoTx.fees > 0
        )
      }
      default:
        return false
    }
  }

  interface GroupedDay {
    dateKey: string
    dayLabel: string
    transactions: TransactionItem[]
  }

  interface GroupedMonth {
    monthKey: string
    monthLabel: string
    days: GroupedDay[]
  }

  const groupedTransactions = useMemo((): GroupedMonth[] => {
    if (!transactions?.transactions.length) return []

    const monthsMap = new Map<string, Map<string, TransactionItem[]>>()

    transactions.transactions.forEach(tx => {
      const date = new Date(tx.date)
      const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`
      const dayKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`

      if (!monthsMap.has(monthKey)) {
        monthsMap.set(monthKey, new Map())
      }
      const daysMap = monthsMap.get(monthKey)!
      if (!daysMap.has(dayKey)) {
        daysMap.set(dayKey, [])
      }
      daysMap.get(dayKey)!.push(tx)
    })

    const result: GroupedMonth[] = []

    const sortedMonths = Array.from(monthsMap.keys()).sort((a, b) =>
      b.localeCompare(a),
    )

    sortedMonths.forEach(monthKey => {
      const daysMap = monthsMap.get(monthKey)!
      const [year, month] = monthKey.split("-").map(Number)

      const monthLabel = new Intl.DateTimeFormat(locale, {
        month: "long",
        year: "numeric",
      }).format(new Date(year, month - 1, 1))

      const sortedDays = Array.from(daysMap.keys()).sort((a, b) =>
        b.localeCompare(a),
      )

      const days: GroupedDay[] = sortedDays.map(dayKey => {
        const [, , day] = dayKey.split("-").map(Number)
        const dayDate = new Date(year, month - 1, day)

        const dayLabel = new Intl.DateTimeFormat(locale, {
          weekday: "short",
          day: "numeric",
        }).format(dayDate)

        return {
          dateKey: dayKey,
          dayLabel,
          transactions: daysMap.get(dayKey)!,
        }
      })

      result.push({
        monthKey,
        monthLabel,
        days,
      })
    })

    return result
  }, [transactions, locale])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 shrink-0">
          {t.transactions.title}
        </h1>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="flex items-center rounded-md border border-gray-200 dark:border-gray-700 p-0.5 sm:p-1">
            <button
              onClick={() => handleViewModeChange("list")}
              className={`flex items-center gap-1 px-2.5 py-2 rounded text-xs sm:text-sm font-medium transition-colors ${
                viewMode === "list"
                  ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              <List className="h-4 w-4" />
              <span className="hidden sm:inline">
                {t.transactions.calendar.listView}
              </span>
            </button>
            <button
              onClick={() => handleViewModeChange("calendar")}
              className={`flex items-center gap-1 px-2.5 py-2 rounded text-xs sm:text-sm font-medium transition-colors ${
                viewMode === "calendar"
                  ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              <CalendarDays className="h-4 w-4" />
              <span className="hidden sm:inline">
                {t.transactions.calendar.calendarView}
              </span>
            </button>
          </div>
          <Button
            onClick={handleOpenCreateDialog}
            size="sm"
            className="flex items-center gap-1.5 px-3"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">
              {t.transactions.addManualTransaction}
            </span>
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:flex-1 sm:min-w-[180px] sm:max-w-[240px]">
            <Label
              htmlFor="entities"
              className="text-xs font-medium mb-1 block text-gray-500 dark:text-gray-400 flex items-center gap-1"
            >
              <Landmark className="h-3 w-3" />
              <span>{t.transactions.entities}</span>
            </Label>
            <MultiSelect
              options={entityOptions}
              value={filters.entities}
              onChange={value => handleFilterChange("entities", value)}
              placeholder={t.transactions.selectEntities}
              className="w-full"
            />
          </div>

          <div className="w-full sm:flex-1 sm:min-w-[180px] sm:max-w-[240px]">
            <Label
              htmlFor="product-types"
              className="text-xs font-medium mb-1 block text-gray-500 dark:text-gray-400 flex items-center gap-1"
            >
              <Layers className="h-3 w-3" />
              <span>{t.transactions.productTypes}</span>
            </Label>
            <MultiSelect
              options={productTypeOptions}
              value={filters.product_types}
              onChange={value => handleFilterChange("product_types", value)}
              placeholder={t.transactions.selectProductTypes}
              className="w-full"
            />
          </div>

          <div className="w-full sm:flex-1 sm:min-w-[180px] sm:max-w-[240px]">
            <Label
              htmlFor="transaction-types"
              className="text-xs font-medium mb-1 block text-gray-500 dark:text-gray-400 flex items-center gap-1"
            >
              <ArrowLeftRight className="h-3 w-3" />
              <span>{t.transactions.transactionTypes}</span>
            </Label>
            <MultiSelect
              options={transactionTypeOptions}
              value={filters.types}
              onChange={value => handleFilterChange("types", value)}
              placeholder={t.transactions.selectTransactionTypes}
              className="w-full"
            />
          </div>

          {viewMode === "list" && (
            <>
              <div className="w-full sm:flex-1 sm:min-w-[200px] sm:max-w-[240px]">
                <Label
                  htmlFor="from-date"
                  className="text-xs font-medium mb-1 block text-gray-500 dark:text-gray-400 flex items-center gap-1"
                >
                  <Calendar className="h-3 w-3" />
                  {t.transactions.fromDate}
                </Label>
                <DatePicker
                  id="from-date"
                  value={filters.from_date}
                  onChange={value => handleFilterChange("from_date", value)}
                  placeholder={t.transactions.fromDate}
                />
              </div>

              <div className="w-full sm:flex-1 sm:min-w-[200px] sm:max-w-[240px]">
                <Label
                  htmlFor="to-date"
                  className="text-xs font-medium mb-1 block text-gray-500 dark:text-gray-400 flex items-center gap-1"
                >
                  <Calendar className="h-3 w-3" />
                  {t.transactions.toDate}
                </Label>
                <DatePicker
                  id="to-date"
                  value={filters.to_date}
                  onChange={value => handleFilterChange("to_date", value)}
                  placeholder={t.transactions.toDate}
                />
              </div>
            </>
          )}

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Button
              onClick={handleApplyFilters}
              disabled={loadingTxs}
              size="icon"
              title={t.transactions.search}
            >
              <Search className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              onClick={handleClearFilters}
              disabled={loadingTxs}
              size="icon"
              title={t.transactions.clear}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {filters.historic_entry_id && (
        <div className="flex flex-col gap-3 rounded-md border border-blue-200 bg-blue-50 p-4 text-blue-700 dark:border-blue-500/40 dark:bg-blue-900/20 dark:text-blue-200 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-semibold">
              {t.transactions.historicFilter.title}
            </p>
            <p className="text-xs">
              {historicEntryName
                ? t.transactions.historicFilter.description.replace(
                    "{project}",
                    historicEntryName,
                  )
                : t.transactions.historicFilter.descriptionGeneric}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="self-start sm:self-auto"
            onClick={clearHistoricFilter}
          >
            {t.transactions.historicFilter.clear}
          </Button>
        </div>
      )}

      {viewMode === "calendar" && (
        <TransactionsCalendarView
          transactions={calendarTransactions}
          loading={loadingTxs}
          currentMonth={calendarMonth}
          currentYear={calendarYear}
          onMonthChange={handleCalendarMonthChange}
          onBadgeClick={handleBadgeClick}
        />
      )}

      {viewMode === "list" && transactions && (
        <>
          {/* Desktop Results Card */}
          <Card className="hidden md:block overflow-hidden">
            {loadingTxs && (
              <div className="flex justify-end px-6 pt-4">
                <LoadingSpinner size="sm" />
              </div>
            )}

            {transactions.transactions.length === 0 ? (
              <div className="flex flex-col items-center gap-4 py-12 px-6 text-center">
                <div className="text-gray-400 dark:text-gray-600">
                  <Search className="mx-auto h-12 w-12" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {t.transactions.noTransactionsFound}
                </h3>
              </div>
            ) : (
              <>
                {/* Desktop Grouped List */}
                <div className="px-6 pt-6 pb-4 space-y-6">
                  {groupedTransactions.map(monthGroup => (
                    <div key={monthGroup.monthKey}>
                      <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 capitalize">
                        {monthGroup.monthLabel}
                      </h3>
                      <div className="space-y-1">
                        {monthGroup.days.map(dayGroup => (
                          <div key={dayGroup.dateKey}>
                            <div className="flex items-center gap-3 py-2">
                              <span className="text-xs font-medium text-gray-400 dark:text-gray-500 w-16 capitalize">
                                {dayGroup.dayLabel}
                              </span>
                              <div className="flex-1 h-px bg-gray-100 dark:bg-gray-800" />
                            </div>
                            <div className="space-y-1 ml-0">
                              {dayGroup.transactions.map(tx => {
                                const isExpanded = expandedCards.has(tx.id)
                                const hasDetails = hasTransactionDetails(tx)
                                return (
                                  <div
                                    key={tx.id}
                                    className="group rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors"
                                  >
                                    <div className="flex items-center gap-3 py-3 px-3">
                                      <div className="flex-1 min-w-0">
                                        <div className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">
                                          {tx.name}
                                        </div>
                                        <div className="flex items-center gap-2 mt-1">
                                          <Badge
                                            className={`${getTransactionTypeColor(tx.type)} text-xs inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                            onClick={() =>
                                              handleBadgeClick(
                                                "transactionType",
                                                tx.type,
                                              )
                                            }
                                          >
                                            {getIconForTxType(
                                              tx.type,
                                              "h-3 w-3",
                                            )}
                                            {t.enums?.transactionType?.[
                                              tx.type
                                            ] || tx.type}
                                          </Badge>
                                          <Badge
                                            className={`${getProductTypeColor(tx.product_type)} text-xs inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                            onClick={() =>
                                              handleBadgeClick(
                                                "productType",
                                                tx.product_type,
                                              )
                                            }
                                          >
                                            {getIconForProductType(
                                              tx.product_type,
                                            )}
                                            {t.enums?.productType?.[
                                              tx.product_type
                                            ] || tx.product_type}
                                          </Badge>
                                          <EntityBadge
                                            name={tx.entity.name}
                                            origin={tx.entity.origin}
                                            onClick={() =>
                                              handleBadgeClick(
                                                "entity",
                                                tx.entity.id,
                                              )
                                            }
                                            className="text-xs"
                                          />
                                        </div>
                                      </div>
                                      <div className="text-right shrink-0">
                                        <div
                                          className={`font-semibold ${
                                            getTransactionDisplayType(
                                              tx.type,
                                            ) === "in"
                                              ? "text-green-600 dark:text-green-400"
                                              : tx.type === TxType.FEE
                                                ? "text-red-600 dark:text-red-400"
                                                : "text-gray-900 dark:text-gray-100"
                                          }`}
                                        >
                                          {getTransactionDisplayType(
                                            tx.type,
                                          ) === "in"
                                            ? "+"
                                            : tx.type === TxType.FEE
                                              ? "-"
                                              : ""}
                                          {formatCurrency(
                                            tx.net_amount ?? tx.amount,
                                            locale,
                                            settings.general.defaultCurrency,
                                            tx.currency,
                                          )}
                                        </div>
                                      </div>
                                      {hasDetails && (
                                        <button
                                          onClick={() =>
                                            toggleCardExpansion(tx.id)
                                          }
                                          className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                                        >
                                          {isExpanded ? (
                                            <ChevronUp className="h-4 w-4" />
                                          ) : (
                                            <ChevronDown className="h-4 w-4" />
                                          )}
                                        </button>
                                      )}
                                    </div>
                                    {hasDetails && isExpanded && (
                                      <div className="px-3 pb-3 ml-0">
                                        <div className="pl-4 space-y-2 border-l-2 border-gray-200 dark:border-gray-700">
                                          {renderTransactionDetails(tx)}
                                          {tx.source === DataSource.MANUAL && (
                                            <div className="flex flex-wrap gap-2 pt-3">
                                              <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() =>
                                                  handleEditTransaction(tx)
                                                }
                                                className="flex items-center gap-2"
                                              >
                                                <Pencil className="h-4 w-4" />
                                                {t.common.edit}
                                              </Button>
                                              <Button
                                                variant="destructive"
                                                size="sm"
                                                onClick={() =>
                                                  handleRequestDelete(tx)
                                                }
                                                className="flex items-center gap-2"
                                              >
                                                <Trash2 className="h-4 w-4" />
                                                {t.common.delete}
                                              </Button>
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Desktop Pagination */}
                <div className="flex justify-center items-center gap-3 px-6 pb-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1 || loadingTxs}
                    className="px-3 py-2"
                  >
                    ←
                  </Button>

                  <span className="text-sm text-gray-600 dark:text-gray-400 px-3">
                    {t.transactions.page} {currentPage}
                  </span>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={
                      transactions?.transactions.length < ITEMS_PER_PAGE ||
                      loadingTxs
                    }
                    className="px-3 py-2"
                  >
                    →
                  </Button>
                </div>
              </>
            )}
          </Card>

          {loadingTxs && (
            <div className="md:hidden flex justify-end mb-4">
              <LoadingSpinner size="sm" />
            </div>
          )}

          {/* Mobile No Results */}
          {transactions.transactions.length === 0 && (
            <Card className="flex flex-col items-center gap-4 p-10 text-center md:hidden">
              <div className="text-gray-400 dark:text-gray-600">
                <Search className="mx-auto h-12 w-12" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t.transactions.noTransactionsFound}
              </h3>
            </Card>
          )}

          {/* Mobile Grouped List */}
          {transactions.transactions.length > 0 && (
            <div className="md:hidden space-y-6">
              {groupedTransactions.map(monthGroup => (
                <div key={monthGroup.monthKey}>
                  <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3 capitalize">
                    {monthGroup.monthLabel}
                  </h3>
                  <div className="space-y-1">
                    {monthGroup.days.map(dayGroup => (
                      <div key={dayGroup.dateKey}>
                        <div className="flex items-center gap-3 py-2">
                          <span className="text-xs font-medium text-gray-400 dark:text-gray-500 w-16 capitalize">
                            {dayGroup.dayLabel}
                          </span>
                          <div className="flex-1 h-px bg-gray-100 dark:bg-gray-800" />
                        </div>
                        <div className="space-y-1 ml-0">
                          {dayGroup.transactions.map(tx => {
                            const isExpanded = expandedCards.has(tx.id)
                            const hasDetails = hasTransactionDetails(tx)
                            return (
                              <div
                                key={tx.id}
                                className="group rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors"
                              >
                                <div className="flex items-center gap-3 py-3 pl-3 pr-1.5">
                                  <div className="flex-1 min-w-0">
                                    <div className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">
                                      {tx.name}
                                    </div>
                                    <div className="flex items-center gap-2 mt-1">
                                      <Badge
                                        className={`${getTransactionTypeColor(tx.type)} text-xs inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                        onClick={() =>
                                          handleBadgeClick(
                                            "transactionType",
                                            tx.type,
                                          )
                                        }
                                      >
                                        {getIconForTxType(tx.type, "h-3 w-3")}
                                        {t.enums?.transactionType?.[tx.type] ||
                                          tx.type}
                                      </Badge>
                                      <Badge
                                        className={`${getProductTypeColor(tx.product_type)} text-xs inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                        onClick={() =>
                                          handleBadgeClick(
                                            "productType",
                                            tx.product_type,
                                          )
                                        }
                                      >
                                        {getIconForProductType(tx.product_type)}
                                        {t.enums?.productType?.[
                                          tx.product_type
                                        ] || tx.product_type}
                                      </Badge>
                                      <EntityBadge
                                        name={tx.entity.name}
                                        origin={tx.entity.origin}
                                        onClick={() =>
                                          handleBadgeClick(
                                            "entity",
                                            tx.entity.id,
                                          )
                                        }
                                        className="text-xs"
                                      />
                                    </div>
                                  </div>
                                  <div className="text-right shrink-0">
                                    <div
                                      className={`font-semibold ${
                                        getTransactionDisplayType(tx.type) ===
                                        "in"
                                          ? "text-green-600 dark:text-green-400"
                                          : tx.type === TxType.FEE
                                            ? "text-red-600 dark:text-red-400"
                                            : "text-gray-900 dark:text-gray-100"
                                      }`}
                                    >
                                      {getTransactionDisplayType(tx.type) ===
                                      "in"
                                        ? "+"
                                        : tx.type === TxType.FEE
                                          ? "-"
                                          : ""}
                                      {formatCurrency(
                                        tx.net_amount ?? tx.amount,
                                        locale,
                                        settings.general.defaultCurrency,
                                        tx.currency,
                                      )}
                                    </div>
                                  </div>
                                  {hasDetails && (
                                    <button
                                      onClick={() => toggleCardExpansion(tx.id)}
                                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                                    >
                                      {isExpanded ? (
                                        <ChevronUp className="h-4 w-4" />
                                      ) : (
                                        <ChevronDown className="h-4 w-4" />
                                      )}
                                    </button>
                                  )}
                                </div>
                                {hasDetails && isExpanded && (
                                  <div className="px-3 pb-3 ml-0">
                                    <div className="pl-4 space-y-2 border-l-2 border-gray-200 dark:border-gray-700">
                                      {renderTransactionDetails(tx)}
                                      {tx.source === DataSource.MANUAL && (
                                        <div className="flex flex-wrap gap-2 pt-3">
                                          <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() =>
                                              handleEditTransaction(tx)
                                            }
                                            className="flex items-center gap-2"
                                          >
                                            <Pencil className="h-4 w-4" />
                                            {t.common.edit}
                                          </Button>
                                          <Button
                                            variant="destructive"
                                            size="sm"
                                            onClick={() =>
                                              handleRequestDelete(tx)
                                            }
                                            className="flex items-center gap-2"
                                          >
                                            <Trash2 className="h-4 w-4" />
                                            {t.common.delete}
                                          </Button>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Mobile Pagination */}
              <div className="flex justify-center items-center mt-6 gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1 || loadingTxs}
                  className="px-3 py-2"
                >
                  ←
                </Button>

                <span className="text-sm text-gray-600 dark:text-gray-400 px-3">
                  {t.transactions.page} {currentPage}
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={
                    transactions?.transactions.length < ITEMS_PER_PAGE ||
                    loadingTxs
                  }
                  className="px-3 py-2"
                >
                  →
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <ManualTransactionDialog
        isOpen={isDialogOpen}
        mode={dialogMode}
        transaction={selectedTransaction}
        entities={manualEntityOptions}
        currencyOptions={currencyOptions}
        defaultCurrency={defaultCurrency}
        onClose={handleDialogClose}
        onSubmit={handleSubmitTransaction}
        isSubmitting={isSubmittingTransaction}
      />

      <ConfirmationDialog
        isOpen={isDeleteDialogOpen}
        title={t.transactions.deleteManualTransactionTitle}
        message={t.transactions.deleteManualTransactionMessage}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        isLoading={isDeletingTransaction}
        warning={t.transactions.deleteManualTransactionWarning}
      />
    </div>
  )
}
