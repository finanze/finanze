import { PeriodicFlow } from "@/domain"

export interface PeriodicFlowPort {
  save(flow: PeriodicFlow): Promise<PeriodicFlow>
  update(flow: PeriodicFlow): Promise<void>
  delete(flowId: string): Promise<void>
  getAll(): Promise<PeriodicFlow[]>
  getById(flowId: string): Promise<PeriodicFlow | null>
}
