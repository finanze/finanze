import { DataSource, EntityOrigin } from "."

export interface ManualEntryData {
  tracker_key?: string | null
}

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
  REAL_ESTATE = "REAL_ESTATE",
  CROWDLENDING = "CROWDLENDING",
  CRYPTO = "CRYPTO",
  COMMODITY = "COMMODITY",
  BOND = "BOND",
  DERIVATIVE = "DERIVATIVE",
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
  source: DataSource
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
  source: DataSource
}

export interface Loan {
  id: string
  type: LoanType
  currency: string
  current_installment: number
  interest_rate: number
  loan_amount: number
  next_payment_date?: string | null
  principal_outstanding: number
  principal_paid: number | null
  interest_type: InterestType
  euribor_rate?: number | null
  fixed_years?: number | null
  name?: string | null
  creation: string
  maturity: string
  unpaid?: number | null
  source: DataSource
}

export enum EquityType {
  STOCK = "STOCK",
  ETF = "ETF",
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
  type: EquityType
  subtype?: string | null
  info_sheet_url?: string | null
  manual_data?: ManualEntryData | null
  source: DataSource
}

export interface FundPortfolio {
  id: string
  name?: string | null
  currency?: string | null
  initial_investment?: number | null
  market_value?: number | null
  account?: Account | null
  account_id?: string | null
  source: DataSource
}

export enum AssetType {
  EQUITY = "EQUITY",
  FIXED_INCOME = "FIXED_INCOME",
  MONEY_MARKET = "MONEY_MARKET",
  MIXED = "MIXED",
  OTHER = "OTHER",
}

export enum FundType {
  MUTUAL_FUND = "MUTUAL_FUND",
  PRIVATE_EQUITY = "PRIVATE_EQUITY",
  PENSION_FUND = "PENSION_FUND",
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
  type: FundType
  asset_type?: AssetType | null
  currency: string
  portfolio?: FundPortfolio | null
  info_sheet_url?: string | null
  manual_data?: ManualEntryData | null
  source: DataSource
}

export interface FactoringDetail {
  id: string
  name: string
  amount: number
  currency: string
  interest_rate: number
  late_interest_rate: number
  profitability: number
  gross_interest_rate: number
  gross_late_interest_rate?: number | null
  start: string
  last_invest_date: string
  maturity: string
  type: string
  state: string
  source: DataSource
}

export interface RealEstateCFDetail {
  id: string
  name: string
  amount: number
  pending_amount: number
  currency: string
  interest_rate: number
  profitability: number
  start: string
  last_invest_date: string
  maturity: string
  type: string
  business_type: string
  state: string
  extended_maturity?: string | null
  extended_interest_rate?: number | null
  source: DataSource
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
  source: DataSource
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

export enum CryptoCurrencyType {
  NATIVE = "NATIVE",
  TOKEN = "TOKEN",
}

export interface CryptoAsset {
  id: string
  name: string
  symbol: string
  icon_urls?: string[] | null
  external_ids?: Record<string, string> | null
}

export interface CryptoCurrencyPosition {
  id: string
  name: string
  symbol: string
  amount: number
  type: CryptoCurrencyType
  crypto_asset?: CryptoAsset | null
  contract_address?: string | null
  market_value?: number | null
  currency?: string | null
  initial_investment?: number | null
  average_buy_price?: number | null
  investment_currency?: string | null
  source: DataSource
}

export interface CryptoCurrencyWallet {
  id?: string | null
  address?: string | null
  name?: string | null
  assets?: CryptoCurrencyPosition[] | null
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
export type PartialProductPositions = Partial<
  Record<ProductType, ProductPosition>
>

export interface EntitySummary {
  id: string
  name: string
  origin: EntityOrigin
}

export interface GlobalPosition {
  id: string
  entity: EntitySummary
  date: string
  products: ProductPositions
  source: DataSource
}

export interface EntitiesPosition {
  positions: Record<string, GlobalPosition>
}

export interface PositionQueryRequest {
  entities?: string[]
}

export interface UpdatePositionRequest {
  entity_id?: string | null
  new_entity_name?: string | null
  new_entity_icon_url?: string | null
  net_crypto_entity_details?: {
    provider_asset_id: string
    provider: string
  } | null
  products: PartialProductPositions
}
