export enum EntityStatus {
  CONNECTED = "CONNECTED",
  DISCONNECTED = "DISCONNECTED",
  REQUIRES_LOGIN = "REQUIRES_LOGIN",
}

export interface Entity {
  id: string
  name: string
  is_real: boolean
  status: EntityStatus
  features: Feature[]
  credentials_template: Record<string, string>
  setup_login_type: EntitySetupLoginType
  pin?: {
    positions: number
  }
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

export interface ScrapeRequest {
  entity: string
  features: Feature[]
  code?: string
  processId?: string
  avoidNewLogin?: boolean
}

export interface LoginResponse {
  code: LoginResultCode
  processId?: string
  details?: any
}

export interface ScrapeResponse {
  code: ScrapeResultCode
  details?: {
    countdown?: number
    processId?: string
    credentials?: Record<string, string>
  }
  data?: any
}

export interface EntitiesResponse {
  entities: Entity[]
  virtual: boolean
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

export enum ScrapeResultCode {
  // Success
  COMPLETED = "COMPLETED",

  // Cooldown
  COOLDOWN = "COOLDOWN",

  // Bad user input
  ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND",
  FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED",

  // Entity or feature disabled (also bad input)
  DISABLED = "DISABLED",

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

export interface Settings {
  export: {
    sheets: {
      globals: {
        spreadsheetId: string
        datetimeFormat: string
        dateFormat: string
      }
      summary: any[]
      investments: any[]
      contributions: any[]
      transactions: any[]
      historic: any[]
    }
  }
  scrape: {
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

export interface ExportRequest {
  target: ExportTarget
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
