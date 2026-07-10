import { useState, useEffect, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clipboard,
  Info,
  Link2,
  Link2Off,
  Upload,
} from "lucide-react"
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
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { Badge } from "@/components/ui/Badge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { setupIntegration, disableIntegration } from "@/services/api"
import { cn } from "@/lib/utils"
import { copyToClipboard } from "@/lib/clipboard"
import {
  PlatformType,
  ExternalIntegrationStatus,
  ExternalIntegrationType,
  type ExternalIntegration,
} from "@/types"
import { getPlatformType } from "@/lib/platform"

const INTEGRATION_CATEGORY_ORDER: ExternalIntegrationType[] = [
  ExternalIntegrationType.ENTITY_PROVIDER,
  ExternalIntegrationType.CRYPTO_PROVIDER,
  ExternalIntegrationType.CRYPTO_MARKET_PROVIDER,
  ExternalIntegrationType.DATA_SOURCE,
]

type IntegrationHintPart =
  | { type: "text"; value: string }
  | { type: "link"; label: string; url: string }
  | { type: "copylink"; label: string; url: string }

const parseIntegrationHintParts = (
  rawParts: unknown,
): IntegrationHintPart[] | undefined => {
  if (!Array.isArray(rawParts)) {
    return undefined
  }

  const parsed = rawParts
    .map(part => {
      if (typeof part === "string") {
        return part.trim() ? ({ type: "text", value: part } as const) : null
      }

      if (!part || typeof part !== "object") {
        return null
      }

      const data = part as Record<string, unknown>
      const type = typeof data.type === "string" ? data.type : undefined

      if (type === "copylink") {
        const label = typeof data.label === "string" ? data.label.trim() : ""
        const url = typeof data.url === "string" ? data.url.trim() : ""
        return label && url ? ({ type: "copylink", label, url } as const) : null
      }

      if (type === "link") {
        const label = typeof data.label === "string" ? data.label.trim() : ""
        const url = typeof data.url === "string" ? data.url.trim() : ""
        return label && url ? ({ type: "link", label, url } as const) : null
      }

      const value = typeof data.value === "string" ? data.value : undefined

      return value && value.trim() ? ({ type: "text", value } as const) : null
    })
    .filter(Boolean) as IntegrationHintPart[]

  return parsed.length > 0 ? parsed : undefined
}

const PRIVATE_KEY_PEM_REGEX =
  /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+-----END [A-Z0-9 ]*PRIVATE KEY-----/

function PrivateKeyField({
  id,
  label,
  value,
  hasError,
  disabled,
  onChange,
}: {
  id: string
  label: string
  value: string
  hasError: boolean
  disabled: boolean
  onChange: (value: string) => void
}) {
  const { t } = useI18n()
  const copy = t.settings.privateKeyField
  const [manual, setManual] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  const handleFile = useCallback(
    async (file: File) => {
      setFileError(null)
      try {
        const text = (await file.text()).trim()
        if (!PRIVATE_KEY_PEM_REGEX.test(text)) {
          setFileName(null)
          setFileError(copy.invalid)
          onChange("")
          return
        }
        onChange(text)
        setFileName(file.name)
      } catch {
        setFileName(null)
        setFileError(copy.readError)
      }
    },
    [copy.invalid, copy.readError, onChange],
  )

  const inputId = `${id}-file`

  return (
    <div className="space-y-2">
      {!manual ? (
        <>
          <label
            htmlFor={inputId}
            onDragOver={event => {
              event.preventDefault()
              if (!disabled) setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={event => {
              event.preventDefault()
              setDragOver(false)
              if (disabled) return
              const file = event.dataTransfer.files?.[0]
              if (file) void handleFile(file)
            }}
            className={cn(
              "flex flex-col items-center justify-center gap-1 rounded-md border border-dashed px-4 py-6 text-center text-sm transition-colors",
              disabled
                ? "cursor-not-allowed opacity-60"
                : "cursor-pointer hover:bg-muted/50",
              dragOver ? "border-primary bg-primary/5" : "border-input",
              hasError ? "border-red-500" : undefined,
            )}
          >
            <Upload className="h-5 w-5 text-muted-foreground" />
            {fileName && value ? (
              <span className="font-medium text-green-600 dark:text-green-400">
                {copy.loaded.replace("{file}", fileName)}
              </span>
            ) : (
              <>
                <span className="font-medium">{copy.dropHint}</span>
                <span className="text-xs text-muted-foreground">
                  {copy.browse}
                </span>
              </>
            )}
          </label>
          <input
            id={inputId}
            type="file"
            accept=".pem,.key,.txt,application/x-pem-file"
            className="hidden"
            disabled={disabled}
            onChange={event => {
              const file = event.target.files?.[0]
              if (file) void handleFile(file)
              event.target.value = ""
            }}
          />
          {fileError && (
            <p className="text-xs text-red-600 dark:text-red-400">
              {fileError}
            </p>
          )}
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              setManual(true)
              setFileError(null)
            }}
            className="text-xs text-muted-foreground underline"
          >
            {copy.manualToggle}
          </button>
        </>
      ) : (
        <>
          <textarea
            id={id}
            value={value}
            disabled={disabled}
            onChange={event => onChange(event.target.value)}
            placeholder={copy.manualPlaceholder || String(label)}
            rows={6}
            className={cn(
              "w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm font-mono shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
              hasError ? "border-red-500" : undefined,
            )}
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => setManual(false)}
            className="text-xs text-muted-foreground underline"
          >
            {copy.uploadToggle}
          </button>
        </>
      )}
    </div>
  )
}

export function IntegrationsTab() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const { showToast, externalIntegrations, fetchExternalIntegrations } =
    useAppContext()

  const [isSetupLoading, setIsSetupLoading] = useState<Record<string, boolean>>(
    {},
  )
  const [isDisableLoading, setIsDisableLoading] = useState<
    Record<string, boolean>
  >({})
  const [integrationPayloads, setIntegrationPayloads] = useState<
    Record<string, Record<string, string>>
  >({})
  const [integrationErrors, setIntegrationErrors] = useState<
    Record<string, Record<string, boolean>>
  >({})
  const [expandedIntegrations, setExpandedIntegrations] = useState<
    Record<string, boolean>
  >({})
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const platform = getPlatformType()

  const getIntegrationCopy = useCallback(
    (integration: ExternalIntegration) => {
      const translations =
        (
          ((t.settings as unknown as Record<string, unknown>)?.integration ??
            {}) as Record<string, unknown>
        )[integration.id] ?? {}

      const copy = translations as Record<string, unknown>

      const descriptionRaw =
        typeof copy.description === "string" ? copy.description.trim() : ""
      const helpRaw = typeof copy.help === "string" ? copy.help.trim() : ""
      const hintRaw =
        typeof copy.hint === "object" && copy.hint !== null
          ? (copy.hint as Record<string, unknown>)
          : undefined

      const hintText =
        typeof hintRaw?.text === "string" ? hintRaw.text.trim() : ""
      const hintTitleRaw =
        typeof hintRaw?.title === "string" ? hintRaw.title.trim() : ""
      const hintParts = parseIntegrationHintParts(hintRaw?.parts)
      const hintStepsRaw = Array.isArray(hintRaw?.steps)
        ? hintRaw.steps
        : undefined
      const hintSteps = hintStepsRaw
        ?.map(step => parseIntegrationHintParts(step))
        .filter(Boolean) as IntegrationHintPart[][] | undefined

      const hint =
        hintParts || hintText || (hintSteps && hintSteps.length > 0)
          ? {
              title: hintTitleRaw || integration.name,
              text: hintText || undefined,
              parts: hintParts,
              steps: hintSteps && hintSteps.length > 0 ? hintSteps : undefined,
            }
          : undefined

      return {
        title: integration.name,
        description: descriptionRaw || undefined,
        helpLabel: helpRaw || undefined,
        hint,
      }
    },
    [t],
  )

  const formatIntegrationMessage = useCallback(
    (message: string, integrationName: string) =>
      message
        .replace(/\{entity\}/g, integrationName)
        .replace(/\{integration\}/g, integrationName),
    [],
  )

  const [copiedHintUrl, setCopiedHintUrl] = useState<string | null>(null)

  const handleCopyHintUrl = useCallback(
    async (url: string) => {
      const ok = await copyToClipboard(url)
      if (ok) {
        setCopiedHintUrl(url)
        setTimeout(
          () => setCopiedHintUrl(prev => (prev === url ? null : prev)),
          1500,
        )
      } else {
        showToast(t.common.error, "error")
      }
    },
    [showToast, t],
  )

  const handleIntegrationFieldChange = useCallback(
    (integrationId: string, field: string, value: string) => {
      setIntegrationPayloads(prev => ({
        ...prev,
        [integrationId]: {
          ...(prev[integrationId] ?? {}),
          [field]: value,
        },
      }))

      setIntegrationErrors(prev => {
        const current = prev[integrationId]
        if (!current || !current[field]) {
          return prev
        }

        const updatedIntegrationErrors = { ...current, [field]: false }
        const next = { ...prev, [integrationId]: updatedIntegrationErrors }

        if (Object.values(updatedIntegrationErrors).every(error => !error)) {
          delete next[integrationId]
        }

        return next
      })
    },
    [],
  )

  const handleSetupIntegration = useCallback(
    async (integrationId: string) => {
      const integration = externalIntegrations.find(
        item => item.id === integrationId,
      )

      if (!integration) {
        return
      }

      const { title: integrationName } = getIntegrationCopy(integration)

      if (integrationId === "GOOGLE_SHEETS" && platform === PlatformType.WEB) {
        showToast(t.settings.googleSheetsWebDisabled, "warning")
        return
      }

      const schema = integration.payload_schema ?? {}
      const payload = integrationPayloads[integrationId] ?? {}

      const requiredFields = Object.keys(schema)
      const missingFields: Record<string, boolean> = {}

      requiredFields.forEach(field => {
        if (!payload[field] || payload[field].trim() === "") {
          missingFields[field] = true
        }
      })

      if (Object.keys(missingFields).length > 0) {
        setIntegrationErrors(prev => ({
          ...prev,
          [integrationId]: {
            ...(prev[integrationId] ?? {}),
            ...missingFields,
          },
        }))
        showToast(t.settings.validationError, "error")
        return
      }

      const sanitizedPayload: Record<string, string> = {}
      requiredFields.forEach(field => {
        if (payload[field] !== undefined) {
          sanitizedPayload[field] = payload[field].trim()
        }
      })

      setIsSetupLoading(prev => ({ ...prev, [integrationId]: true }))

      try {
        await setupIntegration(integrationId, sanitizedPayload)
        setIntegrationErrors(prev => {
          if (!prev[integrationId]) {
            return prev
          }

          const rest = { ...prev }
          delete rest[integrationId]
          return rest
        })
        setIntegrationPayloads(prev => {
          const clearedFields: Record<string, string> = {}
          requiredFields.forEach(field => {
            clearedFields[field] = ""
          })
          return { ...prev, [integrationId]: clearedFields }
        })
        const successMessage = formatIntegrationMessage(
          t.settings.integrationEnabledSuccess,
          integrationName,
        )
        showToast(successMessage, "success")
        await fetchExternalIntegrations(true)
      } catch (error) {
        console.error(error)
        const code = (error as any)?.code
        const translated = (code && (t.errors as any)?.[code]) || t.common.error
        const formattedError = formatIntegrationMessage(
          translated,
          integrationName,
        )
        showToast(formattedError, "error")
      } finally {
        setIsSetupLoading(prev => ({ ...prev, [integrationId]: false }))
      }
    },
    [
      externalIntegrations,
      fetchExternalIntegrations,
      formatIntegrationMessage,
      getIntegrationCopy,
      integrationPayloads,
      platform,
      showToast,
      t,
    ],
  )

  const handleDisableIntegration = useCallback(
    async (integrationId: string) => {
      const integration = externalIntegrations.find(
        item => item.id === integrationId,
      )

      if (!integration) {
        return
      }

      const { title: integrationName } = getIntegrationCopy(integration)

      setIsDisableLoading(prev => ({ ...prev, [integrationId]: true }))

      try {
        await disableIntegration(integrationId)
        const successMessage = formatIntegrationMessage(
          t.settings.integrationDisabledSuccess,
          integrationName,
        )
        showToast(successMessage, "success")
        await fetchExternalIntegrations(true)
      } catch (error) {
        console.error(error)
        const code = (error as any)?.code
        const translated = (code && (t.errors as any)?.[code]) || t.common.error
        const formatted = formatIntegrationMessage(translated, integrationName)
        showToast(formatted, "error")
      } finally {
        setIsDisableLoading(prev => ({ ...prev, [integrationId]: false }))
      }
    },
    [
      externalIntegrations,
      fetchExternalIntegrations,
      formatIntegrationMessage,
      getIntegrationCopy,
      showToast,
      t,
    ],
  )

  const toggleIntegrationCard = (integrationId: string) => {
    setExpandedIntegrations(prev => ({
      ...prev,
      [integrationId]: !prev[integrationId],
    }))
  }

  useEffect(() => {
    setIntegrationPayloads(prev => {
      const next: Record<string, Record<string, string>> = {}

      externalIntegrations.forEach(integration => {
        const schema = integration.payload_schema ?? {}
        const existing = prev[integration.id] ?? {}
        const payload: Record<string, string> = {}

        Object.keys(schema).forEach(field => {
          payload[field] = existing[field] ?? ""
        })

        next[integration.id] = payload
      })

      return next
    })

    setIntegrationErrors(prev => {
      const next: Record<string, Record<string, boolean>> = {}

      externalIntegrations.forEach(integration => {
        const schemaFields = Object.keys(integration.payload_schema ?? {})
        const existingErrors = prev[integration.id]

        if (existingErrors) {
          const filtered: Record<string, boolean> = {}
          schemaFields.forEach(field => {
            if (existingErrors[field]) {
              filtered[field] = true
            }
          })

          if (Object.keys(filtered).length > 0) {
            next[integration.id] = filtered
          }
        }
      })

      return next
    })

    setExpandedIntegrations(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        next[integration.id] = prev[integration.id] ?? false
      })

      return next
    })

    setIsSetupLoading(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        if (prev[integration.id]) {
          next[integration.id] = prev[integration.id]
        }
      })

      return next
    })

    setIsDisableLoading(prev => {
      const next: Record<string, boolean> = {}

      externalIntegrations.forEach(integration => {
        if (prev[integration.id]) {
          next[integration.id] = prev[integration.id]
        }
      })

      return next
    })
  }, [externalIntegrations])

  useEffect(() => {
    const focus = searchParams.get("focus")
    if (!focus) {
      return
    }

    const integrationId = focus.toUpperCase()
    const exists = externalIntegrations.some(
      integration => integration.id === integrationId,
    )

    if (!exists) {
      return
    }

    setExpandedIntegrations(prev => {
      if (prev[integrationId]) {
        return prev
      }

      return {
        ...prev,
        [integrationId]: true,
      }
    })
    setHighlighted(integrationId)

    const timer = setTimeout(() => setHighlighted(null), 3500)
    return () => clearTimeout(timer)
  }, [externalIntegrations, searchParams])

  const renderIntegrationCard = (integration: ExternalIntegration) => {
    const schemaEntries = Object.entries(integration.payload_schema ?? {})
    const payload = integrationPayloads[integration.id] ?? {}
    const errors = integrationErrors[integration.id] ?? {}
    const isExpanded = expandedIntegrations[integration.id] ?? false
    const isEnabled = integration.status === ExternalIntegrationStatus.ON
    const isLoading = !!isSetupLoading[integration.id]
    const disableLoading = !!isDisableLoading[integration.id]
    const disabledForPlatform =
      integration.id === "GOOGLE_SHEETS" && platform === PlatformType.WEB
    const isUnavailable = !integration.available

    const { title, description, helpLabel, hint } =
      getIntegrationCopy(integration)

    const hintContent = (() => {
      if (!hint) {
        return null
      }

      const renderText = (value: string, keyPrefix: string) =>
        value.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((segment, segIndex) => {
          const boldMatch = segment.match(/^\*\*([^*]+)\*\*$/)
          if (boldMatch) {
            return (
              <strong key={`${keyPrefix}-b-${segIndex}`}>{boldMatch[1]}</strong>
            )
          }
          const italicMatch = segment.match(/^\*([^*]+)\*$/)
          if (italicMatch) {
            return <em key={`${keyPrefix}-i-${segIndex}`}>{italicMatch[1]}</em>
          }
          return <span key={`${keyPrefix}-t-${segIndex}`}>{segment}</span>
        })

      const renderParts = (parts: IntegrationHintPart[], keyPrefix: string) =>
        parts.map((part, index) => {
          if (part.type === "link") {
            return (
              <a
                key={`${keyPrefix}-link-${index}`}
                href={part.url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-primary"
              >
                {part.label}
              </a>
            )
          }

          if (part.type === "copylink") {
            const isCopied = copiedHintUrl === part.url
            return (
              <button
                key={`${keyPrefix}-copy-${index}`}
                type="button"
                onClick={() => handleCopyHintUrl(part.url)}
                title={t.common.copy}
                className={cn(
                  "inline-flex items-center gap-1 align-baseline underline break-all transition-colors duration-200",
                  isCopied ? "text-green-500" : "text-primary",
                )}
              >
                {part.label}
                {isCopied ? (
                  <Check className="h-3 w-3 flex-shrink-0" />
                ) : (
                  <Clipboard className="h-3 w-3 flex-shrink-0" />
                )}
              </button>
            )
          }

          return (
            <span key={`${keyPrefix}-text-${index}`}>
              {renderText(part.value, `${keyPrefix}-text-${index}`)}
            </span>
          )
        })

      if (hint.steps) {
        return (
          <ol className="text-sm leading-relaxed list-decimal pl-5 space-y-1.5">
            {hint.steps.map((step, sIdx) => (
              <li key={`${integration.id}-hint-step-${sIdx}`}>
                {renderParts(step, `${integration.id}-hint-step-${sIdx}`)}
              </li>
            ))}
          </ol>
        )
      }

      if (hint.parts) {
        return (
          <p className="text-sm leading-relaxed">
            {renderParts(hint.parts, `${integration.id}-hint`)}
          </p>
        )
      }

      if (hint.text) {
        return <p className="text-sm leading-relaxed">{hint.text}</p>
      }

      return null
    })()

    const hintButtonLabel =
      helpLabel ?? t.settings.integrationHintButton ?? t.common.help

    const hasHintLabel =
      typeof hintButtonLabel === "string" && hintButtonLabel.trim().length > 0

    const canSubmit =
      schemaEntries.length === 0 ||
      schemaEntries.every(([field]) => (payload[field] ?? "").trim() !== "")

    const iconSrc = `icons/external-integrations/${integration.id}.png`
    const isHighlighted = highlighted === integration.id

    return (
      <Card
        key={integration.id}
        className={cn(
          "self-start",
          isUnavailable ? "opacity-60" : undefined,
          isHighlighted ? "ring-2 ring-yellow-500 animate-pulse" : undefined,
        )}
      >
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div
              className={cn(
                "flex flex-1 items-center justify-between",
                isUnavailable ? "cursor-not-allowed" : "cursor-pointer",
              )}
              onClick={() => {
                if (!isUnavailable) {
                  toggleIntegrationCard(integration.id)
                }
              }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <img
                  src={iconSrc}
                  alt={title}
                  className="h-12 w-12 object-contain flex-shrink-0"
                />
                <div className="min-w-0">
                  <CardTitle className="text-lg break-words">{title}</CardTitle>
                  {isUnavailable && (
                    <p className="text-xs text-muted-foreground">
                      {t.common.notAvailableOnPlatform}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center space-x-1 flex-shrink-0">
                <Badge
                  className={cn(
                    "hidden sm:flex",
                    isEnabled
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                  )}
                >
                  {isEnabled ? t.common.enabled : t.common.disabled}
                </Badge>
                <span
                  className={cn(
                    "sm:hidden h-2.5 w-2.5 rounded-full flex-shrink-0",
                    isEnabled ? "bg-green-500" : "bg-red-500",
                  )}
                />
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </div>
            </div>
          </div>
          {description && (
            <CardDescription className="pt-2">{description}</CardDescription>
          )}
        </CardHeader>
        {isExpanded && !isUnavailable && (
          <CardContent className="space-y-4">
            {schemaEntries.length > 0 ? (
              schemaEntries.map(([field, label], index) => {
                const value = payload[field] ?? ""
                const hasError = !!errors[field]
                const inputType = /secret|password|token|key/i.test(field)
                  ? "password"
                  : "text"
                const showHintInline = Boolean(hintContent) && index === 0

                return (
                  <div key={field} className="space-y-2">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <Label
                        htmlFor={`${integration.id}-${field}`}
                        className="leading-tight"
                      >
                        {label}
                      </Label>
                      {showHintInline && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              size={hasHintLabel ? "sm" : "icon"}
                              type="button"
                              aria-label={
                                hasHintLabel ? hintButtonLabel : t.common.help
                              }
                              className={cn(
                                "text-xs text-muted-foreground",
                                hasHintLabel
                                  ? "gap-1 h-auto px-2 py-1"
                                  : "h-8 w-8 p-0",
                              )}
                            >
                              <Info className="h-4 w-4" />
                              {hasHintLabel ? (
                                <span>{hintButtonLabel}</span>
                              ) : undefined}
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent
                            align="start"
                            collisionPadding={12}
                            className="w-80 p-3 space-y-2 overflow-y-auto max-h-[min(70vh,var(--radix-popover-content-available-height))]"
                          >
                            <h4 className="text-sm font-medium">
                              {hint?.title ?? title}
                            </h4>
                            {hintContent}
                          </PopoverContent>
                        </Popover>
                      )}
                    </div>
                    {field === "private_key" ? (
                      <PrivateKeyField
                        id={`${integration.id}-${field}`}
                        label={String(label)}
                        value={value}
                        hasError={hasError}
                        disabled={isUnavailable || disabledForPlatform}
                        onChange={newValue =>
                          handleIntegrationFieldChange(
                            integration.id,
                            field,
                            newValue,
                          )
                        }
                      />
                    ) : (
                      <Input
                        id={`${integration.id}-${field}`}
                        type={inputType}
                        value={value}
                        onChange={event =>
                          handleIntegrationFieldChange(
                            integration.id,
                            field,
                            event.target.value,
                          )
                        }
                        placeholder={String(label)}
                        disabled={isUnavailable || disabledForPlatform}
                        className={cn(hasError ? "border-red-500" : undefined)}
                      />
                    )}
                  </div>
                )
              })
            ) : (
              <p className="text-sm text-muted-foreground">
                {t.common.notAvailable}
              </p>
            )}

            <div className="flex items-center justify-end gap-2">
              {disabledForPlatform && (
                <span className="text-xs text-muted-foreground">
                  {`(${t.settings.googleSheetsWebDisabled})`}
                </span>
              )}
              {isEnabled && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDisableIntegration(integration.id)}
                  disabled={disableLoading}
                >
                  {disableLoading ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      {t.common.loading}
                    </>
                  ) : (
                    <>
                      <Link2Off className="h-4 w-4 sm:mr-2" />
                      <span className="hidden sm:inline">
                        {t.entities.disconnect}
                      </span>
                    </>
                  )}
                </Button>
              )}
              <Button
                size="sm"
                onClick={() => handleSetupIntegration(integration.id)}
                disabled={
                  isLoading ||
                  !canSubmit ||
                  disabledForPlatform ||
                  isUnavailable
                }
              >
                {isLoading ? (
                  <>
                    <LoadingSpinner size="sm" color="invert" className="mr-2" />
                    {t.common.loading}
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    {t.common.setup}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-8"
    >
      {externalIntegrations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10">
            <LoadingSpinner size="md" />
            <p className="text-sm text-muted-foreground">{t.common.loading}</p>
          </CardContent>
        </Card>
      ) : (
        INTEGRATION_CATEGORY_ORDER.map(category => {
          const items = externalIntegrations.filter(
            integration => integration.type === category,
          )

          if (items.length === 0) {
            return null
          }

          return (
            <div key={category} className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300">
                {t.settings.integrationCategories[category]}
              </h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4">
                {items.map(integration => renderIntegrationCard(integration))}
              </div>
            </div>
          )
        })
      )}
    </motion.div>
  )
}
