import {
  Landmark,
  Briefcase,
  Banknote,
  DollarSign,
  FileText,
  FileMinus,
  Repeat,
  ArrowLeftRight,
  Undo,
  BarChart3,
  Coins,
  Bitcoin,
  TrendingUp,
  PiggyBank,
  Gem,
  HandCoins,
  Building2,
  House,
} from "lucide-react"
import { TxType } from "@/types/transactions"
import { ProductType } from "@/types/position"
import { JSX } from "react"

export const ASSET_TYPE_TO_COLOR_MAP: Record<string, string> = {
  STOCK_ETF: "#3b82f6", // Equivalent to text-blue-500
  FUND: "#06b6d4", // Equivalent to text-cyan-500
  REAL_ESTATE_CF: "#10b981", // Equivalent to text-green-500
  REAL_ESTATE: "#059669", // Tailwind emerald-600
  FACTORING: "#f59e0b", // Equivalent to text-amber-500
  DEPOSIT: "#8b5cf6", // Equivalent to text-purple-500
  CASH: "#6b7280", // Equivalent to text-gray-500
  CROWDLENDING: "#ec4899", // Equivalent to text-pink-500
  CRYPTO: "#f97316", // Equivalent to text-orange-500
  COMMODITY: "#eab308", // Equivalent to text-yellow-500
  PENDING_FLOWS: "#14b8a6", // Equivalent to text-teal-500
}

export function getPieSliceColorForAssetType(type: string): string {
  return ASSET_TYPE_TO_COLOR_MAP[type] || "#6b7280"
}

export function getIconForAssetType(
  type: string,
  size: string = "h-4 w-4",
  color: string | null = null,
): JSX.Element {
  switch (type) {
    case "STOCK_ETF":
      return <BarChart3 className={`${size} ${color ?? "text-blue-500"}`} />
    case "FUND":
      return <BarChart3 className={`${size} ${color ?? "text-cyan-500"}`} />
    case "REAL_ESTATE_CF":
      return <Building2 className={`${size} ${color ?? "text-green-500"}`} />
    case "REAL_ESTATE":
      return <House className={`${size} ${color ?? "text-emerald-600"}`} />
    case "FACTORING":
      return <Briefcase className={`${size} ${color ?? "text-amber-500"}`} />
    case "DEPOSIT":
      return <Landmark className={`${size} ${color ?? "text-purple-500"}`} />
    case "CASH":
      return <Banknote className={`${size} ${color ?? "text-gray-500"}`} />
    case "CROWDLENDING":
      return <Coins className={`${size} ${color ?? "text-pink-500"}`} />
    case "CRYPTO":
      return <Bitcoin className={`${size} ${color ?? "text-orange-500"}`} />
    case "COMMODITY":
      return <Gem className={`${size} ${color ?? "text-yellow-500"}`} />
    case "PENDING_FLOWS":
      return <HandCoins className={`${size} ${color ?? "text-teal-500"}`} />
    default:
      return <Coins className={`${size} ${color ?? "text-gray-500"}`} />
  }
}

export function getIconForProductType(
  type: ProductType,
  size: string = "h-3 w-3",
): JSX.Element {
  return getIconForAssetType(type, size, "")
}

export const getIconForTxType = (txType: TxType, size: string = "h-4 w-4") => {
  const iconClass = size
  switch (txType) {
    case TxType.BUY:
      return <TrendingUp className={iconClass} />
    case TxType.SELL:
      return <PiggyBank className={iconClass} />
    case TxType.DIVIDEND:
      return <Banknote className={iconClass} />
    case TxType.INTEREST:
      return <Banknote className={iconClass} />
    case TxType.INVESTMENT:
      return <Briefcase className={iconClass} />
    case TxType.RIGHT_ISSUE:
      return <FileText className={iconClass} />
    case TxType.RIGHT_SELL:
      return <FileMinus className={iconClass} />
    case TxType.SUBSCRIPTION:
      return <Repeat className={iconClass} />
    case TxType.SWAP_FROM:
    case TxType.SWAP_TO:
      return <ArrowLeftRight className={iconClass} />
    case TxType.REPAYMENT:
      return <Undo className={iconClass} />
    default:
      return <DollarSign className={iconClass} />
  }
}
