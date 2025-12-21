import {
  createClient,
  SupabaseClient,
  AuthChangeEvent,
} from "@supabase/supabase-js"
import type {
  CloudAuthProvider,
  CloudSession,
  AuthStateChangeCallback,
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
        persistSession: true,
        detectSessionInUrl: true,
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

  async signOut(): Promise<void> {
    const { error } = await this.getClient().auth.signOut()
    if (error) {
      throw error
    }
  }

  async clearLocalSession(): Promise<void> {
    const authAny = this.getClient().auth as unknown as {
      _removeSession?: () => Promise<void>
      stopAutoRefresh?: () => void
    }

    authAny.stopAutoRefresh?.()

    if (authAny._removeSession) {
      await authAny._removeSession()
      return
    }

    if (typeof window !== "undefined") {
      try {
        const hostname = new URL(SUPABASE_URL).hostname
        const projectRef = hostname.split(".")[0]
        const key = `sb-${projectRef}-auth-token`
        window.localStorage?.removeItem(key)
        window.sessionStorage?.removeItem(key)
      } catch {
        // ignore
      }
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
}
