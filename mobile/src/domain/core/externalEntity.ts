import { Entity, EntityType } from "./entity"
import { ExternalIntegrationId } from "./externalIntegration"

export enum ExternalEntityStatus {
  UNLINKED = "UNLINKED",
  LINKED = "LINKED",
  ORPHAN = "ORPHAN",
}

export interface ExternalEntity {
  id: string
  entityId: string
  status: ExternalEntityStatus
  provider: ExternalIntegrationId
  date?: string | null
  providerInstanceId?: string | null
  payload?: Record<string, any> | null
}

export interface ProviderExternalEntityDetails {
  id: string
  name: string
  bic: string
  type: EntityType
  icon: string | null
}

export interface ExternalEntityCandidates {
  entities: ProviderExternalEntityDetails[]
}

export interface ExternalEntityCandidatesQuery {
  providers: ExternalIntegrationId[] | null
  country: string | null
}

export interface ExternalEntityLoginRequest {
  externalEntity: ExternalEntity
  redirectHost?: string | null
  relink?: boolean
  institutionId?: string | null
  userLanguage?: string | null
}

export interface ExternalEntityFetchRequest {
  externalEntity: ExternalEntity
  entity: Entity
}

export enum ExternalEntitySetupResponseCode {
  ALREADY_LINKED = "ALREADY_LINKED",
  CONTINUE_WITH_LINK = "CONTINUE_WITH_LINK",
}

export interface ExternalEntityConnectionResult {
  code: ExternalEntitySetupResponseCode
  link?: string | null
  providerInstanceId?: string | null
  payload?: any | null
  id?: string | null
}

export interface ExternalFetchRequest {
  externalEntityId: string
}

export interface ConnectExternalEntityRequest {
  institutionId: string | null
  externalEntityId: string | null
  provider: ExternalIntegrationId | null
  relink?: boolean
  redirectHost?: string | null
  userLanguage?: string | null
}

export interface CompleteExternalEntityLinkRequest {
  payload?: Record<string, any> | null
  externalEntityId?: string | null
}

export interface DeleteExternalEntityRequest {
  externalEntityId: string
}
