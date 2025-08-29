import React, { useMemo, useState } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import {
  InvestmentDistributionChart,
  InvestmentDistributionLegend,
} from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  convertCurrency,
  getEntitiesWithProductType,
  calculateInvestmentDistribution,
} from "@/utils/financialDataUtils"
import { ProductType } from "@/types/position"
import { ArrowLeft, Calendar, Percent, TrendingUp } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function DepositsInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all deposit positions
  const allDepositPositions = useMemo(() => {
    if (!positionsData?.positions) return []

    const deposits: any[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      const depositProduct = entityPosition.products[ProductType.DEPOSIT]
      if (
        depositProduct &&
        "entries" in depositProduct &&
        depositProduct.entries.length > 0
      ) {
        const entityName = entityPosition.entity?.name || "Unknown"

        depositProduct.entries.forEach((deposit: any) => {
          const convertedAmount = convertCurrency(
            deposit.amount,
            deposit.currency,
            settings.general.defaultCurrency,
            exchangeRates,
          )

          const convertedExpectedAmount = deposit.expected_interests
            ? convertCurrency(
                deposit.expected_interests,
                deposit.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              )
            : null

          deposits.push({
            ...deposit,
            entity: entityName,
            entityId: entityPosition.entity?.id,
            convertedAmount,
            convertedExpectedAmount,
            formattedAmount: formatCurrency(
              deposit.amount,
              locale,
              deposit.currency,
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

    return deposits
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  // Filter positions based on selected entities
  const filteredDepositPositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return allDepositPositions
    }
    return allDepositPositions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [allDepositPositions, selectedEntities])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithDeposits = getEntitiesWithProductType(
      positionsData,
      ProductType.DEPOSIT,
    )
    return (
      entities
        ?.filter(entity => entitiesWithDeposits.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  // Calculate chart data
  const chartData = useMemo(() => {
    const mappedPositions = filteredDepositPositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.convertedAmount, // Use converted amount for chart
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [filteredDepositPositions])

  const totalValue = useMemo(() => {
    return filteredDepositPositions.reduce(
      (sum, position) => sum + (position.convertedAmount || 0),
      0,
    )
  }, [filteredDepositPositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  // Calculate percentage within deposits type
  const totalDepositValue = useMemo(() => {
    return filteredDepositPositions.reduce(
      (sum, position) => sum + (position.convertedAmount || 0),
      0,
    )
  }, [filteredDepositPositions])

  // Calculate weighted average interest rate
  const weightedAverageInterest = useMemo(() => {
    if (filteredDepositPositions.length === 0) return 0

    const totalWeightedInterest = filteredDepositPositions.reduce(
      (sum, position) => {
        const weight = position.convertedAmount || 0
        const interest = position.interest_rate || 0
        return sum + weight * interest
      },
      0,
    )

    return totalValue > 0 ? (totalWeightedInterest / totalValue) * 100 : 0
  }, [filteredDepositPositions, totalValue])

  const totalExpectedReturn = useMemo(() => {
    return filteredDepositPositions.reduce((sum, position) => {
      return sum + (position.convertedExpectedAmount || 0)
    }, 0)
  }, [filteredDepositPositions])

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
        <h1 className="text-2xl font-bold">{t.common.deposits}</h1>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredDepositPositions.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  t.common.deposits.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  t.common.deposits.toLowerCase(),
                )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* KPI Cards Row (aligned with other products) */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Invested Card */}
            <Card className="flex-shrink-0">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.dashboard.investedAmount}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold">{formattedTotalValue}</p>
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
                  {filteredDepositPositions.length}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {filteredDepositPositions.length === 1
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

            {/* Expected Profit (Interests) Card */}
            <Card className="flex-shrink-0">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.investments.expectedProfit}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                  {formatCurrency(
                    totalExpectedReturn,
                    locale,
                    settings.general.defaultCurrency,
                  )}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Distribution Chart & Legend */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            <div className="xl:col-span-2 flex flex-col">
              <InvestmentDistributionChart
                data={chartData}
                title={t.common.distribution}
                locale={locale}
                currency={settings.general.defaultCurrency}
                hideLegend
                containerClassName="h-full"
              />
            </div>
            <div className="xl:col-span-1 flex flex-col">
              <InvestmentDistributionLegend
                data={chartData}
                locale={locale}
                currency={settings.general.defaultCurrency}
              />
            </div>
          </div>

          {/* Positions List */}
          <div className="space-y-4 pb-6">
            {filteredDepositPositions.map(deposit => {
              const percentageOfDeposits =
                totalDepositValue > 0
                  ? ((deposit.convertedAmount || 0) / totalDepositValue) * 100
                  : 0

              return (
                <Card key={deposit.id} className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                        <h3 className="font-semibold text-lg">
                          {deposit.name}
                        </h3>
                        <Badge variant="outline">{deposit.entity}</Badge>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <div className="flex items-center gap-1">
                          <Percent size={14} />
                          <span>
                            {t.investments.interest}:{" "}
                            <span className="text-green-600 dark:text-green-400 font-medium">
                              {(deposit.interest_rate * 100).toFixed(2)}%
                            </span>
                          </span>
                        </div>

                        <div className="flex items-center gap-1">
                          <Calendar size={14} />
                          <span>
                            {t.investments.maturity}:{" "}
                            {formatDate(deposit.maturity, locale)}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <TrendingUp size={12} />
                          <span>
                            {t.investments.creation}:{" "}
                            {formatDate(deposit.creation, locale)}
                          </span>
                        </div>
                      </div>

                      {deposit.formattedExpectedAmount && (
                        <div className="text-sm">
                          <span className="text-gray-600 dark:text-gray-400">
                            {t.investments.expectedProfit}:{" "}
                          </span>
                          <span className="font-medium text-green-600 dark:text-green-400">
                            {deposit.formattedExpectedAmount}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                      <div className="text-2xl font-bold">
                        {deposit.formattedAmount}
                      </div>
                      {deposit.currency !==
                        settings.general.defaultCurrency && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {deposit.formattedConvertedAmount}
                        </div>
                      )}
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        <span className="font-medium text-blue-600 dark:text-blue-400">
                          {percentageOfDeposits.toFixed(1)}%
                        </span>
                        {" " +
                          t.investments.ofInvestmentType.replace(
                            "{type}",
                            t.common.deposits.toLowerCase(),
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
