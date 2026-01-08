export enum LoginResultCode {
  CREATED = "CREATED",
  RESUMED = "RESUMED",
  CODE_REQUESTED = "CODE_REQUESTED",
  MANUAL_LOGIN = "MANUAL_LOGIN",
  NOT_LOGGED = "NOT_LOGGED",
  INVALID_CODE = "INVALID_CODE",
  INVALID_CREDENTIALS = "INVALID_CREDENTIALS",
  NO_CREDENTIALS_AVAILABLE = "NO_CREDENTIALS_AVAILABLE",
  LOGIN_REQUIRED = "LOGIN_REQUIRED",
  UNEXPECTED_ERROR = "UNEXPECTED_LOGIN_ERROR",
}

export interface EntitySession {
  creation: string
  expiration: string | null
  payload: Record<string, any>
}

export interface EntityLoginResult {
  code: LoginResultCode
  message?: string | null
  details?: Record<string, any> | null
  processId?: string | null
  session?: EntitySession | null
}

export interface TwoFactor {
  code?: string | null
  processId?: string | null
}

export interface LoginOptions {
  avoidNewLogin?: boolean
  forceNewSession?: boolean
}

export interface EntityLoginRequest {
  entityId: string
  credentials: Record<string, string>
  twoFactor?: TwoFactor | null
  options?: LoginOptions | null
}

export interface EntityLoginParams {
  credentials: Record<string, string>
  twoFactor?: TwoFactor | null
  options?: LoginOptions | null
  session?: EntitySession | null
}

export interface EntityDisconnectRequest {
  entityId: string
}
