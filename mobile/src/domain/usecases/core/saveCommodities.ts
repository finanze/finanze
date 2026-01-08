import { UpdateCommodityPosition } from "@/domain"

export interface SaveCommodities {
  execute(commodityPosition: UpdateCommodityPosition): Promise<void>
}
