import {
  WeightUnit,
  CommodityType,
  LoanType,
  InterestType,
  EntitiesPosition,
} from "./position"

export enum EntityStatus {
  CONNECTED = "CONNECTED",
  DISCONNECTED = "DISCONNECTED",
  REQUIRES_LOGIN = "REQUIRES_LOGIN",
}

export enum EntityType {
  FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION",
  CRYPTO_WALLET = "CRYPTO_WALLET",
  COMMODITY = "COMMODITY",
}

export enum EntityOrigin {
  MANUAL = "MANUAL",
  NATIVE = "NATIVE",
  EXTERNALLY_PROVIDED = "EXTERNALLY_PROVIDED",
  INTERNAL = "INTERNAL",
}

export enum DataSource {
  REAL = "REAL",
  SHEETS = "SHEETS",
  MANUAL = "MANUAL",
}

export interface CryptoWalletConnection {
  id: string
  entity_id: string
  address: string
  name: string
}

export interface Entity {
  id: string
  name: string
  type: EntityType
  origin: EntityOrigin
  natural_id: string
  status?: EntityStatus
  features: Feature[]
  credentials_template?: Record<string, string>
  setup_login_type?: EntitySetupLoginType
  pin?: {
    positions: number
  }
  connected?: CryptoWalletConnection[]
  last_fetch: Record<Feature, string>
  required_external_integrations?: string[]
  external_entity_id?: string | null
  virtual_features: Record<Feature, string>
}

export enum EntitySetupLoginType {
  MANUAL = "MANUAL",
  AUTOMATED = "AUTOMATED",
}

export enum CredentialType {
  ID = "ID",
  USER = "USER",
  PASSWORD = "PASSWORD",
  PIN = "PIN",
  PHONE = "PHONE",
  EMAIL = "EMAIL",
  API_TOKEN = "API_TOKEN",
  INTERNAL = "INTERNAL",
  INTERNAL_TEMP = "INTERNAL_TEMP",
}

export type Feature =
  | "POSITION"
  | "AUTO_CONTRIBUTIONS"
  | "TRANSACTIONS"
  | "HISTORIC"

export interface AuthRequest {
  username: string
  password: string
}

export interface ChangePasswordRequest {
  username: string
  oldPassword: string
  newPassword: string
}

export interface LoginStatusResponse {
  status: "LOCKED" | "UNLOCKED"
  last_logged?: string
}

export interface LoginRequest {
  entity: string
  credentials: Record<string, string>
  code?: string
  processId?: string
}

export interface FetchRequest {
  entity?: string
  features: Feature[]
  code?: string
  processId?: string
  avoidNewLogin?: boolean
  deep?: boolean
}

export interface LoginResponse {
  code: LoginResultCode
  processId?: string
  details?: any
}

export interface FetchResponse {
  code: FetchResultCode
  details?: {
    countdown?: number
    processId?: string
    credentials?: Record<string, string>
  }
  data?: any
}

export enum VirtualFetchErrorType {
  SHEET_NOT_FOUND = "SHEET_NOT_FOUND",
  MISSING_FIELD = "MISSING_FIELD",
  VALIDATION_ERROR = "VALIDATION_ERROR",
}

export interface VirtualFetchError {
  type: VirtualFetchErrorType
  entry: string
  detail?:
    | {
        field: string
        value: string
      }[]
    | string[]
  row?: string[]
}

export interface VirtualFetchResponse {
  code: VirtualFetchResultCode
  data?: any
  errors?: VirtualFetchError[]
}

export interface EntitiesResponse {
  entities: Entity[]
}

export enum LoginResultCode {
  // Success
  CREATED = "CREATED",
  RESUMED = "RESUMED",

  // Flow deferral
  CODE_REQUESTED = "CODE_REQUESTED",
  MANUAL_LOGIN = "MANUAL_LOGIN",

  // Flow not completed (expected)
  NOT_LOGGED = "NOT_LOGGED",

  // Bad user input
  INVALID_CODE = "INVALID_CODE",
  INVALID_CREDENTIALS = "INVALID_CREDENTIALS",

  // Not setup
  NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE",

  // Error
  LOGIN_REQUIRED = "LOGIN_REQUIRED",
  UNEXPECTED_ERROR = "UNEXPECTED_LOGIN_ERROR",
}

export enum FetchResultCode {
  // Success
  COMPLETED = "COMPLETED",
  PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED",

  // Cooldown
  COOLDOWN = "COOLDOWN",

  // Bad user input
  FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED",

  // External entities
  LINK_EXPIRED = "LINK_EXPIRED",
  REMOTE_FAILED = "REMOTE_FAILED",

  // Login related codes
  CODE_REQUESTED = "CODE_REQUESTED",
  MANUAL_LOGIN = "MANUAL_LOGIN",
  NOT_LOGGED = "NOT_LOGGED",
  INVALID_CODE = "INVALID_CODE",
  INVALID_CREDENTIALS = "INVALID_CREDENTIALS",
  NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE",
  LOGIN_REQUIRED = "LOGIN_REQUIRED",
  UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR",
}

export enum VirtualFetchResultCode {
  // Success
  COMPLETED = "COMPLETED",

  // Virtual fetch not enabled
  DISABLED = "DISABLED",
}

export interface Settings {
  general: {
    defaultCurrency: string
  }
  export: {
    sheets: {
      globals: {
        spreadsheetId: string
        datetimeFormat: string
        dateFormat: string
      }
      position: any[]
      contributions: any[]
      transactions: any[]
      historic: any[]
    }
  }
  fetch: {
    updateCooldown: number
    virtual: {
      enabled: boolean
      globals: {
        spreadsheetId: string
        datetimeFormat: string
        dateFormat: string
      }
      investments: any[]
      transactions: any[]
    }
  }
}

export enum ExportTarget {
  GOOGLE_SHEETS = "GOOGLE_SHEETS",
}

export interface ExportOptions {
  exclude_non_real?: boolean
}

export interface ExportRequest {
  target: ExportTarget
  options: ExportOptions
}

export enum PlatformType {
  WINDOWS = "windows",
  MAC = "mac",
  LINUX = "linux",
  WEB = "web",
}

export interface PlatformInfo {
  type: PlatformType
  arch?: string
  osVersion?: string
  electronVersion?: string
}

export type ThemeMode = "light" | "dark" | "system"

export interface ExchangeRates {
  [baseCurrency: string]: {
    [targetCurrency: string]: number
  }
}

export interface CreateCryptoWalletRequest {
  entityId: string
  name: string
  address: string
}

export interface UpdateCryptoWalletConnectionRequest {
  id: string
  name: string
}

// Electron window interface
declare global {
  interface Window {
    ipcAPI?: {
      apiUrl: () => Promise<string>
      platform: () => Promise<PlatformInfo>
      changeThemeMode: (mode: ThemeMode) => void
      showAbout: () => void
      requestExternalLogin: (
        id: string,
        request?: any,
      ) => Promise<{ success: boolean }>
      onCompletedExternalLogin: (
        callback: (
          id: string,
          result: {
            success: boolean
            credentials: Record<string, string>
          },
        ) => void,
      ) => void
    }
  }
}

export interface CommodityRegister {
  name: string
  amount: number
  unit: WeightUnit
  type: CommodityType
  initial_investment?: number | null
  average_buy_price?: number | null
  currency?: string | null
}

export interface SaveCommodityRequest {
  registers: CommodityRegister[]
}

export enum ExternalIntegrationType {
  CRYPTO_PROVIDER = "CRYPTO_PROVIDER",
  DATA_SOURCE = "DATA_SOURCE",
  ENTITY_PROVIDER = "ENTITY_PROVIDER",
}

export enum ExternalIntegrationStatus {
  ON = "ON",
  OFF = "OFF",
}

export interface ExternalIntegration {
  id: string
  name: string
  status: ExternalIntegrationStatus
  type: ExternalIntegrationType
}

export interface ExternalIntegrations {
  integrations: ExternalIntegration[]
}

export enum ExternalIntegrationId {
  GOOGLE_SHEETS = "GOOGLE_SHEETS",
  ETHERSCAN = "ETHERSCAN",
  GOCARDLESS = "GOCARDLESS",
}

export enum ExternalEntityStatus {
  UNLINKED = "UNLINKED",
  LINKED = "LINKED",
}

export interface ExternalEntity {
  id: string
  entity_id: string
  status: ExternalEntityStatus
  provider: ExternalIntegrationId
  date: string
  provider_instance_id: string
  payload?: Record<string, any> | null
}

export interface ProviderExternalEntityDetails {
  id: string
  name: string
  bic: string
  type: EntityType
  icon?: string | null
}

export interface ExternalEntityCandidates {
  entities: ProviderExternalEntityDetails[]
}

export enum ExternalEntitySetupResponseCode {
  ALREADY_LINKED = "ALREADY_LINKED",
  CONTINUE_WITH_LINK = "CONTINUE_WITH_LINK",
}

export interface ExternalEntityConnectionResult {
  id?: string | null
  code: ExternalEntitySetupResponseCode
  link?: string | null
  provider_instance_id?: string | null
  payload?: any
}

export interface ConnectExternalEntityRequest {
  institution_id?: string | null
  external_entity_id?: string | null
  provider?: ExternalIntegrationId | null
  relink?: boolean
}

export interface GoogleIntegrationCredentials {
  client_id: string
  client_secret: string
}

export interface EtherscanIntegrationData {
  api_key: string
}

export interface GoCardlessIntegrationCredentials {
  secret_id: string
  secret_key: string
}

export enum FlowType {
  EARNING = "EARNING",
  EXPENSE = "EXPENSE",
}

export enum FlowFrequency {
  DAILY = "DAILY",
  WEEKLY = "WEEKLY",
  MONTHLY = "MONTHLY",
  EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS",
  QUARTERLY = "QUARTERLY",
  EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS",
  SEMIANNUALLY = "SEMIANNUALLY",
  YEARLY = "YEARLY",
}

export interface PeriodicFlow {
  id?: string
  name: string
  amount: number
  flow_type: FlowType
  frequency: FlowFrequency
  category?: string
  enabled: boolean
  since: string
  until?: string
  currency: string
  icon?: string
  linked?: boolean
  next_date?: string
  max_amount?: number
}

export interface PendingFlow {
  id: string
  name: string
  amount: number
  flow_type: FlowType
  category?: string
  enabled: boolean
  date?: string
  currency: string
  icon?: string
}

export interface CreatePeriodicFlowRequest {
  name: string
  amount: number
  flow_type: FlowType
  frequency: FlowFrequency
  category?: string
  enabled: boolean
  since: string
  until?: string
  currency: string
  icon?: string
  max_amount?: number
}

export interface UpdatePeriodicFlowRequest {
  id: string
  name: string
  amount: number
  flow_type: FlowType
  frequency: FlowFrequency
  category?: string
  enabled: boolean
  since: string
  until?: string
  currency: string
  icon?: string
  max_amount?: number
}

export interface CreatePendingFlowRequest {
  name: string
  amount: number
  flow_type: FlowType
  category?: string
  enabled: boolean
  date?: string
  currency: string
  icon?: string
  max_amount?: number
}

export interface SavePendingFlowsRequest {
  flows: CreatePendingFlowRequest[]
}

export enum RealEstateFlowSubtype {
  LOAN = "LOAN",
  SUPPLY = "SUPPLY",
  COST = "COST",
  RENT = "RENT",
}

export interface LoanPayload {
  type: LoanType
  loan_amount?: number | null
  interest_rate: number
  euribor_rate?: number | null
  interest_type: InterestType
  fixed_years?: number | null
  principal_outstanding: number
  monthly_interests?: number | null
}

export interface RentPayload {}

export interface SupplyPayload {
  tax_deductible?: boolean
}

export interface CostPayload {
  tax_deductible?: boolean
}

export type RealEstateFlowPayload =
  | LoanPayload
  | RentPayload
  | SupplyPayload
  | CostPayload

export interface RealEstateFlow {
  periodic_flow_id?: string | null
  periodic_flow?: PeriodicFlow | null
  flow_subtype: RealEstateFlowSubtype
  description: string
  payload: RealEstateFlowPayload
}

export interface PurchaseExpense {
  concept: string
  amount: number
  description?: string | null
}

export interface Valuation {
  date: string
  amount: number
  notes?: string | null
}

export interface Location {
  address?: string | null
  cadastral_reference?: string | null
}

export interface BasicInfo {
  name: string
  is_residence: boolean
  is_rented: boolean
  bathrooms?: number | null
  bedrooms?: number | null
  photo_url?: string | null
}

export interface PurchaseInfo {
  date: string
  price: number
  expenses: PurchaseExpense[]
}

export interface ValuationInfo {
  estimated_market_value: number
  valuations: Valuation[]
  annual_appreciation?: number | null
}

export interface Amortization {
  concept: string
  base_amount: number
  percentage: number
  amount: number
}

export interface RentalData {
  marginal_tax_rate?: number | null
  amortizations: Amortization[]
  vacancy_rate?: number | null
}

export interface RealEstate {
  id?: string | null
  basic_info: BasicInfo
  currency: string
  location: Location
  purchase_info: PurchaseInfo
  valuation_info: ValuationInfo
  flows: RealEstateFlow[]
  created_at?: string | null
  updated_at?: string | null
  rental_data?: RentalData | null
}

export interface CreateRealEstateRequest {
  data: Omit<RealEstate, "id" | "created_at" | "updated_at" | "basic_info"> & {
    basic_info: Omit<BasicInfo, "photo_url">
  }
  photo?: File | null
}

export interface UpdateRealEstateRequest {
  data: RealEstate & {
    remove_unassigned_flows: boolean
  }
  photo?: File | null
}

export interface DeleteRealEstateRequest {
  remove_related_flows: boolean
}

export interface LoanCalculationRequest {
  loan_amount?: number | null
  principal_outstanding?: number | null
  interest_rate: number
  interest_type: InterestType
  euribor_rate?: number | null
  fixed_years?: number | null
  start: string
  end: string
}

export interface LoanCalculationResult {
  current_monthly_payment?: number | null
  current_monthly_interests?: number | null
  principal_outstanding?: number | null
  installment_date?: string | null
}

// Forecast types
export interface ForecastRequest {
  target_date: string
  entities?: string[]
  excluded_entities?: string[]
  avg_annual_market_increase?: number | null
  avg_annual_crypto_increase?: number | null
  avg_annual_commodity_increase?: number | null
}

export interface CashDelta {
  currency: string
  amount: number
}

export interface RealEstateEquityForecast {
  id: string
  equity_now?: number | null
  equity_at_target?: number | null
  principal_outstanding_now?: number | null
  principal_outstanding_at_target?: number | null
  currency: string
}

export interface ForecastResult {
  target_date: string
  positions: EntitiesPosition
  cash_delta: CashDelta[]
  real_estate: RealEstateEquityForecast[]
  crypto_appreciation: number
  commodity_appreciation: number
}

// External entity additional requests
export interface CompleteExternalEntityLinkRequest {
  payload?: Record<string, any> | null
}

export interface DeleteExternalEntityRequest {
  external_entity_id: string
}
