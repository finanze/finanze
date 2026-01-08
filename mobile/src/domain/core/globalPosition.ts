import { CommodityRegister } from "./commodity"
import { CryptoAsset, CryptoCurrencyType } from "./crypto"
import { Entity } from "./entity"
import { ExternalIntegrationId } from "./externalIntegration"
import { DataSource } from "./fetchRecord"
import { Dezimal } from "@/domain/dezimal"

export interface ManualEntryData {
  trackerKey?: string | null
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

export interface Account {
  id: string | null
  total: Dezimal
  currency: string
  type: AccountType
  name?: string | null
  iban?: string | null
  interest?: Dezimal | null
  retained?: Dezimal | null
  pendingTransfers?: Dezimal | null
  source?: DataSource
}

export enum CardType {
  CREDIT = "CREDIT",
  DEBIT = "DEBIT",
}

export interface Card {
  id: string | null
  currency: string
  type: CardType
  used: Dezimal
  active?: boolean
  limit?: Dezimal | null
  name?: string | null
  ending?: string | number | null
  relatedAccount?: string | null
  source?: DataSource
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

export interface Loan {
  id: string | null
  type: LoanType
  currency: string
  currentInstallment: Dezimal
  interestRate: Dezimal
  loanAmount: Dezimal
  creation: string
  maturity: string
  principalOutstanding: Dezimal
  principalPaid?: Dezimal | null
  interestType?: InterestType
  nextPaymentDate?: string | null
  euriborRate?: Dezimal | null
  fixedYears?: number | null
  name?: string | null
  unpaid?: Dezimal | null
  source?: DataSource
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

export enum EquityType {
  STOCK = "STOCK",
  ETF = "ETF",
}

export interface StockDetail {
  id: string | null
  name: string
  ticker: string
  isin: string
  shares: Dezimal
  marketValue: Dezimal
  currency: string
  type: EquityType
  initialInvestment?: Dezimal | null
  averageBuyPrice?: Dezimal | null
  market?: string
  subtype?: string | null
  infoSheetUrl?: string | null
  manualData?: ManualEntryData | null
  source?: DataSource
}

export interface FundPortfolio {
  id: string | null
  name?: string | null
  currency?: string | null
  initialInvestment?: Dezimal | null
  marketValue?: Dezimal | null
  accountId?: string | null
  account?: Account | null
  source?: DataSource
}

export interface FundDetail {
  id: string | null
  name: string
  isin: string
  market: string | null
  shares: Dezimal
  marketValue: Dezimal
  currency: string
  type: FundType
  initialInvestment?: Dezimal | null
  averageBuyPrice?: Dezimal | null
  assetType?: AssetType | null
  portfolio?: FundPortfolio | null
  infoSheetUrl?: string | null
  manualData?: ManualEntryData | null
  source?: DataSource
}

export interface FactoringDetail {
  id: string | null
  name: string
  amount: Dezimal
  currency: string
  interestRate: Dezimal
  start: string
  maturity: string
  type: string
  state: string
  lastInvestDate?: string | null
  profitability?: Dezimal | null
  lateInterestRate?: Dezimal | null
  grossInterestRate?: Dezimal | null
  grossLateInterestRate?: Dezimal | null
  source?: DataSource
}

export interface RealEstateCFDetail {
  id: string | null
  name: string
  amount: Dezimal
  pendingAmount: Dezimal
  currency: string
  interestRate: Dezimal
  start: string
  maturity: string
  type: string
  state: string
  businessType?: string
  lastInvestDate?: string | null
  profitability?: Dezimal | null
  extendedMaturity?: string | null
  extendedInterestRate?: Dezimal | null
  source?: DataSource
}

export interface Deposit {
  id: string | null
  name: string
  amount: Dezimal
  currency: string
  interestRate: Dezimal
  creation: string
  maturity: string
  expectedInterests?: Dezimal | null
  source?: DataSource
}

export interface CryptoCurrencyPosition {
  id: string | null
  symbol: string
  amount: Dezimal
  type: CryptoCurrencyType
  name?: string | null
  cryptoAsset?: CryptoAsset | null
  marketValue?: Dezimal | null
  currency?: string | null
  contractAddress?: string | null
  initialInvestment?: Dezimal | null
  averageBuyPrice?: Dezimal | null
  investmentCurrency?: string | null
  walletAddress?: string | null
  walletName?: string | null
  source?: DataSource
}

export interface CryptoCurrencyWallet {
  id?: string | null
  address?: string | null
  name?: string | null
  assets?: CryptoCurrencyPosition[]
}

export enum CryptoInitialInvestmentType {
  CRYPTO = "CRYPTO",
  TOKEN = "TOKEN",
}

export interface CryptoInitialInvestment {
  walletConnectionId: string
  symbol: string
  type: CryptoInitialInvestmentType
  initialInvestment: Dezimal | null
  averageBuyPrice: Dezimal | null
  investmentCurrency: string
  currency: string
}

export interface Commodity extends CommodityRegister {
  id?: string
}

export interface Crowdlending {
  id: string
  total: Dezimal | null
  weightedInterestRate: Dezimal | null
  currency: string
  distribution?: Record<string, any> | null
  entries?: any[] | null
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

export interface Deposits {
  entries: Deposit[]
}

export interface CryptoCurrencies {
  entries: CryptoCurrencyWallet[]
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

export type ProductPositions = Partial<Record<ProductType, ProductPosition>>

export interface GlobalPosition {
  id: string
  entity: Entity
  date?: string | null
  products?: ProductPositions
  source?: DataSource
}

export interface HistoricalPosition {
  positions: ProductPositions
}

export interface EntitiesPosition {
  positions: Record<string, GlobalPosition>
}

export interface PositionQueryRequest {
  entities?: string[] | null
  excludedEntities?: string[] | null
  real?: boolean | null
  products?: ProductType[] | null
}

export interface CryptoEntityDetails {
  providerAssetId: string
  provider: ExternalIntegrationId
}

export interface UpdatePositionRequest {
  products: ProductPositions
  entityId?: string | null
  newEntityName?: string | null
  newEntityIconUrl?: string | null
  netCryptoEntityDetails?: CryptoEntityDetails | null
}

export interface ManualPositionData {
  entryId: string
  globalPositionId: string
  productType: ProductType
  data: ManualEntryData
}
