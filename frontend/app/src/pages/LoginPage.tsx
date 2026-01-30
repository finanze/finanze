import type React from "react"

import { useState, useEffect, useCallback } from "react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Switch } from "@/components/ui/Switch"
import { motion } from "framer-motion"
import { useAuth } from "@/context/AuthContext"
import {
  LockKeyhole,
  AlertCircle,
  User,
  KeyRound,
  Wrench,
  ScanFace,
  Fingerprint,
  ArrowLeft,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { useAppContext } from "@/context/AppContext"
import { AuthResultCode } from "@/types"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  LoginQuickSettings,
  VersionMismatchInfo,
} from "@/components/ui/ThemeSelector"
import { AdvancedSettings } from "@/components/ui/AdvancedSettings"
import { getApiServerInfo, checkStatus } from "@/services/api"
import { setFeatureFlags } from "@/context/featureFlagsStore"
import { isNativeMobile } from "@/lib/platform"
import {
  authenticateWithBiometric,
  checkBiometricAvailability,
  deleteCredentials,
  getCredentials,
  hasStoredCredentials as hasStoredBiometricCredentials,
  saveCredentials,
  BiometricType,
} from "@/lib/mobile/biometric"
import type { BiometricAvailability } from "@/lib/mobile/biometric"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [oldPassword, setOldPassword] = useState("")
  const [repeatPassword, setRepeatPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<AuthResultCode | null>(null)
  const [errorDetails, setErrorDetails] = useState<string | null>(null)
  const [isSignupMode, setIsSignupMode] = useState(false)
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)
  const [isDesktopApp, setIsDesktopApp] = useState(false)
  const [versionMismatch, setVersionMismatch] =
    useState<VersionMismatchInfo | null>(null)
  const [biometricAvailability, setBiometricAvailability] =
    useState<BiometricAvailability | null>(null)
  const [enableBiometric, setEnableBiometric] = useState(false)
  const [hasStoredCredentials, setHasStoredCredentials] = useState(false)
  const [isBiometricLoading, setIsBiometricLoading] = useState(false)
  const {
    login,
    signup,
    changePassword,
    isLoading,
    lastLoggedUser,
    isChangingPassword,
    pendingPasswordChangeUser,
    cancelPasswordChange,
  } = useAuth()
  const { showToast } = useAppContext()
  const { t } = useI18n()

  const isLoginMode = !isSignupMode && !isChangingPassword

  const biometricTypeForDisplay = biometricAvailability?.biometricType

  const checkBiometricStatus = useCallback(async () => {
    if (!__MOBILE__ || !isNativeMobile()) return

    const availability = await checkBiometricAvailability()
    setBiometricAvailability(availability)

    if (availability.isAvailable) {
      const hasCredentials = await hasStoredBiometricCredentials()
      setHasStoredCredentials(hasCredentials)
      if (hasCredentials) {
        setEnableBiometric(true)
      }
    } else {
      setHasStoredCredentials(false)
      setEnableBiometric(false)
    }
  }, [])

  const handleBiometricLogin = useCallback(async () => {
    if (!__MOBILE__ || !isNativeMobile()) return
    if (!hasStoredCredentials) return

    setIsBiometricLoading(true)
    try {
      const authenticated = await authenticateWithBiometric(
        t.login.biometricLoginReason,
      )
      if (!authenticated) {
        showToast(t.login.biometricLoginFailed, "error")
        return
      }

      const credentials = await getCredentials()
      if (!credentials) {
        showToast(t.login.biometricLoginFailed, "error")
        return
      }

      const { code, message } = await login(
        credentials.username,
        credentials.password,
      )
      if (code !== AuthResultCode.SUCCESS) {
        if (code === AuthResultCode.INVALID_CREDENTIALS) {
          await deleteCredentials()
          setHasStoredCredentials(false)
        }
        setError(
          code === AuthResultCode.INVALID_CREDENTIALS
            ? t.login.invalidCredentials
            : code === AuthResultCode.USER_NOT_FOUND
              ? t.login.userNotFound
              : t.login.unexpectedErrorContact,
        )
        setErrorCode(code)
        if (message) setErrorDetails(message)
      }
    } finally {
      setIsBiometricLoading(false)
    }
  }, [hasStoredCredentials, login, showToast, t])

  useEffect(() => {
    checkBiometricStatus()
  }, [checkBiometricStatus])

  useEffect(() => {
    if (!__MOBILE__ || !isNativeMobile()) return

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        checkBiometricStatus()
      }
    }

    window.addEventListener("focus", checkBiometricStatus)
    document.addEventListener("visibilitychange", onVisibility)
    return () => {
      window.removeEventListener("focus", checkBiometricStatus)
      document.removeEventListener("visibilitychange", onVisibility)
    }
  }, [checkBiometricStatus])

  useEffect(() => {
    if (isChangingPassword) {
      const userForDisplay = pendingPasswordChangeUser || lastLoggedUser
      if (userForDisplay) {
        setUsername(userForDisplay)
      }
      setIsSignupMode(false)
    } else if (lastLoggedUser) {
      setUsername(lastLoggedUser)
      setIsSignupMode(false)
    } else {
      setIsSignupMode(true)
    }
  }, [lastLoggedUser, isChangingPassword, pendingPasswordChangeUser])

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }

    if (window.ipcAPI) {
      setIsDesktopApp(true)
    }
  }, [])

  useEffect(() => {
    const checkVersionMismatch = async () => {
      try {
        const serverInfo = await getApiServerInfo()
        if (!serverInfo.isCustomServer) {
          setVersionMismatch(null)
          return
        }

        const statusResponse = await checkStatus()
        setFeatureFlags(statusResponse.features)
        const remoteVersion = statusResponse.server?.version
        const localVersion = __APP_VERSION__

        if (remoteVersion && remoteVersion !== localVersion) {
          setVersionMismatch({ localVersion, remoteVersion })
        } else {
          setVersionMismatch(null)
        }
      } catch (error) {
        console.error("Failed to check version mismatch:", error)
        setVersionMismatch(null)
      }
    }

    checkVersionMismatch()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setErrorCode(null)
    setErrorDetails(null)

    if ((isSignupMode || isChangingPassword) && password !== repeatPassword) {
      setError(t.login.passwordsDontMatch)
      return
    }

    const saveCredentialsIfEnabled = async () => {
      if (!__MOBILE__ || !isNativeMobile()) return

      if (enableBiometric && biometricAvailability?.isAvailable) {
        try {
          await saveCredentials({ username, password })
        } catch {
          // Silently fail; biometric storage is optional
        }
      }
    }

    const deleteStoredCredentialsIfDisabled = async () => {
      if (!__MOBILE__ || !isNativeMobile()) return
      if (!biometricAvailability?.isAvailable) return
      if (enableBiometric) return
      if (!hasStoredCredentials) return

      try {
        await deleteCredentials()
      } catch {
        // Silently fail; credential deletion is best-effort
      }
      setHasStoredCredentials(false)
    }

    try {
      if (isChangingPassword) {
        const result = await changePassword(oldPassword, password)
        if (result) {
          showToast(t.login.changePasswordSuccess, "success")
          setOldPassword("")
          setPassword("")
          setRepeatPassword("")
          setError(null)
          await saveCredentialsIfEnabled()
          await deleteStoredCredentialsIfDisabled()
        }
      } else if (isSignupMode) {
        const signupResult = await signup(username, password)
        if (!signupResult) {
          setError(t.login.invalidCredentials)
        } else {
          await saveCredentialsIfEnabled()
        }
      } else {
        const { code, message } = await login(username, password)
        switch (code) {
          case AuthResultCode.SUCCESS:
            await saveCredentialsIfEnabled()
            break
          case AuthResultCode.INVALID_CREDENTIALS:
            setError(t.login.invalidCredentials)
            setErrorCode(code)
            break
          case AuthResultCode.USER_NOT_FOUND:
            setError(t.login.userNotFound)
            setErrorCode(code)
            break
          case AuthResultCode.UNEXPECTED_ERROR:
          default:
            setError(t.login.unexpectedErrorContact)
            setErrorCode(AuthResultCode.UNEXPECTED_ERROR)
            if (message) {
              setErrorDetails(message)
            }
            break
        }
      }
    } catch (error: any) {
      if (isChangingPassword) {
        if (
          error.status === 401 ||
          error.message?.includes("401") ||
          error.message?.toLowerCase().includes("unauthorized") ||
          error.message?.toLowerCase().includes("invalid")
        ) {
          setError(t.login.invalidCredentials)
          showToast(t.login.invalidCredentials, "error")
        } else {
          const errorMessage = error.message || t.login.changePasswordError
          setError(errorMessage)
          showToast(errorMessage, "error")
        }
      } else {
        setError(t.login.unexpectedErrorContact)
        setErrorCode(AuthResultCode.UNEXPECTED_ERROR)
        if (error?.message) {
          setErrorDetails(error.message)
        }
      }
    }
  }

  const handleCancelPasswordChange = () => {
    cancelPasswordChange()
    setError(null)
    setErrorCode(null)
    setErrorDetails(null)
    setOldPassword("")
    setPassword("")
    setRepeatPassword("")
    setIsSignupMode(false)
  }

  const getTitle = () => {
    if (isChangingPassword) {
      return t.login.changePasswordTitle
    } else if (isSignupMode) {
      return t.login.signupTitle
    } else if (lastLoggedUser) {
      return t.login.welcomeBack.replace("{username}", lastLoggedUser)
    } else {
      return t.login.title
    }
  }

  const getSubtitle = () => {
    if (isChangingPassword) {
      return null
    } else if (isSignupMode) {
      return t.login.signupSubtitle
    } else {
      return t.login.subtitle
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-50 dark:bg-black p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gradient-100 to-gradient-300 dark:from-gradient-900 dark:to-black">
      <div className="absolute bottom-6 left-6">
        <LoginQuickSettings
          isDesktop={isDesktopApp}
          onOpenAdvancedSettings={() => setShowAdvancedSettings(true)}
          versionMismatch={versionMismatch}
        />
      </div>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <Card
          className={cn("relative shadow-lg", error ? "border-red-500" : "")}
        >
          <CardHeader className="space-y-1 flex flex-col items-center">
            {isChangingPassword && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute left-4 top-4"
                onClick={handleCancelPasswordChange}
                disabled={isLoading}
                aria-label={t.common.cancel}
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
            )}
            <div className="w-16 h-16 bg-primary rounded-full flex items-center justify-center mb-4 shadow-md">
              {isChangingPassword ? (
                <KeyRound className="h-8 w-8 text-primary-foreground" />
              ) : lastLoggedUser && !isSignupMode ? (
                <User className="h-8 w-8 text-primary-foreground" />
              ) : (
                <LockKeyhole className="h-8 w-8 text-primary-foreground" />
              )}
            </div>
            <CardTitle className="text-3xl text-center">{getTitle()}</CardTitle>
            {!isChangingPassword && (
              <CardDescription className="text-center text-base">
                {getSubtitle()}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit}
              className="space-y-6"
              noValidate={isChangingPassword}
            >
              {/* Username field - show for signup or when no lastLoggedUser, but NOT in change password mode */}
              {!isChangingPassword && (isSignupMode || !lastLoggedUser) && (
                <div className="space-y-2">
                  <Label htmlFor="username">{t.login.usernameLabel}</Label>
                  <div className="relative">
                    <Input
                      id="username"
                      type="text"
                      value={username}
                      onChange={e => setUsername(e.target.value)}
                      placeholder={t.login.usernamePlaceholder}
                      required={!isChangingPassword}
                      autoFocus={
                        !isNativeMobile() && (isSignupMode || !lastLoggedUser)
                      }
                      autoCapitalize="off"
                      className={cn(error ? "border-red-500 pr-10" : "")}
                    />
                    {error && (
                      <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                        <AlertCircle className="h-5 w-5 text-red-500" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Old password field - only for change password mode */}
              {isChangingPassword && (
                <div className="space-y-2">
                  <Label htmlFor="oldPassword">
                    {t.login.oldPasswordLabel}
                  </Label>
                  <div className="relative">
                    <Input
                      id="oldPassword"
                      type="password"
                      value={oldPassword}
                      onChange={e => setOldPassword(e.target.value)}
                      placeholder={t.login.oldPasswordPlaceholder}
                      required
                      autoFocus={!isNativeMobile()}
                      className={cn(error ? "border-red-500 pr-10" : "")}
                    />
                    {error && (
                      <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                        <AlertCircle className="h-5 w-5 text-red-500" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Password field - label and placeholder change based on mode */}
              <div className="space-y-2">
                <Label htmlFor="password">
                  {isChangingPassword
                    ? t.login.newPasswordLabel
                    : t.login.passwordLabel}
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder={
                      isChangingPassword
                        ? t.login.newPasswordPlaceholder
                        : t.login.passwordPlaceholder
                    }
                    required
                    autoFocus={
                      !isNativeMobile() &&
                      !isSignupMode &&
                      !isChangingPassword &&
                      !!lastLoggedUser
                    }
                    className={cn(error ? "border-red-500 pr-10" : "")}
                  />
                  {error && (
                    <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                      <AlertCircle className="h-5 w-5 text-red-500" />
                    </div>
                  )}
                </div>
              </div>

              {/* Repeat password field - show for signup and change password modes */}
              {(isSignupMode || isChangingPassword) && (
                <div className="space-y-2">
                  <Label htmlFor="repeatPassword">
                    {t.login.repeatPasswordLabel}
                  </Label>
                  <div className="relative">
                    <Input
                      id="repeatPassword"
                      type="password"
                      value={repeatPassword}
                      onChange={e => setRepeatPassword(e.target.value)}
                      placeholder={t.login.repeatPasswordPlaceholder}
                      required
                      className={cn(error ? "border-red-500 pr-10" : "")}
                    />
                    {error && (
                      <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                        <AlertCircle className="h-5 w-5 text-red-500" />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {isNativeMobile() &&
                biometricAvailability?.isAvailable &&
                (!isLoginMode || !hasStoredCredentials) && (
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2">
                      {biometricTypeForDisplay === BiometricType.FACE ? (
                        <ScanFace className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <Fingerprint className="h-5 w-5 text-muted-foreground" />
                      )}
                      <Label
                        htmlFor="enableBiometric"
                        className="text-sm cursor-pointer"
                      >
                        {t.login.enableBiometric.replace(
                          "{type}",
                          biometricTypeForDisplay === BiometricType.FACE
                            ? t.login.biometricFaceId
                            : t.login.biometricFingerprint,
                        )}
                      </Label>
                    </div>
                    <Switch
                      id="enableBiometric"
                      checked={enableBiometric}
                      onCheckedChange={setEnableBiometric}
                    />
                  </div>
                )}

              {error && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-red-500 dark:text-red-400 text-center flex items-center justify-center"
                >
                  {error}
                  {errorCode === AuthResultCode.UNEXPECTED_ERROR &&
                    errorDetails && (
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="ml-2 h-7 w-7 text-red-500"
                            aria-label={t.login.viewErrorDetails}
                          >
                            <Wrench className="h-4 w-4" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent
                          className="w-64 text-left text-sm"
                          sideOffset={8}
                        >
                          <p className="font-medium text-foreground">
                            {t.login.errorDetailsTitle}
                          </p>
                          <p className="mt-2 text-muted-foreground break-words">
                            {errorDetails}
                          </p>
                        </PopoverContent>
                      </Popover>
                    )}
                </motion.div>
              )}

              {isNativeMobile() && hasStoredCredentials && isLoginMode ? (
                <div className="flex items-center gap-3">
                  <Button
                    type="submit"
                    className="flex-1 text-lg py-6 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 transition-all duration-300 shadow-md"
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <>
                        <LoadingSpinner size="sm" className="mr-2" />
                        {t.common.loading}
                      </>
                    ) : (
                      t.common.unlock
                    )}
                  </Button>

                  <Button
                    type="button"
                    className="h-12 w-12 p-0 shrink-0"
                    disabled={isBiometricLoading}
                    onClick={handleBiometricLogin}
                    aria-label={t.login.biometricAuth}
                    title={t.login.biometricAuth}
                  >
                    {isBiometricLoading ? (
                      <LoadingSpinner size="sm" />
                    ) : biometricTypeForDisplay === BiometricType.FACE ? (
                      <ScanFace className="h-5 w-5" />
                    ) : (
                      <Fingerprint className="h-5 w-5" />
                    )}
                  </Button>
                </div>
              ) : (
                <Button
                  type="submit"
                  className="w-full text-lg py-6 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 transition-all duration-300 shadow-md"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      {t.common.loading}
                    </>
                  ) : isChangingPassword ? (
                    t.login.changePassword
                  ) : isSignupMode ? (
                    t.login.signup
                  ) : (
                    t.common.unlock
                  )}
                </Button>
              )}

              {(isSignupMode || isChangingPassword) && (
                <p className="text-xs text-muted-foreground text-center mt-4">
                  {t.login.syncPasswordHint}
                </p>
              )}
            </form>
          </CardContent>
        </Card>
      </motion.div>
      <AdvancedSettings
        isOpen={showAdvancedSettings}
        onClose={() => setShowAdvancedSettings(false)}
      />
    </div>
  )
}
