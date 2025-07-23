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
import { ArrowLeft, Calendar, Percent, Building, Clock } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function RealEstateCFInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

  // Get all real estate positions
  const allRealEstatePositions = useMemo(() => {
    if (!positionsData?.positions) return []

    const realEstates: any[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      const realEstateProduct =
        entityPosition.products[ProductType.REAL_ESTATE_CF]
      if (
        realEstateProduct &&
        "entries" in realEstateProduct &&
        realEstateProduct.entries.length > 0
      ) {
        const entityName = entityPosition.entity?.name || "Unknown"

        realEstateProduct.entries.forEach((realEstate: any) => {
          const convertedAmount = convertCurrency(
            realEstate.amount,
            realEstate.currency,
            settings.general.defaultCurrency,
            exchangeRates,
          )

          const convertedPendingAmount = isNaN(realEstate.pending_amount)
            ? null
            : convertCurrency(
                realEstate.pending_amount,
                realEstate.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              )

          realEstates.push({
            ...realEstate,
            entity: entityName,
            entityId: entityPosition.entity?.id,
            convertedAmount,
            convertedPendingAmount,
            formattedAmount: formatCurrency(
              realEstate.amount,
              locale,
              realEstate.currency,
            ),
            formattedConvertedAmount: formatCurrency(
              convertedAmount,
              locale,
              settings.general.defaultCurrency,
            ),
            formattedPendingAmount:
              convertedPendingAmount !== null
                ? formatCurrency(
                    convertedPendingAmount,
                    locale,
                    settings.general.defaultCurrency,
                  )
                : null,
          })
        })
      }
    })

    return realEstates
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  // Filter positions based on selected entities
  const filteredRealEstatePositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return allRealEstatePositions
    }
    return allRealEstatePositions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [allRealEstatePositions, selectedEntities])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithRealEstate = getEntitiesWithProductType(
      positionsData,
      ProductType.REAL_ESTATE_CF,
    )
    return (
      entities
        ?.filter(entity => entitiesWithRealEstate.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  // Calculate chart data
  const chartData = useMemo(() => {
    const mappedPositions = filteredRealEstatePositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.convertedPendingAmount, // Use converted amount for chart
    }))
    return calculateInvestmentDistribution(mappedPositions, "symbol")
  }, [filteredRealEstatePositions])

  const totalValue = useMemo(() => {
    return filteredRealEstatePositions.reduce(
      (sum, position) => sum + (position.convertedPendingAmount || 0),
      0,
    )
  }, [filteredRealEstatePositions])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  // Calculate weighted average interest rate
  const weightedAverageInterest = useMemo(() => {
    if (filteredRealEstatePositions.length === 0) return 0

    const totalWeightedInterest = filteredRealEstatePositions.reduce(
      (sum, position) => {
        const weight = position.convertedPendingAmount || 0
        const interest = position.interest_rate || 0
        return sum + weight * interest
      },
      0,
    )

    return totalValue > 0 ? (totalWeightedInterest / totalValue) * 100 : 0
  }, [filteredRealEstatePositions, totalValue])

  // Calculate percentage within real estate type
  const totalRealEstateValue = useMemo(() => {
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
        <h1 className="text-2xl font-bold">{t.common.realEstateCf}</h1>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredRealEstatePositions.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  t.common.realEstateCf.toLowerCase(),
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  t.common.realEstateCf.toLowerCase(),
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
                  {t.common.realEstateCf}
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
                  {filteredRealEstatePositions.length}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {filteredRealEstatePositions.length === 1
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
            {filteredRealEstatePositions.map(realEstate => {
              const percentageOfRealEstate =
                totalRealEstateValue > 0
                  ? ((realEstate.convertedPendingAmount || 0) /
                      totalRealEstateValue) *
                    100
                  : 0

              return (
                <Card key={realEstate.id} className="p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                        <h3 className="font-semibold text-lg">
                          {realEstate.name}
                        </h3>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{realEstate.entity}</Badge>
                          <Badge variant="default" className="text-xs">
                            {formatSnakeCaseToHuman(realEstate.state)}
                          </Badge>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <div className="flex items-center gap-1">
                          <Building size={14} />
                          <span>
                            {t.investments.type}:{" "}
                            {formatSnakeCaseToHuman(
                              realEstate.investment_project_type,
                            )}
                          </span>
                        </div>

                        <div className="flex items-center gap-1">
                          <Percent size={14} />
                          <span>
                            {t.investments.interest}:{" "}
                            <span className="text-green-600 dark:text-green-400 font-medium">
                              {(realEstate.interest_rate * 100).toFixed(2)}%
                            </span>
                            {" " + t.investments.annually}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <Calendar size={14} />
                          <span>
                            {t.investments.lastInvest}:{" "}
                            {formatDate(realEstate.last_invest_date, locale)}
                          </span>
                        </div>

                        <div className="flex items-center gap-1">
                          <Clock size={14} />
                          <span>
                            {t.investments.maturity}:{" "}
                            {formatDate(realEstate.maturity, locale)}
                          </span>
                        </div>
                      </div>

                      {realEstate.formattedPendingAmount && (
                        <div className="text-sm">
                          <span className="text-gray-600 dark:text-gray-400">
                            {t.investments.pending}:{" "}
                          </span>
                          <span className="font-medium text-orange-600 dark:text-orange-400">
                            {realEstate.formattedPendingAmount}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="text-left sm:text-right space-y-1 flex-shrink-0">
                      <div className="text-2xl font-bold">
                        {realEstate.formattedAmount}
                      </div>
                      {realEstate.currency !==
                        settings.general.defaultCurrency && (
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {realEstate.formattedConvertedAmount}
                        </div>
                      )}
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        <span className="font-medium text-blue-600 dark:text-blue-400">
                          {percentageOfRealEstate.toFixed(1)}%
                        </span>
                        {" " +
                          t.investments.ofInvestmentType.replace(
                            "{type}",
                            t.common.realEstateCf.toLowerCase(),
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
