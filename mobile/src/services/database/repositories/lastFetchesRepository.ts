import { DataManager } from "../dataManager"
import { Entity, Feature, FetchRecord } from "@/domain"
import { LastFetchesPort } from "@/application/ports"
import { LastFetchesQueries } from "./queries"

export class LastFetchesRepository implements LastFetchesPort {
  constructor(private client: DataManager) {}

  async getByEntityId(entityId: string): Promise<FetchRecord[]> {
    try {
      const result = await this.client.query<any>(
        LastFetchesQueries.GET_BY_ENTITY_ID,
        [entityId],
      )
      return result.rows.map(row => ({
        entityId: row.entity_id,
        feature: row.feature as Feature,
        date: row.date,
      }))
    } catch {
      return []
    }
  }

  async getAll(): Promise<FetchRecord[]> {
    try {
      const result = await this.client.query<any>(
        "SELECT entity_id, feature, date FROM last_fetches",
      )
      return result.rows.map(row => ({
        entityId: row.entity_id,
        feature: row.feature as Feature,
        date: row.date,
      }))
    } catch {
      return []
    }
  }

  async getGroupedByEntity(
    feature: Feature,
  ): Promise<Map<Entity, FetchRecord>> {
    try {
      const result = await this.client.query<any>(
        LastFetchesQueries.GET_GROUPED_BY_ENTITY,
        [feature],
      )

      const map = new Map<Entity, FetchRecord>()
      for (const row of result.rows) {
        const entity: Entity = {
          id: row.entity_id,
          name: row.entity_name,
          naturalId: row.entity_natural_id ?? null,
          type: row.entity_type,
          origin: row.entity_origin,
          iconUrl: row.icon_url,
        }
        const record: FetchRecord = {
          entityId: row.entity_id,
          feature: row.feature as Feature,
          date: row.date,
        }
        map.set(entity, record)
      }
      return map
    } catch {
      return new Map()
    }
  }

  async save(fetchRecords: FetchRecord[]): Promise<void> {
    for (const record of fetchRecords) {
      await this.client.execute(LastFetchesQueries.UPSERT, [
        record.entityId,
        record.feature,
        record.date,
      ])
    }
  }
}
