import { useState, useEffect, useCallback } from "react"
import { useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { ChevronDown, ChevronUp, Info, Link2, Link2Off } from "lucide-react"
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
import {
  PlatformType,
  ExternalIntegrationStatus,
  type ExternalIntegration,
} from "@/types"

type IntegrationHintPart =
  | { type: "text"; value: string }
  | { type: "link"; label: string; url: string }

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

export function IntegrationsTab() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const {
    showToast,
    externalIntegrations,
    fetchExternalIntegrations,
    platform,
  } = useAppContext()

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

      const hint =
        hintParts || hintText
          ? {
              title: hintTitleRaw || integration.name,
              text: hintText || undefined,
              parts: hintParts,
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
        const successMessage = formatIntegrationMessage(
          t.settings.integrationEnabledSuccess,
          integrationName,
        )
        showToast(successMessage, "success")
        await fetchExternalIntegrations()
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
        await fetchExternalIntegrations()
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

    const { title, description, helpLabel, hint } =
      getIntegrationCopy(integration)

    const hintContent = (() => {
      if (!hint) {
        return null
      }

      if (hint.parts) {
        return (
          <p className="text-sm leading-relaxed">
            {hint.parts.map((part, index) => {
              if (part.type === "link") {
                return (
                  <a
                    key={`${integration.id}-hint-link-${index}`}
                    href={part.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline text-primary"
                  >
                    {part.label}
                  </a>
                )
              }

              return (
                <span key={`${integration.id}-hint-text-${index}`}>
                  {part.value}
                </span>
              )
            })}
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
          isHighlighted ? "ring-2 ring-yellow-500 animate-pulse" : undefined,
        )}
      >
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div
              className="flex flex-1 items-center justify-between cursor-pointer"
              onClick={() => toggleIntegrationCard(integration.id)}
            >
              <div className="flex items-center gap-3">
                <img
                  src={iconSrc}
                  alt={title}
                  className="h-12 w-12 object-contain"
                />
                <div>
                  <CardTitle className="text-lg">{title}</CardTitle>
                </div>
              </div>
              <div className="flex items-center space-x-1">
                <Badge
                  className={cn(
                    isEnabled
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                  )}
                >
                  {isEnabled ? t.common.enabled : t.common.disabled}
                </Badge>
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
        {isExpanded && (
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
                    <div className="flex items-start justify-between gap-2">
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
                          <PopoverContent className="w-80 p-3 space-y-2">
                            <h4 className="text-sm font-medium">
                              {hint?.title ?? title}
                            </h4>
                            {hintContent}
                          </PopoverContent>
                        </Popover>
                      )}
                    </div>
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
                      className={cn(hasError ? "border-red-500" : undefined)}
                    />
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
                      <Link2Off className="mr-2 h-4 w-4" />
                      {t.entities.disconnect}
                    </>
                  )}
                </Button>
              )}
              <Button
                size="sm"
                onClick={() => handleSetupIntegration(integration.id)}
                disabled={isLoading || !canSubmit || disabledForPlatform}
              >
                {isLoading ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
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
      className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4"
    >
      {externalIntegrations.length === 0 ? (
        <Card className="col-span-full">
          <CardContent className="flex flex-col items-center gap-3 py-10">
            <LoadingSpinner size="md" />
            <p className="text-sm text-muted-foreground">{t.common.loading}</p>
          </CardContent>
        </Card>
      ) : (
        externalIntegrations.map(integration =>
          renderIntegrationCard(integration),
        )
      )}
    </motion.div>
  )
}
