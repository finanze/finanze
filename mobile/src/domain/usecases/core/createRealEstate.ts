import { CreateRealEstateRequest } from "@/domain"

export interface CreateRealEstate {
  execute(request: CreateRealEstateRequest): Promise<void>
}
