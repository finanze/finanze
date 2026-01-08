import { InterestType } from "./globalPosition"
import { Dezimal } from "@/domain/dezimal"

export interface LoanCalculationParams {
  loanAmount: Dezimal | null
  interestRate: Dezimal
  interestType: InterestType
  euriborRate: Dezimal | null
  fixedYears: number | null
  start: string
  end: string
  principalOutstanding: Dezimal | null
}

export interface LoanCalculationResult {
  currentMonthlyPayment: Dezimal | null
  currentMonthlyInterests: Dezimal | null
  principalOutstanding: Dezimal | null
  installmentDate?: string | null
}
