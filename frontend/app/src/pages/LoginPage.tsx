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
import { LockKeyhole, AlertCircle, User } from "lucide-react"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSignupMode, setIsSignupMode] = useState(false)
  const { login, signup, isLoading, lastLoggedUser } = useAuth()
  const { t } = useI18n()

  useEffect(() => {
    if (lastLoggedUser) {
      setUsername(lastLoggedUser)
      setIsSignupMode(false)
    } else {
      setIsSignupMode(true)
    }
  }, [lastLoggedUser])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      if (isSignupMode) {
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
    } catch {
      setError(t.login.serverError)
    }
  }

  const getTitle = () => {
    if (isSignupMode) {
      return t.login.signupTitle
    } else if (lastLoggedUser) {
      return t.login.welcomeBack.replace("{username}", lastLoggedUser)
    } else {
      return t.login.title
    }
  }

  const getSubtitle = () => {
    return isSignupMode ? t.login.signupSubtitle : t.login.subtitle
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
              {lastLoggedUser && !isSignupMode ? (
                <User className="h-8 w-8 text-primary-foreground" />
              ) : (
                <LockKeyhole className="h-8 w-8 text-primary-foreground" />
              )}
            </div>
            <CardTitle className="text-3xl text-center">{getTitle()}</CardTitle>
            <CardDescription className="text-center text-base">
              {getSubtitle()}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {(isSignupMode || !lastLoggedUser) && (
                <div className="space-y-2">
                  <Label htmlFor="username">{t.login.usernameLabel}</Label>
                  <div className="relative">
                    <Input
                      id="username"
                      type="text"
                      value={username}
                      onChange={e => setUsername(e.target.value)}
                      placeholder={t.login.usernamePlaceholder}
                      required
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

              <div className="space-y-2">
                <Label htmlFor="password">{t.login.passwordLabel}</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder={t.login.passwordPlaceholder}
                    required
                    autoFocus={!isSignupMode && !!lastLoggedUser}
                    className={cn(error ? "border-red-500 pr-10" : "")}
                  />
                  {error && (
                    <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                      <AlertCircle className="h-5 w-5 text-red-500" />
                    </div>
                  )}
                </div>
              </div>

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
