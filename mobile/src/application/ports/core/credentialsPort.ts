import { EntityCredentials, FinancialEntityCredentialsEntry } from "@/domain"

export interface CredentialsPort {
  get(entityId: string): Promise<EntityCredentials | null>
  getAvailableEntities(): Promise<FinancialEntityCredentialsEntry[]>
  save(entityId: string, credentials: EntityCredentials): Promise<void>
  delete(entityId: string): Promise<void>
  updateLastUsage(entityId: string): Promise<void>
  updateExpiration(entityId: string, expiration: string | null): Promise<void>
}
