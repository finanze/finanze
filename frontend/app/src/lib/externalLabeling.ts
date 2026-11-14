import { ExternalIntegrationStatus, type ExternalIntegration } from "@/types"
import type { AIProviderEntry } from "@/types/ai"
import type { ExternalLabelingSettings } from "@/types/labeling"

export function externalProviderState(
  entry: AIProviderEntry,
  integrations: ExternalIntegration[],
) {
  const integration = integrations.find(item => item.id === entry.provider)
  if (!integration?.available) return "unavailableHere" as const
  if (integration.status === ExternalIntegrationStatus.EXPIRED)
    return "expired" as const
  if (integration.status !== ExternalIntegrationStatus.ON)
    return "notConnected" as const
  return "connected" as const
}

export function effectiveAIProviders(
  override: AIProviderEntry[] | undefined,
  shared: AIProviderEntry[] | undefined,
): AIProviderEntry[] {
  return override?.length ? override : (shared ?? [])
}

export function resolveAIProvider(
  entries: AIProviderEntry[],
  integrations: ExternalIntegration[],
) {
  return entries.find(
    entry =>
      entry.model.trim() &&
      externalProviderState(entry, integrations) === "connected",
  )
}

export function resolveExternalProvider(
  settings: ExternalLabelingSettings | undefined,
  integrations: ExternalIntegration[],
  shared?: AIProviderEntry[],
) {
  return settings?.enabled
    ? resolveAIProvider(
        effectiveAIProviders(settings.providers, shared),
        integrations,
      )
    : undefined
}
