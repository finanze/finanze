import { AvailableExternalIntegrations } from "@/domain"

export interface GetExternalIntegrations {
  execute(): Promise<AvailableExternalIntegrations>
}
