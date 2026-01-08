import { LoanCalculationParams, LoanCalculationResult } from "@/domain"

export interface CalculateLoan {
  execute(params: LoanCalculationParams): Promise<LoanCalculationResult>
}
