import { Entity } from "@/domain"

export interface EntityPort {
  insert(entity: Entity): Promise<void>
  update(entity: Entity): Promise<void>
  getById(entityId: string): Promise<Entity | null>
  getAll(): Promise<Entity[]>
  getByNaturalId(naturalId: string): Promise<Entity | null>
  getByName(name: string): Promise<Entity | null>
  deleteById(entityId: string): Promise<void>
  getDisabledEntities(): Promise<Entity[]>
}
