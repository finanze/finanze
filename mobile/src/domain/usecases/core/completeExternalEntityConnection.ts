import { CompleteExternalEntityLinkRequest } from "@/domain"

export interface CompleteExternalEntityConnection {
  execute(request: CompleteExternalEntityLinkRequest): Promise<void>
}
