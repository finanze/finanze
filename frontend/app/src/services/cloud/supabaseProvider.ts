import {
  createClient,
  SupabaseClient,
  AuthChangeEvent,
} from "@supabase/supabase-js"
import type {
  CloudAuthProvider,
  CloudSession,
  AuthStateChangeCallback,
  EmailPasswordSignUpResult,
  CloudAuthEvent,
} from "./types"

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string
const SUPABASE_PUBLISHABLE_KEY = import.meta.env
  .VITE_SUPABASE_PUBLISHABLE_KEY as string

export class SupabaseAuthProvider implements CloudAuthProvider {
  private client: SupabaseClient | null = null

  async initialize(): Promise<void> {
    if (this.client) {
      return
    }

    if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
      throw new Error("Supabase configuration is missing")
    }
    this.client = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: {
        // IMPORTANT: keep this disabled until the app can hydrate a server-backed
        // session first. Otherwise, Supabase may eagerly refresh an expired
        // local-storage session, causing extra requests and token churn.
        autoRefreshToken: false,
        // The backend is the source of truth for the session - it provides the
        // token on init and shares it with other clients. Persisting locally
        // causes "refresh_token_already_used" errors when the backend or another
        // client has already consumed the refresh token.
        persistSession: false,
        detectSessionInUrl: true,
        // Use PKCE flow for OAuth (Google) and for email links that return a
        // PKCE code, relying on the verifier stored by auth-js.
        flowType: "pkce",
      },
    })
  }

  private getClient(): SupabaseClient {
    if (!this.client) {
      throw new Error("SupabaseAuthProvider not initialized")
    }
    return this.client
  }

  async handleAuthCallbackUrl(url: string): Promise<void> {
    const urlObj = new URL(url)

    const hash = urlObj.hash.startsWith("#")
      ? urlObj.hash.substring(1)
      : urlObj.hash
    const hashParams = new URLSearchParams(hash)
    const accessToken = hashParams.get("access_token")
    const refreshToken = hashParams.get("refresh_token")

    if (accessToken && refreshToken) {
      await this.setSession(accessToken, refreshToken)
      return
    }

    const code = urlObj.searchParams.get("code")
    if (code) {
      await this.exchangeCodeForSession(code)
      return
    }

    // No session material in the URL (could be a non-auth deeplink).
  }

  async signInWithGoogle(callbackUrl: string): Promise<void> {
    const isElectron = typeof window !== "undefined" && !!window.ipcAPI

    if (!isElectron) {
      throw new Error("Google sign-in is only available in the desktop app")
    }

    const { data, error } = await this.getClient().auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: callbackUrl,
        skipBrowserRedirect: true,
      },
    })
    if (error) {
      throw error
    }
    if (data?.url) {
      window.open(data.url, "_blank", "noopener,noreferrer")
    }
  }

  async signInWithEmail(email: string, password: string): Promise<void> {
    const { error } = await this.getClient().auth.signInWithPassword({
      email,
      password,
    })
    if (error) {
      throw error
    }
  }

  async signUpWithEmail(
    email: string,
    password: string,
    options?: { emailRedirectTo?: string },
  ): Promise<EmailPasswordSignUpResult> {
    const { data, error } = await this.getClient().auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: options?.emailRedirectTo,
      },
    })

    if (error) {
      throw error
    }

    // Supabase may return a user object but with an empty `identities` array
    // when the email is already registered (no new identity created).
    if (data.user?.identities && data.user.identities.length === 0) {
      return { status: "EMAIL_ALREADY_REGISTERED" }
    }

    if (!data.session) {
      return { status: "PENDING_EMAIL_CONFIRMATION", email }
    }

    return { status: "SIGNED_IN" }
  }

  async requestPasswordReset(
    email: string,
    options?: { emailRedirectTo?: string },
  ): Promise<void> {
    const { error } = await this.getClient().auth.resetPasswordForEmail(email, {
      redirectTo: options?.emailRedirectTo,
    })
    if (error) {
      throw error
    }
  }

  async updatePassword(password: string): Promise<void> {
    const { error } = await this.getClient().auth.updateUser({
      password,
    })
    if (error) {
      throw error
    }
  }

  async signOut(): Promise<void> {
    const { error } = await this.getClient().auth.signOut()
    if (error) {
      throw error
    }
  }

  async clearLocalSession(): Promise<void> {
    // With persistSession: false, there's no local session to clear.
    // We still stop auto-refresh and call internal methods as a safeguard.
    const authAny = this.getClient().auth as unknown as {
      _removeSession?: () => Promise<void>
      stopAutoRefresh?: () => void
    }

    authAny.stopAutoRefresh?.()

    if (authAny._removeSession) {
      await authAny._removeSession()
    }
  }

  async setSession(accessToken: string, refreshToken: string): Promise<void> {
    const { error } = await this.getClient().auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken,
    })
    if (error) {
      throw error
    }
  }

  async setAutoRefreshEnabled(enabled: boolean): Promise<void> {
    const authAny = this.getClient().auth as unknown as {
      startAutoRefresh?: () => void
      stopAutoRefresh?: () => void
    }

    if (enabled) {
      authAny.startAutoRefresh?.()
    } else {
      authAny.stopAutoRefresh?.()
    }
  }

  async exchangeCodeForSession(code: string): Promise<void> {
    const { error } = await this.getClient().auth.exchangeCodeForSession(code)
    if (error) {
      throw error
    }
  }

  async getSession(): Promise<CloudSession | null> {
    const {
      data: { session },
      error,
    } = await this.getClient().auth.getSession()
    if (error) {
      throw error
    }
    if (!session) {
      return null
    }
    return {
      accessToken: session.access_token,
      refreshToken: session.refresh_token,
      tokenType: session.token_type,
      expiresAt: session.expires_at ?? 0,
      user: {
        email: session.user.email ?? "",
        id: session.user.id,
      },
    }
  }

  onAuthStateChange(callback: AuthStateChangeCallback): () => void {
    const {
      data: { subscription },
    } = this.getClient().auth.onAuthStateChange(
      (event: AuthChangeEvent, session) => {
        if (event === "SIGNED_OUT" || !session) {
          callback(null)
          return
        }

        callback({
          accessToken: session.access_token,
          refreshToken: session.refresh_token,
          tokenType: session.token_type,
          expiresAt: session.expires_at ?? 0,
          user: {
            email: session.user.email ?? "",
            id: session.user.id,
          },
        })
      },
    )

    return () => {
      subscription.unsubscribe()
    }
  }

  onAuthEvent(callback: (event: CloudAuthEvent) => void): () => void {
    const {
      data: { subscription },
    } = this.getClient().auth.onAuthStateChange((event: AuthChangeEvent) => {
      callback(event as unknown as CloudAuthEvent)
    })

    return () => {
      subscription.unsubscribe()
    }
  }
}
