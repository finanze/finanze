import { PeriodicFlow } from "@/domain"

export interface SavePeriodicFlow {
  execute(flow: PeriodicFlow): Promise<void>
}
