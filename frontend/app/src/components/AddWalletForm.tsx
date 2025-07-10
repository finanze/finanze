import { useState } from "react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Loader2, ArrowLeft } from "lucide-react"
import { Entity } from "@/types"
import { useI18n } from "@/i18n"
import { ApiErrorException } from "@/utils/apiErrors"

interface AddWalletFormProps {
  entity: Entity
  onSubmit: (name: string, address: string) => Promise<void>
  onCancel: () => void
  isLoading?: boolean
}

export function AddWalletForm({
  entity,
  onSubmit,
  onCancel,
  isLoading = false,
}: AddWalletFormProps) {
  const { t } = useI18n()
  const [formData, setFormData] = useState({
    name: "",
    address: "",
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string>("")

  const validateForm = () => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = t.walletForm.errors.nameRequired
    }

    if (!formData.address.trim()) {
      newErrors.address = t.walletForm.errors.addressRequired
    } else if (formData.address.length < 10) {
      newErrors.address = t.walletForm.errors.addressTooShort
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    try {
      setSubmitError("")
      await onSubmit(formData.name.trim(), formData.address.trim())
    } catch (error) {
      console.error("Add wallet error:", error)

      const translatedError =
        t.walletForm.errors[
          (error as ApiErrorException).code as keyof typeof t.walletForm.errors
        ]
      setSubmitError(translatedError || t.walletForm.errors.generic)
    }
  }

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: "" }))
    }
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="p-1 h-6 w-6"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <CardTitle className="text-lg">{t.walletForm.title}</CardTitle>
            <CardDescription>
              {t.walletForm.description.replace("{{entityName}}", entity.name)}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wallet-name">{t.walletForm.fields.name}</Label>
            <Input
              id="wallet-name"
              type="text"
              value={formData.name}
              onChange={e => handleInputChange("name", e.target.value)}
              placeholder={t.walletForm.placeholders.name}
              disabled={isLoading}
              className={errors.name ? "border-red-500" : ""}
            />
            {errors.name && (
              <p className="text-sm text-red-500">{errors.name}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wallet-address">
              {t.walletForm.fields.address}
            </Label>
            <Input
              id="wallet-address"
              type="text"
              value={formData.address}
              onChange={e => handleInputChange("address", e.target.value)}
              placeholder={t.walletForm.placeholders.address}
              disabled={isLoading}
              className={errors.address ? "border-red-500" : ""}
            />
            {errors.address && (
              <p className="text-sm text-red-500">{errors.address}</p>
            )}
          </div>

          {submitError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{submitError}</p>
            </div>
          )}

          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={isLoading}
              className="flex-1"
            >
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={isLoading} className="flex-1">
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.walletForm.submit}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
