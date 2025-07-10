import React, { useState, useEffect, useMemo } from "react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { getTransactions } from "@/services/api"
import {
  TransactionsResult,
  TransactionQueryRequest,
  TxType,
  type AccountTx,
  type StockTx,
  type FundTx,
  type FactoringTx,
  type realEstateCFTx,
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
import { formatCurrency, formatDate } from "@/lib/formatters"
import { getTransactionDisplayType } from "@/utils/financialDataUtils"
import {
  Search,
  RotateCcw,
  Calendar,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { getIconForTxType, getIconForProductType } from "@/utils/dashboardUtils"

interface TransactionFilters {
  entities: string[]
  excluded_entities: string[]
  product_types: ProductType[]
  types: TxType[]
  from_date: string
  to_date: string
}

const ITEMS_PER_PAGE = 20

export default function TransactionsPage() {
  const { t, locale } = useI18n()
  const { entities, inactiveEntities, settings } = useAppContext()

  const [transactions, setTransactions] = useState<TransactionsResult | null>(
    null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set())

  const [filters, setFilters] = useState<TransactionFilters>({
    entities: [],
    excluded_entities: inactiveEntities?.map(e => e.id) || [],
    product_types: [],
    types: [],
    from_date: "",
    to_date: "",
  })

  const entityOptions: MultiSelectOption[] = useMemo(() => {
    return (
      entities
        ?.filter(entity => entity.features.includes("TRANSACTIONS"))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities])

  const productTypeOptions: MultiSelectOption[] = useMemo(() => {
    const productTypes = Object.values(ProductType).filter(
      type =>
        type !== ProductType.CROWDLENDING && type !== ProductType.COMMODITY,
    )
    return productTypes.map(type => ({
      value: type,
      label: t.enums?.productType?.[type] || type,
    }))
  }, [t])

  const transactionTypeOptions: MultiSelectOption[] = useMemo(() => {
    const txTypes = Object.values(TxType)
    return txTypes.map(type => ({
      value: type,
      label: (t.enums as any)?.transactionType?.[type] || type,
    }))
  }, [t])

  const fetchTransactions = async (
    page: number = 1,
    resetPage: boolean = false,
  ) => {
    setLoading(true)
    setError(null)

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
      setTransactions(result)

      if (resetPage) {
        setCurrentPage(1)
      }
    } catch (err) {
      console.error("Error fetching transactions:", err)
      setError(t.errors.UNEXPECTED_ERROR)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions(1, true)
  }, [])

  const handleFilterChange = (key: keyof TransactionFilters, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }))
  }

  const handleApplyFilters = () => {
    fetchTransactions(1, true)
  }

  const handleClearFilters = () => {
    setFilters({
      entities: [],
      excluded_entities: inactiveEntities?.map(e => e.id) || [],
      product_types: [],
      types: [],
      from_date: "",
      to_date: "",
    })
    fetchTransactions(1, true)
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

  const getTransactionTypeColor = (type: TxType): string => {
    switch (type) {
      case TxType.BUY:
      case TxType.INVESTMENT:
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
      case TxType.SELL:
      case TxType.REPAYMENT:
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
      case TxType.DIVIDEND:
      case TxType.INTEREST:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
    }
  }

  const getProductTypeColor = (type: ProductType): string => {
    switch (type) {
      case ProductType.STOCK_ETF:
        return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100"
      case ProductType.FUND:
        return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
      case ProductType.CRYPTO:
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
      case ProductType.ACCOUNT:
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
      case ProductType.DEPOSIT:
        return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
    }
  }

  const getEntityColor = (entityName: string): string => {
    // Simple hash function to generate consistent colors for entity names
    let hash = 0
    for (let i = 0; i < entityName.length; i++) {
      const char = entityName.charCodeAt(i)
      hash = (hash << 5) - hash + char
      hash = hash & hash // Convert to 32-bit integer
    }

    // Use absolute value and modulo to get a consistent color
    const colorIndex = Math.abs(hash) % 8

    const colors = [
      "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100",
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
      "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
      "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100",
      "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-100",
      "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100",
      "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100",
    ]

    return colors[colorIndex]
  }

  const renderTransactionDetails = (tx: any) => {
    const commonFields = <></>

    switch (tx.product_type) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return (
          <>
            {commonFields}
            {stockTx.ticker && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.ticker}:</span>{" "}
                {stockTx.ticker}
              </div>
            )}
            {stockTx.isin && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.isin}:</span>{" "}
                {stockTx.isin}
              </div>
            )}
            {stockTx.shares && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.shares}:</span>{" "}
                {stockTx.shares.toLocaleString()}
              </div>
            )}
            {stockTx.price && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.price}:</span>{" "}
                {formatCurrency(
                  stockTx.price,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {stockTx.fees > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  stockTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {stockTx.market && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.market}:</span>{" "}
                {stockTx.market}
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
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">{t.transactions.isin}:</span>{" "}
              {fundTx.isin}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">{t.transactions.shares}:</span>{" "}
              {fundTx.shares.toLocaleString()}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">{t.transactions.price}:</span>{" "}
              {formatCurrency(
                fundTx.price,
                locale,
                settings.general.defaultCurrency,
                tx.currency,
              )}
            </div>
            {fundTx.fees > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  fundTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">{t.transactions.market}:</span>{" "}
              {fundTx.market}
            </div>
          </>
        )
      }

      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return (
          <>
            {commonFields}
            {accountTx.fees > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  accountTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {accountTx.retentions > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
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
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
                  {t.transactions.interestRate}:
                </span>{" "}
                {(accountTx.interest_rate * 100).toFixed(2)}%
              </div>
            )}
            {accountTx.avg_balance && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
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
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  factoringTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {factoringTx.retentions > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
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
            {factoringTx.interests > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.interests}:</span>{" "}
                {formatCurrency(
                  factoringTx.interests,
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
        const realEstateTx = tx as realEstateCFTx
        return (
          <>
            {commonFields}
            {realEstateTx.fees > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  realEstateTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {realEstateTx.retentions > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
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
            {realEstateTx.interests > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.interests}:</span>{" "}
                {formatCurrency(
                  realEstateTx.interests,
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
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  depositTx.fees,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {depositTx.retentions > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">
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
            {depositTx.interests > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.interests}:</span>{" "}
                {formatCurrency(
                  depositTx.interests,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
          </>
        )
      }

      case ProductType.CRYPTO: {
        // For crypto, we can show basic investment details if available
        const cryptoTx = tx as any
        return (
          <>
            {commonFields}
            {cryptoTx.ticker && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.ticker}:</span>{" "}
                {cryptoTx.ticker}
              </div>
            )}
            {cryptoTx.shares && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.amount}:</span>{" "}
                {cryptoTx.shares.toLocaleString()}
              </div>
            )}
            {cryptoTx.price && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.price}:</span>{" "}
                {formatCurrency(
                  cryptoTx.price,
                  locale,
                  settings.general.defaultCurrency,
                  tx.currency,
                )}
              </div>
            )}
            {cryptoTx.fees > 0 && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <span className="font-medium">{t.transactions.fees}:</span>{" "}
                {formatCurrency(
                  cryptoTx.fees,
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

  if (loading && !transactions) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t.transactions.title}
        </h1>
      </div>

      {/* Filters */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-6 text-gray-900 dark:text-gray-100">
          {t.transactions.filters}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-6 mb-6">
          <div className="space-y-2 flex flex-col">
            <Label htmlFor="entities" className="text-sm font-medium">
              {t.transactions.entities}
            </Label>
            <MultiSelect
              options={entityOptions}
              value={filters.entities}
              onChange={value => handleFilterChange("entities", value)}
              placeholder={t.transactions.selectEntities}
              className="w-full min-h-[40px] flex-1"
            />
          </div>

          <div className="space-y-2 flex flex-col">
            <Label htmlFor="product-types" className="text-sm font-medium">
              {t.transactions.productTypes}
            </Label>
            <MultiSelect
              options={productTypeOptions}
              value={filters.product_types}
              onChange={value => handleFilterChange("product_types", value)}
              placeholder={t.transactions.selectProductTypes}
              className="w-full min-h-[40px] flex-1"
            />
          </div>

          <div className="space-y-2 flex flex-col">
            <Label htmlFor="transaction-types" className="text-sm font-medium">
              {t.transactions.transactionTypes}
            </Label>
            <MultiSelect
              options={transactionTypeOptions}
              value={filters.types}
              onChange={value => handleFilterChange("types", value)}
              placeholder={t.transactions.selectTransactionTypes}
              className="w-full min-h-[40px] flex-1"
            />
          </div>

          <div className="space-y-2 flex flex-col">
            <Label
              htmlFor="from-date"
              className="text-sm font-medium flex items-center gap-1"
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

          <div className="space-y-2 flex flex-col">
            <Label
              htmlFor="to-date"
              className="text-sm font-medium flex items-center gap-1"
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
        </div>

        <div className="flex gap-3">
          <Button
            onClick={handleApplyFilters}
            disabled={loading}
            className="flex items-center gap-2"
          >
            <Search className="h-4 w-4" />
            {t.transactions.search}
          </Button>
          <Button
            variant="outline"
            onClick={handleClearFilters}
            disabled={loading}
            className="flex items-center gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            {t.transactions.clear}
          </Button>
        </div>
      </Card>

      {/* Results */}
      {error && (
        <Card className="p-6">
          <div className="text-red-600 dark:text-red-400">{error}</div>
        </Card>
      )}

      {transactions && (
        <>
          {/* Desktop Results Card */}
          <Card className="hidden md:block overflow-hidden">
            <div className="flex justify-between items-center mb-4 px-6 pt-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t.transactions.results}
                {transactions.transactions.length > 0 && (
                  <span className="text-sm font-normal text-gray-600 dark:text-gray-400 ml-2">
                    ({transactions.transactions.length} {t.transactions.items})
                  </span>
                )}
              </h2>
              {loading && <LoadingSpinner size="sm" />}
            </div>

            {transactions.transactions.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400 px-6">
                {t.transactions.noTransactionsFound}
              </div>
            ) : (
              <>
                {/* Desktop Table */}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700">
                        <th className="text-left py-4 px-3 font-medium text-gray-700 dark:text-gray-300">
                          {t.transactions.date}
                        </th>
                        <th className="text-left py-4 px-3 font-medium text-gray-700 dark:text-gray-300">
                          {t.transactions.name}
                        </th>
                        <th className="text-center py-4 px-3 font-medium text-gray-700 dark:text-gray-300 w-24">
                          {t.transactions.type}
                        </th>
                        <th className="text-center py-4 px-3 font-medium text-gray-700 dark:text-gray-300 w-32">
                          {t.transactions.product}
                        </th>
                        <th className="text-right py-4 px-3 font-medium text-gray-700 dark:text-gray-300">
                          {t.transactions.amount}
                        </th>
                        <th className="text-center py-4 px-3 font-medium text-gray-700 dark:text-gray-300">
                          {t.transactions.entity}
                        </th>
                        <th className="text-center py-4 px-3 font-medium text-gray-700 dark:text-gray-300 w-20">
                          Details
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.transactions.map((tx, index) => {
                        const isExpanded = expandedCards.has(tx.id)
                        const hasDetails =
                          tx.product_type === ProductType.STOCK_ETF ||
                          tx.product_type === ProductType.FUND ||
                          tx.product_type === ProductType.ACCOUNT ||
                          tx.product_type === ProductType.FACTORING ||
                          tx.product_type === ProductType.REAL_ESTATE_CF ||
                          tx.product_type === ProductType.DEPOSIT ||
                          tx.product_type === ProductType.CRYPTO

                        return (
                          <React.Fragment key={tx.id}>
                            <tr
                              className={`transition-colors duration-300 ${
                                index % 2 === 0
                                  ? "bg-neutral-50 dark:bg-black"
                                  : "bg-white dark:bg-neutral-900"
                              }`}
                            >
                              <td className="py-4 px-3 text-sm text-gray-900 dark:text-gray-100">
                                {formatDate(tx.date, locale)}
                              </td>
                              <td className="py-4 px-3">
                                <div className="font-medium text-sm text-gray-900 dark:text-gray-100 flex items-center gap-2">
                                  {tx.name}
                                  {!tx.is_real && (
                                    <span
                                      className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
                                      title="Virtual/User Imported Transaction"
                                    >
                                      📝
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="py-4 px-3 text-center w-24">
                                <Badge
                                  className={`${getTransactionTypeColor(tx.type)} whitespace-normal break-words text-xs inline-flex items-center justify-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                  onClick={() =>
                                    handleBadgeClick("transactionType", tx.type)
                                  }
                                >
                                  {getIconForTxType(tx.type, "h-3 w-3")}
                                  {t.enums?.transactionType?.[tx.type] ||
                                    tx.type}
                                </Badge>
                              </td>
                              <td className="py-4 px-3 text-center w-32">
                                <Badge
                                  className={`${getProductTypeColor(tx.product_type)} whitespace-normal break-words text-xs inline-flex items-center justify-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                                  onClick={() =>
                                    handleBadgeClick(
                                      "productType",
                                      tx.product_type,
                                    )
                                  }
                                >
                                  {getIconForProductType(tx.product_type)}
                                  {t.enums?.productType?.[tx.product_type] ||
                                    tx.product_type}
                                </Badge>
                              </td>
                              <td className="py-4 px-3 text-right">
                                <div
                                  className={`font-medium ${
                                    getTransactionDisplayType(tx.type) === "in"
                                      ? "text-green-600 dark:text-green-400"
                                      : ""
                                  }`}
                                >
                                  {getTransactionDisplayType(tx.type) === "in"
                                    ? "+"
                                    : ""}
                                  {formatCurrency(
                                    tx.amount,
                                    locale,
                                    settings.general.defaultCurrency,
                                    tx.currency,
                                  )}
                                </div>
                              </td>
                              <td className="py-4 px-3 text-center">
                                <Badge
                                  className={`${getEntityColor(tx.entity.name)} whitespace-normal break-words text-xs inline-flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity`}
                                  onClick={() =>
                                    handleBadgeClick("entity", tx.entity.id)
                                  }
                                >
                                  {tx.entity.name}
                                  {!tx.entity.is_real && (
                                    <span className="ml-1 opacity-70">(V)</span>
                                  )}
                                </Badge>
                              </td>
                              <td className="py-4 px-3 text-center w-20">
                                {hasDetails && (
                                  <button
                                    onClick={() => toggleCardExpansion(tx.id)}
                                    className="inline-flex items-center justify-center p-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                                  >
                                    {isExpanded ? (
                                      <ChevronUp className="h-4 w-4" />
                                    ) : (
                                      <ChevronDown className="h-4 w-4" />
                                    )}
                                  </button>
                                )}
                              </td>
                            </tr>
                            {hasDetails && isExpanded && (
                              <tr
                                className={`${
                                  index % 2 === 0
                                    ? "bg-neutral-50 dark:bg-black"
                                    : "bg-white dark:bg-neutral-900"
                                }`}
                              >
                                <td colSpan={7} className="px-3 pb-4">
                                  <div className="pl-4 space-y-2 border-l-2 border-gray-200 dark:border-gray-700">
                                    {renderTransactionDetails(tx)}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Desktop Pagination */}
                <div className="flex justify-center items-center mt-6 gap-3 px-6 pb-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1 || loading}
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
                      loading
                    }
                    className="px-3 py-2"
                  >
                    →
                  </Button>
                </div>
              </>
            )}
          </Card>

          {/* Mobile Results Header */}
          <div className="md:hidden flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t.transactions.results}
              {transactions.transactions.length > 0 && (
                <span className="text-sm font-normal text-gray-600 dark:text-gray-400 ml-2">
                  ({transactions.transactions.length} {t.transactions.items})
                </span>
              )}
            </h2>
            {loading && <LoadingSpinner size="sm" />}
          </div>

          {/* Mobile No Results */}
          {transactions.transactions.length === 0 && (
            <div className="md:hidden text-center py-8 text-gray-500 dark:text-gray-400">
              {t.transactions.noTransactionsFound}
            </div>
          )}

          {/* Mobile Cards */}
          {transactions.transactions.length > 0 && (
            <div className="md:hidden space-y-4">
              {transactions.transactions.map(tx => {
                const isExpanded = expandedCards.has(tx.id)
                const hasDetails =
                  tx.product_type === ProductType.STOCK_ETF ||
                  tx.product_type === ProductType.FUND ||
                  tx.product_type === ProductType.ACCOUNT ||
                  tx.product_type === ProductType.FACTORING ||
                  tx.product_type === ProductType.REAL_ESTATE_CF ||
                  tx.product_type === ProductType.DEPOSIT ||
                  tx.product_type === ProductType.CRYPTO

                return (
                  <Card
                    key={tx.id}
                    className="p-4 transition-colors duration-300"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex-1 min-w-0 pr-3">
                        <div className="font-medium text-gray-900 dark:text-gray-100 flex items-start gap-2 flex-wrap break-words">
                          <span className="break-words min-w-0">{tx.name}</span>
                          {!tx.is_real && (
                            <span
                              className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200 flex-shrink-0"
                              title="Virtual/User Imported Transaction"
                            >
                              📝
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {formatDate(tx.date, locale)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div
                          className={`font-medium ${
                            getTransactionDisplayType(tx.type) === "in"
                              ? "text-green-600 dark:text-green-400"
                              : ""
                          }`}
                        >
                          {getTransactionDisplayType(tx.type) === "in"
                            ? "+"
                            : ""}
                          {formatCurrency(
                            tx.amount,
                            locale,
                            settings.general.defaultCurrency,
                            tx.currency,
                          )}
                        </div>
                      </div>
                    </div>

                    <div
                      className={`flex flex-wrap gap-2 ${hasDetails && isExpanded ? "mb-2" : "mb-0"}`}
                    >
                      <Badge
                        className={`${getTransactionTypeColor(tx.type)} whitespace-normal break-words inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                        onClick={() =>
                          handleBadgeClick("transactionType", tx.type)
                        }
                      >
                        {getIconForTxType(tx.type, "h-3 w-3")}
                        {t.enums?.transactionType?.[tx.type] || tx.type}
                      </Badge>
                      <Badge
                        className={`${getProductTypeColor(tx.product_type)} whitespace-normal break-words inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition-opacity`}
                        onClick={() =>
                          handleBadgeClick("productType", tx.product_type)
                        }
                      >
                        {getIconForProductType(tx.product_type)}
                        {t.enums?.productType?.[tx.product_type] ||
                          tx.product_type}
                      </Badge>
                      <Badge
                        className={`${getEntityColor(tx.entity.name)} whitespace-normal break-words inline-flex items-center cursor-pointer hover:opacity-80 transition-opacity`}
                        onClick={() => handleBadgeClick("entity", tx.entity.id)}
                      >
                        {tx.entity.name}
                        {!tx.entity.is_real && (
                          <span className="ml-1 opacity-75">(V)</span>
                        )}
                      </Badge>

                      {hasDetails && (
                        <button
                          onClick={() => toggleCardExpansion(tx.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                        >
                          {isExpanded ? (
                            <>
                              <ChevronUp className="h-3 w-3" />
                              Less
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-3 w-3" />
                              More
                            </>
                          )}
                        </button>
                      )}
                    </div>

                    {hasDetails && isExpanded && (
                      <div className="pt-2 space-y-2 border-t border-gray-100 dark:border-gray-800">
                        {renderTransactionDetails(tx)}
                      </div>
                    )}
                  </Card>
                )
              })}

              {/* Mobile Pagination */}
              <div className="flex justify-center items-center mt-6 gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1 || loading}
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
                    loading
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
    </div>
  )
}
