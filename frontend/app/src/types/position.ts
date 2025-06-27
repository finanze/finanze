export enum ProductType {
  ACCOUNT = "ACCOUNT",
  CARD = "CARD",
  LOAN = "LOAN",
  STOCK_ETF = "STOCK_ETF",
  FUND = "FUND",
  FUND_PORTFOLIO = "FUND_PORTFOLIO",
  DEPOSIT = "DEPOSIT",
  FACTORING = "FACTORING",
  REAL_STATE_CF = "REAL_STATE_CF",
  CROWDLENDING = "CROWDLENDING",
  CRYPTO = "CRYPTO",
}

export enum AccountType {
  CHECKING = "CHECKING",
  VIRTUAL_WALLET = "VIRTUAL_WALLET",
  BROKERAGE = "BROKERAGE",
  SAVINGS = "SAVINGS",
  FUND_PORTFOLIO = "FUND_PORTFOLIO",
}

export enum CardType {
  CREDIT = "CREDIT",
  DEBIT = "DEBIT",
}

export enum LoanType {
  MORTGAGE = "MORTGAGE",
  STANDARD = "STANDARD",
}

export interface Account {
  id: string
  total: number
  currency: string
  type: AccountType
  name?: string | null
  iban?: string | null
  interest?: number | null
  retained?: number | null
  pending_transfers?: number | null
}

export interface Card {
  id: string
  currency: string
  type: CardType
  used: number
  active: boolean
  limit?: number | null
  name?: string | null
  ending?: string | null
  related_account?: string | null
}

export interface Loan {
  id: string
  type: LoanType
  currency: string
  current_installment: number
  interest_rate: number
  loan_amount: number
  next_payment_date: string
  principal_outstanding: number
  principal_paid: number
  name?: string | null
}

export interface StockDetail {
  id: string
  name: string
  ticker: string
  isin: string
  market: string
  shares: number
  initial_investment: number
  average_buy_price: number
  market_value: number
  currency: string
  type: string
  subtype?: string | null
}

export interface FundPortfolio {
  id: string
  name?: string | null
  currency?: string | null
  initial_investment?: number | null
  market_value?: number | null
}

export interface FundDetail {
  id: string
  name: string
  isin: string
  market: string
  shares: number
  initial_investment: number
  average_buy_price: number
  market_value: number
  currency: string
  portfolio?: FundPortfolio | null
}

export interface FactoringDetail {
  id: string
  name: string
  amount: number
  currency: string
  interest_rate: number
  gross_interest_rate: number
  last_invest_date: string
  maturity: string
  type: string
  state: string
}

export interface RealStateCFDetail {
  id: string
  name: string
  amount: number
  pending_amount: number
  currency: string
  interest_rate: number
  last_invest_date: string
  maturity: string
  type: string
  business_type: string
  state: string
  extended_maturity?: string | null
}

export interface Accounts {
  entries: Account[]
}

export interface Cards {
  entries: Card[]
}

export interface Loans {
  entries: Loan[]
}

export interface StockInvestments {
  entries: StockDetail[]
}

export interface FundInvestments {
  entries: FundDetail[]
}

export interface FundPortfolios {
  entries: FundPortfolio[]
}

export interface FactoringInvestments {
  entries: FactoringDetail[]
}

export interface RealStateCFInvestments {
  entries: RealStateCFDetail[]
}

export interface Deposit {
  id: string
  name: string
  amount: number
  currency: string
  expected_interests: number
  interest_rate: number
  creation: string
  maturity: string
}

export interface Deposits {
  entries: Deposit[]
}

export interface Crowdlending {
  id: string
  total: number
  weighted_interest_rate: number
  currency: string
  distribution: any
  entries: any[]
}

export interface CryptoCurrencyToken {
  id: string
  token_id: string
  name: string
  symbol: string
  token: string
  amount: number
  initial_investment?: number | null
  average_buy_price?: number | null
  market_value?: number | null
  currency?: string | null
  type?: string | null
}

export interface CryptoCurrencyWallet {
  id: string
  wallet_connection_id: string
  address: string
  name: string
  symbol: string
  crypto: string
  amount: number
  initial_investment?: number | null
  average_buy_price?: number | null
  market_value?: number | null
  currency?: string | null
  tokens?: CryptoCurrencyToken[] | null
}

export interface CryptoCurrencies {
  entries: CryptoCurrencyWallet[]
}

export type ProductPosition =
  | Accounts
  | Cards
  | Loans
  | StockInvestments
  | FundInvestments
  | FundPortfolios
  | FactoringInvestments
  | RealStateCFInvestments
  | Deposits
  | Crowdlending
  | CryptoCurrencies

export type ProductPositions = Record<ProductType, ProductPosition>

export interface Investments {
  stocks?: StockInvestments | null
  funds?: FundInvestments | null
  fund_portfolios: FundPortfolio[]
  factoring?: FactoringInvestments | null
  real_state_cf?: RealStateCFInvestments | null
  deposits?: Deposits | null
  crowdlending?: Crowdlending | null
  crypto_currencies?: CryptoCurrencies | null
}

export interface EntitySummary {
  id: string
  name: string
  is_real: boolean
}

export interface GlobalPosition {
  id: string
  entity: EntitySummary
  date: string
  products: ProductPositions
  is_real: boolean
}

export interface EntitiesPosition {
  positions: Record<string, GlobalPosition>
}

// Position query request
export interface PositionQueryRequest {
  entities?: string[] // Add entities filter
  excluded_entities?: string[]
}
