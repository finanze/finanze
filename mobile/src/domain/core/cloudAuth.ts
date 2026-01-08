export interface CloudAuthToken {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresAt: number
}

export interface CloudAuthRequest {
  token: CloudAuthToken | null
}

export enum CloudUserRole {
  NONE = "NONE",
  PLUS = "PLUS",
}

export interface CloudAuthResponse {
  role: CloudUserRole | null
  permissions: string[] | null
}

export interface CloudAuthTokenData {
  email: string
  role: CloudUserRole
  permissions: string[]
}

export interface CloudAuthData {
  role: CloudUserRole
  permissions: string[]
  token: CloudAuthToken
  email: string
}

export enum CloudPermission {
  BACKUP_INFO = "backup.info",
  BACKUP_CREATE = "backup.create",
  BACKUP_IMPORT = "backup.import",
  BACKUP_ERASE = "backup.erase",
}
