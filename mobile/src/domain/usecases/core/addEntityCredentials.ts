import { EntityLoginRequest, EntityLoginResult } from "@/domain"

export interface AddEntityCredentials {
  execute(loginRequest: EntityLoginRequest): Promise<EntityLoginResult>
}
