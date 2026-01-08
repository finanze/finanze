import { AvailableSources } from "@/domain"

export interface GetAvailableEntities {
  execute(): Promise<AvailableSources>
}
