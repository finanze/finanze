import { ProductType } from "./position"
import { DataSource, EntityOrigin } from "."

export enum TxType {
  BUY = "BUY",
  SELL = "SELL",
  DIVIDEND = "DIVIDEND",
  RIGHT_ISSUE = "RIGHT_ISSUE",
  RIGHT_SELL = "RIGHT_SELL",
  SUBSCRIPTION = "SUBSCRIPTION",
  SWAP_FROM = "SWAP_FROM",
  SWAP_TO = "SWAP_TO",

  TRANSFER_IN = "TRANSFER_IN",
  TRANSFER_OUT = "TRANSFER_OUT",
  SWITCH_FROM = "SWITCH_FROM",
  SWITCH_TO = "SWITCH_TO",

  INVESTMENT = "INVESTMENT",
  REPAYMENT = "REPAYMENT",
  INTEREST = "INTEREST",

  FEE = "FEE",
}

// Base transaction interface
export interface BaseTx {
  id: string
  ref: string
  name: string
  amount: number
  currency: string
  type: TxType
  date: string
  entity: {
    id: string
    name: string
    origin: EntityOrigin
  }
  source: DataSource
  product_type: ProductType
}

// Base investment transaction interface
export type BaseInvestmentTx = BaseTx

// Account transaction interface
export interface AccountTx extends BaseTx {
  fees: number
  retentions: number
  interest_rate?: number
  avg_balance?: number
  net_amount?: number
}

// Stock transaction interface
export interface StockTx extends BaseInvestmentTx {
  net_amount: number
  isin?: string
  shares: number
  price: number
  fees: number
  ticker?: string
  market?: string
  retentions?: number
  order_date?: string
  linked_tx?: string
}

// Fund transaction interface
export interface FundTx extends BaseInvestmentTx {
  net_amount: number
  isin: string
  shares: number
  price: number
  market: string
  fees: number
  retentions?: number
  order_date?: string
}

export interface FundPortfolioTx extends BaseInvestmentTx {
  fees: number
  iban?: string
}

// Factoring transaction interface
export interface FactoringTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
  interests: number
}

// Real state crowdfunding transaction interface
export interface RealEstateCFTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
  interests: number
}

// Deposit transaction interface
export interface DepositTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
  interests: number
}

export type ManualTransactionPayload =
  | AccountTx
  | StockTx
  | FundTx
  | FundPortfolioTx
  | FactoringTx
  | RealEstateCFTx
  | DepositTx

// Transactions container
export interface Transactions {
  investment?: BaseInvestmentTx[]
  account?: AccountTx[]
}

type Tx = AccountTx &
  StockTx &
  FundTx &
  FactoringTx &
  RealEstateCFTx &
  DepositTx

// Transaction query result
export interface TransactionsResult {
  transactions: Tx[]
}

// Transaction query request
export interface TransactionQueryRequest {
  page?: number
  limit?: number
  entities?: string[]
  excluded_entities?: string[]
  product_types?: ProductType[]
  from_date?: string
  to_date?: string
  types?: TxType[]
}
