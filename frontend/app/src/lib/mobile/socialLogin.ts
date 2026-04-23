import { isNativeMobile, isIOS } from "@/lib/platform"

function getUrlSafeNonce(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return Array.from(array, byte => byte.toString(16).padStart(2, "0")).join("")
}

async function sha256Hash(message: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(message)
  const hashBuffer = await crypto.subtle.digest("SHA-256", data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("")
}

async function getNonce(): Promise<{ rawNonce: string; nonceDigest: string }> {
  const rawNonce = getUrlSafeNonce()
  const nonceDigest = await sha256Hash(rawNonce)
  return { rawNonce, nonceDigest }
}

function decodeJWT(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split(".")[1]
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map(c => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

interface GoogleLoginResponseOnline {
  responseType: "online"
  accessToken: { token: string }
  idToken: string
  profile: {
    email: string | null
    familyName: string | null
    givenName: string | null
    id: string | null
    name: string | null
    imageUrl: string | null
  }
}

export interface MobileGoogleSignInResult {
  success: boolean
  idToken?: string
  rawNonce?: string
  error?: string
}

export interface MobileAppleSignInResult {
  success: boolean
  idToken?: string
  rawNonce?: string
  error?: string
}

let socialLoginInitialized = false

async function initializeSocialLogin(): Promise<void> {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return
  if (socialLoginInitialized) return

  const { SocialLogin } = await import("@capgo/capacitor-social-login")

  const webClientId = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID as string
  const iOSClientId = import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID as string

  if (!webClientId) {
    throw new Error("VITE_GOOGLE_WEB_CLIENT_ID is not configured")
  }

  await SocialLogin.initialize({
    google: {
      webClientId,
      ...(isIOS() && iOSClientId
        ? {
            iOSClientId,
            iOSServerClientId: webClientId,
          }
        : {}),
      mode: "online",
    },
  })

  socialLoginInitialized = true
}

function validateJWTToken(
  idToken: string,
  expectedNonceDigest: string,
  validClientIds: string[],
): { valid: boolean; error?: string } {
  const decodedToken = decodeJWT(idToken)

  if (!decodedToken) {
    return { valid: false, error: "Failed to decode JWT token" }
  }

  const audience = decodedToken.aud as string | undefined
  if (!audience || !validClientIds.includes(audience)) {
    return {
      valid: false,
      error: `Invalid audience. Expected one of ${validClientIds.join(" or ")}, got ${audience}`,
    }
  }

  const tokenNonce = decodedToken.nonce as string | undefined
  if (tokenNonce && tokenNonce !== expectedNonceDigest) {
    return {
      valid: false,
      error: `Nonce mismatch. Expected ${expectedNonceDigest}, got ${tokenNonce}`,
    }
  }

  return { valid: true }
}

export async function signInWithGoogleMobile(
  retry = false,
): Promise<MobileGoogleSignInResult> {
  if (!__MOBILE__) {
    return { success: false, error: "Not running on mobile platform" }
  }
  if (!isNativeMobile()) {
    return { success: false, error: "Not running on native mobile" }
  }

  try {
    const { SocialLogin } = await import("@capgo/capacitor-social-login")

    await initializeSocialLogin()

    const { rawNonce, nonceDigest } = await getNonce()

    const response = await SocialLogin.login({
      provider: "google",
      options: {
        scopes: ["email", "profile"],
        nonce: nonceDigest,
        forcePrompt: true,
      },
    })

    if (response.result.responseType !== "online") {
      return {
        success: false,
        error: "Offline mode not supported. Please use online mode.",
      }
    }

    const googleResponse = response.result as GoogleLoginResponseOnline

    if (!googleResponse.idToken) {
      return { success: false, error: "Failed to get Google ID token" }
    }

    const webClientId = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID as string
    const iOSClientId = import.meta.env.VITE_GOOGLE_IOS_CLIENT_ID as string
    const validClientIds = [webClientId, iOSClientId].filter(Boolean)

    const validation = validateJWTToken(
      googleResponse.idToken,
      nonceDigest,
      validClientIds,
    )

    if (!validation.valid) {
      console.warn("JWT validation failed:", validation.error)

      if (!retry) {
        console.log("Logging out from Google and retrying...")
        try {
          await SocialLogin.logout({ provider: "google" })
        } catch (logoutError) {
          console.error("Error during logout:", logoutError)
        }

        return signInWithGoogleMobile(true)
      }

      return {
        success: false,
        error: validation.error || "JWT validation failed",
      }
    }

    const decodedToken = decodeJWT(googleResponse.idToken)
    const hasNonce = decodedToken?.nonce !== undefined

    return {
      success: true,
      idToken: googleResponse.idToken,
      rawNonce: hasNonce ? rawNonce : undefined,
    }
  } catch (error) {
    console.error("Google authentication error:", error)
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Google authentication failed",
    }
  }
}

export async function logoutFromGoogleMobile(): Promise<void> {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  try {
    const { SocialLogin } = await import("@capgo/capacitor-social-login")
    await SocialLogin.logout({ provider: "google" })
  } catch {
    // Ignore logout errors
  }
}

export async function signInWithAppleMobile(): Promise<MobileAppleSignInResult> {
  if (!__MOBILE__) {
    return { success: false, error: "Not running on mobile platform" }
  }
  if (!isNativeMobile()) {
    return { success: false, error: "Not running on native mobile" }
  }

  try {
    const { SocialLogin } = await import("@capgo/capacitor-social-login")

    const { rawNonce, nonceDigest } = await getNonce()

    const response = await SocialLogin.login({
      provider: "apple",
      options: {
        scopes: ["email", "name"],
        nonce: nonceDigest,
      },
    })

    const appleResponse = response.result as {
      idToken?: string
      authorizationCode?: string
    }

    if (!appleResponse.idToken) {
      return { success: false, error: "Failed to get Apple identity token" }
    }

    return {
      success: true,
      idToken: appleResponse.idToken,
      rawNonce,
    }
  } catch (error) {
    console.error("Apple authentication error:", error)
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Apple authentication failed",
    }
  }
}

export async function logoutFromAppleMobile(): Promise<void> {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  try {
    const { SocialLogin } = await import("@capgo/capacitor-social-login")
    await SocialLogin.logout({ provider: "apple" })
  } catch {
    // Ignore logout errors
  }
}
