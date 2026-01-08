import { AutoContributions } from "./autoContributions"
import { Feature } from "./entity"
import { LoginOptions, TwoFactor } from "./entityLogin"
import { GlobalPosition } from "./globalPosition"
import { Historic } from "./historic"
import { Transactions } from "./transactions"

export enum FetchResultCode {
  COMPLETED = "COMPLETED",
  PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED",
  COOLDOWN = "COOLDOWN",
  FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED",
  LINK_EXPIRED = "LINK_EXPIRED",
  REMOTE_FAILED = "REMOTE_FAILED",
  CODE_REQUESTED = "CODE_REQUESTED",
  MANUAL_LOGIN = "MANUAL_LOGIN",
  NOT_LOGGED = "NOT_LOGGED",
  INVALID_CODE = "INVALID_CODE",
  INVALID_CREDENTIALS = "INVALID_CREDENTIALS",
  NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE",
  NOT_CONNECTED = "NOT_CONNECTED",
  LOGIN_REQUIRED = "LOGIN_REQUIRED",
  UNEXPECTED_LOGIN_ERROR = "UNEXPECTED_LOGIN_ERROR",
}

export interface FetchOptions {
  deep?: boolean
}

export interface FetchRequest {
  entityId: string | null
  features: Feature[]
  twoFactor?: TwoFactor | null
  loginOptions?: LoginOptions | null
  fetchOptions?: FetchOptions | null
}

export interface FetchedData {
  position?: GlobalPosition | null
  autoContributions?: AutoContributions | null
  transactions?: Transactions | null
  historic?: Historic | null
}

export interface FetchResult {
  code: FetchResultCode
  data?: FetchedData | FetchedData[] | null
  details?: Record<string, any> | null
}
