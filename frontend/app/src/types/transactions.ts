import { EquityType, FundType, ProductType } from "./position"
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
  equity_type?: EquityType
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
  fund_type?: FundType
}

export interface FundPortfolioTx extends BaseInvestmentTx {
  fees: number
  portfolio_name: string
  iban?: string
}

// Factoring transaction interface
export interface FactoringTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
}

// Real state crowdfunding transaction interface
export interface RealEstateCFTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
}

// Deposit transaction interface
export interface DepositTx extends BaseInvestmentTx {
  net_amount: number
  fees: number
  retentions: number
}

export interface ManualTransactionBasePayload {
  id: string
  ref: string
  name: string
  amount: number
  currency: string
  type: TxType
  date: string
  entity_id: string
  source: DataSource
  product_type: ProductType
}

export interface ManualAccountTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.ACCOUNT
  fees?: number
  retentions?: number
  interest_rate?: number
  avg_balance?: number
}

export interface ManualStockTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.STOCK_ETF
  ticker?: string
  isin?: string
  shares: number
  price: number
  fees?: number
  retentions?: number
  market?: string
  order_date?: string
}

export interface ManualFundTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.FUND
  isin: string
  shares: number
  price: number
  fees?: number
  retentions?: number
  market?: string
  order_date?: string
}

export interface ManualFundPortfolioTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.FUND_PORTFOLIO
  portfolio_name: string
  fees?: number
  iban?: string
}

export interface ManualFactoringTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.FACTORING
  fees?: number
  retentions?: number
}

export interface ManualRealEstateTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.REAL_ESTATE_CF
  fees?: number
  retentions?: number
}

export interface ManualDepositTransactionPayload
  extends ManualTransactionBasePayload {
  product_type: ProductType.DEPOSIT
  fees?: number
  retentions?: number
}

export type ManualTransactionPayload =
  | ManualAccountTransactionPayload
  | ManualStockTransactionPayload
  | ManualFundTransactionPayload
  | ManualFundPortfolioTransactionPayload
  | ManualFactoringTransactionPayload
  | ManualRealEstateTransactionPayload
  | ManualDepositTransactionPayload

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
  historic_entry_id?: string
}
