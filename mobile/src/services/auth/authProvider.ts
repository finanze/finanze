import { Session } from "@supabase/supabase-js"
import {
  GoogleSignin,
  statusCodes,
} from "@react-native-google-signin/google-signin"
import * as AuthSession from "expo-auth-session"
import * as WebBrowser from "expo-web-browser"
import { Buffer } from "buffer"
import { supabase } from "./supabaseClient"
import { Config } from "../../config"

import type { AuthStateChangeCallback, CloudSession } from "@/domain/cloudAuth"
import { CloudUserRole } from "@/domain"

// Configure Google Sign-In
export const configureGoogleSignIn = () => {
  GoogleSignin.configure({
    webClientId: Config.GOOGLE_WEB_CLIENT_ID,
    iosClientId: Config.GOOGLE_IOS_CLIENT_ID,
    offlineAccess: true,
  })
}

const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  const parts = token.split(".")
  if (parts.length < 2) return null

  const base64Url = parts[1]
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
  const padded = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  )

  try {
    const json = Buffer.from(padded, "base64").toString("utf8")
    const payload = JSON.parse(json)
    if (payload && typeof payload === "object") {
      return payload as Record<string, unknown>
    }
    return null
  } catch {
    return null
  }
}

const parseRole = (roleValue: unknown): CloudUserRole => {
  if (typeof roleValue !== "string") return CloudUserRole.NONE
  const normalized = roleValue.toUpperCase()
  if (normalized === CloudUserRole.PLUS) return CloudUserRole.PLUS
  return CloudUserRole.NONE
}

const parsePermissions = (permissionsValue: unknown): string[] => {
  if (!Array.isArray(permissionsValue)) return []
  return permissionsValue.filter(p => typeof p === "string") as string[]
}

// Convert Supabase session to CloudSession
const toCloudSession = (session: Session): CloudSession => {
  const payload = decodeJwtPayload(session.access_token)
  const role = parseRole(payload?.user_role)
  const permissions = parsePermissions(payload?.permissions)

  return {
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
    tokenType: session.token_type,
    expiresAt: session.expires_at ?? 0,
    user: {
      email:
        session.user.email ??
        (typeof payload?.email === "string" ? (payload.email as string) : ""),
      id: session.user.id,
      role,
      permissions,
    },
  }
}

export class AuthProvider {
  private initialized = false

  private async signInWithGoogleOAuth(): Promise<void> {
    WebBrowser.maybeCompleteAuthSession()

    const redirectTo = AuthSession.makeRedirectUri({
      scheme: "finanze",
      path: "auth/callback",
    })

    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        skipBrowserRedirect: true,
      },
    })

    if (error) {
      throw error
    }

    if (!data?.url) {
      throw new Error("No OAuth URL received from Supabase")
    }

    const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo)

    if (result.type !== "success") {
      throw new Error("Google sign-in was cancelled")
    }

    const callbackUrl = new URL(result.url)
    const authCode = callbackUrl.searchParams.get("code")

    if (!authCode) {
      throw new Error("No auth code received from Google")
    }

    const { error: exchangeError } =
      await supabase.auth.exchangeCodeForSession(authCode)

    if (exchangeError) {
      throw exchangeError
    }
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    try {
      configureGoogleSignIn()
      this.initialized = true
    } catch (error) {
      console.error("Failed to initialize auth provider:", error)
    }
  }

  async signInWithEmail(email: string, password: string): Promise<void> {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (error) {
      throw error
    }
  }

  async signInWithGoogle(): Promise<void> {
    try {
      // Check if device has Google Play Services
      await GoogleSignin.hasPlayServices()

      // Sign in with Google
      const userInfo = await GoogleSignin.signIn()

      if (!userInfo.data?.idToken) {
        throw new Error("No ID token received from Google")
      }

      // Sign in to Supabase with Google ID token
      const { error } = await supabase.auth.signInWithIdToken({
        provider: "google",
        token: userInfo.data.idToken,
      })

      if (error) {
        throw error
      }
    } catch (error: any) {
      // If Supabase rejects due to an OIDC nonce mismatch, fall back to the PKCE OAuth flow.
      if (
        typeof error?.message === "string" &&
        error.message.includes("Passed nonce and nonce in id_token")
      ) {
        await this.signInWithGoogleOAuth()
        return
      }

      if (error.code === statusCodes.SIGN_IN_CANCELLED) {
        throw new Error("Google sign-in was cancelled")
      } else if (error.code === statusCodes.IN_PROGRESS) {
        throw new Error("Google sign-in is already in progress")
      } else if (error.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        throw new Error("Google Play Services not available")
      }
      throw error
    }
  }

  async signOut(): Promise<void> {
    // Sign out from Google if signed in
    try {
      if (GoogleSignin.hasPreviousSignIn()) {
        await GoogleSignin.signOut()
      }
    } catch (error) {
      console.error("Google sign out error:", error)
    }

    // Sign out from Supabase
    const { error } = await supabase.auth.signOut()
    if (error) {
      throw error
    }
  }

  async getSession(): Promise<CloudSession | null> {
    const {
      data: { session },
      error,
    } = await supabase.auth.getSession()

    if (error) {
      throw error
    }

    if (!session) {
      return null
    }

    return toCloudSession(session)
  }

  onAuthStateChange(callback: AuthStateChangeCallback): () => void {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT" || !session) {
        callback(null)
        return
      }
      callback(toCloudSession(session))
    })

    return () => {
      subscription.unsubscribe()
    }
  }

  async refreshSession(): Promise<CloudSession | null> {
    const {
      data: { session },
      error,
    } = await supabase.auth.refreshSession()

    if (error) {
      throw error
    }

    if (!session) {
      return null
    }

    return toCloudSession(session)
  }
}

export const authProvider = new AuthProvider()
