import { DisconnectedExternalIntegrationRequest } from "@/domain"

export interface DisconnectExternalIntegration {
  execute(request: DisconnectedExternalIntegrationRequest): Promise<void>
}
