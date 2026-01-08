import { Entity } from "./entity"
import { DataSource } from "./fetchRecord"
import { EquityType, FundType, ProductType } from "./globalPosition"
import { Dezimal } from "@/domain/dezimal"

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

export interface BaseTx {
  id: string | null
  ref: string
  name: string
  amount: Dezimal
  currency: string
  type: TxType
  date: string
  entity: Entity
  source: DataSource
  productType: ProductType
}

export interface BaseInvestmentTx extends BaseTx {}

export interface AccountTx extends BaseTx {
  fees: Dezimal
  retentions: Dezimal
  interestRate?: Dezimal | null
  avgBalance?: Dezimal | null
  netAmount?: Dezimal | null
}

export interface StockTx extends BaseInvestmentTx {
  shares: Dezimal
  price: Dezimal
  fees: Dezimal
  netAmount?: Dezimal | null
  isin?: string | null
  ticker?: string | null
  market?: string | null
  retentions?: Dezimal | null
  orderDate?: string | null
  linkedTx?: string | null
  equityType?: EquityType | null
}

export interface CryptoCurrencyTx extends BaseInvestmentTx {
  currencyAmount: Dezimal
  symbol: string
  price: Dezimal
  fees: Dezimal
  contractAddress?: string | null
  netAmount?: Dezimal | null
  retentions?: Dezimal | null
  orderDate?: string | null
}

export interface FundTx extends BaseInvestmentTx {
  shares: Dezimal
  price: Dezimal
  fees: Dezimal
  netAmount?: Dezimal | null
  isin?: string | null
  market?: string | null
  retentions?: Dezimal | null
  orderDate?: string | null
  fundType?: FundType | null
}

export interface FundPortfolioTx extends BaseInvestmentTx {
  portfolioName: string
  iban?: string | null
  fees?: Dezimal
}

export interface FactoringTx extends BaseInvestmentTx {
  fees: Dezimal
  retentions: Dezimal
  netAmount?: Dezimal | null
}

export interface RealEstateCFTx extends BaseInvestmentTx {
  fees: Dezimal
  retentions: Dezimal
  netAmount?: Dezimal | null
}

export interface DepositTx extends BaseInvestmentTx {
  fees: Dezimal
  retentions: Dezimal
  netAmount?: Dezimal | null
}

export interface Transactions {
  investment?: BaseInvestmentTx[] | null
  account?: AccountTx[] | null
}

export interface TransactionsResult {
  transactions: BaseTx[]
}

export interface TransactionQueryRequest {
  page?: number
  limit?: number
  entities?: string[] | null
  excludedEntities?: string[] | null
  productTypes?: ProductType[] | null
  fromDate?: string | null
  toDate?: string | null
  types?: TxType[] | null
  historicEntryId?: string | null
}
