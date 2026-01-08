import { PeriodicFlow } from "./earningsExpenses"
import { FileUpload } from "./fileUpload"
import { InterestType, LoanType } from "./globalPosition"
import { Dezimal } from "@/domain/dezimal"

export enum RealEstateFlowSubtype {
  LOAN = "LOAN",
  SUPPLY = "SUPPLY",
  COST = "COST",
  RENT = "RENT",
}

export interface LoanPayload {
  type: LoanType
  loanAmount: Dezimal | null
  interestRate: Dezimal
  euriborRate: Dezimal | null
  interestType: InterestType
  fixedYears: number | null
  principalOutstanding: Dezimal
  monthlyInterests?: Dezimal | null
}

export interface RentPayload {}

export interface SupplyPayload {
  taxDeductible?: boolean
}

export interface CostPayload {
  taxDeductible?: boolean
}

export type RealEstateFlowPayload =
  | LoanPayload
  | RentPayload
  | SupplyPayload
  | CostPayload

export interface RealEstateFlow {
  periodicFlowId: string | null
  periodicFlow: PeriodicFlow | null
  flowSubtype: RealEstateFlowSubtype
  description: string
  payload: RealEstateFlowPayload
}

export interface PurchaseExpense {
  concept: string
  amount: Dezimal
  description: string | null
}

export interface Valuation {
  date: string
  amount: Dezimal
  notes: string | null
}

export interface Location {
  address?: string | null
  cadastralReference?: string | null
}

export interface BasicInfo {
  name: string
  isResidence: boolean
  isRented: boolean
  bathrooms?: number | null
  bedrooms?: number | null
  photoUrl?: string | null
}

export interface PurchaseInfo {
  date: string
  price: Dezimal
  expenses: PurchaseExpense[]
}

export interface ValuationInfo {
  estimatedMarketValue: Dezimal
  valuations: Valuation[]
  annualAppreciation?: Dezimal | null
}

export interface Amortization {
  concept: string
  baseAmount: Dezimal
  amount: Dezimal
  percentage: Dezimal
}

export interface RentalData {
  amortizations: Amortization[]
  marginalTaxRate?: Dezimal | null
  vacancyRate?: Dezimal | null
}

export interface RealEstate {
  id: string | null
  basicInfo: BasicInfo
  location: Location
  purchaseInfo: PurchaseInfo
  valuationInfo: ValuationInfo
  flows: RealEstateFlow[]
  currency: string
  rentalData: RentalData | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface CreateRealEstateRequest {
  realEstate: RealEstate
  photo: FileUpload | null
}

export interface UpdateRealEstateRequest {
  realEstate: RealEstate
  removeUnassignedFlows: boolean
  photo: FileUpload | null
}

export interface DeleteRealEstateRequest {
  id: string | null
  removeRelatedFlows: boolean
}
