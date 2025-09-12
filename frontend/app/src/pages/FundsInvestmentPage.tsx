import React, { useMemo, useRef, useState, useCallback, useEffect } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getColorForName } from "@/lib/utils"
// Filters consolidated locally (was using InvestmentFilters) to show entity + portfolio selectors in one bar.
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import {
  getStockAndFundPositions,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  convertCurrency,
} from "@/utils/financialDataUtils"
import { ProductType } from "@/types/position"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Filter,
  FilterX,
} from "lucide-react"
import { MultiSelect } from "@/components/ui/MultiSelect"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function FundsInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [selectedPortfolios, setSelectedPortfolios] = useState<string[]>([])

  // Get all fund positions
  const allFundPositions = useMemo(() => {
    const allPositions = getStockAndFundPositions(
      positionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    )
    // Add entityId to each position for proper filtering
    return allPositions
      .filter(position => position.type === "FUND")
      .map(position => {
        const entityObj = entities?.find(e => e.name === position.entity)
        return {
          ...position,
          entityId: entityObj?.id || position.entity,
        }
      })
  }, [
    positionsData,
    locale,
    settings.general.defaultCurrency,
    exchangeRates,
    entities,
  ])

  // Filter positions based on selected entities
  const filteredFundPositions = useMemo(() => {
    let base = allFundPositions
    if (selectedEntities.length > 0) {
      base = base.filter(p => selectedEntities.includes(p.entityId))
    }
    if (selectedPortfolios.length > 0) {
      base = base.filter(
        p => p.portfolioName && selectedPortfolios.includes(p.portfolioName),
      )
    }
    return base
  }, [allFundPositions, selectedEntities, selectedPortfolios])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithFunds = getEntitiesWithProductType(
      positionsData,
      ProductType.FUND,
    )
    return (
      entities
        ?.filter(entity => entitiesWithFunds.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  const portfolioOptions: MultiSelectOption[] = useMemo(() => {
    const names = new Set<string>()
    allFundPositions.forEach(p => {
      // If entity filters are active, only consider those entities
      if (selectedEntities.length > 0 && !selectedEntities.includes(p.entityId))
        return
      if (p.portfolioName) names.add(p.portfolioName)
    })
    return Array.from(names)
      .sort()
      .map(name => ({ value: name, label: name }))
  }, [allFundPositions, selectedEntities])

  // Remove selected portfolios no longer available after entity filter changes
  useEffect(() => {
    setSelectedPortfolios(prev =>
      prev.filter(p => portfolioOptions.some(o => o.value === p)),
    )
  }, [portfolioOptions])

  // Calculate chart data - map StockFundPosition to match chart expectations
  const chartData = useMemo(() => {
    const mappedPositions = filteredFundPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.value, // This is already converted to user currency
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [filteredFundPositions])

  const totalInitialInvestment = useMemo(() => {
    return filteredFundPositions.reduce((sum, position) => {
      // Prefer backend provided initialInvestment (cost basis). Fallback to shares * average buy price.
      const rawInitialInvestment =
        position.initialInvestment != null
          ? position.initialInvestment
          : (position.shares || 0) * (position.price || 0)

      const converted =
        exchangeRates && position.currency !== settings.general.defaultCurrency
          ? convertCurrency(
              rawInitialInvestment,
              position.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          : rawInitialInvestment

      return sum + converted
    }, 0)
  }, [filteredFundPositions, exchangeRates, settings.general.defaultCurrency])

  const totalValue = useMemo(() => {
    return filteredFundPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [filteredFundPositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  // Calculate percentage within fund type
  const totalFundValue = useMemo(() => {
    return filteredFundPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [filteredFundPositions])

  // refs map for scrolling/highlighting
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const handleSliceClick = useCallback((slice: any) => {
    const ref = itemRefs.current[slice.name]
    if (ref) {
      ref.scrollIntoView({ behavior: "smooth", block: "center" })
      setHighlighted(slice.name)
      setTimeout(
        () => setHighlighted(prev => (prev === slice.name ? null : prev)),
        1500,
      )
    }
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const handleClearAllFilters = () => {
    setSelectedEntities([])
    setSelectedPortfolios([])
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/investments")}
        >
          <ArrowLeft size={20} />
        </Button>
        <h1 className="text-2xl font-bold">{t.common.fundsInvestments}</h1>
      </div>

      {/* Unified Filters Bar */}
      <div className="pb-6 border-b border-gray-200 dark:border-gray-800">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Filter size={16} />
            <span>{t.transactions.filters}:</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 flex-1">
            <div className="w-full sm:max-w-xs">
              <MultiSelect
                options={entityOptions}
                value={selectedEntities}
                onChange={setSelectedEntities}
                placeholder={t.transactions.selectEntities}
              />
            </div>
            {portfolioOptions.length > 0 && (
              <div className="w-full sm:max-w-xs">
                <MultiSelect
                  options={portfolioOptions}
                  value={selectedPortfolios}
                  onChange={setSelectedPortfolios}
                  placeholder={(t.investments as any).portfolio || "Portfolio"}
                />
              </div>
            )}
          </div>
          {(selectedEntities.length > 0 || selectedPortfolios.length > 0) && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearAllFilters}
              className="flex items-center gap-2 self-start lg:self-auto"
            >
              <FilterX size={16} />
              {t.transactions.clear}
            </Button>
          )}
        </div>
      </div>

      {filteredFundPositions.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  t.common.fundsInvestments.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  t.common.fundsInvestments.toLowerCase(),
                )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            {/* KPI vertical stack */}
            <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.common.fundsInvestments}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex justify-between items-baseline">
                    <p className="text-2xl font-bold">{formattedTotalValue}</p>
                    {totalInitialInvestment > 0 &&
                      (() => {
                        const percentageValue =
                          ((totalValue - totalInitialInvestment) /
                            totalInitialInvestment) *
                          100
                        const sign = percentageValue >= 0 ? "+" : "-"
                        return (
                          <p
                            className={`text-sm font-medium ${percentageValue === 0 ? "text-gray-500 dark:text-gray-400" : percentageValue > 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                          >
                            {sign}
                            {formatPercentage(
                              Math.abs(percentageValue),
                              locale,
                            )}
                          </p>
                        )
                      })()}
                  </div>
                  {totalInitialInvestment > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {t.dashboard.investedAmount}{" "}
                      {formatCurrency(
                        totalInitialInvestment,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.investments.numberOfAssets}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">
                    {filteredFundPositions.length}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {filteredFundPositions.length === 1
                      ? t.investments.asset
                      : t.investments.assets}
                  </p>
                </CardContent>
              </Card>
            </div>
            {/* Chart */}
            <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
              <InvestmentDistributionChart
                data={chartData}
                title={t.common.distribution}
                locale={locale}
                currency={settings.general.defaultCurrency}
                hideLegend
                containerClassName="overflow-visible w-full"
                variant="bare"
                onSliceClick={handleSliceClick}
              />
            </div>
          </div>

          {/* Positions List (sorted desc by current value) */}
          <div className="space-y-4 pb-6">
            {[...filteredFundPositions]
              .sort((a, b) => (b.value || 0) - (a.value || 0))
              .map(position => {
                const percentageOfFunds =
                  totalFundValue > 0
                    ? ((position.value || 0) / totalFundValue) * 100
                    : 0

                const distributionEntry = chartData.find(
                  c => c.name === (position.name || position.symbol),
                )
                const borderColor = distributionEntry?.color || "transparent"
                const isHighlighted =
                  highlighted === (position.name || position.symbol)

                return (
                  <Card
                    key={position.id}
                    ref={el => {
                      itemRefs.current[position.name || position.symbol] = el
                    }}
                    className={`p-6 border-l-4 transition-colors ${isHighlighted ? "ring-2 ring-offset-0 ring-primary" : ""}`}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 flex-wrap">
                          <h3 className="text-lg font-semibold">
                            {position.name}
                          </h3>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                const entityObj = entities?.find(
                                  e => e.name === position.entity,
                                )
                                const id = entityObj?.id || position.entity
                                setSelectedEntities(prev =>
                                  prev.includes(id) ? prev : [...prev, id],
                                )
                              }}
                              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getColorForName(position.entity)} transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary`}
                            >
                              {position.entity}
                            </button>
                            {position.portfolioName && (
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedPortfolios(prev =>
                                    prev.includes(position.portfolioName!)
                                      ? prev
                                      : [...prev, position.portfolioName!],
                                  )
                                }}
                                className="text-xs inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 font-medium transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary"
                              >
                                {position.portfolioName}
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-4 text-sm">
                          {position.isin && (
                            <div>
                              <span className="text-gray-600 dark:text-gray-400">
                                {t.transactions.isin}:{" "}
                              </span>
                              <span className="font-medium">
                                {position.isin}
                              </span>
                            </div>
                          )}
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.investments.shares}:{" "}
                            </span>
                            <span className="font-medium">
                              {position.shares?.toLocaleString()}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.investments.price}:{" "}
                            </span>
                            <span className="font-medium">
                              {formatCurrency(
                                position.price,
                                locale,
                                position.currency,
                              )}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                        <div className="flex items-center gap-2 justify-end">
                          {position.formattedGainLossAmount && (
                            <span
                              className={`text-sm ${
                                (position.gainLossAmount || 0) >= 0
                                  ? "text-green-500"
                                  : "text-red-500"
                              }`}
                            >
                              {position.formattedGainLossAmount}
                            </span>
                          )}
                          <div className="text-xl font-semibold">
                            {position.formattedOriginalValue ||
                              position.formattedValue}
                          </div>
                        </div>
                        {position.currency !==
                          settings.general.defaultCurrency && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {position.formattedValue}
                          </div>
                        )}
                        <div className="text-sm text-gray-600 dark:text-gray-400">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfFunds.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.funds.toLowerCase(),
                            )}
                        </div>
                        <div className="flex items-center gap-1 text-sm justify-end">
                          {position.change >= 0 ? (
                            <TrendingUp size={16} className="text-green-500" />
                          ) : (
                            <TrendingDown size={16} className="text-red-500" />
                          )}
                          <span
                            className={
                              position.change >= 0
                                ? "text-green-500"
                                : "text-red-500"
                            }
                          >
                            {position.change >= 0 ? "+" : ""}
                            {position.change.toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </Card>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}
