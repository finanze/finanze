import { ContributionQueryRequest, EntityContributions } from "@/domain"

export interface GetContributions {
  execute(query: ContributionQueryRequest): Promise<EntityContributions>
}
