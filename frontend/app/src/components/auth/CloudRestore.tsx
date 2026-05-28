import type React from "react"
import { useState, useCallback, useRef, useEffect } from "react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowLeft,
  Download,
  Mail,
  AlertCircle,
  ShieldAlert,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { isNativeMobile, isIOS } from "@/lib/platform"
import { SupabaseAuthProvider } from "@/services/cloud/supabaseProvider"
import type { CloudSession } from "@/services/cloud/types"
import {
  getBackupsInfoWithCloudAuth,
  importBackup,
  cloudAuth,
  getApiServerInfo,
} from "@/services/api"
import { useAuth } from "@/context/AuthContext"
import type { FullBackupsInfo, BackupFileType } from "@/types"

type RestoreStep = "login" | "checking" | "credentials" | "importing" | "error"

interface CloudRestoreProps {
  onBack: () => void
  onRestoreComplete: () => void
  isDesktop: boolean
  pendingUsername?: string
}

const GoogleIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24">
    <path
      fill="currentColor"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="currentColor"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="currentColor"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="currentColor"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
)

const AppleIcon = () => (
  <svg className="h-7 w-7" viewBox="0 0 24 24">
    <path
      fill="currentColor"
      d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"
    />
  </svg>
)

export function CloudRestore({
  onBack,
  onRestoreComplete,
  isDesktop,
  pendingUsername,
}: CloudRestoreProps) {
  const { t } = useI18n()
  const { guestSignup, signup, logout } = useAuth()

  const [step, setStep] = useState<RestoreStep>("login")
  const [email, setEmail] = useState("")
  const [cloudPassword, setCloudPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loadingMethod, setLoadingMethod] = useState<
    "email" | "google" | "apple" | "restore" | null
  >(null)
  const [cloudSession, setCloudSession] = useState<CloudSession | null>(null)
  const [backups, setBackups] = useState<FullBackupsInfo | null>(null)
  const [restoreUsername, setRestoreUsername] = useState(pendingUsername || "")
  const [encryptionKey, setEncryptionKey] = useState("")
  const [guestCreated, setGuestCreated] = useState(false)

  const providerRef = useRef<SupabaseAuthProvider | null>(null)
  const unsubscribeRef = useRef<(() => void) | null>(null)

  const isElectron = Boolean(window.ipcAPI)
  const canUseGoogleSignIn = isElectron || isNativeMobile()
  const canUseAppleSignIn = isElectron || (isNativeMobile() && isIOS())

  const getProvider = useCallback(() => {
    if (!providerRef.current) {
      providerRef.current = new SupabaseAuthProvider()
    }
    return providerRef.current
  }, [])

  useEffect(() => {
    const init = async () => {
      const provider = getProvider()
      await provider.initialize()
    }
    init()

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current()
        unsubscribeRef.current = null
      }
    }
  }, [getProvider])

  const handleCloudLoginSuccess = useCallback(
    async (session: CloudSession) => {
      setCloudSession(session)
      setStep("checking")
      setError(null)

      try {
        const backupsInfo = await getBackupsInfoWithCloudAuth(
          session.accessToken,
        )

        const hasBackups = Object.values(backupsInfo.pieces).some(
          piece => piece.remote !== null,
        )

        if (!hasBackups) {
          setError(t.login.cloudRestore.noBackupsFound)
          setStep("login")
          setLoadingMethod(null)
          return
        }

        setBackups(backupsInfo)
        setStep("credentials")
      } catch (err) {
        console.error("Failed to check backups:", err)
        setError(t.login.cloudRestore.backupCheckFailed)
        setStep("login")
      } finally {
        setLoadingMethod(null)
      }
    },
    [t],
  )

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoadingMethod("email")

    try {
      const provider = getProvider()
      await provider.signInWithEmail(email, cloudPassword)
      const session = await provider.getSession()
      if (!session) {
        setError(t.settings.cloud.loginError)
        return
      }
      await handleCloudLoginSuccess(session)
    } catch (err: unknown) {
      console.error("Cloud sign-in error:", err)
      const maybeMessage =
        typeof err === "object" && err && "message" in err
          ? (err as { message?: string }).message
          : null
      if (
        maybeMessage?.includes("Invalid login") ||
        maybeMessage?.includes("invalid_credentials")
      ) {
        setError(t.settings.cloud.loginErrorInvalidCredentials)
      } else if (maybeMessage?.includes("Email not confirmed")) {
        setError(t.settings.cloud.loginErrorEmailNotConfirmed)
      } else {
        setError(t.settings.cloud.loginError)
      }
    } finally {
      setLoadingMethod(null)
    }
  }

  const handleGoogleSignIn = async () => {
    setError(null)
    setLoadingMethod("google")

    try {
      const provider = getProvider()

      if (isNativeMobile()) {
        const { signInWithGoogleMobile } =
          await import("@/lib/mobile/socialLogin")
        const result = await signInWithGoogleMobile()
        if (!result.idToken) {
          throw new Error("No ID token received from Google")
        }
        await provider.signInWithIdToken(
          "google",
          result.idToken,
          result.rawNonce,
        )
      } else {
        const serverInfo = await getApiServerInfo()
        const callbackUrl = `${serverInfo.baseUrl}/oauth/callback`

        const unsubscribe = provider.onAuthStateChange(async session => {
          if (session) {
            unsubscribe()
            await handleCloudLoginSuccess(session)
          }
        })
        unsubscribeRef.current = unsubscribe

        if (window.ipcAPI?.onOAuthCallbackUrl) {
          const ipcUnsub = window.ipcAPI.onOAuthCallbackUrl(async payload => {
            try {
              await provider.handleAuthCallbackUrl(payload.url)
            } catch (error) {
              const urlObj = new URL(payload.url)
              const code = urlObj.searchParams.get("code")
              if (code) {
                await provider.exchangeCodeForSession(code)
              } else {
                throw error
              }
            }
          })
          const prevUnsub = unsubscribeRef.current
          unsubscribeRef.current = () => {
            prevUnsub?.()
            ipcUnsub?.()
          }
        }

        await provider.signInWithGoogle(callbackUrl)
        return
      }

      const session = await provider.getSession()
      if (!session) {
        setError(t.settings.cloud.loginError)
        return
      }
      await handleCloudLoginSuccess(session)
    } catch (err) {
      console.error("Google sign-in error:", err)
      setError(err instanceof Error ? err.message : t.settings.cloud.loginError)
    } finally {
      setLoadingMethod(null)
    }
  }

  const handleAppleSignIn = async () => {
    setError(null)
    setLoadingMethod("apple")

    try {
      const provider = getProvider()

      if (isNativeMobile()) {
        const { signInWithAppleMobile } =
          await import("@/lib/mobile/socialLogin")
        const result = await signInWithAppleMobile()
        if (!result.idToken) {
          throw new Error("No ID token received from Apple")
        }
        await provider.signInWithIdToken(
          "apple",
          result.idToken,
          result.rawNonce,
        )
      } else {
        const serverInfo = await getApiServerInfo()
        const callbackUrl = `${serverInfo.baseUrl}/oauth/callback`

        const unsubscribe = provider.onAuthStateChange(async session => {
          if (session) {
            unsubscribe()
            await handleCloudLoginSuccess(session)
          }
        })
        unsubscribeRef.current = unsubscribe

        if (window.ipcAPI?.onOAuthCallbackUrl) {
          const ipcUnsub = window.ipcAPI.onOAuthCallbackUrl(async payload => {
            try {
              await provider.handleAuthCallbackUrl(payload.url)
            } catch (error) {
              const urlObj = new URL(payload.url)
              const code = urlObj.searchParams.get("code")
              if (code) {
                await provider.exchangeCodeForSession(code)
              } else {
                throw error
              }
            }
          })
          const prevUnsub = unsubscribeRef.current
          unsubscribeRef.current = () => {
            prevUnsub?.()
            ipcUnsub?.()
          }
        }

        await provider.signInWithApple(callbackUrl)
        return
      }

      const session = await provider.getSession()
      if (!session) {
        setError(t.settings.cloud.loginError)
        return
      }
      await handleCloudLoginSuccess(session)
    } catch (err) {
      console.error("Apple sign-in error:", err)
      setError(err instanceof Error ? err.message : t.settings.cloud.loginError)
    } finally {
      setLoadingMethod(null)
    }
  }

  const handleRestore = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!cloudSession || !backups) return

    setError(null)
    setLoadingMethod("restore")
    setStep("importing")

    try {
      if (!guestCreated) {
        const success = await guestSignup(restoreUsername)
        if (!success) {
          setError(t.login.cloudRestore.guestCreationFailed)
          setStep("credentials")
          setLoadingMethod(null)
          return
        }
        setGuestCreated(true)
      }

      await cloudAuth({
        token: {
          access_token: cloudSession.accessToken,
          refresh_token: cloudSession.refreshToken,
          token_type: cloudSession.tokenType,
          expires_at: cloudSession.expiresAt,
        },
      })

      const backupTypes: BackupFileType[] = Object.keys(backups.pieces).filter(
        key => backups.pieces[key as BackupFileType]?.remote !== null,
      ) as BackupFileType[]

      await importBackup({
        types: backupTypes,
        password: encryptionKey,
        force: true,
        initialize: true,
      })

      await logout()

      const success2 = await signup(restoreUsername, encryptionKey)
      if (!success2) {
        setError(t.login.cloudRestore.loginAfterRestoreFailed)
        setStep("credentials")
        setLoadingMethod(null)
        return
      }

      onRestoreComplete()
    } catch (err: unknown) {
      console.error("Restore failed:", err)
      const maybeCode =
        typeof err === "object" && err && "code" in err
          ? (err as { code?: string }).code
          : null

      if (maybeCode === "INVALID_BACKUP_CREDENTIALS") {
        setError(t.login.cloudRestore.invalidEncryptionKey)
      } else {
        setError(t.login.cloudRestore.restoreFailed)
      }
      setStep("credentials")
    } finally {
      setLoadingMethod(null)
    }
  }

  const handleBack = async () => {
    if (step === "importing") return

    if (guestCreated) {
      try {
        await logout()
      } catch {
        // ignore
      }
      setGuestCreated(false)
    }

    if (cloudSession) {
      try {
        const provider = getProvider()
        await provider.signOut()
      } catch {
        // ignore
      }
      setCloudSession(null)
    }

    setStep("login")
    setError(null)
    setBackups(null)
    setRestoreUsername("")
    setEncryptionKey("")
    onBack()
  }

  const isImporting = step === "importing"

  if (step === "checking") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-8">
        <LoadingSpinner size="lg" />
        <p className="text-sm text-muted-foreground">
          {t.login.cloudRestore.checkingBackups}
        </p>
      </div>
    )
  }

  if (step === "importing") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-8">
        <LoadingSpinner size="lg" />
        <p className="text-base font-medium">
          {t.login.cloudRestore.importing}
        </p>
        <div className="flex flex-col items-center gap-1 text-amber-500">
          <ShieldAlert className="h-4 w-4" />
          <p className="text-sm text-center">
            {t.login.cloudRestore.dontCloseApp}
          </p>
        </div>
      </div>
    )
  }

  if (step === "credentials") {
    return (
      <AnimatePresence mode="wait">
        <motion.div
          key="credentials"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className={cn("space-y-6", isDesktop ? "mx-auto max-w-md" : "w-full")}
        >
          <div className="text-center space-y-2">
            <Download className="h-8 w-8 mx-auto text-primary" />
            <p className="text-base font-medium">
              {t.login.cloudRestore.backupFound}
            </p>
          </div>

          <form onSubmit={handleRestore} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="restoreUsername">{t.login.nameLabel}</Label>
              <Input
                id="restoreUsername"
                type="text"
                value={restoreUsername}
                onChange={e => setRestoreUsername(e.target.value)}
                placeholder={t.login.namePlaceholder}
                required
                autoCapitalize="off"
                disabled={!!loadingMethod || !!pendingUsername}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="encryptionKey">
                {t.login.cloudRestore.encryptionKeyLabel}
              </Label>
              <Input
                id="encryptionKey"
                type="password"
                value={encryptionKey}
                onChange={e => setEncryptionKey(e.target.value)}
                placeholder={t.login.cloudRestore.encryptionKeyPlaceholder}
                required
                disabled={!!loadingMethod}
              />
              <p className="text-xs text-muted-foreground">
                {t.login.cloudRestore.encryptionKeyHint}
              </p>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-sm text-destructive text-center flex items-center justify-center gap-2"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </motion.div>
            )}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              disabled={!!loadingMethod || !restoreUsername || !encryptionKey}
            >
              {loadingMethod === "restore" ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  {t.login.cloudRestore.importing}
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  {t.login.cloudRestore.restoreButton}
                </>
              )}
            </Button>
          </form>

          <button
            type="button"
            onClick={handleBack}
            disabled={isImporting}
            className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t.login.cloudRestore.backToSignup}
          </button>
        </motion.div>
      </AnimatePresence>
    )
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key="cloud-login"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{ duration: 0.2 }}
        className={cn("space-y-6", isDesktop ? "mx-auto max-w-md" : "w-full")}
      >
        <form onSubmit={handleEmailSignIn} className="space-y-4">
          <Input
            type="email"
            placeholder={t.settings.cloud.emailPlaceholder}
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            disabled={!!loadingMethod}
          />
          <Input
            type="password"
            placeholder={t.settings.cloud.passwordPlaceholder}
            value={cloudPassword}
            onChange={e => setCloudPassword(e.target.value)}
            required
            disabled={!!loadingMethod}
            minLength={6}
          />

          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-sm text-destructive text-center flex items-center justify-center gap-2"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </motion.div>
          )}

          <Button
            type="submit"
            disabled={!!loadingMethod}
            className="w-full"
            size="lg"
          >
            {loadingMethod === "email" ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                {t.settings.cloud.loggingIn}
              </>
            ) : (
              <>
                <Mail className="mr-2 h-4 w-4" />
                {t.settings.cloud.signInWithEmail}
              </>
            )}
          </Button>
        </form>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border/50" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground">
              {t.settings.cloud.orContinueWith}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleGoogleSignIn}
            disabled={!!loadingMethod || !canUseGoogleSignIn}
            className="w-full"
            size="lg"
          >
            {loadingMethod === "google" ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                {t.settings.cloud.loggingIn}
              </>
            ) : (
              <>
                <GoogleIcon />
                <span className="ml-2">
                  {t.settings.cloud.signInWithGoogle}
                </span>
              </>
            )}
          </Button>
          {!canUseGoogleSignIn && (
            <span className="text-xs text-muted-foreground">
              {t.settings.cloud.googleDesktopOnly}
            </span>
          )}

          {canUseAppleSignIn && (
            <Button
              type="button"
              variant="outline"
              onClick={handleAppleSignIn}
              disabled={!!loadingMethod}
              className="w-full"
              size="lg"
            >
              {loadingMethod === "apple" ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  {t.settings.cloud.loggingIn}
                </>
              ) : (
                <>
                  <AppleIcon />
                  <span className="ml-2">
                    {t.settings.cloud.signInWithApple}
                  </span>
                </>
              )}
            </Button>
          )}
        </div>

        <button
          type="button"
          onClick={handleBack}
          className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t.login.cloudRestore.backToSignup}
        </button>
      </motion.div>
    </AnimatePresence>
  )
}
