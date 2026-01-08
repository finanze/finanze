import {
  BaseTx,
  DataSource,
  TransactionQueryRequest,
  Transactions,
} from "@/domain"

export interface TransactionPort {
  save(data: Transactions): Promise<void>
  getAll(
    real?: boolean | null,
    excludedEntities?: string[] | null,
  ): Promise<Transactions>
  getRefsByEntity(entityId: string): Promise<any>
  getByEntity(entityId: string): Promise<Transactions>
  getByEntityAndSource(
    entityId: string,
    source: DataSource,
  ): Promise<Transactions>
  getRefsBySourceType(real: boolean): Promise<any>
  getByFilters(query: TransactionQueryRequest): Promise<BaseTx[]>
  deleteBySource(source: DataSource): Promise<void>
  deleteByEntitySource(entityId: string, source: DataSource): Promise<void>
  getById(txId: string): Promise<BaseTx | null>
  deleteById(txId: string): Promise<void>
}
