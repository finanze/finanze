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

export type EmailPasswordSignUpResult =
  | {
      status: "PENDING_EMAIL_CONFIRMATION"
      email: string
    }
  | {
      status: "EMAIL_ALREADY_REGISTERED"
    }
  | {
      status: "SIGNED_IN"
    }

export type AuthStateChangeCallback = (session: CloudSession | null) => void

export type CloudAuthEvent =
  | "INITIAL_SESSION"
  | "SIGNED_IN"
  | "SIGNED_OUT"
  | "TOKEN_REFRESHED"
  | "USER_UPDATED"
  | "PASSWORD_RECOVERY"
  | "MFA_CHALLENGE_VERIFIED"

export interface CloudAuthProvider {
  initialize(): Promise<void>
  handleAuthCallbackUrl(url: string): Promise<void>
  signInWithGoogle(callbackUrl: string): Promise<void>
  signInWithEmail(email: string, password: string): Promise<void>
  signUpWithEmail(
    email: string,
    password: string,
    options?: { emailRedirectTo?: string },
  ): Promise<EmailPasswordSignUpResult>
  requestPasswordReset(
    email: string,
    options?: { emailRedirectTo?: string },
  ): Promise<void>
  updatePassword(password: string): Promise<void>
  signOut(): Promise<void>
  clearLocalSession(): Promise<void>
  getSession(): Promise<CloudSession | null>
  setSession(accessToken: string, refreshToken: string): Promise<void>
  setAutoRefreshEnabled(enabled: boolean): Promise<void>
  exchangeCodeForSession(code: string): Promise<void>
  onAuthStateChange(callback: AuthStateChangeCallback): () => void
  onAuthEvent(callback: (event: CloudAuthEvent) => void): () => void
}
