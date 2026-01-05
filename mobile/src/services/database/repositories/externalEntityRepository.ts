import { DataManager } from "../dataManager"
import { ExternalEntity, ExternalEntityStatus } from "@/domain"
import { ExternalEntityPort } from "@/application/ports"
import { ExternalEntityQueries } from "./queries"

export class ExternalEntityRepository implements ExternalEntityPort {
  constructor(private client: DataManager) {}

  async upsert(ee: ExternalEntity): Promise<void> {
    await this.client.execute(ExternalEntityQueries.UPSERT, [
      ee.id,
      ee.entityId,
      ee.status,
      ee.provider,
      ee.date ?? null,
      ee.providerInstanceId ?? null,
      ee.payload != null ? JSON.stringify(ee.payload) : null,
    ])
  }

  async updateStatus(
    eeId: string,
    status: ExternalEntityStatus,
  ): Promise<void> {
    await this.client.execute(ExternalEntityQueries.UPDATE_STATUS, [
      status,
      eeId,
    ])
  }

  async getById(eeId: string): Promise<ExternalEntity | null> {
    try {
      const result = await this.client.query<any>(
        ExternalEntityQueries.GET_BY_ID,
        [eeId],
      )
      if (result.rows.length === 0) return null
      return this.mapRow(result.rows[0])
    } catch {
      return null
    }
  }

  async getByEntityId(entityId: string): Promise<ExternalEntity | null> {
    try {
      const result = await this.client.query<any>(
        ExternalEntityQueries.GET_BY_ENTITY_ID,
        [entityId],
      )

      if (result.rows.length === 0) return null

      return this.mapRow(result.rows[0])
    } catch {
      return null
    }
  }

  async deleteById(eeId: string): Promise<void> {
    await this.client.execute(ExternalEntityQueries.DELETE_BY_ID, [eeId])
  }

  async getAll(): Promise<ExternalEntity[]> {
    try {
      const result = await this.client.query<any>(ExternalEntityQueries.GET_ALL)
      return result.rows.map((r: any) => this.mapRow(r))
    } catch {
      return []
    }
  }

  private mapRow(row: any): ExternalEntity {
    let payload: Record<string, unknown> | null = null
    try {
      payload = row.payload ? JSON.parse(row.payload) : null
    } catch {
      payload = null
    }

    return {
      id: row.id,
      entityId: row.entity_id,
      status: row.status as ExternalEntityStatus,
      provider: row.provider,
      date: row.date ?? null,
      providerInstanceId: row.provider_instance_id ?? null,
      payload,
    }
  }
}
