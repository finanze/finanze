import { CryptoWalletConnection } from "./crypto"
import { Entity, Feature } from "./entity"
import { ExternalIntegrationId } from "./externalIntegration"
import { ProductType } from "./globalPosition"
import {
  CredentialType,
  EntitySessionCategory,
  EntitySetupLoginType,
  PinDetails,
} from "./nativeEntity"

export enum FinancialEntityStatus {
  CONNECTED = "CONNECTED",
  DISCONNECTED = "DISCONNECTED",
  REQUIRES_LOGIN = "REQUIRES_LOGIN",
}

export interface AvailableSource extends Entity {
  features: Feature[]
  lastFetch: Partial<Record<Feature, string>>
  setupLoginType?: EntitySetupLoginType | null
  sessionCategory?: EntitySessionCategory | null
  credentialsTemplate?: Record<string, CredentialType> | null
  pin?: PinDetails | null
  status?: FinancialEntityStatus | null
  connected?: CryptoWalletConnection[] | null
  requiredExternalIntegrations?: ExternalIntegrationId[]
  externalEntityId?: string | null
  virtualFeatures?: Partial<Record<Feature, string>>
  nativelySupportedProducts?: ProductType[] | null
}

export interface AvailableSources {
  entities: AvailableSource[]
}
