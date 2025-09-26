import React, { useMemo, useState, useRef, useCallback } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { getColorForName } from "@/lib/utils"
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
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { ArrowLeft, Calendar, Percent, TrendingUp } from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
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

          // Profitability provided as decimal (e.g. 0.1 = 10%)
          const profitabilityDecimal = !isNaN(factor.profitability)
            ? factor.profitability
            : null
          const rawProfit =
            profitabilityDecimal !== null
              ? factor.amount * profitabilityDecimal
              : null
          const expectedAtMaturity =
            rawProfit !== null ? factor.amount + rawProfit : null
          const convertedExpectedAmount =
            expectedAtMaturity !== null
              ? convertCurrency(
                  expectedAtMaturity,
                  factor.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const convertedProfit =
            rawProfit !== null
              ? convertCurrency(
                  rawProfit,
                  factor.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const profitabilityPct =
            profitabilityDecimal !== null ? profitabilityDecimal * 100 : null

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
            convertedProfit,
            formattedProfit: convertedProfit
              ? formatCurrency(
                  convertedProfit,
                  locale,
                  settings.general.defaultCurrency,
                )
              : null,
            profitabilityPct,
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

  const { weightedAverageProfitability, totalProfit } = useMemo(() => {
    let weightedProfitabilityAcc = 0
    let profitAcc = 0
    filteredFactoringPositions.forEach(position => {
      profitAcc += position.convertedProfit || 0
      if (
        position.profitabilityPct !== null &&
        !isNaN(position.profitabilityPct) &&
        position.convertedAmount
      ) {
        weightedProfitabilityAcc +=
          position.profitabilityPct * position.convertedAmount
      }
    })
    const wap = totalValue > 0 ? weightedProfitabilityAcc / totalValue : 0
    return { totalProfit: profitAcc, weightedAverageProfitability: wap }
  }, [filteredFactoringPositions, totalValue])

  // Calculate percentage within factoring type
  const totalFactoringValue = useMemo(() => {
    return totalValue
  }, [totalValue])

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
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t.common.factoring}</h1>
          <PinAssetButton assetId="factoring" />
        </div>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredFactoringPositions.length === 0 ? (
        <Card className="p-14 text-center flex flex-col items-center gap-4">
          {getIconForAssetType(
            ProductType.FACTORING,
            "h-16 w-16",
            "text-gray-400 dark:text-gray-600",
          )}
          <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
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
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.dashboard.investedAmount}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">{formattedTotalValue}</p>
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
                    {filteredFactoringPositions.length}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {filteredFactoringPositions.length === 1
                      ? t.investments.asset
                      : t.investments.assets}
                  </p>
                </CardContent>
              </Card>
              <Card>
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
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.investments.expectedProfit}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                    {formatCurrency(
                      totalProfit,
                      locale,
                      settings.general.defaultCurrency,
                    )}
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">
                    {weightedAverageProfitability.toFixed(2)}%
                    <span className="ml-1 text-gray-500 dark:text-gray-400">
                      {t.investments.profitability}
                    </span>
                  </p>
                </CardContent>
              </Card>
            </div>
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

          {/* Positions List (sorted desc by converted amount) */}
          <div className="space-y-4 pb-6">
            {[...filteredFactoringPositions]
              .sort(
                (a, b) => (b.convertedAmount || 0) - (a.convertedAmount || 0),
              )
              .map(factor => {
                const percentageOfFactoring =
                  totalFactoringValue > 0
                    ? ((factor.convertedAmount || 0) / totalFactoringValue) *
                      100
                    : 0

                const distributionEntry = chartData.find(
                  c => c.name === (factor.name || factor.symbol),
                )
                const borderColor = distributionEntry?.color || "transparent"
                const isHighlighted =
                  highlighted === (factor.name || factor.symbol)

                return (
                  <Card
                    key={factor.id}
                    ref={el => {
                      itemRefs.current[factor.name || factor.symbol] = el
                    }}
                    className={`p-6 border-l-4 transition-colors ${isHighlighted ? "ring-2 ring-primary" : ""}`}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                          <h3 className="font-semibold text-lg">
                            {factor.name}
                          </h3>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                const entityObj = entities?.find(
                                  e => e.name === factor.entity,
                                )
                                const id = entityObj?.id || factor.entity
                                setSelectedEntities(prev =>
                                  prev.includes(id) ? prev : [...prev, id],
                                )
                              }}
                              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getColorForName(factor.entity)} transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary`}
                            >
                              {factor.entity}
                            </button>
                            <Badge variant="default" className="text-xs">
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
                              <span className="text-blue-600 dark:text-neutral-500 font-medium">
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

                        {(factor.formattedExpectedAmount ||
                          factor.formattedProfit) && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-sm">
                            {factor.formattedExpectedAmount && (
                              <div>
                                <span className="text-gray-600 dark:text-gray-400">
                                  {t.investments.expectedAtMaturity}:{" "}
                                </span>
                                <span className="font-medium text-green-600 dark:text-green-400">
                                  {factor.formattedExpectedAmount}
                                </span>
                              </div>
                            )}
                            {factor.formattedProfit && (
                              <div>
                                <span className="text-gray-600 dark:text-gray-400">
                                  {t.investments.profit}:{" "}
                                </span>
                                <span className="font-medium text-emerald-600 dark:text-emerald-400">
                                  {factor.formattedProfit}
                                  {factor.profitabilityPct !== null && (
                                    <span className="ml-1 text-xs text-emerald-500 dark:text-emerald-300">
                                      ({factor.profitabilityPct.toFixed(2)}%)
                                    </span>
                                  )}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                        <div className="text-2xl font-bold">
                          {factor.formattedAmount}
                        </div>
                        {factor.currency !==
                          settings.general.defaultCurrency && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {factor.formattedConvertedAmount}
                          </div>
                        )}
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-0.5">
                          <span className="font-medium text-blue-600 dark:text-blue-400">
                            {percentageOfFactoring.toFixed(1)}%
                          </span>
                          {" " +
                            t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.factoring.toLowerCase(),
                            )}
                          {/* Profit already shown above; avoid duplication */}
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
