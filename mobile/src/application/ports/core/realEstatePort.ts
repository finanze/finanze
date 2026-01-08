import { RealEstate } from "@/domain"

export interface RealEstatePort {
  insert(realEstate: RealEstate): Promise<null>
  update(realEstate: RealEstate): Promise<null>
  delete(realEstateId: string): Promise<null>
  getById(realEstateId: string): Promise<RealEstate | null>
  getAll(): Promise<RealEstate[]>
}
