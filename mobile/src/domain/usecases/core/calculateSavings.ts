import { SavingsCalculationRequest, SavingsCalculationResult } from "@/domain"

export interface CalculateSavings {
  execute(request: SavingsCalculationRequest): Promise<SavingsCalculationResult>
}
