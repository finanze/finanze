import { UpdateRealEstateRequest } from "@/domain"

export interface UpdateRealEstate {
  execute(request: UpdateRealEstateRequest): Promise<void>
}
