import { Entity, Feature } from "./entity"
import { ExternalIntegrationId } from "./externalIntegration"
import { ProductType } from "./globalPosition"

export interface PinDetails {
  positions: number
}

export enum CredentialType {
  ID = "ID",
  USER = "USER",
  PASSWORD = "PASSWORD",
  PIN = "PIN",
  PHONE = "PHONE",
  EMAIL = "EMAIL",
  API_TOKEN = "API_TOKEN",
  INTERNAL = "INTERNAL",
  INTERNAL_TEMP = "INTERNAL_TEMP",
}

export enum EntitySetupLoginType {
  MANUAL = "MANUAL",
  AUTOMATED = "AUTOMATED",
}

export enum EntitySessionCategory {
  NONE = "NONE",
  SHORT = "SHORT",
  MEDIUM = "MEDIUM",
  UNDEFINED = "UNDEFINED",
}

export interface NativeFinancialEntity extends Entity {
  setupLoginType: EntitySetupLoginType
  sessionCategory: EntitySessionCategory
  credentialsTemplate: Record<string, CredentialType>
  features: Feature[]
  products: ProductType[]
  pin?: PinDetails | null
}

export interface NativeCryptoWalletEntity extends Entity {
  features: Feature[]
  requiredExternalIntegrations: ExternalIntegrationId[]
}

export type EntityCredentials = Partial<Record<string, string>>

export interface FinancialEntityCredentialsEntry {
  entityId: string
  createdAt?: string | null
  lastUsedAt?: string | null
  expiration?: string | null
}
