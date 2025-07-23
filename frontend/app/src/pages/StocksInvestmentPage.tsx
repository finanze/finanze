import React, { useMemo, useState } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import {
  getStockAndFundPositions,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  convertCurrency,
} from "@/utils/financialDataUtils"
import { ProductType } from "@/types/position"
import { ArrowLeft, TrendingUp, TrendingDown } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function StocksInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all stock positions
  const allStockPositions = useMemo(() => {
    const allPositions = getStockAndFundPositions(
      positionsData,
      locale,
      settings.general.defaultCurrency,
      exchangeRates,
    )
    // Add entityId to each position for proper filtering
    return allPositions
      .filter(position => position.type === "STOCK_ETF")
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
  const filteredStockPositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return allStockPositions
    }
    return allStockPositions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [allStockPositions, selectedEntities])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithStocks = getEntitiesWithProductType(
      positionsData,
      ProductType.STOCK_ETF,
    )
    return (
      entities
        ?.filter(entity => entitiesWithStocks.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  // Calculate chart data
  const chartData = useMemo(() => {
    const mappedPositions = filteredStockPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.value, // This is already converted to user currency
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [filteredStockPositions])

  const totalInitialInvestment = useMemo(() => {
    return filteredStockPositions.reduce((sum, position) => {
      // Calculate initial investment as shares * average buy price in original currency
      const initialInvestmentOriginal =
        (position.shares || 0) * (position.price || 0)

      // Convert to user currency if needed
      const initialInvestmentConverted =
        exchangeRates && position.currency !== settings.general.defaultCurrency
          ? convertCurrency(
              initialInvestmentOriginal,
              position.currency,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          : initialInvestmentOriginal

      return sum + initialInvestmentConverted
    }, 0)
  }, [filteredStockPositions, exchangeRates, settings.general.defaultCurrency])

  const totalValue = useMemo(() => {
    return filteredStockPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [filteredStockPositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  // Calculate percentage within stock type
  const totalStockValue = useMemo(() => {
    return filteredStockPositions.reduce(
      (sum, position) => sum + (position.value || 0),
      0,
    )
  }, [filteredStockPositions])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
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
        <h1 className="text-2xl font-bold">{t.common.stocksEtfs}</h1>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredStockPositions.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  t.common.stocksEtfs.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  t.common.stocksEtfs.toLowerCase(),
                )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* KPI Cards Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Market Value Card */}
            <Card className="flex-shrink-0">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.common.stocksEtfs}
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
                          {formatPercentage(Math.abs(percentageValue), locale)}
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

            {/* Number of Assets Card */}
            <Card className="flex-shrink-0">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.investments.numberOfAssets}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold">
                  {filteredStockPositions.length}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {filteredStockPositions.length === 1
                    ? t.investments.asset
                    : t.investments.assets}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Chart */}
          <InvestmentDistributionChart
            data={chartData}
            title={t.common.distributionByAsset}
            locale={locale}
            currency={settings.general.defaultCurrency}
          />

          {/* Positions List */}
          <div className="space-y-4 pb-6">
            {filteredStockPositions.map(position => {
              const percentageOfStocks =
                totalStockValue > 0
                  ? ((position.value || 0) / totalStockValue) * 100
                  : 0

              return (
                <Card key={position.id} className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 flex-wrap">
                        <h3 className="text-lg font-semibold">
                          {position.name}
                        </h3>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{position.entity}</Badge>
                          {position.portfolioName && (
                            <Badge variant="secondary" className="text-xs">
                              {position.portfolioName}
                            </Badge>
                          )}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 text-sm">
                        <div>
                          <span className="text-gray-600 dark:text-gray-400">
                            {t.investments.symbol}:{" "}
                          </span>
                          <span className="font-medium">{position.symbol}</span>
                        </div>
                        {position.isin && (
                          <div>
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.transactions.isin}:{" "}
                            </span>
                            <span className="font-medium">{position.isin}</span>
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
                          {percentageOfStocks.toFixed(1)}%
                        </span>
                        {" " +
                          t.investments.ofInvestmentType.replace(
                            "{type}",
                            t.common.stocks.toLowerCase(),
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
