import {
  ExternalEntityCandidates,
  ExternalEntityCandidatesQuery,
} from "@/domain"

export interface GetAvailableExternalEntities {
  execute(
    request: ExternalEntityCandidatesQuery,
  ): Promise<ExternalEntityCandidates>
}
