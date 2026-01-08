import { Entity, Feature, FetchRecord } from "@/domain"

export interface LastFetchesPort {
  getByEntityId(entityId: string): Promise<FetchRecord[]>
  getGroupedByEntity(feature: Feature): Promise<Map<Entity, FetchRecord>>
  save(fetchRecords: FetchRecord[]): Promise<void>
}
