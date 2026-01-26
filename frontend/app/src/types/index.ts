import {
  WeightUnit,
  CommodityType,
  LoanType,
  InterestType,
  EntitiesPosition,
  ProductType,
  GlobalPosition,
  CryptoCurrencyType,
} from "./position"
import {
  ContributionTargetType,
  ContributionTargetSubtype,
} from "./contributions"
import type {
  AutoUpdateActionResult,
  AutoUpdateCheckResult,
  AutoUpdateErrorInfo,
  AutoUpdateInfo,
  AutoUpdateProgressInfo,
} from "./release"
import { Transactions } from "./transactions"

export enum EntityStatus {
  CONNECTED = "CONNECTED",
  DISCONNECTED = "DISCONNECTED",
  REQUIRES_LOGIN = "REQUIRES_LOGIN",
}

export enum EntityType {
  FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION",
  CRYPTO_WALLET = "CRYPTO_WALLET",
  CRYPTO_EXCHANGE = "CRYPTO_EXCHANGE",
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
  icon_url?: string | null
  status?: EntityStatus
  features: Feature[]
  credentials_template?: Record<string, string>
  setup_login_type?: EntitySetupLoginType
  session_category?: EntitySessionCategory
  pin?: {
    positions: number
  }
  connected?: CryptoWalletConnection[]
  last_fetch: Record<Feature, string>
  required_external_integrations?: string[]
  external_entity_id?: string | null
  virtual_features: Record<Feature, string>
  natively_supported_products?: ProductType[] | null
  fetchable?: boolean
}

export enum EntitySessionCategory {
  // No session requiring human action to re-create or minutes-long session
  NONE = "NONE",
  // Little hours-long session
  SHORT = "SHORT",
  // Some days-long session
  MEDIUM = "MEDIUM",
  // No session, renewable or weeks-long session
  UNDEFINED = "UNDEFINED",
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

export enum AuthResultCode {
  SUCCESS = "SUCCESS",
  INVALID_CREDENTIALS = "INVALID_CREDENTIALS",
  USER_NOT_FOUND = "USER_NOT_FOUND",
  UNEXPECTED_ERROR = "UNEXPECTED_ERROR",
}

export interface ChangePasswordRequest {
  username: string
  oldPassword: string
  newPassword: string
}

export interface User {
  id: string
  username: string
  path: string
}

export enum FFStatus {
  ON = "ON",
  OFF = "OFF",
}

export type FFValue = FFStatus | string

export type FeatureFlags = Record<string, FFValue>

export enum CloudRole {
  NONE = "NONE",
  PLUS = "PLUS",
}

export interface CloudAuthToken {
  access_token: string
  refresh_token: string
  token_type: string
  expires_at: number
}

export interface CloudAuthData {
  role: CloudRole
  permissions: string[]
  email: string
  token: CloudAuthToken
}

export interface CloudAuthRequest {
  token: CloudAuthToken | null
}

export interface CloudAuthResponse {
  role: CloudRole
  permissions: string[]
}

export enum BackupFileType {
  DATA = "DATA",
  CONFIG = "CONFIG",
}

export enum BackupMode {
  OFF = "OFF",
  AUTO = "AUTO",
  MANUAL = "MANUAL",
}

export enum SyncStatus {
  SYNC = "SYNC",
  PENDING = "PENDING",
  CONFLICT = "CONFLICT",
  OUTDATED = "OUTDATED",
  MISSING = "MISSING",
}

export interface BackupInfo {
  id: string
  protocol: number
  date: string
  type: BackupFileType
  size: number
}

export interface FullBackupInfo {
  local: BackupInfo | null
  remote: BackupInfo | null
  status: SyncStatus
  has_local_changes: boolean
  last_update: string
}

export interface FullBackupsInfo {
  pieces: Record<BackupFileType, FullBackupInfo>
}

export interface BackupSyncResult {
  pieces: Record<BackupFileType, FullBackupInfo>
}

export interface UploadBackupRequest {
  types: BackupFileType[]
  force?: boolean
}

export interface ImportBackupRequest {
  types: BackupFileType[]
  force?: boolean
}

export interface BackupSettings {
  mode: BackupMode
}

export interface StatusResponse {
  status: "LOCKED" | "UNLOCKED"
  lastLogged?: string | null
  user?: User | null
  server: {
    version: string
    options: BackendOptions
  }
  features: FeatureFlags
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
    wait?: number
    processId?: string
    credentials?: Record<string, string>
  }
  data?: any
}

export enum ImportErrorType {
  SHEET_NOT_FOUND = "SHEET_NOT_FOUND",
  MISSING_FIELD = "MISSING_FIELD",
  VALIDATION_ERROR = "VALIDATION_ERROR",
  UNEXPECTED_COLUMN = "UNEXPECTED_COLUMN",
  UNEXPECTED_ERROR = "UNEXPECTED_ERROR",
}

export interface ImportError {
  type: ImportErrorType
  entry: string
  detail?:
    | {
        field: string
        value: string
      }[]
    | string[]
  row?: string[]
}

export interface ImportedData {
  positions?: Array<GlobalPosition>
  transactions?: Transactions
}

export interface ImportResult {
  code: ImportResultCode
  data?: any
  errors?: ImportError[]
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

export enum ImportResultCode {
  // Success
  COMPLETED = "COMPLETED",

  // Failure
  UNSUPPORTED_FILE_FORMAT = "UNSUPPORTED_FILE_FORMAT",
  INVALID_TEMPLATE = "INVALID_TEMPLATE",

  // Import not configured
  DISABLED = "DISABLED",
}

export interface Settings {
  general: {
    defaultCurrency: string
    defaultCommodityWeightUnit: string
  }
  export?: {
    sheets?: {
      globals?: {
        spreadsheetId?: string
        datetimeFormat?: string
        dateFormat?: string
      }
      position?: any[]
      contributions?: any[]
      transactions?: any[]
      historic?: any[]
    }
  }
  importing?: {
    sheets?: {
      globals?: {
        spreadsheetId?: string
        datetimeFormat?: string
        dateFormat?: string
      }
      position?: any[]
      transactions?: any[]
    }
  }
  assets: {
    crypto: {
      stablecoins: string[]
      hideUnknownTokens: boolean
    }
  }
}

export enum PlatformType {
  WINDOWS = "windows",
  MAC = "mac",
  LINUX = "linux",
  WEB = "web",
  IOS = "ios",
  ANDROID = "android",
}

export interface PlatformInfo {
  type: PlatformType
  arch?: string
  osVersion?: string
  electronVersion?: string
  chromiumVersion?: string | null
  nodeVersion?: string | null
  webViewVersion?: string | null
}

export type ThemeMode = "light" | "dark" | "system"

export interface AboutAppInfo {
  appName: string
  version: string
  author?: string | null
  repository?: string | null
  homepage?: string | null
}

export type BackendLogLevel =
  | "NONE"
  | "DEBUG"
  | "INFO"
  | "WARNING"
  | "ERROR"
  | "CRITICAL"

export interface BackendStartOptions {
  dataDir?: string
  port?: number
  logLevel?: BackendLogLevel
  logDir?: string
  logFile?: string
  logFileLevel?: BackendLogLevel
  thirdPartyLogLevel?: BackendLogLevel
}

export interface BackendRuntimeArgs {
  port: number
  logLevel: BackendLogLevel
  dataDir?: string
  logDir?: string
  logFileLevel?: BackendLogLevel
  thirdPartyLogLevel?: BackendLogLevel
}

export interface BackendOptions extends BackendStartOptions {}

export type BackendState =
  | "stopped"
  | "starting"
  | "running"
  | "stopping"
  | "error"

export interface BackendErrorInfo {
  message: string
  stack?: string | null
  code?: string | number | null
}

export interface BackendStatus {
  state: BackendState
  pid: number | null
  args: BackendRuntimeArgs | null
  startedAt: number | null
  exitedAt: number | null
  error: BackendErrorInfo | null
}

export interface BackendActionResult {
  success: boolean
  status: BackendStatus
  error?: BackendErrorInfo
}

export type ExchangeRates = Record<string, Record<string, number>>

export interface FinanzeConfig {
  backend?: BackendStartOptions
  serverUrl?: string
}

export interface CreateCryptoWalletRequest {
  entityId: string
  name: string
  addresses: string[]
}

export interface UpdateCryptoWalletConnectionRequest {
  id: string
  name: string
}

export interface CryptoWalletConnectionResult {
  created?: Array<{
    id: string
    address: string
    name?: string | null
  }>
  failed?: Record<string, string>
}

declare global {
  interface Window {
    platform: PlatformInfo
    ipcAPI?: {
      apiUrl: () => Promise<{ url: string; custom: boolean }>
      changeThemeMode: (mode: ThemeMode) => void
      showAbout: () => void
      getAboutInfo: () => Promise<AboutAppInfo>
      requestExternalLogin: (
        id: string,
        request?: any,
      ) => Promise<{ success: boolean }>
      startBackend: (
        options?: BackendStartOptions,
      ) => Promise<BackendActionResult>
      stopBackend: () => Promise<BackendActionResult>
      restartBackend: () => Promise<BackendActionResult>
      getBackendStatus: () => Promise<BackendStatus>
      selectDirectory: (initialPath?: string) => Promise<string | null>
      onBackendStatusChange: (
        callback: (status: BackendStatus) => void,
      ) => () => void
      onCompletedExternalLogin: (
        callback: (
          id: string,
          result: {
            success: boolean
            credentials: Record<string, string>
          },
        ) => void,
      ) => void
      checkForUpdates: () => Promise<AutoUpdateCheckResult>
      downloadUpdate: () => Promise<AutoUpdateActionResult>
      quitAndInstall: () => Promise<AutoUpdateActionResult>
      onCheckingForUpdate: (callback: () => void) => () => void
      onUpdateAvailable: (
        callback: (info: AutoUpdateInfo) => void,
      ) => () => void
      onUpdateNotAvailable: (
        callback: (info: AutoUpdateInfo) => void,
      ) => () => void
      onUpdateDownloaded: (
        callback: (info: AutoUpdateInfo) => void,
      ) => () => void
      onDownloadProgress: (
        callback: (progress: AutoUpdateProgressInfo) => void,
      ) => () => void
      onUpdateError: (
        callback: (error: AutoUpdateErrorInfo) => void,
      ) => () => void
      onOAuthCallback: (
        callback: (tokens: {
          access_token: string
          refresh_token: string
          type?: string
        }) => void,
      ) => () => void

      onOAuthCallbackError: (
        callback: (payload: {
          error: string
          error_description: string | null
          error_code: string | null
        }) => void,
      ) => () => void

      onOAuthCallbackCode: (
        callback: (payload: { code: string }) => void,
      ) => () => void

      onOAuthCallbackUrl: (
        callback: (payload: { url: string }) => void,
      ) => () => void
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
  CRYPTO_MARKET_PROVIDER = "CRYPTO_MARKET_PROVIDER",
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
  payload_schema?: Record<string, string> | null
}

export interface ExternalIntegrations {
  integrations: ExternalIntegration[]
}

export enum ExternalEntityStatus {
  UNLINKED = "UNLINKED",
  LINKED = "LINKED",
  ORPHAN = "ORPHAN",
}

export interface ExternalEntity {
  id: string
  entity_id: string
  status: ExternalEntityStatus
  provider: string
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
  provider?: string | null
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

export enum InstrumentType {
  STOCK = "STOCK",
  ETF = "ETF",
  MUTUAL_FUND = "MUTUAL_FUND",
}

export interface InstrumentDataRequest {
  type: InstrumentType
  isin?: string | null
  name?: string | null
  ticker?: string | null
}

export interface InstrumentOverview {
  isin?: string | null
  name?: string | null
  currency?: string | null
  symbol?: string | null
  type?: InstrumentType | null
  market?: string | null
  price?: number | null
}

export interface InstrumentInfo {
  name?: string | null
  currency?: string | null
  type: InstrumentType
  price?: number | null
  symbol?: string | null
  isin?: string | null
}

export interface InstrumentsResponse {
  entries: InstrumentInfo[]
}

export interface CryptoAssetPlatform {
  provider_id: string
  name: string
  contract_address: string
  icon_url?: string | null
  related_entity_id?: string | null
}

export interface CryptoAssetDetails {
  name: string
  symbol: string
  platforms: CryptoAssetPlatform[]
  provider: string
  provider_id: string
  price: Record<string, number>
  icon_url?: string | null
  type: CryptoCurrencyType
}

export interface AvailableCryptoAsset {
  name: string
  symbol: string
  platforms: CryptoAssetPlatform[]
  provider: string
  provider_id: string
}

export interface AvailableCryptoAssetsResult {
  provider: string
  assets: AvailableCryptoAsset[]
  page: number
  limit: number
  total: number
}

// Template system
export enum TemplateType {
  EXPORT = "EXPORT",
  IMPORT = "IMPORT",
}

export enum TemplateFieldType {
  TEXT = "TEXT",
  CURRENCY = "CURRENCY",
  INTEGER = "INTEGER",
  DECIMAL = "DECIMAL",
  DATE = "DATE",
  DATETIME = "DATETIME",
  BOOLEAN = "BOOLEAN",
  ENUM = "ENUM",
}

export interface TemplateField {
  field: string
  type: TemplateFieldType
  name?: string | null
  enum_values?: string[]
  default?: any
}

export interface Template {
  id?: string | null
  name: string
  feature: Feature
  type: TemplateType
  fields: TemplateField[]
  products?: ProductType[] | null
}

export interface TemplateCreateField {
  field: string
  custom_name?: string
  default?: any
}

export interface TemplateUpdateField extends TemplateCreateField {}

export interface TemplateCreatePayload {
  name: string
  feature: Feature
  type: TemplateType
  fields: TemplateCreateField[]
  products?: ProductType[]
}

export interface TemplateUpdatePayload extends TemplateCreatePayload {
  id: string
}

export interface TemplateFeatureField {
  field: string
  key: string
  required: boolean
  type: TemplateFieldType
  enum_values?: string[]
  or_requires?: string[]
  template_type?: TemplateType
  default?: any
  disabled_default: boolean
}

export interface TemplateFeatureDefinition {
  feature: Feature
  fields: TemplateFeatureField[]
  product: ProductType | null
  template_type: TemplateType | null
}

export enum NumberFormat {
  EUROPEAN = "EUROPEAN",
  ENGLISH = "ENGLISH",
}

export enum FileFormat {
  CSV = "CSV",
  TSV = "TSV",
  XLSX = "XLSX",
}

export interface TemplateConfigPayload {
  id: string
  params?: Record<string, string> | null
}

export interface FileExportRequest {
  format: FileFormat
  number_format: NumberFormat
  feature: Feature
  data?: ProductType[] | null
  datetime_format?: string | null
  date_format?: string | null
  template?: TemplateConfigPayload | null
}

export interface FileImportRequest {
  feature: Feature
  number_format: NumberFormat
  product: ProductType
  datetime_format?: string | null
  date_format?: string | null
  templateId: string
  templateParams?: Record<string, string> | null
  preview?: boolean
}

// Money Events
export enum MoneyEventType {
  CONTRIBUTION = "CONTRIBUTION",
  PERIODIC_FLOW = "PERIODIC_FLOW",
  PENDING_FLOW = "PENDING_FLOW",
  MATURITY = "MATURITY",
}

export enum MoneyEventFrequency {
  DAILY = "DAILY",
  WEEKLY = "WEEKLY",
  BIWEEKLY = "BIWEEKLY",
  MONTHLY = "MONTHLY",
  EVERY_TWO_MONTHS = "EVERY_TWO_MONTHS",
  EVERY_FOUR_MONTHS = "EVERY_FOUR_MONTHS",
  QUARTERLY = "QUARTERLY",
  SEMIANNUAL = "SEMIANNUAL",
  YEARLY = "YEARLY",
}

export interface PeriodicContributionDetails {
  target_type: ContributionTargetType
  target_subtype?: ContributionTargetSubtype | null
  target: string
  target_name?: string | null
}

export interface MoneyEvent {
  id?: string | null
  name: string
  amount: number
  currency: string
  date: string
  type: MoneyEventType
  frequency?: MoneyEventFrequency | null
  icon?: string | null
  details?: PeriodicContributionDetails | null
  product_type?: ProductType | null
}

export interface MoneyEventQuery {
  from_date: string
  to_date: string
}

export interface MoneyEvents {
  events: MoneyEvent[]
}

// Auto-refresh configuration
export enum AutoRefreshMode {
  OFF = "OFF",
  NO_2FA = "NO_2FA",
}

export enum AutoRefreshMaxOutdatedTime {
  THREE_HOURS = "THREE_HOURS",
  SIX_HOURS = "SIX_HOURS",
  TWELVE_HOURS = "TWELVE_HOURS",
  DAY = "DAY",
  TWO_DAYS = "TWO_DAYS",
  WEEK = "WEEK",
}

export interface AutoRefreshEntityEntry {
  id: string
}

export interface AutoRefresh {
  mode: AutoRefreshMode
  max_outdated: AutoRefreshMaxOutdatedTime
  entities: AutoRefreshEntityEntry[]
}

export interface DataConfig {
  autoRefresh: AutoRefresh
}

// Savings Calculations
export enum SavingsPeriodicity {
  MONTHLY = "MONTHLY",
  QUARTERLY = "QUARTERLY",
  YEARLY = "YEARLY",
}

export interface SavingsScenarioRequest {
  id: string
  annual_market_performance: number
  periodic_contribution?: number | null
  target_amount?: number | null
}

export interface SavingsRetirementRequest {
  withdrawal_amount?: number | null
  withdrawal_years?: number | null
}

export interface SavingsCalculationRequest {
  base_amount?: number | null
  years?: number | null
  periodicity: SavingsPeriodicity
  scenarios: SavingsScenarioRequest[]
  retirement?: SavingsRetirementRequest | null
}

export interface SavingsPeriodEntry {
  period_index: number
  contributed: number
  total_contributed: number
  total_invested: number
  revaluation: number
  total_revaluation: number
  balance: number
}

export interface SavingsRetirementPeriodEntry {
  period_index: number
  withdrawal: number
  total_withdrawn: number
  revaluation: number
  balance: number
}

export interface SavingsRetirementResult {
  withdrawal_amount: number
  duration_periods: number
  duration_years: number
  total_withdrawn: number
  periods: SavingsRetirementPeriodEntry[]
}

export interface SavingsScenarioResult {
  scenario_id: string
  annual_market_performance: number
  periodic_contribution: number
  accumulation_periods: SavingsPeriodEntry[]
  total_contributions: number
  total_revaluation: number
  final_balance: number
  retirement?: SavingsRetirementResult | null
}

export interface SavingsCalculationResult {
  scenarios: SavingsScenarioResult[]
}
export interface GetBackupsInfoRequest {
  only_local?: boolean
}
