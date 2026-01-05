import React from "react"
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
  CreditCard,
  WalletMinimal,
  FlaskConical,
} from "lucide-react-native"
import { TxType } from "@/domain"

export function getIconForAssetType(
  type: string,
  { color, size = 14 }: { color: string; size?: number },
) {
  const iconProps = { color, size, strokeWidth: 2 }

  switch (type) {
    case "STOCK_ETF":
    case "FUND":
      return <BarChart3 {...iconProps} />
    case "FUND_PORTFOLIO":
      return <WalletMinimal {...iconProps} />
    case "REAL_ESTATE_CF":
      return <Building2 {...iconProps} />
    case "REAL_ESTATE":
      return <House {...iconProps} />
    case "FACTORING":
      return <Briefcase {...iconProps} />
    case "DEPOSIT":
      return <Landmark {...iconProps} />
    case "CASH":
    case "ACCOUNT":
      return <Banknote {...iconProps} />
    case "CROWDLENDING":
      return <Coins {...iconProps} />
    case "CRYPTO":
      return <Bitcoin {...iconProps} />
    case "COMMODITY":
      return <Gem {...iconProps} />
    case "PENDING_FLOWS":
    case "LOAN":
      return <HandCoins {...iconProps} />
    case "BOND":
      return <FileText {...iconProps} />
    case "DERIVATIVE":
      return <FlaskConical {...iconProps} />
    case "CARD":
      return <CreditCard {...iconProps} />
    default:
      return <Coins {...iconProps} />
  }
}

export function getIconForTxType(
  txType: TxType,
  { color, size = 14 }: { color: string; size?: number },
) {
  const iconProps = { color, size, strokeWidth: 2 }

  switch (txType) {
    case TxType.BUY:
      return <TrendingUp {...iconProps} />
    case TxType.SELL:
      return <PiggyBank {...iconProps} />
    case TxType.DIVIDEND:
    case TxType.INTEREST:
      return <Banknote {...iconProps} />
    case TxType.INVESTMENT:
      return <Briefcase {...iconProps} />
    case TxType.RIGHT_ISSUE:
      return <FileText {...iconProps} />
    case TxType.RIGHT_SELL:
    case TxType.FEE:
      return <FileMinus {...iconProps} />
    case TxType.SUBSCRIPTION:
      return <Repeat {...iconProps} />
    case TxType.SWAP_FROM:
    case TxType.SWAP_TO:
      return <ArrowLeftRight {...iconProps} />
    case TxType.TRANSFER_IN:
    case TxType.SWITCH_FROM:
      return <ArrowDownRight {...iconProps} />
    case TxType.TRANSFER_OUT:
    case TxType.SWITCH_TO:
      return <ArrowUpRight {...iconProps} />
    case TxType.REPAYMENT:
      return <Undo {...iconProps} />
    default:
      return <DollarSign {...iconProps} />
  }
}
