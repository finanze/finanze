import React from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getIconForProductType } from "@/utils/dashboardUtils"
import { ProductType } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { usePinnedAssets } from "@/context/PinnedAssetsContext"

export default function InvestmentsPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { isLoading } = useFinancialData()
  const { isPinned } = usePinnedAssets()

  const investmentRoutes = React.useMemo(() => {
    const allRoutes = [
      {
        path: "/banking",
        label: t.banking.title,
        icon: getIconForProductType(ProductType.ACCOUNT, "h-6 w-6"),
        color: "bg-teal-100 text-teal-600 dark:bg-teal-900 dark:text-teal-300",
        productType: ProductType.ACCOUNT,
        assetId: "banking" as const,
      },
      {
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        icon: getIconForProductType(ProductType.STOCK_ETF, "h-6 w-6"),
        color:
          "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
        productType: ProductType.STOCK_ETF,
        assetId: "stocks-etfs" as const,
      },
      {
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        icon: getIconForProductType(ProductType.FUND, "h-6 w-6"),
        color:
          "bg-indigo-100 text-indigo-600 dark:bg-indigo-900 dark:text-indigo-300",
        productType: ProductType.FUND,
        assetId: "funds" as const,
      },
      {
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        icon: getIconForProductType(ProductType.DEPOSIT, "h-6 w-6"),
        color: "bg-cyan-100 text-cyan-600 dark:bg-cyan-900 dark:text-cyan-300",
        productType: ProductType.DEPOSIT,
        assetId: "deposits" as const,
      },
      {
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        icon: getIconForProductType(ProductType.FACTORING, "h-6 w-6"),
        color:
          "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300",
        productType: ProductType.FACTORING,
        assetId: "factoring" as const,
      },
      {
        path: "/investments/real-estate-cf",
        label: t.common.realEstateCfInvestments,
        icon: getIconForProductType(ProductType.REAL_ESTATE_CF, "h-6 w-6"),
        color:
          "bg-emerald-100 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300",
        productType: ProductType.REAL_ESTATE_CF,
        assetId: "real-estate-cf" as const,
      },
      {
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        icon: getIconForProductType(ProductType.CRYPTO, "h-6 w-6"),
        color:
          "bg-orange-100 text-orange-600 dark:bg-orange-900 dark:text-orange-300",
        productType: ProductType.CRYPTO,
        assetId: "crypto" as const,
      },
      {
        path: "/real-estate",
        label: t.realEstate.title,
        icon: getIconForProductType(ProductType.REAL_ESTATE, "h-6 w-6"),
        color:
          "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
        productType: ProductType.REAL_ESTATE,
        assetId: "real-estate" as const,
      },
    ]
    // Now always enabled (can navigate without positions)
    return allRoutes.map(route => ({
      ...route,
      isDisabled: false,
      pinned: isPinned(route.assetId),
    }))
  }, [t.common, t.realEstate, isPinned])

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
        <h1 className="text-2xl font-bold">
          {t.common.myAssets || t.common.investments}
        </h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {investmentRoutes.map(route => (
          <Card
            key={route.path}
            className={`p-6 transition-all cursor-pointer relative group ${
              route.isDisabled ? "opacity-50" : "hover:shadow-lg"
            }`}
            onClick={() => navigate(route.path)}
          >
            <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
              <PinAssetButton assetId={route.assetId} />
            </div>
            <div className="flex items-center space-x-4 pr-8">
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
                <div className="flex gap-2 mt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="p-0 h-auto text-primary hover:text-primary/80"
                    onClick={e => {
                      e.stopPropagation()
                      navigate(route.path)
                    }}
                  >
                    {t.common.viewDetails} →
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
