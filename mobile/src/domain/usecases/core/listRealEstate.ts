import { RealEstate } from "@/domain"

export interface ListRealEstate {
  execute(): Promise<RealEstate[]>
}
