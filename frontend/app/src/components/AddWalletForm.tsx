import { useState } from "react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Loader2, Plus, X } from "lucide-react"
import { CryptoWalletConnectionResult, Entity } from "@/types"
import { useI18n } from "@/i18n"
import { ApiErrorException } from "@/utils/apiErrors"

interface AddWalletFormProps {
  entity: Entity
  onSubmit: (
    name: string,
    addresses: string[],
  ) => Promise<CryptoWalletConnectionResult | void>
  onCancel: () => void
  isLoading?: boolean
}

const MAX_ADDRESSES = 10

export function AddWalletForm({
  entity,
  onSubmit,
  onCancel,
  isLoading = false,
}: AddWalletFormProps) {
  const { t } = useI18n()
  const [name, setName] = useState("")
  const [nameError, setNameError] = useState("")
  const [addresses, setAddresses] = useState<string[]>([""])
  const [addressErrors, setAddressErrors] = useState<string[]>([""])

  const addressErrorMap = t.walletForm.addressErrors as Record<string, string>
  const genericErrorMap = t.walletForm.errors as Record<string, string>
  const addressesLabel =
    (t.walletForm.fields as Record<string, string>).addresses ??
    t.walletForm.fields.address

  const translateFailureCode = (code?: string): string => {
    if (!code) {
      return genericErrorMap.generic
    }

    return (
      addressErrorMap[code] || genericErrorMap[code] || genericErrorMap.generic
    )
  }

  const validateForm = () => {
    const trimmedName = name.trim()
    const trimmedAddresses = addresses.map(address => address.trim())
    let isValid = true

    if (!trimmedName) {
      setNameError(t.walletForm.errors.nameRequired)
      isValid = false
    } else {
      setNameError("")
    }

    const newAddressErrors = trimmedAddresses.map(() => "")

    trimmedAddresses.forEach((address, index) => {
      if (!address) {
        newAddressErrors[index] = t.walletForm.errors.addressRequired
        isValid = false
        return
      }

      if (address.length < 10) {
        newAddressErrors[index] = t.walletForm.errors.addressTooShort
        isValid = false
      }
    })

    const duplicates = new Map<string, number[]>()
    trimmedAddresses.forEach((address, index) => {
      if (!address) {
        return
      }
      const key = address.toLowerCase()
      const indexes = duplicates.get(key) ?? []
      indexes.push(index)
      duplicates.set(key, indexes)
    })

    duplicates.forEach(indexes => {
      if (indexes.length > 1) {
        indexes.forEach(idx => {
          newAddressErrors[idx] = t.walletForm.errors.addressDuplicate
        })
        isValid = false
      }
    })

    setAddressErrors(newAddressErrors)

    if (!isValid) {
      return null
    }

    return {
      trimmedName,
      trimmedAddresses,
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    const validated = validateForm()

    if (!validated) {
      return
    }

    const { trimmedName, trimmedAddresses } = validated

    setName(trimmedName)
    setAddresses(trimmedAddresses)

    try {
      const result = await onSubmit(trimmedName, trimmedAddresses)

      if (!result || !result.failed) {
        return
      }

      const failedEntries = result.failed
      const failedDetails = trimmedAddresses
        .map(address => {
          const failureCode = failedEntries[address]
          if (!failureCode) {
            return null
          }
          return {
            value: address,
            error: translateFailureCode(failureCode),
          }
        })
        .filter(Boolean) as Array<{ value: string; error: string }>

      if (failedDetails.length === 0) {
        return
      }

      setAddresses(failedDetails.map(item => item.value))
      setAddressErrors(failedDetails.map(item => item.error))
    } catch (error) {
      console.error("Add wallet error:", error)
      const translatedError = translateFailureCode(
        (error as ApiErrorException).code,
      )
      setAddressErrors(prev => prev.map(() => translatedError))
    }
  }

  const handleNameChange = (value: string) => {
    setName(value)
    if (nameError) {
      setNameError("")
    }
  }

  const handleAddressChange = (index: number, value: string) => {
    setAddresses(prev => {
      const next = [...prev]
      next[index] = value
      return next
    })
    setAddressErrors(prev => {
      const next = [...prev]
      next[index] = ""
      return next
    })
  }

  const handleAddAddress = () => {
    if (addresses.length >= MAX_ADDRESSES) {
      return
    }

    setAddresses(prev => [...prev, ""])
    setAddressErrors(prev => [...prev, ""])
  }

  const handleRemoveAddress = (index: number) => {
    if (addresses.length === 1) {
      return
    }

    setAddresses(prev => prev.filter((_, idx) => idx !== index))
    setAddressErrors(prev => prev.filter((_, idx) => idx !== index))
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-lg">
          {t.walletForm.title.replace("{entityName}", entity.name)}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wallet-name">{t.walletForm.fields.name}</Label>
            <Input
              id="wallet-name"
              type="text"
              value={name}
              onChange={e => handleNameChange(e.target.value)}
              placeholder={t.walletForm.placeholders.name}
              disabled={isLoading}
              className={nameError ? "border-red-500" : ""}
            />
            {nameError && <p className="text-sm text-red-500">{nameError}</p>}
          </div>

          <div className="space-y-3">
            <div className="flex items-baseline justify-between">
              <Label className="text-sm font-medium">{addressesLabel}</Label>
              <span className="text-xs text-muted-foreground">
                {addresses.length}/{MAX_ADDRESSES}
              </span>
            </div>

            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {addresses.map((address, index) => (
                <div key={`wallet-address-${index}`} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor={`wallet-address-${index}`}>
                      {t.walletForm.fields.addressNumber.replace(
                        "{number}",
                        String(index + 1),
                      )}
                    </Label>
                    {addresses.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRemoveAddress(index)}
                        disabled={isLoading}
                        aria-label={t.walletForm.actions.removeAddress}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                  <Input
                    id={`wallet-address-${index}`}
                    type="text"
                    value={address}
                    onChange={e => handleAddressChange(index, e.target.value)}
                    placeholder={t.walletForm.placeholders.address}
                    disabled={isLoading}
                    className={addressErrors[index] ? "border-red-500" : ""}
                  />
                  {addressErrors[index] && (
                    <p className="text-sm text-red-500">
                      {addressErrors[index]}
                    </p>
                  )}
                </div>
              ))}
            </div>

            <Button
              type="button"
              variant="ghost"
              onClick={handleAddAddress}
              disabled={isLoading || addresses.length >= MAX_ADDRESSES}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              {t.walletForm.actions.addAddress}
            </Button>

            {addresses.length >= MAX_ADDRESSES && (
              <p className="text-xs text-destructive">
                {t.walletForm.errors.maxAddresses}
              </p>
            )}
          </div>
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
