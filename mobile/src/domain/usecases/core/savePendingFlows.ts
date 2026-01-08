import { PendingFlow } from "@/domain"

export interface SavePendingFlows {
  execute(flows: PendingFlow[]): Promise<void>
}
