import { WeightUnit, CommodityType } from "./position"

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
  is_real: boolean
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

  // Cooldown
  COOLDOWN = "COOLDOWN",

  // Bad user input
  FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED",

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

export interface GoogleIntegrationCredentials {
  client_id: string
  client_secret: string
}

export interface EtherscanIntegrationData {
  api_key: string
}
