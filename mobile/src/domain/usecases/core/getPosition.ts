import { EntitiesPosition, PositionQueryRequest } from "@/domain"

export interface GetPosition {
  execute(query: PositionQueryRequest): Promise<EntitiesPosition>
}
