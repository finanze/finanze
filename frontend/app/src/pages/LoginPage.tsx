import type React from "react"

import { useState, useEffect } from "react"
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
import { motion } from "framer-motion"
import { useAuth } from "@/context/AuthContext"
import { LockKeyhole, AlertCircle, User, KeyRound } from "lucide-react"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { useAppContext } from "@/context/AppContext"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [oldPassword, setOldPassword] = useState("")
  const [repeatPassword, setRepeatPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSignupMode, setIsSignupMode] = useState(false)
  const {
    login,
    signup,
    changePassword,
    isLoading,
    lastLoggedUser,
    isChangingPassword,
    pendingPasswordChangeUser,
  } = useAuth()
  const { showToast } = useAppContext()
  const { t } = useI18n()

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if ((isSignupMode || isChangingPassword) && password !== repeatPassword) {
      setError(t.login.passwordsDontMatch)
      return
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
        }
      } else if (isSignupMode) {
        const signupResult = await signup(username, password)
        if (!signupResult) {
          setError(t.login.invalidCredentials)
        }
      } else {
        const result = await login(username, password)
        if (!result) {
          setError(t.login.invalidCredentials)
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
        setError(t.login.serverError)
      }
    }
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
      return t.login.changePasswordSubtitle
    } else if (isSignupMode) {
      return t.login.signupSubtitle
    } else {
      return t.login.subtitle
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-black p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-100 to-gray-300 dark:from-gray-900 dark:to-black">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <Card className={cn("shadow-lg", error ? "border-red-500" : "")}>
          <CardHeader className="space-y-1 flex flex-col items-center">
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
            <CardDescription className="text-center text-base">
              {getSubtitle()}
            </CardDescription>
            {/* Show username in change password mode */}
            {isChangingPassword &&
              (pendingPasswordChangeUser || lastLoggedUser) && (
                <CardDescription className="text-center text-sm text-muted-foreground">
                  {t.login.usernameLabel}:{" "}
                  {pendingPasswordChangeUser || lastLoggedUser}
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
                      autoFocus={isSignupMode || !lastLoggedUser}
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
                      autoFocus
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
                      !isSignupMode && !isChangingPassword && !!lastLoggedUser
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

              {error && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-red-500 dark:text-red-400 text-center flex items-center justify-center"
                >
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {error}
                </motion.div>
              )}

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
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
