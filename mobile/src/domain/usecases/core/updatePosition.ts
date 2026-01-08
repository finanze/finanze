import { UpdatePositionRequest } from "@/domain"

export interface UpdatePosition {
  execute(request: UpdatePositionRequest): Promise<void>
}
