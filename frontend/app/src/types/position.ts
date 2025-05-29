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

export interface StockInvestments {
  investment?: number | null
  market_value?: number | null
  details: StockDetail[]
}

export interface FundInvestments {
  investment?: number | null
  market_value?: number | null
  details: FundDetail[]
}

export interface FactoringInvestments {
  total?: number | null
  weighted_interest_rate?: number | null
  details: FactoringDetail[]
}

export interface RealStateCFInvestments {
  total?: number | null
  weighted_interest_rate?: number | null
  details: RealStateCFDetail[]
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
  total?: number | null
  expected_interests?: number | null
  weighted_interest_rate?: number | null
  details: Deposit[]
}

export interface Crowdlending {
  id: string
  total?: number | null
  weighted_interest_rate?: number | null
  currency: string
  distribution: any
  details: any[]
}

export interface Investments {
  stocks?: StockInvestments | null
  funds?: FundInvestments | null
  fund_portfolios: FundPortfolio[]
  factoring?: FactoringInvestments | null
  real_state_cf?: RealStateCFInvestments | null
  deposits?: Deposits | null
  crowdlending?: Crowdlending | null
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
  accounts: Account[]
  cards: Card[]
  loans: Loan[]
  investments?: Investments | null
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
