import { DataManager } from "../dataManager"
import { EntityCredentials, FinancialEntityCredentialsEntry } from "@/domain"
import { CredentialsPort } from "@/application/ports"
import { CredentialQueries } from "./queries"

export class CredentialsRepository implements CredentialsPort {
  constructor(private client: DataManager) {}

  async get(entityId: string): Promise<EntityCredentials | null> {
    try {
      const result = await this.client.query<any>(
        CredentialQueries.GET_BY_ENTITY,
        [entityId],
      )

      if (result.rows.length === 0) return null
      const row = result.rows[0]
      try {
        return row.credentials
          ? (JSON.parse(row.credentials) as EntityCredentials)
          : {}
      } catch {
        return null
      }
    } catch {
      return null
    }
  }

  async getAvailableEntities(): Promise<FinancialEntityCredentialsEntry[]> {
    try {
      const result = await this.client.query<any>(CredentialQueries.GET_ALL)

      return result.rows.map(row => ({
        entityId: row.entity_id,
        createdAt: row.created_at ?? null,
        lastUsedAt: row.last_used_at ?? null,
        expiration: row.expiration ?? null,
      }))
    } catch {
      return []
    }
  }

  async save(entityId: string, credentials: EntityCredentials): Promise<void> {
    const now = new Date().toISOString()
    await this.client.execute(CredentialQueries.INSERT, [
      entityId,
      JSON.stringify(credentials ?? {}),
      now,
      now,
    ])
  }

  async delete(entityId: string): Promise<void> {
    await this.client.execute(CredentialQueries.DELETE_BY_ENTITY, [entityId])
  }

  async updateLastUsage(entityId: string): Promise<void> {
    await this.client.execute(CredentialQueries.UPDATE_LAST_USED_AT, [
      new Date().toISOString(),
      entityId,
    ])
  }

  async updateExpiration(
    entityId: string,
    expiration: string | null,
  ): Promise<void> {
    await this.client.execute(CredentialQueries.UPDATE_EXPIRATION, [
      expiration,
      entityId,
    ])
  }
}
