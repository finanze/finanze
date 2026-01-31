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
  ArrowDownRight,
  ArrowUpRight,
  Wallet,
  CreditCard,
  WalletMinimal,
  FlaskConical,
} from "lucide-react"
import { TxType } from "@/types/transactions"
import { AccountType, ProductType } from "@/types/position"
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
  const hasHexColor = Boolean(color && color.startsWith("#"))
  const hasCustomClass = Boolean(color && !hasHexColor && color !== "")
  const useDefaultColor = color == null

  const getIconClass = (defaultClass: string) =>
    `${size} ${useDefaultColor ? defaultClass : hasCustomClass ? color : ""}`

  const hexColor = hasHexColor ? (color as string) : undefined
  const iconStyle = hexColor ? { color: hexColor } : undefined

  switch (type) {
    case "STOCK_ETF":
      return (
        <BarChart3
          className={getIconClass("text-blue-500")}
          style={iconStyle}
        />
      )
    case "FUND":
      return (
        <BarChart3
          className={getIconClass("text-cyan-500")}
          style={iconStyle}
        />
      )
    case "FUND_PORTFOLIO":
      return (
        <WalletMinimal
          className={getIconClass("text-fuchsia-500")}
          style={iconStyle}
        />
      )
    case "REAL_ESTATE_CF":
      return (
        <Building2
          className={getIconClass("text-green-500")}
          style={iconStyle}
        />
      )
    case "REAL_ESTATE":
      return (
        <House className={getIconClass("text-emerald-600")} style={iconStyle} />
      )
    case "FACTORING":
      return (
        <Briefcase
          className={getIconClass("text-amber-500")}
          style={iconStyle}
        />
      )
    case "DEPOSIT":
      return (
        <Landmark
          className={getIconClass("text-purple-500")}
          style={iconStyle}
        />
      )
    case "CASH":
    case "ACCOUNT":
      return (
        <Banknote className={getIconClass("text-gray-500")} style={iconStyle} />
      )
    case "CROWDLENDING":
      return (
        <Coins className={getIconClass("text-pink-500")} style={iconStyle} />
      )
    case "CRYPTO":
      return (
        <Bitcoin
          className={getIconClass("text-orange-500")}
          style={iconStyle}
        />
      )
    case "COMMODITY":
      return (
        <Gem className={getIconClass("text-yellow-500")} style={iconStyle} />
      )
    case "PENDING_FLOWS":
      return (
        <HandCoins
          className={getIconClass("text-teal-500")}
          style={iconStyle}
        />
      )
    case "BOND":
      return (
        <FileText
          className={getIconClass("text-indigo-500")}
          style={iconStyle}
        />
      )
    case "DERIVATIVE":
      return (
        <FlaskConical
          className={getIconClass("text-brown-500")}
          style={iconStyle}
        />
      )
    case "CARD":
      return (
        <CreditCard
          className={getIconClass("text-orange-500")}
          style={iconStyle}
        />
      )
    case "LOAN":
      return (
        <HandCoins
          className={getIconClass("text-teal-500")}
          style={iconStyle}
        />
      )
    default:
      return (
        <Coins className={getIconClass("text-gray-500")} style={iconStyle} />
      )
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
    case TxType.TRANSFER_IN:
    case TxType.SWITCH_FROM:
      return <ArrowDownRight className={iconClass} />
    case TxType.TRANSFER_OUT:
    case TxType.SWITCH_TO:
      return <ArrowUpRight className={iconClass} />
    case TxType.REPAYMENT:
      return <Undo className={iconClass} />
    case TxType.FEE:
      return <FileMinus className={iconClass} />
    default:
      return <DollarSign className={iconClass} />
  }
}

export const getProductTypeColor = (type: ProductType): string => {
  switch (type) {
    case ProductType.STOCK_ETF:
      return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100"
    case ProductType.FUND:
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
    case ProductType.CRYPTO:
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
    case ProductType.ACCOUNT:
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
    case ProductType.DEPOSIT:
      return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100"
    case ProductType.FACTORING:
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100"
    case ProductType.REAL_ESTATE_CF:
      return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100"
    case ProductType.FUND_PORTFOLIO:
      return "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100"
    case ProductType.BOND:
      return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
    case ProductType.DERIVATIVE:
      return "bg-brown-100 text-brown-800 dark:bg-brown-900 dark:text-brown-100"
    case ProductType.CARD:
      return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
    case ProductType.LOAN:
      return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100"
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
  }
}

export const getAccountTypeIcon = (type: AccountType) => {
  switch (type) {
    case AccountType.CHECKING:
      return <Wallet className="h-4 w-4" />
    case AccountType.SAVINGS:
      return <Building2 className="h-4 w-4" />
    case AccountType.BROKERAGE:
      return <TrendingUp className="h-4 w-4" />
    case AccountType.VIRTUAL_WALLET:
      return <CreditCard className="h-4 w-4" />
    case AccountType.FUND_PORTFOLIO:
      return <TrendingUp className="h-4 w-4" />
    default:
      return <Wallet className="h-4 w-4" />
  }
}

export const getAccountTypeColor = (type: AccountType) => {
  switch (type) {
    case AccountType.CHECKING:
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
    case AccountType.SAVINGS:
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
    case AccountType.BROKERAGE:
      return "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
    case AccountType.VIRTUAL_WALLET:
      return "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
    case AccountType.FUND_PORTFOLIO:
      return "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400"
    default:
      return "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400"
  }
}
