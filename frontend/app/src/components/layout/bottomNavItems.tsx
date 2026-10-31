import { useMemo, type ReactNode } from "react"
import {
  LayoutDashboard,
  TrendingUp,
  ArrowLeftRight,
  Calculator,
  Wallet,
  Blocks,
  Settings,
  FileUp,
  ChartPie,
  CalendarSync,
  HandCoins,
  type LucideIcon,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { ProductType } from "@/types/position"
import { getIconForProductType } from "@/utils/dashboardUtils"
import type { BottomNavItemId } from "@/context/BottomNavContext"

export interface BottomNavEntry {
  path: string
  label: string
  group: "main" | "assets" | "money"
  renderIcon: (className: string) => ReactNode
}

export function useBottomNavCatalog(): Record<BottomNavItemId, BottomNavEntry> {
  const { t } = useI18n()
  return useMemo(() => {
    const route = (
      path: string,
      label: string,
      Icon: LucideIcon,
      group: BottomNavEntry["group"] = "main",
    ): BottomNavEntry => ({
      path,
      label,
      group,
      renderIcon: className => <Icon className={className} />,
    })
    const asset = (
      path: string,
      label: string,
      product: ProductType,
    ): BottomNavEntry => ({
      path,
      label,
      group: "assets",
      renderIcon: className => getIconForProductType(product, className),
    })
    return {
      dashboard: route("/", t.common.dashboard, LayoutDashboard),
      investments: route("/investments", t.common.investments, TrendingUp),
      transactions: route(
        "/transactions",
        t.common.transactions,
        ArrowLeftRight,
      ),
      calculations: route("/calculations", t.calculations.title, Calculator),
      management: route("/management", t.management.title, Wallet),
      entities: route("/entities", t.entities.title, Blocks),
      settings: route("/settings", t.common.settings, Settings),
      export: route("/export", t.export.title, FileUp),
      banking: asset("/banking", t.banking.title, ProductType.ACCOUNT),
      "stocks-etfs": asset(
        "/investments/stocks-etfs",
        t.common.stocksEtfs,
        ProductType.STOCK_ETF,
      ),
      funds: asset(
        "/investments/funds",
        t.common.fundsInvestments,
        ProductType.FUND,
      ),
      deposits: asset(
        "/investments/deposits",
        t.common.depositsInvestments,
        ProductType.DEPOSIT,
      ),
      factoring: asset(
        "/investments/factoring",
        t.common.factoringInvestments,
        ProductType.FACTORING,
      ),
      "real-estate-cf": asset(
        "/investments/real-estate-cf",
        t.common.realEstateCfInvestments,
        ProductType.REAL_ESTATE_CF,
      ),
      crypto: asset(
        "/investments/crypto",
        t.common.cryptoInvestments,
        ProductType.CRYPTO,
      ),
      "market-forecast": asset(
        "/investments/market-forecast",
        t.common.marketForecast,
        ProductType.MARKET_FORECAST,
      ),
      commodities: asset(
        "/investments/commodities",
        t.common.commodities,
        ProductType.COMMODITY,
      ),
      "real-estate": asset(
        "/real-estate",
        t.realEstate.title,
        ProductType.REAL_ESTATE,
      ),
      "management-cashflow": route(
        "/management/cashflow",
        t.management.cashflow,
        ChartPie,
        "money",
      ),
      "management-recurring": route(
        "/management/recurring",
        t.management.recurringMoney,
        CalendarSync,
        "money",
      ),
      "management-pending": route(
        "/management/pending",
        t.management.pendingMoney,
        HandCoins,
        "money",
      ),
    }
  }, [t])
}

export function getActiveBottomNavId(
  pathname: string,
  bar: BottomNavItemId[],
  menu: BottomNavItemId[],
  catalog: Record<BottomNavItemId, BottomNavEntry>,
): BottomNavItemId | "more" {
  const match = [...bar, ...menu]
    .filter(
      id =>
        pathname === catalog[id].path ||
        (catalog[id].path !== "/" &&
          pathname.startsWith(`${catalog[id].path}/`)),
    )
    .sort(
      (first, second) =>
        catalog[second].path.length - catalog[first].path.length,
    )[0]
  if (match) return match
  if (
    bar.includes("investments") &&
    ["/banking", "/investments", "/real-estate"].some(
      path => pathname === path || pathname.startsWith(`${path}/`),
    )
  )
    return "investments"
  return "more"
}
