import React from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useNavigate } from "react-router-dom"
import { Card } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getIconForProductType } from "@/utils/dashboardUtils"
import { ProductType } from "@/types/position"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { usePinnedShortcuts } from "@/context/PinnedShortcutsContext"
import { getEntitiesWithProductType } from "@/utils/financialDataUtils"

export default function InvestmentsPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { isLoading, positionsData, realEstateList } = useFinancialData()
  const { isPinned } = usePinnedShortcuts()

  const investmentRoutes = React.useMemo(() => {
    const allRoutes = [
      {
        path: "/banking",
        label: t.banking.title,
        icon: getIconForProductType(ProductType.ACCOUNT, "h-8 w-8"),
        color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200",
        productType: ProductType.ACCOUNT,
        assetId: "banking" as const,
      },
      {
        path: "/investments/stocks-etfs",
        label: t.common.stocksEtfs,
        icon: getIconForProductType(ProductType.STOCK_ETF, "h-8 w-8"),
        color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-200",
        productType: ProductType.STOCK_ETF,
        assetId: "stocks-etfs" as const,
      },
      {
        path: "/investments/funds",
        label: t.common.fundsInvestments,
        icon: getIconForProductType(ProductType.FUND, "h-8 w-8"),
        color: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-200",
        productType: ProductType.FUND,
        assetId: "funds" as const,
      },
      {
        path: "/investments/deposits",
        label: t.common.depositsInvestments,
        icon: getIconForProductType(ProductType.DEPOSIT, "h-8 w-8"),
        color:
          "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-200",
        productType: ProductType.DEPOSIT,
        assetId: "deposits" as const,
      },
      {
        path: "/investments/factoring",
        label: t.common.factoringInvestments,
        icon: getIconForProductType(ProductType.FACTORING, "h-8 w-8"),
        color:
          "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-200",
        productType: ProductType.FACTORING,
        assetId: "factoring" as const,
      },
      {
        path: "/investments/real-estate-cf",
        label: t.common.realEstateCfInvestments,
        icon: getIconForProductType(ProductType.REAL_ESTATE_CF, "h-8 w-8"),
        color:
          "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-200",
        productType: ProductType.REAL_ESTATE_CF,
        assetId: "real-estate-cf" as const,
      },
      {
        path: "/investments/crypto",
        label: t.common.cryptoInvestments,
        icon: getIconForProductType(ProductType.CRYPTO, "h-8 w-8"),
        color:
          "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-200",
        productType: ProductType.CRYPTO,
        assetId: "crypto" as const,
      },
      {
        path: "/investments/commodities",
        label: t.common.commodities,
        icon: getIconForProductType(ProductType.COMMODITY, "h-8 w-8"),
        color:
          "bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-200",
        productType: ProductType.COMMODITY,
        assetId: "commodities" as const,
      },
      {
        path: "/real-estate",
        label: t.realEstate.title,
        icon: getIconForProductType(ProductType.REAL_ESTATE, "h-8 w-8"),
        color:
          "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
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

  const sortedRoutes = React.useMemo(() => {
    const routesWithPositionInfo = investmentRoutes.map(route => {
      const hasPositions =
        route.productType === ProductType.REAL_ESTATE
          ? realEstateList.length > 0
          : getEntitiesWithProductType(positionsData, route.productType)
              .length > 0

      return {
        ...route,
        hasPositions,
      }
    })

    return routesWithPositionInfo.sort((a, b) => {
      // First: pinned items
      if (a.pinned !== b.pinned) {
        return Number(b.pinned) - Number(a.pinned)
      }
      // Second: items with positions
      if (a.hasPositions !== b.hasPositions) {
        return Number(b.hasPositions) - Number(a.hasPositions)
      }
      // Keep original order for items with same status
      return 0
    })
  }, [investmentRoutes, positionsData, realEstateList])

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
        <h1 className="text-3xl font-bold">
          {t.common.myAssets || t.common.investments}
        </h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
        {sortedRoutes.map(route => (
          <Card
            key={route.path}
            className={`transition-all cursor-pointer relative group overflow-hidden ${
              !route.hasPositions ? "opacity-50" : ""
            } ${route.isDisabled ? "opacity-50" : "hover:shadow-lg"}`}
            onClick={() => navigate(route.path)}
          >
            <div
              className={`absolute top-0 right-0 transition-opacity ${
                route.pinned
                  ? "opacity-100"
                  : "opacity-100 md:opacity-0 md:group-hover:opacity-100"
              }`}
            >
              <div className="h-9 w-9 rounded-full flex items-center justify-center">
                <PinAssetButton
                  assetId={route.assetId}
                  size="icon"
                  className={
                    route.pinned
                      ? "hover:bg-transparent focus-visible:bg-transparent active:bg-transparent rotate-[10deg]"
                      : "text-gray-400 md:text-current hover:bg-transparent focus-visible:bg-transparent active:bg-transparent"
                  }
                />
              </div>
            </div>
            <div
              className={`flex items-center justify-center px-4 py-6 ${route.color}`}
            >
              <div className={route.isDisabled ? "opacity-50" : ""}>
                {route.icon}
              </div>
            </div>
            <div className="flex items-center justify-center px-1 py-2.5 bg-card text-card-foreground">
              <h3 className="text-base font-semibold text-center">
                {route.label}
              </h3>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
