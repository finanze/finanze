import { ConnectedExternalIntegrationRequest } from "@/domain"

export interface ConnectExternalIntegration {
  execute(request: ConnectedExternalIntegrationRequest): Promise<void>
}
