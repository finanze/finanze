import { DataManager } from "../dataManager"
import { Entity } from "@/domain"
import { EntityPort } from "@/application/ports"
import { EntityQueries } from "./queries"

export class EntityRepository implements EntityPort {
  constructor(private client: DataManager) {}

  async insert(entity: Entity): Promise<void> {
    await this.client.execute(EntityQueries.INSERT, [
      entity.id,
      entity.name,
      entity.naturalId ?? null,
      entity.type,
      entity.origin,
      entity.iconUrl ?? null,
    ])
  }

  async update(entity: Entity): Promise<void> {
    await this.client.execute(EntityQueries.UPDATE, [
      entity.name,
      entity.naturalId ?? null,
      entity.type,
      entity.origin,
      entity.iconUrl ?? null,
      entity.id,
    ])
  }

  async getAll(): Promise<Entity[]> {
    const result = await this.client.query<any>(EntityQueries.GET_ALL)
    return result.rows
      .map(this.mapEntity)
      .sort((a, b) => a.name.localeCompare(b.name))
  }

  async getById(id: string): Promise<Entity | null> {
    const result = await this.client.query<any>(EntityQueries.GET_BY_ID, [id])
    if (result.rows.length === 0) return null
    return this.mapEntity(result.rows[0])
  }

  async getByNaturalId(naturalId: string): Promise<Entity | null> {
    const result = await this.client.query<any>(
      EntityQueries.GET_BY_NATURAL_ID,
      [naturalId],
    )
    if (result.rows.length === 0) return null
    return this.mapEntity(result.rows[0])
  }

  async getByName(name: string): Promise<Entity | null> {
    const result = await this.client.query<any>(EntityQueries.GET_BY_NAME, [
      name,
    ])
    if (result.rows.length === 0) return null
    return this.mapEntity(result.rows[0])
  }

  async deleteById(entityId: string): Promise<void> {
    await this.client.execute(EntityQueries.DELETE_BY_ID, [entityId])
  }

  async getDisabledEntities(): Promise<Entity[]> {
    const result = await this.client.query<any>(
      EntityQueries.GET_DISABLED_ENTITIES,
    )

    return result.rows.map(this.mapEntity)
  }

  private mapEntity(row: any): Entity {
    return {
      id: row.id,
      name: row.name,
      naturalId: row.natural_id,
      type: row.type,
      origin: row.origin,
      iconUrl: row.icon_url,
    }
  }
}
