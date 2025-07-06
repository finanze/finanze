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
  Building,
  Coins,
  Bitcoin,
  TrendingUp,
  PiggyBank,
  Gem,
} from "lucide-react"
import { TxType } from "@/types/transactions"
import { ProductType } from "@/types/position"
import { JSX } from "react"

export const ASSET_TYPE_TO_COLOR_MAP: Record<string, string> = {
  STOCK_ETF: "#3b82f6", // Equivalent to text-blue-500
  FUND: "#06b6d4", // Equivalent to text-cyan-500
  REAL_STATE_CF: "#10b981", // Equivalent to text-green-500
  FACTORING: "#f59e0b", // Equivalent to text-amber-500
  DEPOSIT: "#8b5cf6", // Equivalent to text-purple-500
  CASH: "#6b7280", // Equivalent to text-gray-500
  CROWDLENDING: "#ec4899", // Equivalent to text-pink-500
  CRYPTO: "#f97316", // Equivalent to text-orange-500
  COMMODITY: "#eab308", // Equivalent to text-yellow-500
}

export function getPieSliceColorForAssetType(type: string): string {
  return ASSET_TYPE_TO_COLOR_MAP[type] || "#6b7280"
}

export function getIconForProjectType(type: string): JSX.Element {
  switch (type) {
    case "REAL_STATE_CF":
      return <Building className="h-3 w-3" />
    case "FACTORING":
      return <Briefcase className="h-3 w-3" />
    case "DEPOSIT":
      return <DollarSign className="h-3 w-3" />
    default:
      return <DollarSign className="h-3 w-3" />
  }
}

export function getIconForAssetType(type: string): JSX.Element {
  switch (type) {
    case "STOCK_ETF":
      return <BarChart3 className="h-4 w-4 text-blue-500" />
    case "FUND":
      return <BarChart3 className="h-4 w-4 text-cyan-500" />
    case "REAL_STATE_CF":
      return <Building className="h-4 w-4 text-green-500" />
    case "FACTORING":
      return <Briefcase className="h-4 w-4 text-amber-500" />
    case "DEPOSIT":
      return <Landmark className="h-4 w-4 text-purple-500" />
    case "CASH":
      return <Banknote className="h-4 w-4 text-gray-500" />
    case "CROWDLENDING":
      return <Coins className="h-4 w-4 text-pink-500" />
    case "CRYPTO":
      return <Bitcoin className="h-4 w-4 text-orange-500" />
    case "COMMODITY":
      return <Gem className="h-4 w-4 text-yellow-500" />
    default:
      return <Coins className="h-4 w-4 text-gray-500" />
  }
}

// Helper function to get icon for transaction type
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

export function getIconForProductType(
  type: ProductType,
  size: string = "h-3 w-3",
): JSX.Element {
  const iconClass = size
  switch (type) {
    case ProductType.STOCK_ETF:
      return <BarChart3 className={iconClass} />
    case ProductType.FUND:
      return <BarChart3 className={iconClass} />
    case ProductType.REAL_STATE_CF:
      return <Building className={iconClass} />
    case ProductType.FACTORING:
      return <Briefcase className={iconClass} />
    case ProductType.DEPOSIT:
      return <Landmark className={iconClass} />
    case ProductType.ACCOUNT:
      return <Banknote className={iconClass} />
    case ProductType.CROWDLENDING:
      return <Coins className={iconClass} />
    case ProductType.CRYPTO:
      return <Bitcoin className={iconClass} />
    case ProductType.COMMODITY:
      return <Gem className={iconClass} />
    default:
      return <Coins className={iconClass} />
  }
}
