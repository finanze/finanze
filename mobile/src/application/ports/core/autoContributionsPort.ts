import {
  AutoContributions,
  ContributionQueryRequest,
  DataSource,
  Entity,
} from "@/domain"

export interface AutoContributionsPort {
  save(
    entityId: string,
    data: AutoContributions,
    source: DataSource,
  ): Promise<void>
  getAllGroupedByEntity(
    query: ContributionQueryRequest,
  ): Promise<Map<Entity, AutoContributions>>
  deleteBySource(source: DataSource): Promise<void>
}
