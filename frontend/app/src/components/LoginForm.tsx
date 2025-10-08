import type React from "react"
import { useState, useEffect } from "react"
import { Clock } from "lucide-react"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import { CredentialType } from "@/types"

export function LoginForm() {
  const {
    selectedEntity,
    login,
    isLoading,
    storedCredentials,
    selectedFeatures,
    fetchOptions,
  } = useAppContext()
  const [credentials, setCredentials] = useState<Record<string, string>>({})
  const { t } = useI18n()

  useEffect(() => {
    // Initialize with stored credentials if available
    if (storedCredentials) {
      setCredentials(storedCredentials)
    } else {
      setCredentials({})
    }
  }, [storedCredentials])

  if (!selectedEntity) return null

  const lastTransactionsFetchRaw = selectedEntity.last_fetch?.TRANSACTIONS
  const hasTransactionsHistory =
    typeof lastTransactionsFetchRaw === "string" &&
    lastTransactionsFetchRaw.trim() !== ""
  const isDeepFetch = Boolean(fetchOptions.deep)
  const showTransactionsLoadingNotice =
    isLoading &&
    selectedFeatures.includes("TRANSACTIONS") &&
    (!hasTransactionsHistory || isDeepFetch)

  const handleInputChange = (key: string, value: string) => {
    setCredentials(prev => ({ ...prev, [key]: value }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    login(credentials)
  }

  // Get credential fields and sort them (password/PIN types last)
  // Filter out INTERNAL and INTERNAL_TEMP credential types
  const credentialFields = Object.entries(
    selectedEntity.credentials_template || {},
  ).filter(
    ([, type]) =>
      type !== CredentialType.INTERNAL && type !== CredentialType.INTERNAL_TEMP,
  )

  // Sort fields to put password and PIN fields last
  const sortedFields = [...credentialFields].sort((a, b) => {
    const [, typeA] = a
    const [, typeB] = b

    const isSecureA =
      typeA === CredentialType.PASSWORD || typeA === CredentialType.PIN
    const isSecureB =
      typeB === CredentialType.PASSWORD || typeB === CredentialType.PIN

    if (isSecureA && !isSecureB) return 1
    if (!isSecureA && isSecureB) return -1
    return 0
  })

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-center">
          {t.login.enterCredentials} {selectedEntity.name}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {sortedFields.map(([key, type]) => {
            const inputType =
              type === CredentialType.PASSWORD || type === CredentialType.PIN
                ? "password"
                : type === CredentialType.EMAIL
                  ? "email"
                  : "text"

            // Get localized placeholder from i18n
            const placeholder =
              t.login.credentials[type as keyof typeof t.login.credentials] ||
              key

            return (
              <div key={key} className="space-y-2">
                <Label htmlFor={key}>{placeholder}</Label>
                <Input
                  id={key}
                  type={inputType}
                  placeholder={placeholder}
                  value={credentials[key] || ""}
                  onChange={e => handleInputChange(key, e.target.value)}
                  required
                />
              </div>
            )
          })}
          {showTransactionsLoadingNotice && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200/50 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <Clock className="mt-[2px] h-4 w-4 flex-shrink-0" />
              <span>{t.features.transactionsLoadingNotice}</span>
            </div>
          )}
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? t.common.loading : t.common.submit}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
