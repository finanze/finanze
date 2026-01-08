import { PeriodicFlow } from "@/domain"

export interface UpdatePeriodicFlow {
  execute(flow: PeriodicFlow): Promise<void>
}
