import { EntityDisconnectRequest } from "@/domain"

export interface DisconnectEntity {
  execute(request: EntityDisconnectRequest): Promise<void>
}
