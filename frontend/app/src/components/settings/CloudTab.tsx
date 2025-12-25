import { useState } from "react"
import { motion } from "framer-motion"
import { HardDrive, LogOut, Mail, User } from "lucide-react"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Badge } from "@/components/ui/Badge"
import { useI18n } from "@/i18n"
import { useCloud } from "@/context/CloudContext"
import { BackupMode, CloudRole } from "@/types"
import { cn } from "@/lib/utils"

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

export function CloudTab() {
  const { t } = useI18n()
  const {
    user,
    role,
    permissions,
    backupMode,
    setBackupMode,
    isLoading,
    isInitialized,
    oauthError,
    clearOAuthError,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    requestPasswordReset,
    isPasswordRecoveryActive,
    clearPasswordRecovery,
    updatePassword,
    signOut,
  } = useCloud()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<React.ReactNode | null>(null)
  const [authMode, setAuthMode] = useState<"signIn" | "signUp">("signIn")
  const [newPassword, setNewPassword] = useState("")
  const [confirmNewPassword, setConfirmNewPassword] = useState("")
  const [activeAction, setActiveAction] = useState<
    | null
    | "emailSignIn"
    | "emailSignUp"
    | "googleSignIn"
    | "passwordResetRequest"
    | "passwordUpdate"
    | "signOut"
  >(null)

  const isElectron = Boolean(window.ipcAPI)
  const isSignedIn = !!user
  const canSeeBackup = permissions.includes("backup.info")

  const TERMS_URL = "https://finanze.me/terms"
  const PRIVACY_URL = "https://finanze.me/privacy"

  const openExternalUrl = (url: string) => {
    try {
      window.open(url, "_blank")
    } catch {
      // ignore
    }
  }

  const setMode = (mode: BackupMode) => {
    setBackupMode(mode)
  }

  const backupModeSelector = (
    <div
      className="inline-flex w-fit items-center rounded-full border border-border bg-muted/30 p-0.5"
      role="tablist"
      aria-label={t.settings.backup.enableLabel}
    >
      <button
        type="button"
        role="tab"
        aria-selected={backupMode === BackupMode.OFF}
        onClick={() => setMode(BackupMode.OFF)}
        disabled={isLoading}
        className={cn(
          "h-7 rounded-full px-2 text-xs font-medium transition-colors",
          backupMode === BackupMode.OFF
            ? "bg-foreground text-background"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        {t.settings.backup.modes[BackupMode.OFF]}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={backupMode === BackupMode.AUTO}
        onClick={() => setMode(BackupMode.AUTO)}
        disabled={isLoading}
        className={cn(
          "h-7 rounded-full px-2 text-xs font-medium transition-colors",
          backupMode === BackupMode.AUTO
            ? "bg-foreground text-background"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        {t.settings.backup.modes[BackupMode.AUTO]}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={backupMode === BackupMode.MANUAL}
        onClick={() => setMode(BackupMode.MANUAL)}
        disabled={isLoading}
        className={cn(
          "h-7 rounded-full px-2 text-xs font-medium transition-colors",
          backupMode === BackupMode.MANUAL
            ? "bg-foreground text-background"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        {t.settings.backup.modes[BackupMode.MANUAL]}
      </button>
    </div>
  )

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    clearOAuthError()

    setActiveAction(authMode === "signIn" ? "emailSignIn" : "emailSignUp")
    try {
      if (authMode === "signIn") {
        await signInWithEmail(email, password)
        setEmail("")
        setPassword("")
        return
      }

      const result = await signUpWithEmail(email, password)
      setPassword("")

      if (result.status === "EMAIL_ALREADY_REGISTERED") {
        setError(t.settings.cloud.signUpErrors.email_exists)
        return
      }

      if (result.status === "PENDING_EMAIL_CONFIRMATION") {
        const template = t.settings.cloud.signUpSuccessCheckEmail
        const parts = template.split("{email}")
        setSuccess(
          <>
            {parts[0]}
            <strong className="font-semibold">{result.email}</strong>
            {parts.slice(1).join("{email}")}
          </>,
        )
      } else {
        setEmail("")
        setSuccess(t.settings.cloud.signUpSuccess)
      }
    } catch (err: unknown) {
      console.error("Cloud sign-in error:", err)

      const maybeStatus =
        typeof err === "object" && err && "status" in err
          ? (err as { status?: unknown }).status
          : undefined

      const maybeCode =
        typeof err === "object" && err && "code" in err
          ? (err as { code?: unknown }).code
          : undefined

      const maybeMessage =
        typeof err === "object" && err && "message" in err
          ? (err as { message?: unknown }).message
          : undefined

      const code = typeof maybeCode === "string" ? maybeCode : null
      const message = typeof maybeMessage === "string" ? maybeMessage : null
      const status = typeof maybeStatus === "number" ? maybeStatus : null

      if (status === 429) {
        setError(t.settings.cloud.tooManyRequests)
        return
      }

      if (authMode === "signUp") {
        const fallbackCode = code ?? "unknown"
        const translatedError =
          t.settings.cloud.signUpErrors[
            fallbackCode as keyof typeof t.settings.cloud.signUpErrors
          ] ?? t.settings.cloud.signUpErrors.unknown

        setError(translatedError.replace("{error}", fallbackCode))
        return
      }

      if (
        code === "invalid_credentials" ||
        message === "Invalid login credentials"
      ) {
        setError(t.settings.cloud.loginErrorInvalidCredentials)
        return
      }

      if (
        code === "email_not_confirmed" ||
        message?.toLowerCase().includes("not confirmed")
      ) {
        setError(t.settings.cloud.loginErrorEmailNotConfirmed)
        return
      }

      setError(t.settings.cloud.loginError)
    } finally {
      setActiveAction(null)
    }
  }

  const handleForgotPassword = async () => {
    setError(null)
    setSuccess(null)
    clearOAuthError()

    const normalizedEmail = email.trim()
    if (!normalizedEmail) {
      setError(t.settings.cloud.passwordResetEmailRequired)
      return
    }

    setActiveAction("passwordResetRequest")
    try {
      await requestPasswordReset(normalizedEmail)
      const template = t.settings.cloud.passwordResetEmailSent
      const parts = template.split("{email}")
      setSuccess(
        <>
          {parts[0]}
          <strong className="font-semibold">{normalizedEmail}</strong>
          {parts.slice(1).join("{email}")}
        </>,
      )
    } catch (err: unknown) {
      console.error("Password reset request error:", err)

      const maybeStatus =
        typeof err === "object" && err && "status" in err
          ? (err as { status?: unknown }).status
          : undefined

      const status = typeof maybeStatus === "number" ? maybeStatus : null
      if (status === 429) {
        setError(t.settings.cloud.tooManyRequests)
        return
      }

      setError(t.settings.cloud.passwordResetError)
    } finally {
      setActiveAction(null)
    }
  }

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    clearOAuthError()

    if (!newPassword || !confirmNewPassword) {
      setError(t.settings.cloud.passwordUpdateError)
      return
    }

    if (newPassword !== confirmNewPassword) {
      setError(t.settings.cloud.passwordMismatch)
      return
    }

    setActiveAction("passwordUpdate")
    try {
      await updatePassword(newPassword)
      setNewPassword("")
      setConfirmNewPassword("")
      setSuccess(t.settings.cloud.passwordUpdateSuccess)
      clearPasswordRecovery()
    } catch (err: unknown) {
      console.error("Password update error:", err)

      const maybeStatus =
        typeof err === "object" && err && "status" in err
          ? (err as { status?: unknown }).status
          : undefined

      const maybeCode =
        typeof err === "object" && err && "code" in err
          ? (err as { code?: unknown }).code
          : undefined

      const status = typeof maybeStatus === "number" ? maybeStatus : null
      const code = typeof maybeCode === "string" ? maybeCode : null

      if (status === 429) {
        setError(t.settings.cloud.tooManyRequests)
        return
      }

      if (code === "weak_password") {
        setError(t.settings.cloud.signUpErrors.weak_password)
        return
      }

      setError(t.settings.cloud.passwordUpdateError)
    } finally {
      setActiveAction(null)
    }
  }

  if (!isInitialized) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            <CardTitle>{t.settings.cloud.accountTitle}</CardTitle>
          </div>
          <CardDescription>{t.settings.cloud.description}</CardDescription>
        </CardHeader>
        <CardContent>
          {isPasswordRecoveryActive ? (
            <div className="space-y-4 mx-auto max-w-md">
              <div className="space-y-1 text-center">
                <p className="text-base font-medium">
                  {t.settings.cloud.passwordResetTitle}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t.settings.cloud.passwordResetDescription}
                </p>
              </div>

              <form onSubmit={handleUpdatePassword} className="space-y-4">
                <Input
                  type="password"
                  placeholder={t.settings.cloud.newPasswordPlaceholder}
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  minLength={6}
                />
                <Input
                  type="password"
                  placeholder={t.settings.cloud.confirmNewPasswordPlaceholder}
                  value={confirmNewPassword}
                  onChange={e => setConfirmNewPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  minLength={6}
                />

                {success && (
                  <p className="text-sm text-primary text-center">{success}</p>
                )}
                {error && (
                  <p className="text-sm text-destructive text-center">
                    {error}
                  </p>
                )}

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full"
                  size="lg"
                >
                  {isLoading ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      {t.common.saving}
                    </>
                  ) : (
                    t.settings.cloud.updatePassword
                  )}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  disabled={isLoading}
                  className="w-full"
                  onClick={() => {
                    setError(null)
                    setSuccess(null)
                    setNewPassword("")
                    setConfirmNewPassword("")
                    clearPasswordRecovery()
                  }}
                >
                  {t.settings.cloud.cancelPasswordReset}
                </Button>
              </form>
            </div>
          ) : isSignedIn ? (
            <div className="space-y-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-lg border border-border/50 bg-muted/20 p-4 dark:bg-muted/10">
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">
                    {t.settings.cloud.signedInAs}
                  </p>
                  <p className="font-medium">{user.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {role === CloudRole.PLUS && (
                    <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0">
                      {t.settings.cloud.roles[role]}
                    </Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={async () => {
                      setError(null)
                      setSuccess(null)
                      clearOAuthError()
                      setActiveAction("signOut")
                      try {
                        await signOut()
                      } finally {
                        setActiveAction(null)
                      }
                    }}
                    disabled={isLoading}
                    aria-label={t.settings.cloud.logout}
                  >
                    {isLoading && activeAction === "signOut" ? (
                      <LoadingSpinner size="sm" />
                    ) : (
                      <LogOut className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-6 mx-auto max-w-md">
              <form onSubmit={handleEmailAuth} className="space-y-4">
                <Input
                  type="email"
                  placeholder={t.settings.cloud.emailPlaceholder}
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  disabled={isLoading}
                />
                <Input
                  type="password"
                  placeholder={t.settings.cloud.passwordPlaceholder}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  minLength={6}
                />
                {success && (
                  <p className="text-sm text-primary text-center">{success}</p>
                )}
                {error && (
                  <p className="text-sm text-destructive text-center">
                    {error}
                  </p>
                )}
                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full"
                  size="lg"
                >
                  {isLoading &&
                  (activeAction === "emailSignIn" ||
                    activeAction === "emailSignUp") ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      {authMode === "signIn"
                        ? t.settings.cloud.loggingIn
                        : t.settings.cloud.signingUp}
                    </>
                  ) : (
                    <>
                      <Mail className="mr-2 h-4 w-4" />
                      {authMode === "signIn"
                        ? t.settings.cloud.signInWithEmail
                        : t.settings.cloud.signUp}
                    </>
                  )}
                </Button>

                {authMode === "signIn" && (
                  <button
                    type="button"
                    disabled={isLoading}
                    className="w-full text-xs text-muted-foreground"
                    onClick={handleForgotPassword}
                  >
                    {isLoading && activeAction === "passwordResetRequest" ? (
                      <span className="inline-flex items-center justify-center">
                        <LoadingSpinner size="sm" className="mr-2" />
                        {t.settings.cloud.sendingPasswordResetEmail}
                      </span>
                    ) : (
                      t.settings.cloud.forgotPassword
                    )}
                  </button>
                )}

                <button
                  type="button"
                  disabled={isLoading}
                  className="w-full text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                  onClick={() => {
                    setError(null)
                    setSuccess(null)
                    clearOAuthError()
                    setAuthMode(prev =>
                      prev === "signIn" ? "signUp" : "signIn",
                    )
                  }}
                >
                  {authMode === "signIn"
                    ? t.settings.cloud.noAccount
                    : t.settings.cloud.alreadyHaveAccount}
                </button>
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

              <div className="flex flex-col items-center gap-1">
                <Button
                  type="button"
                  variant="outline"
                  onClick={async () => {
                    setError(null)
                    setSuccess(null)
                    clearOAuthError()
                    setActiveAction("googleSignIn")
                    try {
                      await signInWithGoogle()
                    } finally {
                      setActiveAction(null)
                    }
                  }}
                  disabled={isLoading || !isElectron}
                  className="w-full"
                  size="lg"
                >
                  {isLoading && activeAction === "googleSignIn" ? (
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
                {!isElectron && (
                  <span className="text-xs text-muted-foreground">
                    {t.settings.cloud.googleDesktopOnly}
                  </span>
                )}
                {oauthError && (
                  <p className="text-sm text-destructive">{oauthError}</p>
                )}
              </div>

              <p className="text-xs leading-tight text-muted-foreground text-center">
                {t.settings.cloud.legalNoticePrefix}{" "}
                <a
                  href={TERMS_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="underline underline-offset-2 hover:text-foreground"
                  onClick={e => {
                    e.preventDefault()
                    openExternalUrl(TERMS_URL)
                  }}
                >
                  {t.settings.cloud.termsOfService}
                </a>{" "}
                {t.settings.cloud.legalNoticeAnd}{" "}
                <a
                  href={PRIVACY_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="underline underline-offset-2 hover:text-foreground"
                  onClick={e => {
                    e.preventDefault()
                    openExternalUrl(PRIVACY_URL)
                  }}
                >
                  {t.settings.cloud.privacyPolicy}
                </a>
                .
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {isSignedIn && canSeeBackup && (
        <Card>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto]">
            <div>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <HardDrive className="h-5 w-5 text-primary" />
                  <CardTitle>{t.settings.backup.enableLabel}</CardTitle>
                </div>
                <CardDescription>
                  {t.settings.backup.enableDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="sm:hidden">{backupModeSelector}</div>
                <p className="text-sm text-muted-foreground">
                  {t.settings.backup.modeDescriptions[backupMode]}
                </p>
              </CardContent>
            </div>

            <div className="hidden sm:flex items-center px-6">
              {backupModeSelector}
            </div>
          </div>
        </Card>
      )}
    </motion.div>
  )
}
