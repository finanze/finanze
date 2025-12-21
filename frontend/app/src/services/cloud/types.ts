export interface CloudUser {
  email: string
  id: string
}

export interface CloudSession {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresAt: number
  user: CloudUser
}

export type AuthStateChangeCallback = (session: CloudSession | null) => void

export interface CloudAuthProvider {
  initialize(): Promise<void>
  signInWithGoogle(callbackUrl: string): Promise<void>
  signInWithEmail(email: string, password: string): Promise<void>
  signOut(): Promise<void>
  clearLocalSession(): Promise<void>
  getSession(): Promise<CloudSession | null>
  setSession(accessToken: string, refreshToken: string): Promise<void>
  setAutoRefreshEnabled(enabled: boolean): Promise<void>
  exchangeCodeForSession(code: string): Promise<void>
  onAuthStateChange(callback: AuthStateChangeCallback): () => void
}
