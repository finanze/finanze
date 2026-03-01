import { useState } from "react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Loader2, Plus, X, Eye, Wallet, Key } from "lucide-react"
import {
  AddressSource,
  CryptoWalletConnectionResult,
  DerivedAddressesResult,
  Entity,
  ScriptType,
} from "@/types"
import { useI18n } from "@/i18n"
import { ApiErrorException } from "@/utils/apiErrors"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs"
import { deriveCryptoAddresses } from "@/services/api"

export interface AddWalletSubmitData {
  name: string
  source: AddressSource
  addresses: string[]
  xpub?: string
  scriptType?: ScriptType
}

interface AddWalletFormProps {
  entity: Entity
  onSubmit: (
    data: AddWalletSubmitData,
  ) => Promise<CryptoWalletConnectionResult | void>
  onCancel: () => void
  isLoading?: boolean
}

const MAX_ADDRESSES = 10

const SCRIPT_TYPE_LABELS: Record<ScriptType, string> = {
  [ScriptType.P2PKH]: "P2PKH (Legacy)",
  [ScriptType.P2SH_P2WPKH]: "P2SH-P2WPKH (Nested SegWit)",
  [ScriptType.P2WPKH]: "P2WPKH (Native SegWit)",
  [ScriptType.P2TR]: "P2TR (Taproot)",
}

export function AddWalletForm({
  entity,
  onSubmit,
  onCancel,
  isLoading = false,
}: AddWalletFormProps) {
  const { t } = useI18n()
  const supportsHdWallet = entity.allows_hd_wallet === true

  const [name, setName] = useState("")
  const [nameError, setNameError] = useState("")
  const [addressSource, setAddressSource] = useState<AddressSource>(
    AddressSource.MANUAL,
  )

  const [addresses, setAddresses] = useState<string[]>([""])
  const [addressErrors, setAddressErrors] = useState<string[]>([""])

  const [xpub, setXpub] = useState("")
  const [xpubError, setXpubError] = useState("")
  const [scriptType, setScriptType] = useState<ScriptType | "">("")
  const [scriptTypeError, setScriptTypeError] = useState("")

  const [derivedPreview, setDerivedPreview] =
    useState<DerivedAddressesResult | null>(null)
  const [isDerivingAddresses, setIsDerivingAddresses] = useState(false)
  const [deriveError, setDeriveError] = useState("")

  const walletFormT = t.walletForm as Record<string, unknown>
  const addressErrorMap = t.walletForm.addressErrors as Record<string, string>
  const genericErrorMap = t.walletForm.errors as Record<string, string>
  const derivedT = (walletFormT.derived ?? {}) as Record<string, string>
  const addressesLabel =
    (t.walletForm.fields as Record<string, string>).addresses ??
    t.walletForm.fields.address

  const isDerived = addressSource === AddressSource.DERIVED

  const translateFailureCode = (code?: string): string => {
    if (!code) {
      return genericErrorMap.generic
    }
    return (
      addressErrorMap[code] || genericErrorMap[code] || genericErrorMap.generic
    )
  }

  const validateManualForm = () => {
    const trimmedName = name.trim()
    const trimmedAddresses = addresses.map(a => a.trim())
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
      if (!address) return
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

    if (!isValid) return null
    return { trimmedName, trimmedAddresses }
  }

  const validateDerivedForm = (requireName: boolean) => {
    const trimmedName = name.trim()
    const trimmedXpub = xpub.trim()
    let isValid = true

    if (requireName) {
      if (!trimmedName) {
        setNameError(t.walletForm.errors.nameRequired)
        isValid = false
      } else {
        setNameError("")
      }
    } else {
      setNameError("")
    }

    if (!trimmedXpub) {
      setXpubError(derivedT.xpubRequired || "Extended public key is required.")
      isValid = false
    } else {
      setXpubError("")
    }

    if (!scriptType) {
      setScriptTypeError(
        derivedT.scriptTypeRequired || "Script type is required.",
      )
      isValid = false
    } else {
      setScriptTypeError("")
    }

    if (!isValid) return null
    return { trimmedName, trimmedXpub, scriptType: scriptType as ScriptType }
  }

  const handlePreviewAddresses = async (options?: {
    scriptType?: ScriptType
    xpub?: string
  }) => {
    const scriptTypeValue = options?.scriptType ?? (scriptType || undefined)
    const xpubValue = (options?.xpub ?? xpub).trim()

    let isValid = true
    if (!xpubValue) {
      setXpubError(derivedT.xpubRequired || "Extended public key is required.")
      isValid = false
    } else {
      setXpubError("")
    }
    if (!scriptTypeValue) {
      setScriptTypeError(
        derivedT.scriptTypeRequired || "Script type is required.",
      )
      isValid = false
    } else {
      setScriptTypeError("")
    }
    if (!isValid) {
      return
    }

    setIsDerivingAddresses(true)
    setDeriveError("")

    try {
      const result = await deriveCryptoAddresses({
        xpub: xpubValue,
        network: entity.id,
        script_type: scriptTypeValue,
      })
      setDerivedPreview(result)
    } catch (error) {
      console.error("Derive addresses error:", error)
      const apiError = error as ApiErrorException
      if (apiError?.code === "INVALID_REQUEST") {
        setDeriveError(
          derivedT.invalidXpub ||
            "Invalid extended public key. Check it and try again.",
        )
        return
      }
      setDeriveError(
        apiError?.message ||
          derivedT.previewError ||
          "Failed to derive addresses. Check the xpub and try again.",
      )
    } finally {
      setIsDerivingAddresses(false)
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (isDerived) {
      const validated = validateDerivedForm(true)
      if (!validated) return

      if (!derivedPreview) {
        setDeriveError(
          derivedT.previewFirst ||
            "Preview addresses before adding the wallet.",
        )
        return
      }

      try {
        const result = await onSubmit({
          name: validated.trimmedName,
          source: AddressSource.DERIVED,
          addresses: [],
          xpub: validated.trimmedXpub,
          scriptType: validated.scriptType,
        })

        const failedEntries = result?.failed ?? {}
        const xpubFailureCode = failedEntries[validated.trimmedXpub]

        if (xpubFailureCode) {
          setDeriveError(translateFailureCode(xpubFailureCode))
          return
        }

        const fallbackFailureCode = Object.values(failedEntries)[0]
        if (fallbackFailureCode) {
          setDeriveError(translateFailureCode(fallbackFailureCode))
          return
        }
      } catch (error) {
        console.error("Add wallet error:", error)
        setDeriveError(translateFailureCode((error as ApiErrorException).code))
      }
      return
    }

    const validated = validateManualForm()
    if (!validated) return

    const { trimmedName, trimmedAddresses } = validated

    setName(trimmedName)
    setAddresses(trimmedAddresses)

    try {
      const result = await onSubmit({
        name: trimmedName,
        source: AddressSource.MANUAL,
        addresses: trimmedAddresses,
      })

      if (!result || !result.failed) return

      const failedEntries = result.failed
      const failedDetails = trimmedAddresses
        .map(address => {
          const failureCode = failedEntries[address]
          if (!failureCode) return null
          return { value: address, error: translateFailureCode(failureCode) }
        })
        .filter(Boolean) as Array<{ value: string; error: string }>

      if (failedDetails.length === 0) return

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
    if (nameError) setNameError("")
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
    if (addresses.length >= MAX_ADDRESSES) return
    setAddresses(prev => [...prev, ""])
    setAddressErrors(prev => [...prev, ""])
  }

  const handleRemoveAddress = (index: number) => {
    if (addresses.length === 1) return
    setAddresses(prev => prev.filter((_, idx) => idx !== index))
    setAddressErrors(prev => prev.filter((_, idx) => idx !== index))
  }

  const handleChangeSource = (next: AddressSource) => {
    setAddressSource(next)
    setDerivedPreview(null)
    setDeriveError("")
    setXpubError("")
    setScriptTypeError("")
  }

  return (
    <Card
      className={`w-full mx-auto max-h-[88vh] overflow-hidden flex flex-col ${isDerived ? "max-w-6xl" : "max-w-md"}`}
    >
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-lg pr-2 leading-none">
          {t.walletForm.title.replace("{entityName}", entity.name)}
        </CardTitle>
        {supportsHdWallet && (
          <Tabs
            value={addressSource}
            onValueChange={value => handleChangeSource(value as AddressSource)}
            className="shrink-0"
          >
            <TabsList className="h-9">
              <TabsTrigger
                value={AddressSource.MANUAL}
                className="text-xs px-2"
              >
                <Wallet className="h-3.5 w-3.5 mr-1" />
                {derivedT.manualTab || "Manual"}
              </TabsTrigger>
              <TabsTrigger
                value={AddressSource.DERIVED}
                className="text-xs px-2"
              >
                <Key className="h-3.5 w-3.5 mr-1" />
                {derivedT.xpubTab || "XPUB"}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        )}
      </CardHeader>
      <CardContent className="overflow-y-auto min-h-0">
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isDerived && (
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
          )}

          {isDerived ? (
            <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:gap-5 lg:space-y-0">
              <div className="space-y-4 lg:min-w-0">
                <div className="space-y-2">
                  <Label htmlFor="wallet-name">
                    {t.walletForm.fields.name}
                  </Label>
                  <Input
                    id="wallet-name"
                    type="text"
                    value={name}
                    onChange={e => handleNameChange(e.target.value)}
                    placeholder={t.walletForm.placeholders.name}
                    disabled={isLoading}
                    className={nameError ? "border-red-500" : ""}
                  />
                  {nameError && (
                    <p className="text-sm text-red-500">{nameError}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="wallet-xpub">
                    {derivedT.xpubLabel || "Extended Public Key"}
                  </Label>
                  <Input
                    id="wallet-xpub"
                    type="text"
                    value={xpub}
                    onChange={e => {
                      setXpub(e.target.value)
                      if (xpubError) setXpubError("")
                      if (derivedPreview) {
                        setDerivedPreview(null)
                      }
                    }}
                    placeholder={derivedT.xpubPlaceholder || "xpub6..."}
                    disabled={isLoading || isDerivingAddresses}
                    className={xpubError ? "border-red-500" : ""}
                  />
                  {xpubError && (
                    <p className="text-sm text-red-500">{xpubError}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="script-type">
                    {derivedT.scriptTypeLabel || "Script Type"}
                  </Label>
                  <select
                    id="script-type"
                    value={scriptType}
                    onChange={e => {
                      const nextScriptType = e.target.value as ScriptType
                      setScriptType(nextScriptType)
                      if (scriptTypeError) setScriptTypeError("")
                      if (derivedPreview && nextScriptType) {
                        void handlePreviewAddresses({
                          scriptType: nextScriptType,
                        })
                      }
                    }}
                    disabled={isLoading || isDerivingAddresses}
                    className={`flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
                      scriptTypeError ? "border-red-500" : "border-input"
                    }`}
                  >
                    <option value="">
                      {derivedT.scriptTypePlaceholder || "Select script type"}
                    </option>
                    {Object.values(ScriptType).map(st => (
                      <option key={st} value={st}>
                        {SCRIPT_TYPE_LABELS[st]}
                      </option>
                    ))}
                  </select>
                  {scriptTypeError && (
                    <p className="text-sm text-red-500">{scriptTypeError}</p>
                  )}
                </div>

                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    void handlePreviewAddresses()
                  }}
                  disabled={
                    isLoading ||
                    isDerivingAddresses ||
                    !xpub.trim() ||
                    !scriptType
                  }
                  className="w-full"
                >
                  {isDerivingAddresses ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Eye className="mr-2 h-4 w-4" />
                  )}
                  {derivedT.previewButton || "Preview addresses"}
                </Button>

                {deriveError && (
                  <p className="text-sm text-red-500">{deriveError}</p>
                )}
              </div>

              {derivedPreview ? (
                <div className="space-y-3 rounded-lg border border-gray-200 dark:border-gray-700 p-3 max-h-[56vh] overflow-y-auto lg:max-h-[66vh]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      {derivedT.basePath || "Base path"}
                    </span>
                    <code className="text-xs font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                      {derivedPreview.base_path}
                    </code>
                  </div>

                  {derivedPreview.receiving.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium">
                        {derivedT.receivingAddresses || "Receiving addresses"}
                      </p>
                      <div className="space-y-1">
                        {derivedPreview.receiving.map(addr => (
                          <div
                            key={addr.path}
                            className="text-xs py-1 px-2 rounded bg-gray-50 dark:bg-gray-800"
                          >
                            <div className="flex items-center gap-2 sm:hidden">
                              <span className="text-muted-foreground font-mono w-8 flex-shrink-0">
                                {addr.index}
                              </span>
                              <span className="font-mono text-muted-foreground truncate">
                                {addr.path}
                              </span>
                            </div>
                            <div className="font-mono break-all mt-0.5 sm:hidden">
                              {addr.address}
                            </div>

                            <div className="hidden sm:flex items-center gap-2">
                              <span className="text-muted-foreground font-mono w-10 flex-shrink-0">
                                {addr.index}
                              </span>
                              <span className="font-mono text-muted-foreground flex-shrink-0">
                                {addr.path}
                              </span>
                              <span className="font-mono truncate flex-1 text-right">
                                {addr.address}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {derivedPreview.change.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium">
                        {derivedT.changeAddresses || "Change addresses"}
                      </p>
                      <div className="space-y-1">
                        {derivedPreview.change.map(addr => (
                          <div
                            key={addr.path}
                            className="text-xs py-1 px-2 rounded bg-gray-50 dark:bg-gray-800"
                          >
                            <div className="flex items-center gap-2 sm:hidden">
                              <span className="text-muted-foreground font-mono w-8 flex-shrink-0">
                                {addr.index}
                              </span>
                              <span className="font-mono text-muted-foreground truncate">
                                {addr.path}
                              </span>
                            </div>
                            <div className="font-mono break-all mt-0.5 sm:hidden">
                              {addr.address}
                            </div>

                            <div className="hidden sm:flex items-center gap-2">
                              <span className="text-muted-foreground font-mono w-10 flex-shrink-0">
                                {addr.index}
                              </span>
                              <span className="font-mono text-muted-foreground flex-shrink-0">
                                {addr.path}
                              </span>
                              <span className="font-mono truncate flex-1 text-right">
                                {addr.address}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="hidden lg:flex flex-col space-y-3 rounded-lg border border-gray-200 dark:border-gray-700 p-4 justify-center min-h-[420px]">
                  <div className="h-4 w-28 rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                  <div className="h-4 w-44 mt-2 rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                  <div className="h-4 w-36 mt-2 rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                  <div className="h-8 w-full rounded-md bg-primary/10" />
                </div>
              )}
            </div>
          ) : (
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
            <Button
              type="submit"
              disabled={isLoading || (isDerived && !derivedPreview)}
              className="flex-1"
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.walletForm.submit}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
