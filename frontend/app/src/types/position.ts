export enum ProductType {
  ACCOUNT = "ACCOUNT",
  CARD = "CARD",
  LOAN = "LOAN",
  STOCK_ETF = "STOCK_ETF",
  FUND = "FUND",
  FUND_PORTFOLIO = "FUND_PORTFOLIO",
  DEPOSIT = "DEPOSIT",
  FACTORING = "FACTORING",
  REAL_ESTATE_CF = "REAL_ESTATE_CF",
  CROWDLENDING = "CROWDLENDING",
  CRYPTO = "CRYPTO",
  COMMODITY = "COMMODITY",
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

export enum InterestType {
  FIXED = "FIXED",
  VARIABLE = "VARIABLE",
  MIXED = "MIXED",
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
  interest_type: InterestType
  euribor_rate?: number | null
  fixed_years?: number | null
  name?: string | null
  creation?: string | null
  maturity?: string | null
  unpaid?: number | null
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

export interface RealEstateCFDetail {
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

export interface RealEstateCFInvestments {
  entries: RealEstateCFDetail[]
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

export enum CommodityType {
  GOLD = "GOLD",
  SILVER = "SILVER",
  PLATINUM = "PLATINUM",
  PALLADIUM = "PALLADIUM",
}

export enum WeightUnit {
  GRAM = "GRAM",
  TROY_OUNCE = "TROY_OUNCE",
}

export const COMMODITY_SYMBOLS = {
  [CommodityType.GOLD]: "XAU",
  [CommodityType.SILVER]: "XAG",
  [CommodityType.PLATINUM]: "XPT",
  [CommodityType.PALLADIUM]: "XPD",
}

export const WEIGHT_CONVERSIONS: Record<
  WeightUnit,
  Record<WeightUnit, number>
> = {
  [WeightUnit.GRAM]: {
    [WeightUnit.TROY_OUNCE]: 0.032150746568628,
    [WeightUnit.GRAM]: 1,
  },
  [WeightUnit.TROY_OUNCE]: {
    [WeightUnit.GRAM]: 31.1034768,
    [WeightUnit.TROY_OUNCE]: 1,
  },
}

export interface Commodity {
  id: string
  name: string
  amount: number
  unit: WeightUnit
  type: CommodityType
  initial_investment?: number | null
  average_buy_price?: number | null
  market_value?: number | null
  currency?: string | null
}

export interface Commodities {
  entries: Commodity[]
}

export type ProductPosition =
  | Accounts
  | Cards
  | Loans
  | StockInvestments
  | FundInvestments
  | FundPortfolios
  | FactoringInvestments
  | RealEstateCFInvestments
  | Deposits
  | Crowdlending
  | CryptoCurrencies
  | Commodities

export type ProductPositions = Record<ProductType, ProductPosition>

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
