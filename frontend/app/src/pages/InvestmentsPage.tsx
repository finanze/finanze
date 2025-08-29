import React from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getAvailableInvestmentTypes } from "@/utils/financialDataUtils"
import { getIconForProductType } from "@/utils/dashboardUtils"
import { ProductType } from "@/types/position"

export default function InvestmentsPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()

  const availableInvestmentTypes = React.useMemo(() => {
    return getAvailableInvestmentTypes(positionsData)
  }, [positionsData])

  const investmentRoutes = React.useMemo(() => {
    const allRoutes = [
      {
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        icon: getIconForProductType(ProductType.STOCK_ETF, "h-6 w-6"),
        color:
          "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
        productType: ProductType.STOCK_ETF,
      },
      {
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        icon: getIconForProductType(ProductType.FUND, "h-6 w-6"),
        color:
          "bg-indigo-100 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300",
        productType: ProductType.FUND,
      },
      {
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        icon: getIconForProductType(ProductType.DEPOSIT, "h-6 w-6"),
        color: "bg-cyan-100 text-cyan-600 dark:bg-cyan-900 dark:text-cyan-300",
        productType: ProductType.DEPOSIT,
      },
      {
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        icon: getIconForProductType(ProductType.FACTORING, "h-6 w-6"),
        color:
          "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300",
        productType: ProductType.FACTORING,
      },
      {
        path: "/investments/real-estate-cf",
        label: t.common.realEstateCfInvestments,
        icon: getIconForProductType(ProductType.REAL_ESTATE_CF, "h-6 w-6"),
        color:
          "bg-emerald-100 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300",
        productType: ProductType.REAL_ESTATE_CF,
      },
      {
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        icon: getIconForProductType(ProductType.CRYPTO, "h-6 w-6"),
        color:
          "bg-orange-100 text-orange-600 dark:bg-orange-900 dark:text-orange-300",
        productType: ProductType.CRYPTO,
      },
    ]

    return allRoutes.map(route => ({
      ...route,
      isDisabled: !availableInvestmentTypes.includes(route.productType),
    }))
  }, [availableInvestmentTypes, t.common])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t.common.investments}</h1>
      </div>

      {investmentRoutes.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-gray-500 dark:text-gray-400">
            No investment data available
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {investmentRoutes.map(route => (
            <Card
              key={route.path}
              className={`p-6 transition-all cursor-pointer ${
                route.isDisabled
                  ? "opacity-50 cursor-not-allowed"
                  : "hover:shadow-lg"
              }`}
              onClick={() => !route.isDisabled && navigate(route.path)}
            >
              <div className="flex items-center space-x-4">
                <div
                  className={`p-3 rounded-lg ${route.color} ${
                    route.isDisabled ? "opacity-50" : ""
                  }`}
                >
                  {route.icon}
                </div>
                <div className="flex-1">
                  <h3
                    className={`text-lg font-semibold ${
                      route.isDisabled
                        ? "text-gray-400 dark:text-gray-600"
                        : "text-gray-900 dark:text-gray-100"
                    }`}
                  >
                    {route.label}
                  </h3>
                  {!route.isDisabled && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-3 p-0 h-auto text-primary hover:text-primary/80"
                      onClick={e => {
                        e.stopPropagation()
                        navigate(route.path)
                      }}
                    >
                      {t.common.viewDetails} →
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
