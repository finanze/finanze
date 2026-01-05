import { CloudUserRole } from "./core"

export interface CloudUser {
  email: string
  id: string
  role: CloudUserRole
  permissions: string[]
}

export interface CloudSession {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresAt: number
  user: CloudUser
}

export type AuthStateChangeCallback = (session: CloudSession | null) => void
