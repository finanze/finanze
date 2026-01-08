import { DeleteExternalEntityRequest } from "@/domain"

export interface DeleteExternalEntity {
  execute(request: DeleteExternalEntityRequest): Promise<void>
}
