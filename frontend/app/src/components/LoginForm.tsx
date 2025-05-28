import type React from "react"
import { useState, useEffect } from "react"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import { CredentialType } from "@/types"

export function LoginForm() {
  const { selectedEntity, login, isLoading, storedCredentials } =
    useAppContext()
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
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? t.common.loading : t.common.submit}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
