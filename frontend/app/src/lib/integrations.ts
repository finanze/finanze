import type { ExternalIntegration, ExternalIntegrationFamily } from "@/types"

type IntegrationName = Pick<ExternalIntegration, "id" | "name">
type IntegrationTranslations = {
  settings: {
    integration: Record<string, { name?: string; description?: string }>
    aiProviderFamilies: Record<string, string>
    aiProviderMethods: Record<string, string>
  }
}

export function getIntegrationName(
  translations: IntegrationTranslations,
  integrationId: string,
  integration?: IntegrationName,
) {
  const copy = translations.settings.integration[integrationId]
  return copy?.name?.trim() || integration?.name.trim() || integrationId
}

export function getIntegrationFamilyName(
  translations: IntegrationTranslations,
  family: ExternalIntegrationFamily,
) {
  return (
    translations.settings.aiProviderFamilies[family.id]?.trim() ||
    family.name.trim() ||
    family.id
  )
}

export function getIntegrationMethodName(
  translations: IntegrationTranslations,
  integrationId: string,
  integration?: IntegrationName,
) {
  return (
    translations.settings.aiProviderMethods[integrationId]?.trim() ||
    getIntegrationName(translations, integrationId, integration)
  )
}
