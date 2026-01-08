import { DeleteRealEstateRequest } from "@/domain"

export interface DeleteRealEstate {
  execute(deleteRequest: DeleteRealEstateRequest): Promise<void>
}
