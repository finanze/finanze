import { ManualPeriodicContribution } from "@/domain"

export interface UpdateContributions {
  execute(contributions: ManualPeriodicContribution[]): Promise<void>
}
