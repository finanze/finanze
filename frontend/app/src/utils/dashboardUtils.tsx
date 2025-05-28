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
  TrendingUp,
  PiggyBank,
} from "lucide-react"
import { TxType } from "@/types/transactions"
import { JSX } from "react"

// Map asset types to specific colors for consistency between pie chart and legend
export const ASSET_TYPE_TO_COLOR_MAP: Record<string, string> = {
  STOCK_ETF: "#3b82f6", // Equivalent to text-blue-500
  FUND: "#06b6d4", // Equivalent to text-cyan-500
  REAL_STATE_CF: "#10b981", // Equivalent to text-green-500
  FACTORING: "#f59e0b", // Equivalent to text-amber-500
  DEPOSIT: "#8b5cf6", // Equivalent to text-purple-500
  CASH: "#6b7280", // Equivalent to text-gray-500
  CROWDLENDING: "#ec4899", // Equivalent to text-pink-500
}

// Helper function to get color for pie chart slice based on asset type
export function getPieSliceColorForAssetType(type: string): string {
  return ASSET_TYPE_TO_COLOR_MAP[type] || "#6b7280"
}

// Helper function to get icon for project type
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

// Helper function to get icon for asset type
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
    default:
      return <Coins className="h-4 w-4 text-gray-500" />
  }
}

// Helper function to get icon for transaction type
export const getIconForTxType = (txType: TxType) => {
  switch (txType) {
    case TxType.BUY:
      return <TrendingUp className="h-full w-full" />
    case TxType.SELL:
      return <PiggyBank className="h-full w-full" />
    case TxType.DIVIDEND:
      return <Banknote className="h-full w-full" /> // Changed from Landmark
    case TxType.INTEREST:
      return <Banknote className="h-full w-full" /> // Changed from Landmark
    case TxType.INVESTMENT:
      return <Briefcase className="h-full w-full" />
    case TxType.RIGHT_ISSUE:
      return <FileText className="h-full w-full" />
    case TxType.RIGHT_SELL:
      return <FileMinus className="h-full w-full" />
    case TxType.SUBSCRIPTION:
      return <Repeat className="h-full w-full" />
    case TxType.SWAP_FROM:
    case TxType.SWAP_TO:
      return <ArrowLeftRight className="h-full w-full" />
    case TxType.REPAYMENT:
      return <Undo className="h-full w-full" />
    default:
      return <DollarSign className="h-full w-full" />
  }
}
