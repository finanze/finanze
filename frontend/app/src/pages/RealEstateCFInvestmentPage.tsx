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
import { ArrowLeft, Calendar, Percent, Building, Clock } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"

export default function RealEstateCFInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])

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

          const profitabilityDecimal = !isNaN(realEstate.profitability)
            ? realEstate.profitability
            : null
          const rawProfit =
            profitabilityDecimal !== null
              ? realEstate.amount * profitabilityDecimal
              : null
          const rawExpectedAtMaturity =
            rawProfit !== null ? realEstate.amount + rawProfit : null
          const convertedExpectedAtMaturity =
            rawExpectedAtMaturity !== null
              ? convertCurrency(
                  rawExpectedAtMaturity,
                  realEstate.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const convertedProfit =
            rawProfit !== null
              ? convertCurrency(
                  rawProfit,
                  realEstate.currency,
                  settings.general.defaultCurrency,
                  exchangeRates,
                )
              : null
          const profitabilityPct =
            profitabilityDecimal !== null ? profitabilityDecimal * 100 : null

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
            convertedExpectedAtMaturity,
            formattedExpectedAtMaturity:
              convertedExpectedAtMaturity !== null
                ? formatCurrency(
                    convertedExpectedAtMaturity,
                    locale,
                    settings.general.defaultCurrency,
                  )
                : null,
            convertedProfit,
            formattedProfit:
              convertedProfit !== null
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

    return realEstates
  }, [positionsData, settings.general.defaultCurrency, exchangeRates, locale])

  const filteredRealEstatePositions = useMemo(() => {
    if (selectedEntities.length === 0) {
      return allRealEstatePositions
    }
    return allRealEstatePositions.filter(position =>
      selectedEntities.includes(position.entityId),
    )
  }, [allRealEstatePositions, selectedEntities])

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

  const chartData = useMemo(() => {
    const mappedPositions = filteredRealEstatePositions.map(position => ({
      ...position,
      symbol: position.name,
      currentValue: position.convertedPendingAmount,
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

  const { weightedAverageInterest, weightedAverageProfitability, totalProfit } =
    useMemo(() => {
      if (filteredRealEstatePositions.length === 0) {
        return {
          weightedAverageInterest: 0,
          weightedAverageProfitability: 0,
          totalProfit: 0,
        }
      }
      let weightedInterestAcc = 0
      let weightedProfitabilityAcc = 0
      let profitAcc = 0
      filteredRealEstatePositions.forEach(p => {
        const weight = p.convertedPendingAmount || 0
        weightedInterestAcc += (p.interest_rate || 0) * weight
        if (p.profitabilityPct !== null && weight) {
          weightedProfitabilityAcc += p.profitabilityPct * weight
        }
        profitAcc += p.convertedProfit || 0
      })
      return {
        weightedAverageInterest:
          totalValue > 0 ? (weightedInterestAcc / totalValue) * 100 : 0,
        weightedAverageProfitability:
          totalValue > 0 ? weightedProfitabilityAcc / totalValue : 0,
        totalProfit: profitAcc,
      }
    }, [filteredRealEstatePositions, totalValue])

  const totalRealEstateValue = useMemo(() => {
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
        <h1 className="text-2xl font-bold">{t.common.realEstateCf}</h1>
      </div>

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
                    {filteredRealEstatePositions.length}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {filteredRealEstatePositions.length === 1
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
                    {t.investments.interest} {t.investments.annually}
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
                    <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
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

          {/* Positions List (sorted desc by converted pending amount) */}
          <div className="space-y-4 pb-6">
            {[...filteredRealEstatePositions]
              .sort(
                (a, b) =>
                  (b.convertedPendingAmount || 0) -
                  (a.convertedPendingAmount || 0),
              )
              .map(realEstate => {
                const percentageOfRealEstate =
                  totalRealEstateValue > 0
                    ? ((realEstate.convertedPendingAmount || 0) /
                        totalRealEstateValue) *
                      100
                    : 0

                const distributionEntry = chartData.find(
                  c => c.name === (realEstate.name || realEstate.symbol),
                )
                const borderColor = distributionEntry?.color || "transparent"
                const isHighlighted =
                  highlighted === (realEstate.name || realEstate.symbol)

                return (
                  <Card
                    key={realEstate.id}
                    ref={el => {
                      itemRefs.current[realEstate.name || realEstate.symbol] =
                        el
                    }}
                    className={`p-6 border-l-4 transition-colors ${isHighlighted ? "ring-2 ring-primary" : ""}`}
                    style={{ borderLeftColor: borderColor }}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                          <h3 className="font-semibold text-lg">
                            {realEstate.name}
                          </h3>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                const entityObj = entities?.find(
                                  e => e.name === realEstate.entity,
                                )
                                const id = entityObj?.id || realEstate.entity
                                setSelectedEntities(prev =>
                                  prev.includes(id) ? prev : [...prev, id],
                                )
                              }}
                              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getColorForName(realEstate.entity)} transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-primary`}
                            >
                              {realEstate.entity}
                            </button>
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

                        {(realEstate.formattedPendingAmount ||
                          realEstate.formattedProfit) && (
                          <div className="flex flex-col gap-1 text-sm">
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                              {realEstate.formattedPendingAmount && (
                                <div className="flex items-center gap-1">
                                  <span className="text-gray-600 dark:text-gray-400">
                                    {t.investments.pending}:
                                  </span>
                                  <span className="font-medium text-orange-600 dark:text-orange-400">
                                    {realEstate.formattedPendingAmount}
                                  </span>
                                </div>
                              )}
                              {realEstate.formattedProfit && (
                                <div className="flex items-center gap-1">
                                  <span className="text-gray-600 dark:text-gray-400">
                                    {t.investments.expectedProfit}:
                                  </span>
                                  <span className="font-medium text-emerald-600 dark:text-emerald-400">
                                    {realEstate.formattedProfit}
                                    {realEstate.profitabilityPct !== null && (
                                      <span className="ml-1 text-xs text-emerald-500 dark:text-emerald-300">
                                        (
                                        {realEstate.profitabilityPct.toFixed(2)}
                                        %)
                                      </span>
                                    )}
                                  </span>
                                </div>
                              )}
                            </div>
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
                        <div className="text-sm text-gray-600 dark:text-gray-400 space-y-0.5">
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
