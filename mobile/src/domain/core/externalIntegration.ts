export enum ExternalIntegrationType {
  CRYPTO_PROVIDER = "CRYPTO_PROVIDER",
  DATA_SOURCE = "DATA_SOURCE",
  ENTITY_PROVIDER = "ENTITY_PROVIDER",
  CRYPTO_MARKET_PROVIDER = "CRYPTO_MARKET_PROVIDER",
}

export enum ExternalIntegrationStatus {
  ON = "ON",
  OFF = "OFF",
}

export enum ExternalIntegrationId {
  GOOGLE_SHEETS = "GOOGLE_SHEETS",
  ETHERSCAN = "ETHERSCAN",
  ETHPLORER = "ETHPLORER",
  GOCARDLESS = "GOCARDLESS",
  COINGECKO = "COINGECKO",
  CRYPTOCOMPARE = "CRYPTOCOMPARE",
}

export interface ExternalIntegration {
  id: ExternalIntegrationId
  name: string
  type: ExternalIntegrationType
  status: ExternalIntegrationStatus
  payloadSchema?: Record<string, string> | null
}

export interface AvailableExternalIntegrations {
  integrations: ExternalIntegration[]
}

export type ExternalIntegrationPayload = Partial<Record<string, string>>

export interface ConnectedExternalIntegrationRequest {
  integrationId: ExternalIntegrationId
  payload: ExternalIntegrationPayload
}

export interface DisconnectedExternalIntegrationRequest {
  integrationId: ExternalIntegrationId
}

export type EnabledExternalIntegrations = Partial<
  Record<ExternalIntegrationId, ExternalIntegrationPayload>
>
