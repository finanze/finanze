import { ExternalIntegrationStatus, type ExternalIntegration } from "@/types"
import type {
  ExternalLabelingProviderEntry,
  ExternalLabelingSettings,
} from "@/types/labeling"

export function externalProviderState(
  entry: ExternalLabelingProviderEntry,
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

export function resolveExternalProvider(
  settings: ExternalLabelingSettings | undefined,
  integrations: ExternalIntegration[],
) {
  return settings?.enabled
    ? settings.providers.find(
        entry =>
          entry.model.trim() &&
          externalProviderState(entry, integrations) === "connected",
      )
    : undefined
}
