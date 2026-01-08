import { PendingFlow } from "@/domain"

export interface PendingFlowPort {
  save(flows: PendingFlow[]): Promise<void>
  deleteAll(): Promise<void>
  getAll(): Promise<PendingFlow[]>
}
