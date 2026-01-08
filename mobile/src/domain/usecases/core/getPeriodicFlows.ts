import { PeriodicFlow } from "@/domain"

export interface GetPeriodicFlows {
  execute(): Promise<PeriodicFlow[]>
}
