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
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  convertCurrency,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
  formatSnakeCaseToHuman,
} from "@/utils/financialDataUtils"
import { ProductType } from "@/types/position"
import { ArrowLeft, Calendar, Percent, TrendingUp } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function FactoringInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all factoring positions
  const allFactoringPositions = useMemo(() => {
    if (!positionsData?.positions) return []

    const factoring: any[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      const factoringProduct = entityPosition.products[ProductType.FACTORING]
      if (
        factoringProduct &&
        "entries" in factoringProduct &&
        factoringProduct.entries.length > 0
      ) {
        const entityName = entityPosition.entity?.name || "Unknown"

        factoringProduct.entries.forEach((factor: any) => {
          const convertedAmount = convertCurrency(
            factor.amount,
            factor.currency,
            settings.general.defaultCurrency,
            exchangeRates,
          )

          const convertedExpectedAmount = factor.expected_amount
            ? convertCurrency(
                factor.expected_amount,
                factor.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              )
            : null

          factoring.push({
            ...factor,
            entity: entityName,
            entityId: entityPosition.entity?.id,
            convertedAmount,
            convertedExpectedAmount,
            formattedAmount: formatCurrency(
              factor.amount,
              locale,
              factor.currency,
            ),
            formattedConvertedAmount: formatCurrency(
              convertedAmount,
              locale,
              settings.general.defaultCurrency,
            ),
            formattedExpectedAmount: convertedExpectedAmount
              ? formatCurrency(
                  convertedExpectedAmount,
                  locale,
                  settings.general.defaultCurrency,
                )
              : null,
          })
        })
      }
    })

    return factoring
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  // Filter positions based on selected entities
  const filteredFactoringPositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return allFactoringPositions
    }
    return allFactoringPositions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [allFactoringPositions, selectedEntities])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithFactoring = getEntitiesWithProductType(
      positionsData,
      ProductType.FACTORING,
    )
    return (
      entities
        ?.filter(entity => entitiesWithFactoring.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  // Calculate chart data
  const chartData = useMemo(() => {
    const mappedPositions = filteredFactoringPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.convertedAmount, // Use converted amount for chart
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [filteredFactoringPositions])

  const totalValue = useMemo(() => {
    return filteredFactoringPositions.reduce(
      (sum, position) => sum + (position.convertedAmount || 0),
      0,
    )
  }, [filteredFactoringPositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  // Calculate weighted average interest rate
  const weightedAverageInterest = useMemo(() => {
    if (filteredFactoringPositions.length === 0) return 0

    const totalWeightedInterest = filteredFactoringPositions.reduce(
      (sum, position) => {
        const weight = position.convertedAmount || 0
        const interest = position.interest_rate || 0
        return sum + weight * interest
      },
      0,
    )

    return totalValue > 0 ? (totalWeightedInterest / totalValue) * 100 : 0
  }, [filteredFactoringPositions, totalValue])

  const totalExpectedReturn = useMemo(() => {
    return filteredFactoringPositions.reduce((sum, position) => {
      return sum + (position.convertedExpectedAmount || 0)
    }, 0)
  }, [filteredFactoringPositions])

  // Calculate percentage within factoring type
  const totalFactoringValue = useMemo(() => {
    return totalValue
  }, [totalValue])

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
        <h1 className="text-2xl font-bold">{t.common.factoring}</h1>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredFactoringPositions.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  t.common.factoring.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  t.common.factoring.toLowerCase(),
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
                  {t.common.factoring}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold">{formattedTotalValue}</p>
                {totalExpectedReturn > 0 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {t.investments.expected}{" "}
                    {formatCurrency(
                      totalExpectedReturn,
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
                  {filteredFactoringPositions.length}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {filteredFactoringPositions.length === 1
                    ? t.investments.asset
                    : t.investments.assets}
                </p>
              </CardContent>
            </Card>

            {/* Weighted Average Interest Card */}
            <Card className="flex-shrink-0">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.investments.weightedAverageInterest}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold">
                  {weightedAverageInterest.toFixed(2)}%
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {t.investments.annually}
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
            {filteredFactoringPositions.map(factor => {
              const percentageOfFactoring =
                totalFactoringValue > 0
                  ? ((factor.convertedAmount || 0) / totalFactoringValue) * 100
                  : 0

              return (
                <Card key={factor.id} className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                        <h3 className="font-semibold text-lg">{factor.name}</h3>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{factor.entity}</Badge>
                          <Badge
                            variant={
                              factor.state === "ACTIVE"
                                ? "default"
                                : "secondary"
                            }
                            className="text-xs"
                          >
                            {formatSnakeCaseToHuman(factor.state)}
                          </Badge>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <div className="flex items-center gap-1">
                          <Percent size={14} />
                          <span>
                            <span className="text-green-600 dark:text-green-400 font-medium">
                              {(factor.interest_rate * 100).toFixed(2)}%
                            </span>
                            {" / "}
                            <span className="text-blue-600 dark:text-blue-400 font-medium">
                              {(factor.gross_interest_rate * 100).toFixed(2)}%
                            </span>
                            {" " + t.investments.gross}
                          </span>
                        </div>

                        <div className="flex items-center gap-1">
                          <Calendar size={14} />
                          <span>
                            {t.investments.maturity}:{" "}
                            {formatDate(factor.maturity, locale)}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <TrendingUp size={12} />
                          <span>
                            {t.investments.lastInvest}:{" "}
                            {formatDate(factor.last_invest_date, locale)}
                          </span>
                        </div>
                        <span>
                          {t.investments.type}:{" "}
                          {formatSnakeCaseToHuman(factor.type)}
                        </span>
                      </div>

                      {factor.formattedExpectedAmount && (
                        <div className="text-sm">
                          <span className="text-gray-600 dark:text-gray-400">
                            {t.investments.expected}:{" "}
                          </span>
                          <span className="font-medium text-green-600 dark:text-green-400">
                            {factor.formattedExpectedAmount}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                      <div className="text-2xl font-bold">
                        {factor.formattedAmount}
                      </div>
                      {factor.currency !== settings.general.defaultCurrency && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {factor.formattedConvertedAmount}
                        </div>
                      )}
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        <span className="font-medium text-blue-600 dark:text-blue-400">
                          {percentageOfFactoring.toFixed(1)}%
                        </span>
                        {" " +
                          t.investments.ofInvestmentType.replace(
                            "{type}",
                            t.common.factoring.toLowerCase(),
                          )}
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
