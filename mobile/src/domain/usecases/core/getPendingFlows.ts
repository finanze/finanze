import { PendingFlow } from "@/domain"

export interface GetPendingFlows {
  execute(): Promise<PendingFlow[]>
}
