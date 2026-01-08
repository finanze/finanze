import {
  DataSource,
  Entity,
  FundDetail,
  GlobalPosition,
  PositionQueryRequest,
  ProductType,
  StockDetail,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"

export interface PositionPort {
  save(position: GlobalPosition): Promise<void>
  getLastGroupedByEntity(
    query?: PositionQueryRequest | null,
  ): Promise<Map<Entity, GlobalPosition>>
  deletePositionForDate(
    entityId: string,
    date: string,
    source: DataSource,
  ): Promise<void>
  getById(positionId: string): Promise<GlobalPosition | null>
  deleteById(positionId: string): Promise<void>
  getStockDetail(entryId: string): Promise<StockDetail | null>
  getFundDetail(entryId: string): Promise<FundDetail | null>
  updateMarketValue(
    entryId: string,
    productType: ProductType,
    marketValue: Dezimal,
  ): Promise<void>
}
