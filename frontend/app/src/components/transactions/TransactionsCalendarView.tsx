import React, { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import {
  TransactionsResult,
  TxType,
  type AccountTx,
  type StockTx,
  type FundTx,
  type FundPortfolioTx,
  type FactoringTx,
  type RealEstateCFTx,
  type DepositTx,
  type CryptoCurrencyTx,
} from "@/types/transactions"
import { ProductType } from "@/types/position"
import { formatCurrency } from "@/lib/formatters"
import { getTransactionDisplayType } from "@/utils/financialDataUtils"
import {
  getIconForTxType,
  getProductTypeColor,
  getIconForAssetType,
} from "@/utils/dashboardUtils"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { EntityBadge } from "@/components/ui/EntityBadge"
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  X,
  Calendar as CalendarIcon,
} from "lucide-react"

type TransactionItem = TransactionsResult["transactions"][number]

const formatDateKey = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

interface TransactionsCalendarViewProps {
  transactions: TransactionItem[]
  loading: boolean
  currentMonth: number
  currentYear: number
  onMonthChange: (month: number, year: number) => void
  onBadgeClick: (
    type: "entity" | "productType" | "transactionType",
    value: string,
  ) => void
}

interface DayTransactions {
  date: Date
  transactions: TransactionItem[]
  isCurrentMonth: boolean
  isToday: boolean
}

export function TransactionsCalendarView({
  transactions,
  loading,
  currentMonth,
  currentYear,
  onMonthChange,
  onBadgeClick,
}: TransactionsCalendarViewProps) {
  const { t, locale } = useI18n()
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(null)
  const [showYearPicker, setShowYearPicker] = useState(false)

  const transactionsByDate = useMemo(() => {
    const map = new Map<string, TransactionItem[]>()
    transactions.forEach(tx => {
      const dateKey = tx.date.split("T")[0]
      if (!map.has(dateKey)) {
        map.set(dateKey, [])
      }
      map.get(dateKey)!.push(tx)
    })
    return map
  }, [transactions])

  const calendarDays = useMemo((): DayTransactions[] => {
    const days: DayTransactions[] = []
    const firstDayOfMonth = new Date(currentYear, currentMonth, 1)
    const lastDayOfMonth = new Date(currentYear, currentMonth + 1, 0)
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    let startDay = firstDayOfMonth.getDay()
    startDay = startDay === 0 ? 6 : startDay - 1

    const prevMonthLastDay = new Date(currentYear, currentMonth, 0)
    for (let i = startDay - 1; i >= 0; i--) {
      const date = new Date(
        currentYear,
        currentMonth - 1,
        prevMonthLastDay.getDate() - i,
      )
      const dateKey = formatDateKey(date)
      days.push({
        date,
        transactions: transactionsByDate.get(dateKey) || [],
        isCurrentMonth: false,
        isToday: date.getTime() === today.getTime(),
      })
    }

    for (let day = 1; day <= lastDayOfMonth.getDate(); day++) {
      const date = new Date(currentYear, currentMonth, day)
      const dateKey = formatDateKey(date)
      days.push({
        date,
        transactions: transactionsByDate.get(dateKey) || [],
        isCurrentMonth: true,
        isToday: date.getTime() === today.getTime(),
      })
    }

    const remainingDays = 42 - days.length
    for (let day = 1; day <= remainingDays; day++) {
      const date = new Date(currentYear, currentMonth + 1, day)
      const dateKey = formatDateKey(date)
      days.push({
        date,
        transactions: transactionsByDate.get(dateKey) || [],
        isCurrentMonth: false,
        isToday: date.getTime() === today.getTime(),
      })
    }

    return days
  }, [currentYear, currentMonth, transactionsByDate])

  const daysWithTransactions = useMemo(() => {
    const indices: number[] = []
    calendarDays.forEach((day, index) => {
      if (day.transactions.length > 0) {
        indices.push(index)
      }
    })
    return indices
  }, [calendarDays])

  const handlePrevMonth = () => {
    if (currentMonth === 0) {
      onMonthChange(11, currentYear - 1)
    } else {
      onMonthChange(currentMonth - 1, currentYear)
    }
  }

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      onMonthChange(0, currentYear + 1)
    } else {
      onMonthChange(currentMonth + 1, currentYear)
    }
  }

  const handleToday = () => {
    const today = new Date()
    onMonthChange(today.getMonth(), today.getFullYear())
  }

  const handleYearSelect = (year: number) => {
    onMonthChange(currentMonth, year)
    setShowYearPicker(false)
  }

  const handleDayNavigation = (direction: "prev" | "next") => {
    if (selectedDayIndex === null) return

    const currentPos = daysWithTransactions.indexOf(selectedDayIndex)
    if (direction === "prev" && currentPos > 0) {
      setSelectedDayIndex(daysWithTransactions[currentPos - 1])
    } else if (
      direction === "next" &&
      currentPos < daysWithTransactions.length - 1
    ) {
      setSelectedDayIndex(daysWithTransactions[currentPos + 1])
    }
  }

  const canNavigatePrev =
    selectedDayIndex !== null &&
    daysWithTransactions.indexOf(selectedDayIndex) > 0
  const canNavigateNext =
    selectedDayIndex !== null &&
    daysWithTransactions.indexOf(selectedDayIndex) <
      daysWithTransactions.length - 1

  const getTransactionColor = (type: TxType): string => {
    const displayType = getTransactionDisplayType(type)
    if (displayType === "in") {
      return "bg-green-500 dark:bg-green-400"
    }
    if (type === TxType.FEE) {
      return "bg-red-500 dark:bg-red-400"
    }
    return "bg-blue-500 dark:bg-blue-400"
  }

  const monthName = new Date(currentYear, currentMonth).toLocaleDateString(
    locale,
    { month: "long" },
  )

  const shortMonthName = new Date(currentYear, currentMonth).toLocaleDateString(
    locale,
    { month: "short" },
  )

  const yearOptions = useMemo(() => {
    const years: number[] = []
    const currentYearNow = new Date().getFullYear()
    for (let y = currentYearNow - 10; y <= currentYearNow; y++) {
      years.push(y)
    }
    return years
  }, [])

  const weekdayLabels = useMemo(() => {
    const labels: { short: string; letter: string }[] = []
    const baseDate = new Date(2024, 0, 1)
    while (baseDate.getDay() !== 1) {
      baseDate.setDate(baseDate.getDate() + 1)
    }
    for (let i = 0; i < 7; i++) {
      const short = baseDate.toLocaleDateString(locale, { weekday: "short" })
      const narrow = baseDate.toLocaleDateString(locale, { weekday: "narrow" })
      labels.push({ short, letter: narrow })
      baseDate.setDate(baseDate.getDate() + 1)
    }
    return labels
  }, [locale])

  const selectedDay =
    selectedDayIndex !== null ? calendarDays[selectedDayIndex] : null

  const today = new Date()
  const isCurrentOrFutureMonth =
    currentYear > today.getFullYear() ||
    (currentYear === today.getFullYear() && currentMonth >= today.getMonth())

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between p-2 sm:p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <h2 className="text-base sm:text-xl font-semibold text-gray-900 dark:text-gray-100 capitalize">
              <span className="hidden sm:inline">{monthName}</span>
              <span className="sm:hidden">{shortMonthName}</span> {currentYear}
            </h2>
            {loading && <LoadingSpinner size="sm" />}
          </div>

          <div className="flex items-center gap-1 sm:gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrevMonth}
              className="p-1.5 sm:p-2"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleToday}
              className="px-2 sm:px-3 text-xs sm:text-sm"
            >
              {t.transactions.calendar.today}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleNextMonth}
              className="p-1.5 sm:p-2"
              disabled={isCurrentOrFutureMonth}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>

            <div className="relative ml-1 sm:ml-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowYearPicker(!showYearPicker)}
                className="min-w-[60px] sm:min-w-[80px] text-xs sm:text-sm"
              >
                {currentYear}
              </Button>
              {showYearPicker && (
                <div className="absolute right-0 top-full mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-60 overflow-y-auto">
                  {yearOptions.map(year => (
                    <button
                      key={year}
                      onClick={() => handleYearSelect(year)}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                        year === currentYear
                          ? "bg-gray-100 dark:bg-gray-700 font-medium"
                          : ""
                      }`}
                    >
                      {year}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-7">
          {weekdayLabels.map((day, index) => (
            <div
              key={index}
              className="py-2 sm:py-3 text-center text-xs sm:text-sm font-medium text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700"
            >
              <span className="hidden sm:inline">{day.short}</span>
              <span className="sm:hidden">{day.letter}</span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {calendarDays.map((day, index) => {
            const hasTransactions = day.transactions.length > 0
            const previewTxs = day.transactions.slice(0, 3)
            const moreCount = day.transactions.length - 3

            return (
              <div
                key={index}
                onClick={() => hasTransactions && setSelectedDayIndex(index)}
                className={`min-h-[60px] sm:min-h-[100px] md:min-h-[120px] p-0.5 sm:p-1 md:p-2 border-b border-r border-gray-200 dark:border-gray-700 transition-colors ${
                  day.isCurrentMonth
                    ? "bg-white dark:bg-gray-900"
                    : "bg-gray-50 dark:bg-gray-950"
                } ${hasTransactions ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800" : ""}`}
              >
                <div className="flex items-start justify-between mb-0.5 sm:mb-1">
                  <span
                    className={`text-xs sm:text-sm font-medium ${
                      day.isToday
                        ? "w-5 h-5 sm:w-7 sm:h-7 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] sm:text-sm"
                        : day.isCurrentMonth
                          ? "text-gray-900 dark:text-gray-100"
                          : "text-gray-400 dark:text-gray-600"
                    }`}
                  >
                    {day.date.getDate()}
                  </span>
                </div>

                <div className="space-y-0.5 hidden sm:block">
                  {previewTxs.map(tx => (
                    <div
                      key={tx.id}
                      className={`text-xs truncate rounded px-1 py-0.5 flex items-center gap-1 ${getTransactionColor(tx.type)} text-white ${!day.isCurrentMonth ? "opacity-50" : ""}`}
                      title={tx.name}
                    >
                      {getIconForAssetType(
                        tx.product_type,
                        "h-3 w-3",
                        "text-white",
                      )}
                      <span className="truncate">{tx.name}</span>
                    </div>
                  ))}
                  {moreCount > 0 && (
                    <div
                      className={`text-xs text-gray-500 dark:text-gray-400 pl-1 ${!day.isCurrentMonth ? "opacity-50" : ""}`}
                    >
                      +{moreCount} {t.transactions.calendar.more}
                    </div>
                  )}
                </div>

                {hasTransactions && (
                  <div className="sm:hidden flex flex-wrap gap-0.5 mt-0.5">
                    {day.transactions.slice(0, 4).map(tx => (
                      <div
                        key={tx.id}
                        className={`w-2 h-2 rounded-sm ${getTransactionColor(tx.type)} ${!day.isCurrentMonth ? "opacity-50" : ""}`}
                        title={tx.name}
                      />
                    ))}
                    {day.transactions.length > 4 && (
                      <span
                        className={`text-[8px] text-gray-500 dark:text-gray-400 ${!day.isCurrentMonth ? "opacity-50" : ""}`}
                      >
                        +{day.transactions.length - 4}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      <AnimatePresence>
        {selectedDay && (
          <DayDetailModal
            day={selectedDay}
            onClose={() => setSelectedDayIndex(null)}
            onBadgeClick={onBadgeClick}
            onPrevDay={() => handleDayNavigation("prev")}
            onNextDay={() => handleDayNavigation("next")}
            canNavigatePrev={canNavigatePrev}
            canNavigateNext={canNavigateNext}
          />
        )}
      </AnimatePresence>

      {showYearPicker && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowYearPicker(false)}
        />
      )}
    </div>
  )
}

interface DayDetailModalProps {
  day: DayTransactions
  onClose: () => void
  onBadgeClick: (
    type: "entity" | "productType" | "transactionType",
    value: string,
  ) => void
  onPrevDay: () => void
  onNextDay: () => void
  canNavigatePrev: boolean
  canNavigateNext: boolean
}

function DayDetailModal({
  day,
  onClose,
  onBadgeClick,
  onPrevDay,
  onNextDay,
  canNavigatePrev,
  canNavigateNext,
}: DayDetailModalProps) {
  const { t, locale } = useI18n()
  const { settings } = useAppContext()
  const [expandedTxs, setExpandedTxs] = useState<Set<string>>(new Set())

  const formattedDate = day.date.toLocaleDateString(locale, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })

  const shortFormattedDate = day.date.toLocaleDateString(locale, {
    weekday: "short",
    month: "short",
    day: "numeric",
  })

  const toggleExpanded = (txId: string) => {
    setExpandedTxs(prev => {
      const next = new Set(prev)
      if (next.has(txId)) {
        next.delete(txId)
      } else {
        next.add(txId)
      }
      return next
    })
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

  const hasExtraDetails = (tx: TransactionItem): boolean => {
    switch (tx.product_type) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return !!(
          stockTx.ticker ||
          stockTx.isin ||
          stockTx.shares ||
          stockTx.price ||
          stockTx.fees ||
          stockTx.retentions ||
          stockTx.market
        )
      }
      case ProductType.FUND: {
        const fundTx = tx as FundTx
        return !!(
          fundTx.isin ||
          fundTx.shares ||
          fundTx.price ||
          fundTx.fees ||
          fundTx.retentions ||
          fundTx.market
        )
      }
      case ProductType.FUND_PORTFOLIO: {
        const fpTx = tx as unknown as FundPortfolioTx
        return !!(fpTx.fees || fpTx.iban || (fpTx as any).portfolio_name)
      }
      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return !!(
          tx.type === TxType.INTEREST ||
          accountTx.fees ||
          accountTx.retentions ||
          (accountTx.interest_rate && accountTx.interest_rate > 0) ||
          (accountTx.avg_balance && accountTx.avg_balance > 0)
        )
      }
      case ProductType.FACTORING:
      case ProductType.REAL_ESTATE_CF:
      case ProductType.DEPOSIT: {
        const simpleTx = tx as FactoringTx | RealEstateCFTx | DepositTx
        return !!(simpleTx.fees || simpleTx.retentions)
      }
      case ProductType.CRYPTO: {
        const cryptoTx = tx as CryptoCurrencyTx
        return !!(
          cryptoTx.symbol ||
          cryptoTx.currency_amount ||
          Number(cryptoTx.price || 0) !== 0 ||
          (cryptoTx.fees != null && cryptoTx.fees > 0) ||
          (cryptoTx.retentions != null && cryptoTx.retentions > 0)
        )
      }
      default:
        return false
    }
  }

  const renderTransactionDetails = (tx: TransactionItem) => {
    const detailRowClass = "text-sm text-gray-600 dark:text-gray-400"
    const detailLabelClass = "font-medium text-gray-500 dark:text-gray-300"

    switch (tx.product_type) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return (
          <div className="space-y-1 pt-2">
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
            {stockTx.shares !== undefined && stockTx.shares !== null && (
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
            {stockTx.fees !== undefined && stockTx.fees > 0 && (
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
            {stockTx.retentions !== undefined && stockTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  stockTx.retentions,
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
          </div>
        )
      }

      case ProductType.FUND: {
        const fundTx = tx as FundTx
        return (
          <div className="space-y-1 pt-2">
            {fundTx.isin && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.isin}:</span>{" "}
                {fundTx.isin}
              </div>
            )}
            {fundTx.shares !== undefined && fundTx.shares !== null && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.shares}:
                </span>{" "}
                {fundTx.shares.toLocaleString()}
              </div>
            )}
            {Number(fundTx.price || 0) !== 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.price}:
                </span>{" "}
                {formatCurrency(
                  fundTx.price,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {fundTx.fees !== undefined && fundTx.fees > 0 && (
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
            {fundTx.retentions !== undefined && fundTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  fundTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {fundTx.market && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.market}:
                </span>{" "}
                {fundTx.market}
              </div>
            )}
          </div>
        )
      }

      case ProductType.FUND_PORTFOLIO: {
        const fpTx = tx as unknown as FundPortfolioTx & {
          portfolio_name?: string
        }
        return (
          <div className="space-y-1 pt-2">
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
          </div>
        )
      }

      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return (
          <div className="space-y-1 pt-2">
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
            {accountTx.fees !== undefined && accountTx.fees > 0 && (
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
            {accountTx.retentions !== undefined && accountTx.retentions > 0 && (
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
            {accountTx.interest_rate !== undefined &&
              accountTx.interest_rate > 0 && (
                <div className={detailRowClass}>
                  <span className={detailLabelClass}>
                    {t.transactions.interestRate}:
                  </span>{" "}
                  {(accountTx.interest_rate * 100).toFixed(2)}%
                </div>
              )}
            {accountTx.avg_balance !== undefined &&
              accountTx.avg_balance > 0 && (
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
          </div>
        )
      }

      case ProductType.FACTORING:
      case ProductType.REAL_ESTATE_CF:
      case ProductType.DEPOSIT: {
        const simpleTx = tx as FactoringTx | RealEstateCFTx | DepositTx
        return (
          <div className="space-y-1 pt-2">
            {simpleTx.fees !== undefined && simpleTx.fees > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  simpleTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {simpleTx.retentions !== undefined && simpleTx.retentions > 0 && (
              <div className={detailRowClass}>
                <span className={detailLabelClass}>
                  {t.transactions.retentions}:
                </span>{" "}
                {formatCurrency(
                  simpleTx.retentions,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </div>
        )
      }

      case ProductType.CRYPTO: {
        const cryptoTx = tx as CryptoCurrencyTx
        return (
          <div className="space-y-1 pt-2">
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
            {cryptoTx.fees != null && cryptoTx.fees > 0 && (
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
          </div>
        )
      }

      default:
        return null
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={e => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="w-full max-w-2xl"
      >
        <Card className="max-h-[80vh] overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-3 sm:p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-1 sm:gap-2 min-w-0 flex-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={onPrevDay}
                disabled={!canNavigatePrev}
                className="shrink-0 h-8 w-8"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-1.5 sm:gap-2 min-w-0 flex-1">
                <CalendarIcon className="h-4 w-4 text-gray-500 shrink-0" />
                <h3 className="text-sm sm:text-lg font-semibold text-gray-900 dark:text-gray-100 capitalize truncate">
                  <span className="hidden sm:inline">{formattedDate}</span>
                  <span className="sm:hidden">{shortFormattedDate}</span>
                </h3>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onNextDay}
                disabled={!canNavigateNext}
                className="shrink-0 h-8 w-8"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-sm text-gray-500 dark:text-gray-400 hidden sm:inline">
                {day.transactions.length} {t.transactions.items}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="p-3 sm:p-4 overflow-y-auto space-y-2 sm:space-y-3">
            {day.transactions.map(tx => {
              const isExpanded = expandedTxs.has(tx.id)
              const hasDetails = hasExtraDetails(tx)

              return (
                <div key={tx.id} className="p-3 rounded-lg bg-muted/50">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 pr-1.5">
                        <p className="font-medium text-sm sm:text-base text-gray-900 dark:text-gray-100 truncate">
                          {tx.name}
                        </p>
                        <span
                          className={`font-semibold text-sm sm:text-base shrink-0 ${
                            getTransactionDisplayType(tx.type) === "in"
                              ? "text-green-600 dark:text-green-400"
                              : tx.type === TxType.FEE
                                ? "text-red-600 dark:text-red-400"
                                : "text-gray-900 dark:text-gray-100"
                          }`}
                        >
                          {getTransactionDisplayType(tx.type) === "in"
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
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 sm:gap-2 mt-2">
                        <Badge
                          className={`${getTransactionTypeColor(tx.type)} text-xs cursor-pointer hover:opacity-80 transition-opacity inline-flex items-center gap-1`}
                          onClick={() =>
                            onBadgeClick("transactionType", tx.type)
                          }
                        >
                          {getIconForTxType(tx.type, "h-3 w-3")}
                          {t.enums?.transactionType?.[tx.type] || tx.type}
                        </Badge>
                        <Badge
                          className={`${getProductTypeColor(tx.product_type)} text-xs cursor-pointer hover:opacity-80 transition-opacity inline-flex items-center gap-1`}
                          onClick={() =>
                            onBadgeClick("productType", tx.product_type)
                          }
                        >
                          {getIconForAssetType(tx.product_type, "h-3 w-3", "")}
                          {t.enums?.productType?.[tx.product_type] ||
                            tx.product_type}
                        </Badge>
                        <EntityBadge
                          name={tx.entity.name}
                          origin={tx.entity.origin}
                          onClick={() => onBadgeClick("entity", tx.entity.id)}
                          className="text-xs"
                        />
                        {hasDetails && (
                          <button
                            onClick={() => toggleExpanded(tx.id)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                          >
                            {isExpanded ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {hasDetails && isExpanded && renderTransactionDetails(tx)}
                </div>
              )
            })}
          </div>

          <div className="p-3 sm:hidden border-t border-gray-200 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400 text-center">
            {day.transactions.length} {t.transactions.items}
          </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}
